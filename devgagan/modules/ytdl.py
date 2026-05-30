# ---------------------------------------------------
# File Name: ytdl.py (pure code)
# Description: A Pyrogram bot for downloading files from Telegram channels or groups 
#              and uploading them back to Telegram.
# Created: 2025-01-11
# Last Modified: 2025-01-11
# Version: 2.0.5
# License: MIT License
# ---------------------------------------------------


import yt_dlp
import os
import tempfile
import time
import asyncio
import random
import string
import requests
import logging
import cv2
from devgagan import sex as client
from pyrogram import Client,filters
from telethon import events
from telethon.sync import TelegramClient
from telethon.tl.types import DocumentAttributeVideo
from devgagan.core.func import screenshot, video_metadata, progress_bar
from telethon.tl.functions.messages import EditMessageRequest
from devgagantools import fast_upload
from concurrent.futures import ThreadPoolExecutor
import aiohttp 
from devgagan import app
import logging
import aiofiles
from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC
from mutagen.mp3 import MP3
from devgagan.core.mongo.db import get_mode
 
logger = logging.getLogger(__name__)
 
 
thread_pool = ThreadPoolExecutor()
ongoing_downloads = {}
 
def d_thumbnail(thumbnail_url, save_path):
    try:
        response = requests.get(thumbnail_url, stream=True)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return save_path
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download thumbnail: {e}")
        return None
 
 
async def download_thumbnail_async(url, path):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                with open(path, 'wb') as f:
                    f.write(await response.read())
 
 
async def extract_audio_async(ydl_opts, url):
    def sync_extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)
    return await asyncio.get_event_loop().run_in_executor(thread_pool, sync_extract)
 
 
def get_random_string(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length)) 
 
 
async def process_audio(client, event, url, cookies_env_var=None):
    cookies = None
    if cookies_env_var:
        cookies = os.getenv(cookies_env_var)
 
    temp_cookie_path = None
    if cookies:
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_cookie_file:
            temp_cookie_file.write(cookies)
            temp_cookie_path = temp_cookie_file.name
 
    start_time = time.time()
    random_filename = f"@team_spy_pro_{event.sender_id}"
    download_path = f"{random_filename}.mp3"
 
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f"{random_filename}.%(ext)s",
        'cookiefile': temp_cookie_path,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'quiet': False,
        'noplaylist': True,
    }
    prog = None
    try:
        prog = await event.reply("**__Processing...__**")
        info = await extract_audio_async(ydl_opts, url)
        
        if os.path.exists(download_path):
            title = info.get('title', 'Unknown Title')
            performer = info.get('uploader', 'Unknown Artist')
            thumb_url = info.get('thumbnail')
            duration = int(info.get('duration', 0))
            
            thumb_path = None
            if thumb_url:
                thumb_path = f"{random_filename}.jpg"
                await download_thumbnail_async(thumb_url, thumb_path)
            
            audio = MP3(download_path, ID3=ID3)
            try:
                audio.add_tags()
            except:
                pass
            audio.tags.add(TIT2(encoding=3, text=title))
            audio.tags.add(TPE1(encoding=3, text=performer))
            if thumb_path:
                with open(thumb_path, 'rb') as f:
                    audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=f.read()))
            audio.save()

            await client.send_file(
                event.chat_id,
                download_path,
                caption=f"**{title}**\n\n__Downloaded by @team_spy_pro__",
                attributes=[DocumentAttributeVideo(duration=duration, w=0, h=0, supports_streaming=True)],
                thumb=thumb_path,
                progress_callback=lambda d, t: loop.create_task(
                    progress_bar(d, t, "╭─────────────────────╮\n│      **__Pyro Uploader__**\n├─────────────────────", prog, start_time)
                )
            )
            if thumb_path and os.path.exists(thumb_path):
                os.remove(thumb_path)
            if prog:
                await prog.delete()
        else:
            await event.reply("**__Audio file not found after extraction!__**")
 
    except Exception as e:
        logger.exception("Error during audio extraction or upload")
        await event.reply(f"**__An error occurred: {e}__**")
    finally:
        if os.path.exists(download_path):
            os.remove(download_path)
        if temp_cookie_path and os.path.exists(temp_cookie_path):
            os.remove(temp_cookie_path)
 
 
@client.on(events.NewMessage(pattern="/adl"))
async def audio_dl(event):
    user_id = event.sender_id
    mode = await get_mode(user_id)
    if mode != "restricted":
        return

    if user_id in ongoing_downloads:
        await event.reply("**You already have an ongoing download. Please wait until it completes!**")
        return
 
    if len(event.message.text.split()) < 2:
        await event.reply("**Usage:** `/adl <video-link>`\n\nPlease provide a valid video link!")
        return    
 
    url = event.message.text.split()[1]
    ongoing_downloads[user_id] = True
 
    try:
        if "instagram.com" in url:
            await process_audio(client, event, url, cookies_env_var="INSTA_COOKIES")
        elif "youtube.com" in url or "youtu.be" in url:
            await process_audio(client, event, url, cookies_env_var="YT_COOKIES")
        else:
            await process_audio(client, event, url)
    except Exception as e:
        await event.reply(f"**An error occurred:** `{e}`")
    finally:
        ongoing_downloads.pop(user_id, None)
 
 
