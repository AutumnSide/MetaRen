import random
from helper.ffmpeg import fix_thumb, take_screen_shot  # Custom helpers for thumbnail management
from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from helper.utils import progress_for_pyrogram, convert, humanbytes  # Utility functions
from helper.database import db  # Database interactions
import asyncio
import os
import time
import subprocess  # For executing FFmpeg commands
from config import Config


# Initialize the Pyrogram client
app = Client("test", api_id=Config.STRING_API_ID, api_hash=Config.STRING_API_HASH, session_string=Config.STRING_SESSION)

# Handle 'rename' callback queries
@Client.on_callback_query(filters.regex('rename'))
async def rename(bot, update):
    await update.message.delete()  # Delete the current message
    await update.message.reply_text(
        "__Please enter the new file name.__",
        reply_to_message_id=update.message.reply_to_message.id,
        reply_markup=ForceReply(True)  # Prompt for a new file name
    )

# Handle messages that are replies to a forced prompt
@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply_message = message.reply_to_message  # Get the original message
    if isinstance(reply_message.reply_markup, ForceReply):  # Ensure it's a response to a forced prompt
        new_name = message.text  # The new file name from user input
        await message.delete()  # Delete the user response
        msg = await client.get_messages(message.chat.id, reply_message.id)  # Get the original message
        file = msg.reply_to_message  # The media file to rename
        media = getattr(file, file.media.value)  # Get the media type

        # Ensure the new name has an extension
        if not "." in new_name:
            if "." in media.file_name:
                extn = media.file_name.rsplit('.', 1)[-1]  # Get the extension from the original file
            else:
                extn = "mkv"  # Default extension
            new_name = f"{new_name}.{extn}"  # Append the extension

        await reply_message.delete()  # Delete the prompt message

        # Create inline keyboard buttons for selecting file type
        button = [[InlineKeyboardButton("📁 Document", callback_data="upload_document")]]
        if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
            button.append([InlineKeyboardButton("🎥 Video", callback_data="upload_video")])
        elif file.media == MessageMediaType.AUDIO:
            button.append([InlineKeyboardButton("🎵 Audio", callback_data="upload_audio")])

        # Send a message with the new file name and file type choices
        await message.reply(
            f"Select the output file type.\nFile Name: `{new_name}`",
            reply_markup=InlineKeyboardMarkup(button),
            reply_to_message_id=file.id  # Reply to the original message
        )

