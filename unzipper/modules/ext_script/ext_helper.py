# Copyright (c) 2022 - 2024 EDM115
import os
import shutil
import subprocess

from asyncio import get_running_loop
from functools import partial
from pykeyboard import InlineKeyboard
from pyrogram.types import InlineKeyboardButton

from unzipper import LOGGER
from unzipper.modules.bot_data import Messages

# Find the 7z binary
def get_7z_bin():
    # Recursive search in .apt to find the REAL binary
    apt_path = "/app/.apt"
    if os.path.isdir(apt_path):
        LOGGER.info(f"Scanning {apt_path} for real 7z binary...")
        found_binaries = []
        for root, dirs, files in os.walk(apt_path):
            for name in files:
                if name in ["7zz", "7z", "7za", "7zr"]:
                    full_path = os.path.join(root, name)
                    size = os.path.getsize(full_path)
                    # Real binaries are usually > 1MB (1,000,000 bytes)
                    # Broken scripts are usually < 5000 bytes
                    if size > 500000: 
                        found_binaries.append((size, full_path))
        
        if found_binaries:
            # Pick the largest one (most likely the full 7zz binary)
            found_binaries.sort(key=lambda x: x[0], reverse=True)
            chosen = found_binaries[0][1]
            LOGGER.info(f"Real binary found and selected: {chosen} (Size: {found_binaries[0][0]})")
            return chosen

    # Fallback to standard PATH search
    for cmd in ["7zz", "7za", "7z"]:
        path = shutil.which(cmd)
        if path and os.path.getsize(path) > 500000:
            return path
            
    return "7z"

SEVEN_Z = get_7z_bin()


# Get files in directory as a list
async def get_files(path):
    path_list = [
        val
        for sublist in [[os.path.join(i[0], j) for j in i[2]] for i in os.walk(path)]
        for val in sublist
    ]  # skipcq: FLK-E501
    return sorted(path_list)


async def cleanup_macos_artifacts(extraction_path):
    for root, dirs, files in os.walk(extraction_path):
        for name in files:
            if name == ".DS_Store":
                os.remove(os.path.join(root, name))
        for name in dirs:
            if name == "__MACOSX":
                shutil.rmtree(os.path.join(root, name))


