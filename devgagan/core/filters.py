from pyrogram import filters
from devgagan.core.mongo.db import get_mode

async def mode_check(f, client, message):
    if not message.from_user:
        return False
    user_id = message.from_user.id
    mode = await get_mode(user_id)
    return mode == f.mode

archive_filter = filters.create(mode_check, mode="archive")
restricted_filter = filters.create(mode_check, mode="restricted")
