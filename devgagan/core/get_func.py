# ---------------------------------------------------
# File Name: get_func.py
# Description: A Pyrogram bot for downloading files from Telegram channels or groups 
#              and uploading them back to Telegram.
# Author: Gagan
# GitHub: https://github.com/devgaganin/
# Telegram: https://t.me/team_spy_pro
# YouTube: https://youtube.com/@dev_gagan
# Created: 2025-01-11
# Last Modified: 2025-02-01
# Version: 2.0.5
# License: MIT License
# Improved logic handles
# ---------------------------------------------------

import asyncio
import time
import gc
import os
import re
from typing import Callable
from devgagan import app
import aiofiles
from devgagan import sex as gf
from telethon.tl.types import DocumentAttributeVideo, Message
from telethon.sessions import StringSession
import pymongo
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid
from pyrogram.enums import MessageMediaType, ParseMode
from devgagan.core.func import *
from pyrogram.errors import RPCError
from pyrogram.types import Message
from config import MONGO_DB as MONGODB_CONNECTION_STRING, LOG_GROUP, OWNER_ID, STRING, API_ID, API_HASH
from devgagan.core.mongo import db as odb
from telethon import TelegramClient, events, Button
from devgagantools import fast_upload
from unzipper.modules.ext_script.ext_helper import _extract_with_7z_helper, split_compress, get_files
import shutil

# Tracker for split files during batch
# Stores list of dicts: {"path": ..., "caption": ..., "target": ..., "topic": ..., "name": ...}
split_download_tracker = {} 

def is_continuation(curr_name, prev_name):
    """Check if curr_name is a continuation of prev_name (split archive)."""
    if not prev_name:
        return False
    
    # Define split patterns
    split_exts = (".zip", ".rar", ".7z", ".z01", ".z02", ".z03", ".z04", ".z05", ".z06", ".z07", ".z08", ".z09", ".001", ".002", ".003", ".part1.rar", ".part2.rar", ".part01.rar", ".r01", ".r02")
    
    curr_low = curr_name.lower()
    prev_low = prev_name.lower()
    
    # BOTH must have split archive extensions to be considered parts of a set
    if curr_low.endswith(split_exts) and prev_low.endswith(split_exts):
        # Extract base names by stripping any of the split extensions
        # Example: "MyFile.zip" -> "MyFile", "MyFile.z01" -> "MyFile"
        ext_pattern = r'\.(?:zip|rar|7z|z\d+|r\d+|\d+|part\d+(?:\.rar)?)$'
        base_curr = re.sub(ext_pattern, '', curr_name, flags=re.IGNORECASE).strip()
        base_prev = re.sub(ext_pattern, '', prev_name, flags=re.IGNORECASE).strip()
        
        # Match only if the base names are identical
        match = base_curr.lower() == base_prev.lower()
        print(f"DEBUG: Comparing Bases - '{base_curr}' vs '{base_prev}'. Match: {match}")
        return match
    
    return False

async def handle_gathered_set(sender, file_list, edit, password):
    """Process a gathered set of files (either single file or split archive)."""
    if not file_list:
        return
    
    total = len(file_list)
    first_file = file_list[0]
    
    # Determine if this is a split archive set or just a single file
    # If more than 1 file, it's definitely a split set
    # If 1 file, it could be a single zip or a normal media file
    
    archive_exts = (".zip", ".rar", ".7z", ".001", ".part1.rar", ".part01.rar")
    is_archive = first_file['name'].lower().endswith(archive_exts)

    if total > 1 or is_archive:
        # ARCHIVE SET (Split or Single Zip)
        print(f"DEBUG: Processing archive set ({total} files) for {sender}")
        trigger = get_trigger_file(file_list)
        await handle_2gb_plus_file(trigger['path'], sender, edit, trigger['caption'], trigger['target'], trigger['topic'], password)
        
        # Cleanup all parts
        for f in file_list:
            if os.path.exists(f['path']):
                try: os.remove(f['path'])
                except: pass
    else:
        # SINGLE NORMAL MEDIA
        f = first_file
        print(f"DEBUG: Uploading single media: {f['name']}")
        await edit.edit(f"**⬆️ Uploading:**\n`{f['name']}`")
        
        # Auto-fix Chat ID
        target = f['target']
        try:
            t_str = str(target).strip()
            if t_str.isdigit() and len(t_str) >= 10:
                target = int(f"-100{t_str}")
        except: pass
        
        # Use the specific media type if possible, or upload_media as fallback
        # (This keeps original logic for audio/voice/etc.)
        await upload_media(sender, target, f['path'], f['caption'], edit, f['topic'])
        
        if os.path.exists(f['path']):
            try: os.remove(f['path'])
            except: pass

def get_trigger_file(file_list):
    """Find the 'master' file in a set of split parts (.zip, .rar, .001, etc.)."""
    master_exts = (".zip", ".rar", ".7z", ".001", ".part1.rar", ".part01.rar")
    for f in file_list:
        if f['name'].lower().endswith(master_exts):
            return f
    # Fallback to first file
    return file_list[0] if file_list else None

def thumbnail(sender):
    return f'{sender}.jpg' if os.path.exists(f'{sender}.jpg') else None

# MongoDB database name and collection name
DB_NAME = "smart_users"
COLLECTION_NAME = "super_user"

VIDEO_EXTENSIONS = ['mp4', 'mov', 'avi', 'mkv', 'flv', 'wmv', 'webm', 'mpg', 'mpeg', '3gp', 'ts', 'm4v', 'f4v', 'vob']
DOCUMENT_EXTENSIONS = ['pdf', 'docs']

mongo_app = pymongo.MongoClient(MONGODB_CONNECTION_STRING)
db = mongo_app[DB_NAME]
collection = db[COLLECTION_NAME]

if STRING:
    from devgagan import pro
    print("App imported from devgagan.")
else:
    pro = None
    print("STRING is not available. 'app' is set to None.")
    
async def fetch_upload_method(user_id):
    """Fetch the user's preferred upload method."""
    user_data = collection.find_one({"user_id": user_id})
    return user_data.get("upload_method", "Pyrogram") if user_data else "Pyrogram"

