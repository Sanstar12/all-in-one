# Copyright (c) 2022 - 2024 EDM115
import logging
import time
from devgagan import app as app

boottime = time.time()
logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.FileHandler("unzip-log.txt"), logging.StreamHandler()],
    format="%(asctime)s - %(levelname)s - %(name)s - %(threadName)s - %(message)s",
)
LOGGER = logging.getLogger(__name__)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("aiofiles").setLevel(logging.WARNING)
logging.getLogger("dnspython").setLevel(logging.WARNING)
logging.getLogger("GitPython").setLevel(logging.WARNING)
logging.getLogger("motor").setLevel(logging.WARNING)
logging.getLogger("Pillow").setLevel(logging.WARNING)
logging.getLogger("psutil").setLevel(logging.WARNING)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