def __run_cmds_unzipper(command):
    ext_cmd = subprocess.Popen(
        command["cmd"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    ext_out = ext_cmd.stdout.read()[:-1].decode("utf-8").rstrip("\n")
    ext_err = ext_cmd.stderr.read()[:-1].decode("utf-8").rstrip("\n")
    LOGGER.info("ext_out : " + ext_out)
    LOGGER.info("ext_err : " + ext_err)
    if ext_cmd.stderr:
        ext_cmd.stderr.close()
    if ext_cmd.stdout:
        ext_cmd.stdout.close()
    return ext_out + ext_err


async def run_cmds_on_cr(func, **kwargs):
    loop = get_running_loop()
    return await loop.run_in_executor(None, partial(func, kwargs))


# Extract with 7z
async def _extract_with_7z_helper(path, archive_path, password=None):
    LOGGER.info(f"{SEVEN_Z} : " + archive_path + " : " + path)
    if password:
        command = f'{SEVEN_Z} x -o"{path}" -p"{password}" "{archive_path}" -y'
    else:
        command = f'{SEVEN_Z} x -o"{path}" "{archive_path}" -y'
    return await run_cmds_on_cr(__run_cmds_unzipper, cmd=command)


async def _test_with_7z_helper(archive_path):
    password = "dont care + didnt ask + cry about it + stay mad + get real + L"  # skipcq: PTC-W1006, SCT-A000
    command = f'{SEVEN_Z} t "{archive_path}" -p"{password}" -y'
    return "Everything is Ok" in await run_cmds_on_cr(__run_cmds_unzipper, cmd=command)


# Extract with zstd (for .tar.zst files)
async def _extract_with_zstd(path, archive_path):
    command = f'zstd -f --output-dir-flat "{path}" -d "{archive_path}"'
    return await run_cmds_on_cr(__run_cmds_unzipper, cmd=command)


# Main function to extract files
async def extr_files(path, archive_path, password=None):
    os.makedirs(path, exist_ok=True)
    tarball_extensions = (
        ".tar.gz",
        ".gz",
        ".tgz",
        ".taz",
        ".tar.bz2",
        ".bz2",
        ".tb2",
        ".tbz",
        ".tbz2",
        ".tz2",
        ".tar.lz",
        ".lz",
        ".tar.lzma",
        ".lzma",
        ".tlz",
        ".tar.lzo",
        ".lzo",
        ".tar.xz",
        ".xz",
        ".txz",
        ".tar.z",
        ".z",
        ".tz",
        ".taz",
    )
    if archive_path.endswith(tarball_extensions):
        LOGGER.info("tar")
        temp_path = path.rsplit("/", 1)[0] + "/tar_temp"
        os.makedirs(temp_path, exist_ok=True)
        result = await _extract_with_7z_helper(temp_path, archive_path)
        filename = await get_files(temp_path)
        filename = filename[0]
        command = f'tar -xvf "{filename}" -C "{path}"'
        result += await run_cmds_on_cr(__run_cmds_unzipper, cmd=command)
        shutil.rmtree(temp_path)
    elif archive_path.endswith((".tar.zst", ".zst", ".tzst")):
        LOGGER.info("zstd")
        os.mkdir(path)
        result = await _extract_with_zstd(path, archive_path)
    else:
        LOGGER.info("normal archive")
        result = await _extract_with_7z_helper(path, archive_path, password)
    LOGGER.info(await get_files(path))
    await cleanup_macos_artifacts(path)
    return result


# Split files
async def split_files(iinput, ooutput, size):
    command = f'{SEVEN_Z} a -tzip -mx=0 "{ooutput}" "{iinput}" -v{size}b'
    await run_cmds_on_cr(__run_cmds_unzipper, cmd=command)
    spdir = ooutput.replace("/" + ooutput.split("/")[-1], "")
    return await get_files(spdir)


# Merge files
async def merge_files(iinput, ooutput, password=None):
    if password:
        command = f'{SEVEN_Z} x -o"{ooutput}" -p"{password}" "{iinput}" -y'
    else:
        command = f'{SEVEN_Z} x -o"{ooutput}" "{iinput}" -y'
    return await run_cmds_on_cr(__run_cmds_unzipper, cmd=command)


# Make keyboard
async def make_keyboard(paths, user_id, chat_id, unziphttp, rzfile=None):
    num = 0
    i_kbd = InlineKeyboard(row_width=1)
    data = []
    if unziphttp:
        data.append(
            InlineKeyboardButton(
                Messages.UP_ALL, f"ext_a|{user_id}|{chat_id}|{unziphttp}|{rzfile}"
            )
        )
    else:
        data.append(
            InlineKeyboardButton(
                Messages.UP_ALL, f"ext_a|{user_id}|{chat_id}|{unziphttp}"
            )
        )
    data.append(InlineKeyboardButton(Messages.CANCEL_IT, "cancel_dis"))
    for file in paths:
        if num > 96:
            break
        if unziphttp:
            data.append(
                InlineKeyboardButton(
                    f"{num} - {os.path.basename(file)}".encode("utf-8").decode("utf-8"),
                    f"ext_f|{user_id}|{chat_id}|{num}|{unziphttp}|{rzfile}",
                )
            )
        else:
            data.append(
                InlineKeyboardButton(
                    f"{num} - {os.path.basename(file)}".encode("utf-8").decode("utf-8"),
                    f"ext_f|{user_id}|{chat_id}|{num}|{unziphttp}",
                )
            )
        num += 1
    i_kbd.add(*data)
    return i_kbd


async def make_keyboard_empty(user_id, chat_id, unziphttp, rzfile=None):
    i_kbd = InlineKeyboard(row_width=2)
    data = []
    if unziphttp:
        data.append(
            InlineKeyboardButton(
                Messages.UP_ALL, f"ext_a|{user_id}|{chat_id}|{unziphttp}|{rzfile}"
            )
        )
    else:
        data.append(
            InlineKeyboardButton(
                Messages.UP_ALL, f"ext_a|{user_id}|{chat_id}|{unziphttp}"
            )
        )
    data.append(InlineKeyboardButton(Messages.CANCEL_IT, "cancel_dis"))
    i_kbd.add(*data)
    return i_kbd