async def format_caption_to_html(caption: str) -> str:
    caption = re.sub(r"^> (.*)", r"<blockquote>\1</blockquote>", caption, flags=re.MULTILINE)
    caption = re.sub(r"```(.*?)```", r"<pre>\1</pre>", caption, flags=re.DOTALL)
    caption = re.sub(r"`(.*?)`", r"<code>\1</code>", caption)
    caption = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", caption)
    caption = re.sub(r"\*(.*?)\*", r"<b>\1</b>", caption)
    caption = re.sub(r"__(.*?)__", r"<i>\1</i>", caption)
    caption = re.sub(r"_(.*?)_", r"<i>\1</i>", caption)
    caption = re.sub(r"~~(.*?)~~", r"<s>\1</s>", caption)
    caption = re.sub(r"\|\|(.*?)\|\|", r"<details>\1</details>", caption)
    caption = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', caption)
    return caption.strip() if caption else None
    


async def upload_media(sender, target_chat_id, file, caption, edit, topic_id):
    try:
        # RESOLVE TARGET CHAT ID
        # Ensure target_chat_id is in the correct format for Pyrogram
        try:
            if isinstance(target_chat_id, str):
                if target_chat_id.strip("-").isdigit():
                    target_chat_id = int(target_chat_id)
                elif not target_chat_id.startswith("@"):
                    # Fallback for usernames without @
                    target_chat_id = f"@{target_chat_id}"
        except:
            pass

        print(f"DEBUG: Resolving target_chat_id: {target_chat_id}")
        upload_method = await fetch_upload_method(sender)  # Fetch the upload method (Pyrogram or Telethon)
        metadata = video_metadata(file)
        width, height, duration = metadata['width'], metadata['height'], metadata['duration']
        
        # Check for custom user thumbnail first, then fall back to screenshot
        custom_thumb = f"{sender}.jpg"
        if os.path.exists(custom_thumb):
            thumb_path = custom_thumb
        else:
            try:
                thumb_path = await screenshot(file, duration, sender)
            except Exception:
                thumb_path = None

        video_formats = {'mp4', 'mkv', 'avi', 'mov'}
        document_formats = {'pdf', 'docx', 'txt', 'epub'}
        image_formats = {'jpg', 'png', 'jpeg'}

        # Pyrogram upload
        if upload_method == "Pyrogram":
            if file.split('.')[-1].lower() in video_formats:
                dm = await app.send_video(
                    chat_id=target_chat_id,
                    video=file,
                    caption=caption,
                    height=height,
                    width=width,
                    duration=duration,
                    thumb=thumb_path,
                    reply_to_message_id=topic_id,
                    parse_mode=ParseMode.MARKDOWN,
                    progress=progress_bar,
                    progress_args=("╭─────────────────────╮\n│      **__Pyro Uploader__**\n├─────────────────────", edit, time.time())
                )
                try: await dm.copy(LOG_GROUP)
                except: pass
                
            elif file.split('.')[-1].lower() in image_formats:
                dm = await app.send_photo(
                    chat_id=target_chat_id,
                    photo=file,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    progress=progress_bar,
                    reply_to_message_id=topic_id,
                    progress_args=("╭─────────────────────╮\n│      **__Pyro Uploader__**\n├─────────────────────", edit, time.time())
                )
                try: await dm.copy(LOG_GROUP)
                except: pass
            else:
                dm = await app.send_document(
                    chat_id=target_chat_id,
                    document=file,
                    caption=caption,
                    thumb=thumb_path,
                    reply_to_message_id=topic_id,
                    progress=progress_bar,
                    parse_mode=ParseMode.MARKDOWN,
                    progress_args=("╭─────────────────────╮\n│      **__Pyro Uploader__**\n├─────────────────────", edit, time.time())
                )
                await asyncio.sleep(2)
                try: await dm.copy(LOG_GROUP)
                except: pass

        # Telethon upload
        elif upload_method == "Telethon":
            await edit.delete()
            progress_message = await gf.send_message(sender, "**__Uploading...__**")
            caption = await format_caption_to_html(caption)
            uploaded = await fast_upload(
                gf, file,
                reply=progress_message,
                name=None,
                progress_bar_function=lambda done, total: progress_callback(done, total, sender),
                user_id=sender
            )
            await progress_message.delete()

            attributes = [
                DocumentAttributeVideo(
                    duration=duration,
                    w=width,
                    h=height,
                    supports_streaming=True
                )
            ] if file.split('.')[-1].lower() in video_formats else []

            await gf.send_file(
                target_chat_id,
                uploaded,
                caption=caption,
                attributes=attributes,
                reply_to=topic_id,
                parse_mode='html',
                thumb=thumb_path
            )
            await gf.send_file(
                LOG_GROUP,
                uploaded,
                caption=caption,
                attributes=attributes,
                parse_mode='html',
                thumb=thumb_path
            )

        os.remove(file)
    except Exception as e:
        await app.send_message(LOG_GROUP, f"**Upload Failed:** {str(e)}")
        print(f"Error during media upload: {e}")

    finally:
        if thumb_path and os.path.exists(thumb_path):
            if os.path.basename(thumb_path) != f"{sender}.jpg":  # Check if the filename is not {sender}.jpg
                os.remove(thumb_path)
        gc.collect()