async def fetch_video_info(url, ydl_opts, progress_message, check_duration_and_size):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
 
        if check_duration_and_size:
             
            duration = info_dict.get('duration', 0)
            if duration and duration > 3 * 3600:   
                await progress_message.edit("**❌ __Video is longer than 3 hours. Download aborted...__**")
                return None
 
             
            estimated_size = info_dict.get('filesize_approx', 0)
            if estimated_size and estimated_size > 2 * 1024 * 1024 * 1024:   
                await progress_message.edit("**🤞 __Video size is larger than 2GB. Aborting download.__**")
                return None
 
        return info_dict
 
def download_video(url, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
 
 
@client.on(events.NewMessage(pattern="/dl"))
async def video_dl(event):
    user_id = event.sender_id
    mode = await get_mode(user_id)
    if mode != "restricted":
        return

    if user_id in ongoing_downloads:
        await event.reply("**You already have an ongoing ytdlp download. Please wait until it completes!**")
        return
 
    if len(event.message.text.split()) < 2:
        await event.reply("**Usage:** `/dl <video-link>`\n\nPlease provide a valid video link!")
        return    
 
    url = event.message.text.split()[1]
 
     
    try:
        if "instagram.com" in url:
            await process_video(client, event, url, "INSTA_COOKIES", check_duration_and_size=False)
        elif "youtube.com" in url or "youtu.be" in url:
            await process_video(client, event, url, "YT_COOKIES", check_duration_and_size=True)
        else:
            await process_video(client, event, url, None, check_duration_and_size=False)
    except Exception as e:
        await event.reply(f"**An error occurred:** `{e}`")
    finally:
        ongoing_downloads.pop(user_id, None)

async def process_video(client, event, url, cookies_env_var, check_duration_and_size=False):
    start_time = time.time()
    logger.info(f"Received link: {url}")
     
    cookies = None
    if cookies_env_var:
        cookies = os.getenv(cookies_env_var)
 
     
    random_filename = get_random_string() + ".mp4"
    download_path = os.path.abspath(random_filename)
    logger.info(f"Generated random download path: {download_path}")
 
     
    temp_cookie_path = None
    if cookies:
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_cookie_file:
            temp_cookie_file.write(cookies)
            temp_cookie_path = temp_cookie_file.name
        logger.info(f"Created temporary cookie file at: {temp_cookie_path}")
 
     
    thumbnail_file = None
    metadata = {'width': None, 'height': None, 'duration': None, 'thumbnail': None}
 
     
    ydl_opts = {
        'format': 'best',
        'outtmpl': download_path,
        'cookiefile': temp_cookie_path,
        'quiet': True,
        'noplaylist': True,
    }
 
    progress_message = await event.reply("**__Fetching video info...__**")
 
    try:
        info_dict = await fetch_video_info(url, ydl_opts, progress_message, check_duration_and_size)
        if not info_dict:
            return
 
        metadata['width'] = info_dict.get('width')
        metadata['height'] = info_dict.get('height')
        metadata['duration'] = info_dict.get('duration')
        metadata['thumbnail'] = info_dict.get('thumbnail')
 
        if metadata['thumbnail']:
            thumbnail_file = f"{get_random_string()}.jpg"
            d_thumbnail(metadata['thumbnail'], thumbnail_file)
 
        await progress_message.edit("**__Starting download...__**")
        await asyncio.get_event_loop().run_in_executor(thread_pool, download_video, url, ydl_opts)
 
        if not os.path.exists(download_path):
            await progress_message.edit("**❌ __Download failed.__**")
            return
 
        await progress_message.edit("**__Download complete! Preparing to upload...__**")
 
        if os.path.getsize(download_path) > 2 * 1024 * 1024 * 1024:
            await progress_message.edit("**__File size exceeds 2GB. Splitting and uploading...__**")
            await split_and_upload_file(app, event.sender_id, download_path, f"**{info_dict.get('title', 'Video')}**")
            await progress_message.delete()
        else:
             
            caption = f"**{info_dict.get('title', 'Video')}**\n\n__Downloaded by @team_spy_pro__"
            await app.send_video(
                event.sender_id,
                video=download_path,
                caption=caption,
                width=metadata['width'] or 0,
                height=metadata['height'] or 0,
                duration=metadata['duration'] or 0,
                thumb=thumbnail_file,
                progress=progress_bar,
                progress_args=("╭─────────────────────╮\n│      **__Pyro Uploader__**\n├─────────────────────", progress_message, start_time)
            )
            await progress_message.delete()
 
    except Exception as e:
        logger.exception("An error occurred during video processing")
        await event.reply(f"**An error occurred:** `{e}`")
    finally:
        if os.path.exists(download_path):
            os.remove(download_path)
        if thumbnail_file and os.path.exists(thumbnail_file):
            os.remove(thumbnail_file)
        if temp_cookie_path and os.path.exists(temp_cookie_path):
            os.remove(temp_cookie_path)

async def split_and_upload_file(app, sender, file_path, caption):
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
            edit = await app.send_message(sender, f"⬆️ Uploading part {part_number + 1}...")
            part_caption = f"{caption} \n\n**Part : {part_number + 1}**"
            await app.send_document(sender, document=part_file, caption=part_caption,
                progress=progress_bar,
                progress_args=("╭─────────────────────╮\n│      **__Pyro Uploader__**\n├─────────────────────", edit, time.time())
            )
            await edit.delete()
            os.remove(part_file)  # Cleanup after upload

            part_number += 1

    await start.delete()
    os.remove(file_path)
