 
# ---------------------------------------------------
# File Name: shrink.py
# Description: A Pyrogram bot for downloading files from Telegram channels or groups 
#              and uploading them back to Telegram.
# Created: 2025-01-11
# Last Modified: 2025-01-11
# Version: 2.0.5
# License: MIT License
# ---------------------------------------------------

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import random
import requests
import string
import aiohttp
from devgagan import app
from devgagan.core.func import *
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB, WEBSITE_URL, AD_API, LOG_GROUP  
 
 
tclient = AsyncIOMotorClient(MONGO_DB)
tdb = tclient["telegram_bot"]
token = tdb["tokens"]
 
 
async def create_ttl_index():
    await token.create_index("expires_at", expireAfterSeconds=0)
 
 
 
Param = {}
 
 
async def generate_random_param(length=8):
    """Generate a random parameter."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
 
 
async def get_shortened_url(deep_link):
    api_url = f"https://{WEBSITE_URL}/api?api={AD_API}&url={deep_link}"
 
     
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as response:
            if response.status == 200:
                data = await response.json()   
                if data.get("status") == "success":
                    return data.get("shortenedUrl")
    return None
 
 
async def is_user_verified(user_id):
    """Check if a user has an active session."""
    session = await token.find_one({"user_id": user_id})
    return session is not None
 
 
from devgagan.core.mongo.db import set_mode, get_mode

@app.on_message(filters.command("start"))
async def token_handler(client, message):
    """Handle the /start command."""
    join = await subscribe(client, message)
    if join == 1:
        return
    user_id = message.chat.id
    
    # Mode selection logic
    if len(message.command) <= 1:
        # Check if user already has a mode
        current_mode = await get_mode(user_id)
        
        buttons = [
            [
                InlineKeyboardButton("📦 Archive", callback_data="set_mode_archive"),
                InlineKeyboardButton("🔓 Save Restricted", callback_data="set_mode_restricted")
            ],
            [
                InlineKeyboardButton("Join Channel", url="https://t.me/unlockededu"),
                InlineKeyboardButton("Get Premium", url="https://t.me/Bl4nk_user")
            ]
        ]
        
        mode_text = "Archive" if current_mode == "archive" else "Save Restricted"
        
        image_url = "https://i.ibb.co/1GYX6pWj/IMG-20250608-222205-322.jpg"
        # We try to get the photo from the predefined chat if possible, else fallback
        try:
            chat_id = "save_restricted_content_bots"
            msg = await app.get_messages(chat_id, 796)
            photo = msg.photo.file_id
        except:
            photo = image_url

        await message.reply_photo(
            photo,
            caption=(
                f"Hi 👋 Welcome!\n\n"
                f"Your current mode is: **{mode_text}**\n\n"
                "I am a multi-functional bot:\n"
                "1️⃣ **Save Restricted**: Save posts from restricted channels/groups.\n"
                "2️⃣ **Archive**: Extract and manage zip/tar/rar archives.\n\n"
                "Select a mode below to start using its features:"
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return  
 
    param = message.command[1] if len(message.command) > 1 else None
    freecheck = await chk_user(message, user_id)
    if freecheck != 1:
        await message.reply("You are a premium user no need of token 😉")
        return
 
     
    if param:
        if user_id in Param and Param[user_id] == param:
             
            await token.insert_one({
                "user_id": user_id,
                "param": param,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=3),
            })
            del Param[user_id]   
            await message.reply("✅ You have been verified successfully! Enjoy your session for next 3 hours.")
            return
        else:
            await message.reply("❌ Invalid or expired verification link. Please generate a new token.")
            return

@app.on_message(filters.command("change"))
async def change_mode_handler(client, message):
    user_id = message.chat.id
    buttons = [
        [
            InlineKeyboardButton("📦 Archive", callback_data="set_mode_archive"),
            InlineKeyboardButton("🔓 Save Restricted", callback_data="set_mode_restricted")
        ]
    ]
    await message.reply(
        "Choose your service mode:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"^set_mode_(.*)"))
async def set_mode_callback(client, callback_query):
    mode = callback_query.data.split("_")[2]
    user_id = callback_query.from_user.id
    await set_mode(user_id, mode)
    
    mode_display = "Archive" if mode == "archive" else "Save Restricted"
    await callback_query.answer(f"Mode switched to {mode_display}", show_alert=True)
    await callback_query.message.edit_caption(
        caption=f"✅ Mode successfully switched to: **{mode_display}**\n\nYou can now use the features of this mode. Use /change to switch anytime.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📦 Archive" if mode == "restricted" else "🔓 Save Restricted", 
                                 callback_data="set_mode_archive" if mode == "restricted" else "set_mode_restricted")
        ]])
    )
 
@app.on_message(filters.command("token"))
async def smart_handler(client, message):
    user_id = message.chat.id
     
    freecheck = await chk_user(message, user_id)
    if freecheck != 1:
        await message.reply("You are a premium user no need of token 😉")
        return
    if await is_user_verified(user_id):
        await message.reply("✅ Your free session is already active enjoy!")
    else:
         
        param = await generate_random_param()
        Param[user_id] = param   
 
         
        deep_link = f"https://t.me/{client.me.username}?start={param}"
 
         
        shortened_url = await get_shortened_url(deep_link)
        if not shortened_url:
            await message.reply("❌ Failed to generate the token link. Please try again.")
            return
 
         
        button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Verify the token now...", url=shortened_url)]]
        )
        await message.reply("Click the button below to verify your free access token: \n\n> What will you get ? \n1. No time bound upto 3 hours \n2. Batch command limit will be FreeLimit + 20 \n3. All functions unlocked", reply_markup=button)
 