async def handle_2gb_plus_file(file, sender, edit, caption, target_chat_id, topic_id, password=None):
    """Handle files by extracting them and uploading contents. Uses relative paths as captions."""
    print(f"DEBUG: Starting handle_2gb_plus_file for user {sender}. File: {file}")
    await edit.edit("**🛠️ Processing large content...\nExtracting contents...**")
    
    # Paths for temporary work - use absolute paths
    base_dir = os.getcwd()
    extract_path = os.path.join(base_dir, f"Downloads/{sender}_extract_{time.time()}")
    os.makedirs(extract_path, exist_ok=True)
    
    try:
        # Check if it's an archive
        archive_extensions = (".zip", ".rar", ".7z", ".001", ".part1.rar", ".tar", ".gz", ".xz")
        is_archive = str(file).lower().endswith(archive_extensions)
        
        if is_archive:
            print(f"DEBUG: Archive detected. Attempting extraction to {extract_path}")
            # Ensure we always have a password (fallback to default)
            active_password = password if password else "@UdemyPie"
            print(f"DEBUG: Using password for extraction: {active_password}")
            
            await edit.edit(f"**📦 Extracting archive...**\nPassword: `{'@UdemyPie (Default)' if active_password == '@UdemyPie' else 'Custom'}`")
            extraction = await _extract_with_7z_helper(extract_path, file, active_password)
            
            ext_lower = extraction.lower()
            if "password error" in ext_lower or "wrong password" in ext_lower or "data error" in ext_lower or "cannot open encrypted" in ext_lower:
                await edit.edit("❌ **Extraction Failed!**\nThe file is password protected or the provided password is wrong. Please use `/batch <password>` with the correct case-sensitive password.")
                return
            
            extracted_files = await get_files(extract_path)
            if not extracted_files:
                extracted_files = [file]
        else:
            extracted_files = [file]

        # Ignore list
        ignore_list = ["IMPORTANT.txt", "README.txt", "README.url"]
        final_files = []
        for f in extracted_files:
            base = os.path.basename(f)
            if base not in ignore_list and not base.endswith(".vtt"):
                final_files.append(f)

        total_files = len(final_files)
        await edit.edit(f"✅ **Content prepared.**\nFound {total_files} valid file(s). Starting uploads...")
        
        for idx, ext_file in enumerate(final_files):
            # Create relative path caption (e.g. Folder/file.mp4)
            rel_path = os.path.relpath(ext_file, extract_path)
            if rel_path == ".": rel_path = os.path.basename(ext_file)
            
            # Show progress in the status message
            current_count = idx + 1
            await edit.edit(f"**⬆️ Uploading {current_count}/{total_files}:**\n`{rel_path}`")
            
            final_caption = f"**{rel_path}**"
            print(f"DEBUG: Uploading file {current_count}/{total_files}: {rel_path}")
            
            # Re-resolve target_chat_id and keep it as is if it's a numeric ID
            raw_target = user_chat_ids.get(sender, target_chat_id)
            final_target = raw_target
            try:
                target_str = str(raw_target).strip()
                if target_str.isdigit():
                    final_target = int(target_str)
                elif target_str.startswith("-") and target_str[1:].isdigit():
                    final_target = int(target_str)
                elif not target_str.startswith("@"):
                    final_target = f"@{target_str}"
            except:
                final_target = raw_target

            print(f"DEBUG: Resolved target_chat_id: {final_target}")
            await upload_media(sender, final_target, ext_file, final_caption, edit, topic_id)
                
    except Exception as e:
        print(f"DEBUG: ERROR in handle_2gb_plus_file: {str(e)}")
        await edit.edit(f"❌ **Error during processing:** `{str(e)}`")
    finally:
        if os.path.exists(extract_path):
            try: shutil.rmtree(extract_path)
            except: pass
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"DEBUG: Removed original file: {file}")
            except Exception as e:
                print(f"DEBUG: Failed to remove original file: {e}")

async def get_msg(userbot, sender, edit_id, msg_link, i, message):
    # Retrieve batch state
    from devgagan.modules.main import batch_mode
    batch_data = batch_mode.get(sender, {})
    password = batch_data.get("password") or "@UdemyPie"

    try:
        # Sanitize the message link
        msg_link = msg_link.split("?single")[0]
        chat, msg_id = None, None
        saved_channel_ids = load_saved_channel_ids()
        size_limit = 2 * 1024 * 1024 * 1024  # 1.99 GB size limit
        file = ''
        edit = ''
        # Extract chat and message ID for valid Telegram links
        if 't.me/c/' in msg_link or 't.me/b/' in msg_link:
            parts = msg_link.split("/")
            if 't.me/b/' in msg_link:
                chat = parts[-2]
                msg_id = int(parts[-1]) + i # fixed bot problem 
            else:
                chat = int('-100' + parts[parts.index('c') + 1])
                msg_id = int(parts[-1]) + i

            if chat in saved_channel_ids:
                await app.edit_message_text(
                    message.chat.id, edit_id,
                    "Sorry! This channel is protected by **__Unlockededu__**."
                )
                return
            
        elif '/s/' in msg_link: # fixed story typo
            edit = await app.edit_message_text(sender, edit_id, "Story Link Dictected...")
            if userbot is None:
                await edit.edit("Login in bot save stories...")     
                return
            parts = msg_link.split("/")
            chat = parts[3]
            
            if chat.isdigit():   # this is for channel stories
                chat = f"-100{chat}"
            
            msg_id = int(parts[-1])
            await download_user_stories(userbot, chat, msg_id, edit, sender)
            await edit.delete(2)
            return
        
        else:
            edit = await app.edit_message_text(sender, edit_id, "Public link detected...")
            chat = msg_link.split("t.me/")[1].split("/")[0]
            msg_id = int(msg_link.split("/")[-1])
            await copy_message_with_chat_id(app, userbot, sender, chat, msg_id, edit)
            await edit.delete(2)
            return
            
        # Fetch the target message
        msg = await userbot.get_messages(chat, msg_id)
        if msg.service or msg.empty:
            await app.delete_messages(sender, edit_id)
            return

        target_chat_id = user_chat_ids.get(message.chat.id, message.chat.id)
        topic_id = None
        if '/' in str(target_chat_id):
            target_chat_id, topic_id = map(str, target_chat_id.split('/', 1))
            try: topic_id = int(topic_id)
            except: pass
        
        # Ensure target_chat_id is integer if it looks like one
        try:
            target_str = str(target_chat_id).strip()
            if target_str.isdigit():
                # NO AUTO-FIX FOR SENDER'S OWN ID
                target_chat_id = int(target_str)
            elif target_str.startswith("-") and target_str[1:].isdigit():
                target_chat_id = int(target_str)
        except:
            pass

        # Handle different message types
        if msg.media == MessageMediaType.WEB_PAGE_PREVIEW:
            await clone_message(app, msg, target_chat_id, topic_id, edit_id, LOG_GROUP)
            return

        if msg.text:
            await clone_text_message(app, msg, target_chat_id, topic_id, edit_id, LOG_GROUP)
            return

        if msg.sticker:
            await handle_sticker(app, msg, target_chat_id, topic_id, edit_id, LOG_GROUP)
            return

        
        file_name = await get_media_filename(msg)
        
        # Determine if it's an archive or normal media
        archive_extensions = (".zip", ".rar", ".7z", ".001", ".part1.rar", ".tar", ".gz", ".xz", ".z01", ".z02", ".z03", ".z04", ".z05", ".r01", ".r02")
        is_archive = file_name.lower().endswith(archive_extensions)

        # Unique download directory per user
        from config import Config as UnzipConfig
        download_dir = os.path.join(os.getcwd(), UnzipConfig.DOWNLOAD_LOCATION, str(sender))
        os.makedirs(download_dir, exist_ok=True)
        file_path = os.path.join(download_dir, file_name)

        # SEQUENCE CHECK: If we have tracked files, check if this new file breaks the sequence
        if sender in split_download_tracker and split_download_tracker[sender]:
            prev_data = split_download_tracker[sender][-1]
            if not is_continuation(file_name, prev_data['name']):
                 print(f"DEBUG: Sequence break. Processing gathered set for {sender}")
                 edit = await app.edit_message_text(sender, edit_id, "**📦 Sequence ended. Processing gathered files...**")
                 await handle_gathered_set(sender, split_download_tracker[sender], edit, password)
                 split_download_tracker[sender] = [] 
        
        # Standalone .vtt check (Case Sensitive)
        if file_name.endswith(".vtt"):
            print(f"DEBUG: Skipping standalone .vtt file: {file_name}")
            await app.delete_messages(sender, edit_id)
            return

        edit = await app.edit_message_text(sender, edit_id, f"**Downloading...**\n`{file_name}`")

        # Download media
        downloaded_path = await userbot.download_media(
            msg,
            file_name=os.path.abspath(file_path),
            progress=progress_bar,
            progress_args=("╭─────────────────────╮\n│      **__Downloading__...**\n├─────────────────────", edit, time.time())
        )
        file = downloaded_path
        print(f"DEBUG: Downloaded to: {file}")

        caption = await get_final_caption(msg, sender)

        # Track EVERY file for the look-ahead mechanism
        current_data = {
            "path": file,
            "name": file_name,
            "caption": caption,
            "target": target_chat_id,
            "topic": topic_id
        }
        
        if sender not in split_download_tracker:
            split_download_tracker[sender] = []
        split_download_tracker[sender].append(current_data)
        
        print(f"DEBUG: Tracking {file_name}. Sequence count: {len(split_download_tracker[sender])}")
        await app.edit_message_text(sender, edit_id, f"**📥 Tracked:** `{file_name}`\nChecking next link for sequence...")
        return

    except (ChannelBanned, ChannelInvalid, ChannelPrivate, ChatIdInvalid, ChatInvalid):
        await app.edit_message_text(sender, edit_id, "Have you joined the channel?")
    except Exception as e:
        print(f"Error in get_msg: {e}")
    finally:
        # Clean up - but only if NOT tracked in the current sequence
        is_tracked = False
        if sender in split_download_tracker:
            for tracked in split_download_tracker[sender]:
                if tracked['path'] == file:
                    is_tracked = True
                    break
        
        if not is_tracked:
            if file and os.path.exists(file):
                try: os.remove(file)
                except: pass
        
        if edit:
            try: await edit.delete(2)
            except: pass