# Handle callback queries for file uploads
@Client.on_callback_query(filters.regex("upload"))
async def doc(bot, update):
    # Ensure the Metadata directory exists
    if not os.path.isdir("Metadata"):
        os.mkdir("Metadata")

    # Extract necessary information
    prefix = await db.get_prefix(update.message.chat.id)  # Get the prefix from the database
    suffix = await db.get_suffix(update.message.chat.id)  # Get the suffix from the database
    new_name = update.message.text.split(":-")[1]  # Extract the file name from the message text

    # Add prefix and suffix to the new file name
    try:
        new_filename = add_prefix_suffix(new_name, prefix, suffix)  # Add prefix and suffix
    except Exception as e:
        return await update.message.edit(f"⚠️ Error setting Prefix/Suffix: {e}")

    file_path = f"downloads/{new_filename}"  # The path to save the downloaded file
    file = update.message.reply_to_message  # The original message being replied to

    # Edit the message to indicate the download process has started
    ms = await update.message.edit("⚠️ __**Please wait...**__\n\n**Trying to download....**")

    # Download the media file
    try:
        path = await bot.download_media(
            message=file,
            file_name=file_path,  # Save to this path
            progress=progress_for_pyrogram,
            progress_args=("\n⚠️ __**Please wait...**__\n\n❄️ **Download started....**", ms, time.time())
        )
    except Exception as e:
        return await ms.edit(f"⚠️ Download failed: {e}")

    # Check if metadata should be added
    bool_metadata = await db.get_metadata(update.message.chat.id)

    # If metadata is enabled, construct the FFmpeg command to add metadata
    if bool_metadata:
        metadata = await db.get_metadata_code(update.message.chat.id)  # Get metadata information
        if metadata:
            # Edit message to indicate metadata is being added
            await ms.edit("I found your metadata.\nPlease wait...\nAdding metadata to the file....")
            metadata_args = " ".join([f'-metadata {key}="{value}"' for key, value in metadata.items()])

            # Create the FFmpeg command to add metadata to the file
            cmd = f'ffmpeg -i "{path}" {metadata_args} -c copy "{file_path}"'

            # Run FFmpeg asynchronously to add metadata
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,  # Capture standard output
                stderr=asyncio.subprocess.PIPE  # Capture standard error
            )

            stdout, stderr = await process.communicate()  # Wait for the command to finish
            error_message = stderr.decode()  # Get any error messages

            # Handle errors from FFmpeg
            if error_message:
                return await ms.edit(f"⚠️ FFmpeg Error: {error_message}")

            # Update the message to indicate successful metadata addition
            await ms.edit("**Metadata added successfully ✅**\n\n⚠️ **Trying to upload....**")

    else:
        # If metadata is not enabled, proceed with the upload
        await ms.edit("⚠️ **Trying to upload....**")

    # Obtain additional metadata such as duration
    duration = 0  # Default duration
    try:
        parser = createParser(file_path)  # Create a parser for the file
        file_metadata = extractMetadata(parser)  # Extract metadata
        if file_metadata.has("duration"):
            duration = file_metadata.get('duration').seconds  # Get the duration in seconds
    except:
        pass

    # Handle custom caption and thumbnail
    c_caption = await db.get_caption(update.message.chat.id)  # Get the custom caption from the database
    c_thumb = await db.get_thumbnail(update.message.chat.id)  # Get the custom thumbnail from the database
    ph_path = None  # Default thumbnail path

    if c_caption:  # If there's a custom caption
        try:
            # Format the caption with the new file name, file size, and duration
            caption = c_caption.format(
                filename=new_filename,
                filesize=humanbytes(media.file_size),  # Convert file size to human-readable format
                duration=convert(duration)  # Convert duration to a readable format
            )
        except Exception as e:
            # Handle errors during caption formatting
            return await ms.edit(f"Your caption has an error: {e}")
    else:
        # Default caption with just the new file name
        caption = f"**{new_filename}**"

    # Check if a custom thumbnail is provided
    if c_thumb:
        try:
            # Download the custom thumbnail
            ph_path = await bot.download_media(c_thumb)
            width, height, ph_path = await fix_thumb(ph_path)  # Fix thumbnail size
        except Exception as e:
            # Handle errors during thumbnail handling
            ph_path = None
            print("Error downloading custom thumbnail:", e)
    elif media.thumbs:
        try:
            # Take a screenshot to use as a thumbnail
            ph_path_ = await take_screen_shot(
                file_path, os.path.dirname(os.path.abspath(file_path)), random.randint(0, duration - 1)
            )
            width, height, ph_path = await fix_thumb(ph_path_)  # Fix the thumbnail size
        except Exception as e:
            ph_path = None  # Default if there's an error
            print("Error taking screenshot:", e)

    # Determine the file type for uploading
    upload_type = update.data.split("_")[1]

    # Handle large files (over 2 GB) by uploading to a log channel first
    if media.file_size > 2000 * 1024 * 1024:
        try:
            if upload_type == "document":
                # Upload the document to the log channel
                filw = await app.send_document(
                    Config.LOG_CHANNEL,
                    document=metadata_path if bool_metadata else file_path,  # Use metadata_path if metadata was added
                    thumb=ph_path,  # Use the thumbnail if available
                    caption=caption,  # Caption for the document
                    progress=progress_for_pyrogram,
                    progress_args=("⚠️ Please wait... Uploading...", ms, time.time())
                )

                from_chat = filw.chat.id  # Get the chat ID from where the document was uploaded
                mg_id = filw.id  # Get the message ID
                time.sleep(2)  # Wait before copying
                await bot.copy_message(update.from_user.id, from_chat, mg_id)  # Copy the document to the user
                await ms.delete()  # Delete the intermediate message
                await bot.delete_messages(from_chat, mg_id)  # Delete the original message in the log channel

            elif upload_type == "video":
                # Upload the video to the log channel
                filw = await app.send_video(
                    Config.LOG_CHANNEL,
                    video=metadata_path if bool_metadata else file_path,  # Use metadata_path if metadata was added
                    caption=caption,  # Caption for the video
                    thumb=ph_path,  # Thumbnail for the video
                    width=width,  # Video width
                    height=height,  # Video height
                    duration=duration,  # Video duration
                    progress=progress_for_pyrogram,
                    progress_args=("⚠️ Please wait... Uploading...", ms, time.time())
                )

                from_chat = filw.chat.id  # Get the chat ID from where the video was uploaded
                mg_id = filw.id  # Get the message ID
                time.sleep(2)  # Wait before copying
                await bot.copy_message(update.from_user.id, from_chat, mg_id)  # Copy the video to the user
                await ms.delete()  # Delete the intermediate message
                await bot.delete_messages(from_chat, mg_id)  # Delete the original message in the log channel

            elif upload_type == "audio":
                # Upload the audio to the log channel
                filw = await app.send_audio(
                    Config.LOG_CHANNEL,
                    audio=metadata_path if bool_metadata else file_path,  # Use metadata_path if metadata was added
                    caption=caption,  # Caption for the audio
                    thumb=ph_path,  # Thumbnail for the audio
                    duration=duration,  # Audio duration
                    progress=progress_for_pyrogram,
                    progress_args=("⚠️ Please wait... Uploading...", ms, time.time())
                )

                from_chat = filw.chat.id  # Get the chat ID from where the audio was uploaded
                mg_id = filw.id  # Get the message ID
                time.sleep(2)  # Wait before copying
                await bot.copy_message(update.from_user.id, from_chat, mg_id)  # Copy the audio to the user
                await ms.delete()  # Delete the intermediate message
                await bot.delete_messages(from_chat, mg_id)  # Delete the original message in the log channel

        except Exception as e:
            # Handle errors during upload
            os.remove(file_path)  # Clean up the file
            if ph_path:  # Clean up the thumbnail
                os.remove(ph_path)
            if metadata_path:  # Clean up the metadata path
                os.remove(metadata_path)
            if path:  # Clean up the download path
                os.remove(path)
            return await ms.edit(f"Error during upload: {e}")

    else:
        # For smaller files, upload directly to the user's chat
        try:
            if upload_type == "document":
                await bot.send_document(
                    update.message.chat.id,
                    document=metadata_path if bool_metadata else file_path,  # Use metadata_path if metadata was added
                    thumb=ph_path,
                    caption=caption,  # Caption for the document
                    progress=progress_for_pyrogram,
                    progress_args=("⚠️ Please wait... Uploading...", ms, time.time())
                )
            elif upload_type == "video":
                await bot.send_video(
                    update.message.chat.id,
                    video=metadata_path if bool_metadata else file_path,  # Use metadata_path if metadata was added
                    caption=caption,
                    thumb=ph_path,  # Thumbnail for the video
                    width=width,  # Video width
                    height=height,  # Video height
                    duration=duration,  # Video duration
                    progress=progress_for_pyrogram,
                    progress_args=("⚠️ Please wait... Uploading...", ms, time.time())
                )
            elif upload_type == "audio":
                await bot.send_audio(
                    update.message.chat.id,
                    audio=metadata_path if bool_metadata else file_path,  # Use metadata_path if metadata was added
                    caption=caption,  # Caption for the audio
                    thumb=ph_path,  # Thumbnail for the audio
                    duration=duration,  # Audio duration
                    progress=progress_for_pyrogram,
                    progress_args=("⚠️ Please wait... Uploading...", ms, time.time())
                )
        except Exception as e:
            # Handle errors during upload
            os.remove(file_path)  # Clean up the file
            if ph_path:
                os.remove(ph_path)  # Clean up the thumbnail
            if metadata_path:
                os.remove(metadata_path)  # Clean up the metadata path
            return await ms.edit(f"Error during upload: {e}")

    # Delete the intermediate message after completion
    await ms.delete()

    # Clean up temporary files after uploading
    if ph_path:
        os.remove(ph_path)  # Clean up the thumbnail

