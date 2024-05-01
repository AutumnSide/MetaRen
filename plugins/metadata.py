from mutagen.mp4 import MP4, MP4Tags
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from helper.database import db
from pyromod.exceptions import ListenerTimeout
from config import Txt

# Function to update metadata of a video file
async def update_video_metadata(user_id, metadata_info):
    # Write code to update the metadata of the video file
    # You can use a library like mutagen to modify the metadata
    pass

# Your existing code for handling metadata commands
# ...

@Client.on_callback_query(filters.regex('.*?(custom_metadata|metadata).*?'))
async def query_metadata(bot: Client, query: CallbackQuery):
    data = query.data

    if data.startswith('metadata_'):
        _bool = data.split('_')[1]
        user_metadata = await db.get_metadata_code(query.from_user.id)

        if bool(eval(_bool)):
            await db.set_metadata(query.from_user.id, bool_meta=False)
            await query.message.edit(f"Your Current Metadata:-\n\n➜ `{user_metadata}` ", reply_markup=InlineKeyboardMarkup(OFF))
        else:
            await db.set_metadata(query.from_user.id, bool_meta=True)
            await query.message.edit(f"Your Current Metadata:-\n\n➜ `{user_metadata}` ", reply_markup=InlineKeyboardMarkup(ON))

    elif data == 'cutom_metadata':
        await query.message.delete()
        try:
            # Ask user for video title
            try:
                video_title = await bot.ask(text=Txt.SEND_VIDEO_TITLE, chat_id=query.from_user.id, filters=filters.text, timeout=30)
            except ListenerTimeout:
                await query.message.reply_text("⚠️ Error!!\n\n**Request timed out.**\nRestart by using /metadata", reply_to_message_id=query.message.id)
                return

            # Ask user for audio title
            try:
                audio_title = await bot.ask(text=Txt.SEND_AUDIO_TITLE, chat_id=query.from_user.id, filters=filters.text, timeout=30)
            except ListenerTimeout:
                await query.message.reply_text("⚠️ Error!!\n\n**Request timed out.**\nRestart by using /metadata", reply_to_message_id=query.message.id)
                return

            # Ask user for subtitle title
            try:
                subtitle_title = await bot.ask(text=Txt.SEND_SUBTITLE_TITLE, chat_id=query.from_user.id, filters=filters.text, timeout=30)
            except ListenerTimeout:
                await query.message.reply_text("⚠️ Error!!\n\n**Request timed out.**\nRestart by using /metadata", reply_to_message_id=query.message.id)
                return



            SEND_VIDEO_TITLE ="Enter The Title of the Video"
            SEND_AUDIO_TITLE = "Enter the Title of the Audio"
            SEND_SUBTITLE_TITLE = "Enter thr Title of the Subtitle"
            # Store the metadata information in a dictionary
            metadata_info = {
                "video_title": video_title.text,
                "audio_title": audio_title.text,
                "subtitle_title": subtitle_title.text
            }

            # Update metadata of the video file
            await update_video_metadata(query.from_user.id, metadata_info)

            ms = await query.message.reply_text("**Please Wait...**", reply_to_message_id=metadata.id)
            await db.set_metadata_code(query.from_user.id, metadata_code=metadata.text)
            await ms.edit("**Your Metadata Code Set Successfully ✅**")
        except Exception as e:
            print(e)