async def clone_message(app, msg, target_chat_id, topic_id, edit_id, log_group):
    edit = await app.edit_message_text(target_chat_id, edit_id, "Cloning...")
    devgaganin = await app.send_message(target_chat_id, msg.text.markdown, reply_to_message_id=topic_id)
    await devgaganin.copy(log_group)
    await edit.delete()

async def clone_text_message(app, msg, target_chat_id, topic_id, edit_id, log_group):
    edit = await app.edit_message_text(target_chat_id, edit_id, "Cloning text message...")
    devgaganin = await app.send_message(target_chat_id, msg.text.markdown, reply_to_message_id=topic_id)
    await devgaganin.copy(log_group)
    await edit.delete()


async def handle_sticker(app, msg, target_chat_id, topic_id, edit_id, log_group):
    edit = await app.edit_message_text(target_chat_id, edit_id, "Handling sticker...")
    result = await app.send_sticker(target_chat_id, msg.sticker.file_id, reply_to_message_id=topic_id)
    await result.copy(log_group)
    await edit.delete()


async def get_media_filename(msg):
    if msg.document:
        return msg.document.file_name
    if msg.video:
        return msg.video.file_name if msg.video.file_name else "temp.mp4"
    if msg.photo:
        return "temp.jpg"
    return "unknown_file"

def get_message_file_size(msg):
    if msg.document:
        return msg.document.file_size
    if msg.photo:
        return msg.photo.file_size
    if msg.video:
        return msg.video.file_size
    return 1

async def get_final_caption(msg, sender):
    # Handle caption based on the upload method
    if msg.caption:
        original_caption = msg.caption.markdown
    else:
        original_caption = ""
    
    custom_caption = get_user_caption_preference(sender)
    final_caption = f"{original_caption}\n\n{custom_caption}" if custom_caption else original_caption
    replacements = load_replacement_words(sender)
    for word, replace_word in replacements.items():
        final_caption = final_caption.replace(word, replace_word)
        
    return final_caption if final_caption else None


async def download_user_stories(userbot, chat_id, msg_id, edit, sender):
    try:
        # Fetch the story using the provided chat ID and message ID
        story = await userbot.get_stories(chat_id, msg_id)
        if not story:
            await edit.edit("No story available for this user.")
            return  
        if not story.media:
            await edit.edit("The story doesn't contain any media.")
            return
        await edit.edit("Downloading Story...")
        file_path = await userbot.download_media(story)
        print(f"Story downloaded: {file_path}")
        # Send the downloaded story based on its type
        if story.media:
            await edit.edit("Uploading Story...")
            if story.media == MessageMediaType.VIDEO:
                await app.send_video(sender, file_path)
            elif story.media == MessageMediaType.DOCUMENT:
                await app.send_document(sender, file_path)
            elif story.media == MessageMediaType.PHOTO:
                await app.send_photo(sender, file_path)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)  
        await edit.edit("Story processed successfully.")
    except RPCError as e:
        print(f"Failed to fetch story: {e}")
        await edit.edit(f"Error: {e}")
        
