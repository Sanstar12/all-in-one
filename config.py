# devgagan
# Note if you are trying to deploy on vps then directly fill values in ("")

from os import getenv, path
import os

# VPS --- FILL COOKIES 🍪 in """ ... """ 

INST_COOKIES = """
# wtite up here insta cookies
"""

YTUB_COOKIES = """
# write here yt cookies
"""

API_ID = int(getenv("API_ID", "25214632"))
API_HASH = getenv("API_HASH", "85f9204d557b13f5b336bd67dc073a46")
BOT_TOKEN = getenv("BOT_TOKEN", "8001025057:AAEG31Yg8CNImnS9C78Ct-h9jhMFvJOsx1M")
OWNER_ID = list(map(int, getenv("OWNER_ID", "6618712970").split()))
MONGO_DB = getenv("MONGO_DB", "mongodb+srv://firstmong065:BGQoHt83kaIIen52@cluster0.mwmz9.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
LOG_GROUP = int(getenv("LOG_GROUP", "-1002346542951"))
CHANNEL_ID = int(getenv("CHANNEL_ID", "-1002261822941"))
FREEMIUM_LIMIT = int(getenv("FREEMIUM_LIMIT", "0"))
PREMIUM_LIMIT = int(getenv("PREMIUM_LIMIT", "50000"))
WEBSITE_URL = getenv("WEBSITE_URL", "upshrink.com")
AD_API = getenv("AD_API", "52b4a2cf4687d81e7d3f8f2b7bc2943f618e78cb")
STRING = getenv("STRING", None)
YT_COOKIES = getenv("YT_COOKIES", YTUB_COOKIES)
DEFAULT_SESSION = getenv("DEFAUL_SESSION", None)  # added old method of invite link joining
INSTA_COOKIES = getenv("INSTA_COOKIES", INST_COOKIES)

# Unzipper Config
class Config:
    APP_ID = API_ID
    API_HASH = API_HASH
    BOT_TOKEN = BOT_TOKEN
    # Handle LOGS_CHANNEL specifically as it might be a string or int
    LOGS_CHANNEL = LOG_GROUP
    MONGODB_URL = MONGO_DB
    MONGODB_DBNAME = getenv("MONGODB_DBNAME", "Unzipper_Bot")
    BOT_OWNER = OWNER_ID[0] if OWNER_ID else 0
    DOWNLOAD_LOCATION = f"{path.dirname(__file__)}/Downloaded"
    THUMB_LOCATION = f"{path.dirname(__file__)}/Thumbnails"
    TG_MAX_SIZE = 2097152000
    MAX_MESSAGE_LENGTH = 4096
    CHUNK_SIZE = 1024 * 1024 * 10  # 10 MB
    BOT_THUMB = f"{path.dirname(__file__)}/bot_thumb.jpg"
    MAX_CONCURRENT_TASKS = 75
    MAX_TASK_DURATION_EXTRACT = 120 * 60  # 2 hours (in seconds)
    MAX_TASK_DURATION_MERGE = 240 * 60  # 4 hours (in seconds)
