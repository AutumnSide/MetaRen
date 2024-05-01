import os
import time
import asyncio
import random
import subprocess

from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image

from helper.ffmpeg import fix_thumb, take_screen_shot
from helper.utils import progress_for_pyrogram, convert, humanbytes
from helper.database import db
from config import Config


# Initialize the Pyrogram client
app = Client(
    "test",
    api_id=Config.STRING_API_ID,
    api_hash=Config.STRING_API_HASH,
    session_string=Config.STRING_SESSION,
)

# Helper function to add metadata to files
async def add_metadata(file_path, metadata):
    """Add metadata to a file using FFmpeg."""
    if not metadata:
        return None
    
    metadata_args = " ".join([f'-metadata {key}="{value}"' for key, value in metadata.items()])
    metadata_path = f"metadata_{os.path.basename(file_path)}"
    cmd = f'ffmpeg -i "{file_path}" {metadata_args} -c copy "{metadata_path}"'

    # Run FFmpeg command asynchronously
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()  # Wait for the process to finish
    if stderr:
        raise Exception(f"FFmpeg error: {stderr.decode()}")

    return metadata_path  # Return the new file path with metadata


# Handle 'rename' callback queries
@app.on_callback_query(filters.regex("rename"))
async def rename_callback(bot, update):
    await update.message.delete()  # Delete the current message
    await update.message.reply_text(
        "__Please enter the new file name.__",
        reply_to_message_id=update.message.reply_to_message.id,
        reply_markup=ForceReply(),  # Prompt for a new file name
    )


# Handle messages that are replies to a forced prompt
@app.on_message(filters.private & filters.reply)
async def rename_reply(client, message):
    reply_message = message.reply_to_message  # Get the original message
    if isinstance(reply_message.reply_markup, ForceReply):  # Ensure it's a response to a forced prompt
        new_name = message.text.strip()  # The new file name from user input
        if not new_name:  # Check for empty input
            await message.reply_text("⚠️ File name cannot be empty.", reply_to_message_id=message.message_id)
            return

        await message.delete()  # Delete the user response
        msg = await client.get_messages(message.chat.id, reply_message.message_id)  # Get the original message
        file = msg.reply_to_message  # The media file to rename

        media_type = getattr(file, file.media.value)  # Get the media type

        # Ensure the new name has an extension
        if "." not in new_name:
            extn = media_type.file_name.rsplit(".", 1)[-1] if "." in media_type.file_name else "mkv"
            new_name = f"{new_name}.{extn}"

        # Send inline keyboard with options for output file type
        buttons = [
            [InlineKeyboardButton("📁 Document", callback_data="upload_document")],
            [InlineKeyboardButton("🎥 Video", callback_data="upload_video")],
            [InlineKeyboardButton("🎵 Audio", callback_data="upload_audio")],
        ]

        await message.reply(
            f"Select the output file type.\nFile Name: `{new_name}`",
            reply_markup=InlineKeyboardMarkup(buttons),
            reply_to_message_id=file.message_id,  # Reply to the original message
        )


# Handle callback queries for file uploads
@app.on_callback_query(filters.regex("upload"))
async def upload_callback(bot, update):
    # Ensure the Metadata directory exists
    if not os.path.isdir("downloads"):
        os.mkdir("downloads")

    # Extract necessary information
    try:
        prefix = await db.get_prefix(update.message.chat.id) or ""
        suffix = await db.get_suffix(update.message.chat.id) or ""
        new_name = update.message.text.split(":-")[1].strip()
        new_filename = f"{prefix}{new_name}{suffix}"  # Add prefix and suffix
    except Exception as e:
        return await update.message.edit_text(f"⚠️ Error setting prefix/suffix: {e}")

    file_path = f"downloads/{new_filename}"  # The path to save the downloaded file

    # Start downloading the media
    file = update.message.reply_to_message  # The original message being replied to
    ms = await update.message.edit("⚠️ **Please wait...**\n\n**Download in progress...**")

    try:
        path = await bot.download_media(
            message=file,
            file_name=file_path,  # Save to this path
            progress=progress_for_pyrogram,
            progress_args=("⚠️ Please wait... Downloading...", ms, time.time()),
        )
    except Exception as e:
        return await ms.edit(f"⚠️ Download failed: {e}")

    # Check if metadata should be added
    metadata_path = None
    bool_metadata = await db.get_metadata(update.message.chat.id)

    if bool_metadata:
        metadata = await db.get_metadata_code(update.message.chat.id) or {}
        try:
            metadata_path = await add_metadata(path, metadata)
            path = metadata_path  # Use the new path with metadata
        except Exception as e:
            return await ms.edit(f"⚠️ Error adding metadata: {e}")

    # Determine the file type for uploading
    upload_type = update.data.split("_")[1]

    # Prepare for upload
    await ms.edit("⚠️ **Trying to upload...**")

    # Define custom caption and thumbnail
    custom_caption = await db.get_caption(update.message.chat.id)
    caption = custom_caption.format(
        filename=new_filename,
        filesize=humanbytes(file.document.file_size),
        duration=convert(0),  # Default duration to avoid errors
    ) if custom_caption else f"**{new_filename}**"

    thumb_path = None

    # Handle thumbnail
    if update.message.reply_to_message.thumbs:
        try:
            # Attempt to get the thumbnail from the media
            thumb = update.message.reply_to_message.thumbs[0]
            thumb_path = await bot.download_media(thumb)
            width, height, thumb_path = await fix_thumb(thumb_path)
        except Exception as e:
            thumb_path = None
            print("Error handling thumbnail:", e)

    # Define the upload logic based on type and size
    if upload_type == "document":
        await bot.send_document(
            update.message.chat.id,
            document=path,
            caption=caption,
            thumb=thumb_path if thumb_path else None,
            progress=progress_for_pyrogram,
            progress_args=("⚠️ Please wait... Uploading...", ms, time.time()),
        )
    elif upload_type == "video":
        await bot.send_video(
            update.message.chat.id,
            video=path,
            caption=caption,
            thumb=thumb_path if thumb_path else None,
            progress=progress_for_pyrogram,
            progress_args=("⚠️ Please wait... Uploading...", ms, time.time()),
        )
    elif upload_type == "audio":
        await bot.send_audio(
            update.message.chat.id,
            audio=path,
            caption=caption,
            thumb=thumb_path if thumb_path else None,
            progress=progress_for_pyrogram,
            progress_args=("⚠️ Please wait... Uploading...", ms, time.time()),
        )

    # Clean up temporary files
    if thumb_path:
        os.remove(thumb_path)
    if file_path:
        os.remove(file_path)

    await ms.delete()  # Delete the intermediate message after completion