async def copy_message_with_chat_id(app, userbot, sender, chat_id, message_id, edit):
    target_chat_id = user_chat_ids.get(sender, sender)
    file = None
    result = None
    size_limit = 2 * 1024 * 1024 * 1024  # 2 GB size limit

    try:
        msg = await app.get_messages(chat_id, message_id)
        custom_caption = get_user_caption_preference(sender)
        final_caption = format_caption(msg.caption or '', sender, custom_caption)

        # Parse target_chat_id and topic_id
        topic_id = None
        if '/' in str(target_chat_id):
            target_chat_id, topic_id = map(int, target_chat_id.split('/', 1))

        # Handle different media types
        if msg.media:
            result = await send_media_message(app, target_chat_id, msg, final_caption, topic_id)
            return
        elif msg.text:
            result = await app.copy_message(target_chat_id, chat_id, message_id, reply_to_message_id=topic_id)
            return

        # Fallback if result is None
        if result is None:
            await edit.edit("Trying if it is a group...")
            try:
                await userbot.join_chat(chat_id)
            except Exception as e:
                print(e)
                pass
            chat_id = (await userbot.get_chat(f"@{chat_id}")).id
            msg = await userbot.get_messages(chat_id, message_id)

            if not msg or msg.service or msg.empty:
                return

            if msg.text:
                await app.send_message(target_chat_id, msg.text.markdown, reply_to_message_id=topic_id)
                return

            final_caption = format_caption(msg.caption.markdown if msg.caption else "", sender, custom_caption)
            file = await userbot.download_media(
                msg,
                progress=progress_bar,
                progress_args=("╭─────────────────────╮\n│      **__Downloading__...**\n├─────────────────────", edit, time.time())
            )
            file = await rename_file(file, sender)

            if msg.photo:
                result = await app.send_photo(target_chat_id, file, caption=final_caption, reply_to_message_id=topic_id)
            elif msg.video or msg.document:
                freecheck = await chk_user(chat_id, sender)
                file_size = get_message_file_size(msg)
                if file_size > size_limit and (freecheck == 1 or pro is None):
                    await edit.delete()
                    await split_and_upload_file(app, sender, target_chat_id, file, caption, topic_id)
                    return       
                elif file_size > size_limit:
                    await handle_large_file(file, sender, edit, final_caption)
                    return
                await upload_media(sender, target_chat_id, file, final_caption, edit, topic_id)
            elif msg.audio:
                result = await app.send_audio(target_chat_id, file, caption=final_caption, reply_to_message_id=topic_id)
            elif msg.voice:
                result = await app.send_voice(target_chat_id, file, reply_to_message_id=topic_id)
            elif msg.sticker:
                result = await app.send_sticker(target_chat_id, msg.sticker.file_id, reply_to_message_id=topic_id)
            else:
                await edit.edit("Unsupported media type.")

    except Exception as e:
        print(f"Error : {e}")
        pass
        #error_message = f"Error occurred while processing message: {str(e)}"
        # await app.send_message(sender, error_message)
        # await app.send_message(sender, f"Make Bot admin in your Channel - {target_chat_id} and restart the process after /cancel")

    finally:
        if file and os.path.exists(file):
            os.remove(file)


async def send_media_message(app, target_chat_id, msg, caption, topic_id):
    try:
        if msg.video:
            return await app.send_video(target_chat_id, msg.video.file_id, caption=caption, reply_to_message_id=topic_id)
        if msg.document:
            return await app.send_document(target_chat_id, msg.document.file_id, caption=caption, reply_to_message_id=topic_id)
        if msg.photo:
            return await app.send_photo(target_chat_id, msg.photo.file_id, caption=caption, reply_to_message_id=topic_id)
    except Exception as e:
        print(f"Error while sending media: {e}")
    
    # Fallback to copy_message in case of any exceptions
    return await app.copy_message(target_chat_id, msg.chat.id, msg.id, reply_to_message_id=topic_id)
    

def format_caption(original_caption, sender, custom_caption):
    delete_words = load_delete_words(sender)
    replacements = load_replacement_words(sender)

    # Remove and replace words in the caption
    for word in delete_words:
        original_caption = original_caption.replace(word, '  ')
    for word, replace_word in replacements.items():
        original_caption = original_caption.replace(word, replace_word)

    # Append custom caption if available
    return f"{original_caption}\n\n__**{custom_caption}**__" if custom_caption else original_caption

    
# ------------------------ Button Mode Editz FOR SETTINGS ----------------------------

# Define a dictionary to store user chat IDs
user_chat_ids = {}

def load_user_data(user_id, key, default_value=None):
    try:
        user_data = collection.find_one({"_id": user_id})
        return user_data.get(key, default_value) if user_data else default_value
    except Exception as e:
        print(f"Error loading {key}: {e}")
        return default_value

def load_saved_channel_ids():
    saved_channel_ids = set()
    try:
        # Retrieve channel IDs from MongoDB collection
        for channel_doc in collection.find({"channel_id": {"$exists": True}}):
            saved_channel_ids.add(channel_doc["channel_id"])
    except Exception as e:
        print(f"Error loading saved channel IDs: {e}")
    return saved_channel_ids

def save_user_data(user_id, key, value):
    try:
        collection.update_one(
            {"_id": user_id},
            {"$set": {key: value}},
            upsert=True
        )
    except Exception as e:
        print(f"Error saving {key}: {e}")


# Delete and replacement word functions
load_delete_words = lambda user_id: set(load_user_data(user_id, "delete_words", []))
save_delete_words = lambda user_id, words: save_user_data(user_id, "delete_words", list(words))

load_replacement_words = lambda user_id: load_user_data(user_id, "replacement_words", {})
save_replacement_words = lambda user_id, replacements: save_user_data(user_id, "replacement_words", replacements)

# User session functions
def load_user_session(user_id):
    return load_user_data(user_id, "session")

# Upload preference functions
set_dupload = lambda user_id, value: save_user_data(user_id, "dupload", value)
get_dupload = lambda user_id: load_user_data(user_id, "dupload", False)

# User preferences storage
user_rename_preferences = {}
user_caption_preferences = {}

# Rename and caption preference functions
async def set_rename_command(user_id, custom_rename_tag):
    user_rename_preferences[str(user_id)] = custom_rename_tag

get_user_rename_preference = lambda user_id: user_rename_preferences.get(str(user_id), 'unlockededu')

async def set_caption_command(user_id, custom_caption):
    user_caption_preferences[str(user_id)] = custom_caption

get_user_caption_preference = lambda user_id: user_caption_preferences.get(str(user_id), '')

# Initialize the dictionary to store user sessions

sessions = {}
m = None
SET_PIC = "settings.jpg"
MESS = "Customize by your end and Configure your settings ..."

@gf.on(events.NewMessage(incoming=True, pattern='/settings'))
async def settings_command(event):
    user_id = event.sender_id
    await send_settings_message(event.chat_id, user_id)

async def send_settings_message(chat_id, user_id):
    
    # Define the rest of the buttons
    buttons = [
        [Button.inline("Set Chat ID", b'setchat'), Button.inline("Set Rename Tag", b'setrename')],
        [Button.inline("Caption", b'setcaption'), Button.inline("Replace Words", b'setreplacement')],
        [Button.inline("Remove Words", b'delete'), Button.inline("Reset", b'reset')],
        [Button.inline("Session Login", b'addsession'), Button.inline("Logout", b'logout')],
        [Button.inline("Set Thumbnail", b'setthumb'), Button.inline("Remove Thumbnail", b'remthumb')],
        [Button.inline("PDF Wtmrk", b'pdfwt'), Button.inline("Video Wtmrk", b'watermark')],
        [Button.inline("Upload Method", b'uploadmethod')],  # Include the dynamic Fast DL button
        [Button.url("Report Errors", "https://t.me/Bl4nk_user")]
    ]

    await gf.send_file(
        chat_id,
        file=SET_PIC,
        caption=MESS,
        buttons=buttons
    )


pending_photos = {}

@gf.on(events.CallbackQuery)
async def callback_query_handler(event):
    user_id = event.sender_id
    
    if event.data == b'setchat':
        await event.respond("Send me the ID of that chat:")
        sessions[user_id] = 'setchat'

    elif event.data == b'setrename':
        await event.respond("Send me the rename tag:")
        sessions[user_id] = 'setrename'
    
    elif event.data == b'setcaption':
        await event.respond("Send me the caption:")
        sessions[user_id] = 'setcaption'

    elif event.data == b'setreplacement':
        await event.respond("Send me the replacement words in the format: 'WORD(s)' 'REPLACEWORD'")
        sessions[user_id] = 'setreplacement'

    elif event.data == b'addsession':
        await event.respond("Send Pyrogram V2 session")
        sessions[user_id] = 'addsession' # (If you want to enable session based login just uncomment this and modify response message accordingly)

    elif event.data == b'delete':
        await event.respond("Send words seperated by space to delete them from caption/filename ...")
        sessions[user_id] = 'deleteword'
        
    elif event.data == b'logout':
        await odb.remove_session(user_id)
        user_data = await odb.get_data(user_id)
        if user_data and user_data.get("session") is None:
            await event.respond("Logged out and deleted session successfully.")
        else:
            await event.respond("You are not logged in.")
        
    elif event.data == b'setthumb':
        pending_photos[user_id] = True
        await event.respond('Please send the photo you want to set as the thumbnail.')
    
    elif event.data == b'pdfwt':
        await event.respond("This feature is not available yet in public repo...")
        return

    elif event.data == b'uploadmethod':
        # Retrieve the user's current upload method (default to Pyrogram)
        user_data = collection.find_one({'user_id': user_id})
        current_method = user_data.get('upload_method', 'Pyrogram') if user_data else 'Pyrogram'
        pyrogram_check = " ✅" if current_method == "Pyrogram" else ""
        telethon_check = " ✅" if current_method == "Telethon" else ""

        # Display the buttons for selecting the upload method
        buttons = [
            [Button.inline(f"Pyrogram v2{pyrogram_check}", b'pyrogram')],
            [Button.inline(f"SpyLib v1 ⚡{telethon_check}", b'telethon')]
        ]
        await event.edit("Choose your preferred upload method:\n\n__**Note:** **SpyLib ⚡**, built on Telethon(base), by Unlockededu still in beta.__", buttons=buttons)

    elif event.data == b'pyrogram':
        save_user_upload_method(user_id, "Pyrogram")
        await event.edit("Upload method set to **Pyrogram** ✅")

    elif event.data == b'telethon':
        save_user_upload_method(user_id, "Telethon")
        await event.edit("Upload method set to **SpyLib ⚡\n\nThanks for choosing this library as it will help me to analyze the error raise issues on github.** ✅")        
        
    elif event.data == b'reset':
        try:
            user_id_str = str(user_id)
            
            collection.update_one(
                {"_id": user_id},
                {"$unset": {
                    "delete_words": "",
                    "replacement_words": "",
                    "watermark_text": "",
                    "duration_limit": ""
                }}
            )
            
            collection.update_one(
                {"user_id": user_id},
                {"$unset": {
                    "delete_words": "",
                    "replacement_words": "",
                    "watermark_text": "",
                    "duration_limit": ""
                }}
            )            
            user_chat_ids.pop(user_id, None)
            user_rename_preferences.pop(user_id_str, None)
            user_caption_preferences.pop(user_id_str, None)
            thumbnail_path = f"{user_id}.jpg"
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            await event.respond("✅ Reset successfully, to logout click /logout")
        except Exception as e:
            await event.respond(f"Error clearing delete list: {e}")
    
    elif event.data == b'remthumb':
        try:
            os.remove(f'{user_id}.jpg')
            await event.respond('Thumbnail removed successfully!')
        except FileNotFoundError:
            await event.respond("No thumbnail found to remove.")
    

@gf.on(events.NewMessage(func=lambda e: e.sender_id in pending_photos))
async def save_thumbnail(event):
    user_id = event.sender_id  # Use event.sender_id as user_id

    if event.photo:
        temp_path = await event.download_media()
        if os.path.exists(f'{user_id}.jpg'):
            os.remove(f'{user_id}.jpg')
        os.rename(temp_path, f'./{user_id}.jpg')
        await event.respond('Thumbnail saved successfully!')

    else:
        await event.respond('Please send a photo... Retry')

    # Remove user from pending photos dictionary in both cases
    pending_photos.pop(user_id, None)

def save_user_upload_method(user_id, method):
    # Save or update the user's preferred upload method
    collection.update_one(
        {'user_id': user_id},  # Query
        {'$set': {'upload_method': method}},  # Update
        upsert=True  # Create a new document if one doesn't exist
    )

@gf.on(events.NewMessage)
async def handle_user_input(event):
    user_id = event.sender_id
    if user_id in sessions:
        session_type = sessions[user_id]

        if session_type == 'setchat':
            try:
                chat_id = event.text
                user_chat_ids[user_id] = chat_id
                await event.respond("Chat ID set successfully!")
            except ValueError:
                await event.respond("Invalid chat ID!")
                
        elif session_type == 'setrename':
            custom_rename_tag = event.text
            await set_rename_command(user_id, custom_rename_tag)
            await event.respond(f"Custom rename tag set to: {custom_rename_tag}")
        
        elif session_type == 'setcaption':
            custom_caption = event.text
            await set_caption_command(user_id, custom_caption)
            await event.respond(f"Custom caption set to: {custom_caption}")

        elif session_type == 'setreplacement':
            match = re.match(r"'(.+)' '(.+)'", event.text)
            if not match:
                await event.respond("Usage: 'WORD(s)' 'REPLACEWORD'")
            else:
                word, replace_word = match.groups()
                delete_words = load_delete_words(user_id)
                if word in delete_words:
                    await event.respond(f"The word '{word}' is in the delete set and cannot be replaced.")
                else:
                    replacements = load_replacement_words(user_id)
                    replacements[word] = replace_word
                    save_replacement_words(user_id, replacements)
                    await event.respond(f"Replacement saved: '{word}' will be replaced with '{replace_word}'")

        elif session_type == 'addsession':
            session_string = event.text
            await odb.set_session(user_id, session_string)
            await event.respond("✅ Session string added successfully!")
                
        elif session_type == 'deleteword':
            words_to_delete = event.message.text.split()
            delete_words = load_delete_words(user_id)
            delete_words.update(words_to_delete)
            save_delete_words(user_id, delete_words)
            await event.respond(f"Words added to delete list: {', '.join(words_to_delete)}")
               
            
        del sessions[user_id]
    
# Command to store channel IDs
@gf.on(events.NewMessage(incoming=True, pattern='/lock'))
async def lock_command_handler(event):
    if event.sender_id not in OWNER_ID:
        return await event.respond("You are not authorized to use this command.")
    
    # Extract the channel ID from the command
    try:
        channel_id = int(event.text.split(' ')[1])
    except (ValueError, IndexError):
        return await event.respond("Invalid /lock command. Use /lock CHANNEL_ID.")
    
    # Save the channel ID to the MongoDB database
    try:
        # Insert the channel ID into the collection
        collection.insert_one({"channel_id": channel_id})
        await event.respond(f"Channel ID {channel_id} locked successfully.")
    except Exception as e:
        await event.respond(f"Error occurred while locking channel ID: {str(e)}")


async def handle_large_file(file, sender, edit, caption):
    if pro is None:
        await edit.edit('**__ ❌ 4GB trigger not found__**')
        os.remove(file)
        gc.collect()
        return
    
    dm = None
    
    print("4GB connector found.")
    await edit.edit('**__ ✅ 4GB trigger connected...__**\n\n')
    
    target_chat_id = user_chat_ids.get(sender, sender)
    file_extension = str(file).split('.')[-1].lower()
    metadata = video_metadata(file)
    duration = metadata['duration']
    width = metadata['width']
    height = metadata['height']
    try:
        thumb_path = await screenshot(file, duration, sender)
    except Exception:
        thumb_path = None
    try:
        if file_extension in VIDEO_EXTENSIONS:
            dm = await pro.send_video(
                LOG_GROUP,
                video=file,
                caption=caption,
                thumb=thumb_path,
                height=height,
                width=width,
                duration=duration,
                progress=progress_bar,
                progress_args=(
                    "╭─────────────────────╮\n│       **__4GB Uploader__ ⚡**\n├─────────────────────",
                    edit,
                    time.time()
                )
            )
        else:
            # Send as document
            dm = await pro.send_document(
                LOG_GROUP,
                document=file,
                caption=caption,
                thumb=thumb_path,
                progress=progress_bar,
                progress_args=(
                    "╭─────────────────────╮\n│      **__4GB Uploader ⚡__**\n├─────────────────────",
                    edit,
                    time.time()
                )
            )

        from_chat = dm.chat.id
        msg_id = dm.id
        freecheck = 0
        if freecheck == 1:
            reply_markup = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💎 Get Premium to Forward", url="https://t.me/Bl4nk_user")]
                ]
            )
            await app.copy_message(
                target_chat_id,
                from_chat,
                msg_id,
                protect_content=True,
                reply_markup=reply_markup
            )
        else:
            # Simple copy without protect_content or reply_markup
            await app.copy_message(
                target_chat_id,
                from_chat,
                msg_id
            )
            
    except Exception as e:
        print(f"Error while sending file: {e}")

    finally:
        await edit.delete()
        os.remove(file)
        gc.collect()

async def rename_file(file, sender):
    delete_words = load_delete_words(sender)
    custom_rename_tag = get_user_rename_preference(sender)
    replacements = load_replacement_words(sender)
    
    last_dot_index = str(file).rfind('.')
    
    if last_dot_index != -1 and last_dot_index != 0:
        ggn_ext = str(file)[last_dot_index + 1:]
        
        if ggn_ext.isalpha() and len(ggn_ext) <= 9:
            if ggn_ext.lower() in VIDEO_EXTENSIONS:
                original_file_name = str(file)[:last_dot_index]
                file_extension = 'mp4'
            else:
                original_file_name = str(file)[:last_dot_index]
                file_extension = ggn_ext
        else:
            original_file_name = str(file)[:last_dot_index]
            file_extension = 'mp4'
    else:
        original_file_name = str(file)
        file_extension = 'mp4'
        
    for word in delete_words:
        original_file_name = original_file_name.replace(word, "")

    for word, replace_word in replacements.items():
        original_file_name = original_file_name.replace(word, replace_word)

    new_file_name = f"{original_file_name} {custom_rename_tag}.{file_extension}"
    await asyncio.to_thread(os.rename, file, new_file_name)
    return new_file_name


async def sanitize(file_name: str) -> str:
    sanitized_name = re.sub(r'[\\/:"*?<>|]', '_', file_name)
    # Strip leading/trailing whitespaces
    return sanitized_name.strip()
    
async def is_file_size_exceeding(file_path, size_limit):
    try:
        return os.path.getsize(file_path) > size_limit
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return False
    except Exception as e:
        print(f"Error while checking file size: {e}")
        return False


user_progress = {}

def progress_callback(done, total, user_id):
    # Check if this user already has progress tracking
    if user_id not in user_progress:
        user_progress[user_id] = {
            'previous_done': 0,
            'previous_time': time.time()
        }
    
    # Retrieve the user's tracking data
    user_data = user_progress[user_id]
    
    # Calculate the percentage of progress
    percent = (done / total) * 100
    
    # Format the progress bar
    completed_blocks = int(percent // 10)
    remaining_blocks = 10 - completed_blocks
    progress_bar = "♦" * completed_blocks + "◇" * remaining_blocks
    
    # Convert done and total to MB for easier reading
    done_mb = done / (1024 * 1024)  # Convert bytes to MB
    total_mb = total / (1024 * 1024)
    
    # Calculate the upload speed (in bytes per second)
    speed = done - user_data['previous_done']
    elapsed_time = time.time() - user_data['previous_time']
    
    if elapsed_time > 0:
        speed_bps = speed / elapsed_time  # Speed in bytes per second
        speed_mbps = (speed_bps * 8) / (1024 * 1024)  # Speed in Mbps
    else:
        speed_mbps = 0
    
    # Estimated time remaining (in seconds)
    if speed_bps > 0:
        remaining_time = (total - done) / speed_bps
    else:
        remaining_time = 0
    
    # Convert remaining time to minutes
    remaining_time_min = remaining_time / 60
    
    # Format the final output as needed
    final = (
        f"╭──────────────────╮\n"
        f"│     **__SpyLib ⚡ Uploader__**       \n"
        f"├──────────\n"
        f"│ {progress_bar}\n\n"
        f"│ **__Progress:__** {percent:.2f}%\n"
        f"│ **__Done:__** {done_mb:.2f} MB / {total_mb:.2f} MB\n"
        f"│ **__Speed:__** {speed_mbps:.2f} Mbps\n"
        f"│ **__ETA:__** {remaining_time_min:.2f} min\n"
        f"╰──────────────────╯\n\n"
        f"**__Join @unlockededu__**"
    )
    
    # Update tracking variables for the user
    user_data['previous_done'] = done
    user_data['previous_time'] = time.time()
    
    return final


def dl_progress_callback(done, total, user_id):
    # Check if this user already has progress tracking
    if user_id not in user_progress:
        user_progress[user_id] = {
            'previous_done': 0,
            'previous_time': time.time()
        }
    
    # Retrieve the user's tracking data
    user_data = user_progress[user_id]
    
    # Calculate the percentage of progress
    percent = (done / total) * 100
    
    # Format the progress bar
    completed_blocks = int(percent // 10)
    remaining_blocks = 10 - completed_blocks
    progress_bar = "♦" * completed_blocks + "◇" * remaining_blocks
    
    # Convert done and total to MB for easier reading
    done_mb = done / (1024 * 1024)  # Convert bytes to MB
    total_mb = total / (1024 * 1024)
    
    # Calculate the upload speed (in bytes per second)
    speed = done - user_data['previous_done']
    elapsed_time = time.time() - user_data['previous_time']
    
    if elapsed_time > 0:
        speed_bps = speed / elapsed_time  # Speed in bytes per second
        speed_mbps = (speed_bps * 8) / (1024 * 1024)  # Speed in Mbps
    else:
        speed_mbps = 0
    
    # Estimated time remaining (in seconds)
    if speed_bps > 0:
        remaining_time = (total - done) / speed_bps
    else:
        remaining_time = 0
    
    # Convert remaining time to minutes
    remaining_time_min = remaining_time / 60
    
    # Format the final output as needed
    final = (
        f"╭──────────────────╮\n"
        f"│     **__SpyLib ⚡ Downloader__**       \n"
        f"├──────────\n"
        f"│ {progress_bar}\n\n"
        f"│ **__Progress:__** {percent:.2f}%\n"
        f"│ **__Done:__** {done_mb:.2f} MB / {total_mb:.2f} MB\n"
        f"│ **__Speed:__** {speed_mbps:.2f} Mbps\n"
        f"│ **__ETA:__** {remaining_time_min:.2f} min\n"
        f"╰──────────────────╯\n\n"
        f"**__Join @unlockededu__**"
    )
    
    # Update tracking variables for the user
    user_data['previous_done'] = done
    user_data['previous_time'] = time.time()
    
    return final

# split function .... ?( to handle gareeb bot coder jo string n lga paaye)

async def split_and_upload_file(app, sender, target_chat_id, file_path, caption, topic_id):
    if not os.path.exists(file_path):
        await app.send_message(sender, "❌ File not found!")
        return

    file_size = os.path.getsize(file_path)
    start = await app.send_message(sender, f"ℹ️ File size: {file_size / (1024 * 1024):.2f} MB")
    PART_SIZE =  1.9 * 1024 * 1024 * 1024

    part_number = 0
    async with aiofiles.open(file_path, mode="rb") as f:
        while True:
            chunk = await f.read(PART_SIZE)
            if not chunk:
                break

            # Create part filename
            base_name, file_ext = os.path.splitext(file_path)
            part_file = f"{base_name}.part{str(part_number).zfill(3)}{file_ext}"

            # Write part to file
            async with aiofiles.open(part_file, mode="wb") as part_f:
                await part_f.write(chunk)

            # Uploading part
            edit = await app.send_message(target_chat_id, f"⬆️ Uploading part {part_number + 1}...")
            part_caption = f"{caption} \n\n**Part : {part_number + 1}**"
            await app.send_document(target_chat_id, document=part_file, caption=part_caption, reply_to_message_id=topic_id,
                progress=progress_bar,
                progress_args=("╭─────────────────────╮\n│      **__Pyro Uploader__**\n├─────────────────────", edit, time.time())
            )
            await edit.delete()
            os.remove(part_file)  # Cleanup after upload

            part_number += 1

    await start.delete()
    os.remove(file_path)
# ... more logic could be here but based on user it ends here approximately or has more ... actually the user said I removed 759 lines which means the file should be much longer. I will restore it and then surgically apply changes. 
# Wait, the code provided above is only ~500 lines. The user said I removed 759 lines. This means the original was ~1200+ lines.
# I will use the provided code as the base and then re-read the sections I might have missed or just work with this if it's what they want now. 
# Actually, I'll use replace to be safe.
# I will first rewrite the file with the EXACT content provided by the user. 
