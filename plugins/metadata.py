from mutagen.mp4 import MP4, MP4Tags
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from helper.database import db
from pyromod.exceptions import ListenerTimeout
from config import Txt

# Metadata Toggle buttons
ON = [[InlineKeyboardButton('Enabled ✅', callback_data='metadata_1')], [
    InlineKeyboardButton('Set Metadata', callback_data='custom_metadata')]]
OFF = [[InlineKeyboardButton('Disabled ❌', callback_data='metadata_0')], [
    InlineKeyboardButton('Set Metadata', callback_data='custom_metadata')]]

# /metadata command handler
@Client.on_message(filters.private & filters.command('metadata'))
async def handle_metadata(bot: Client, message: Message):
    ms = await message.reply_text("**Please Wait...**", reply_to_message_id=message.id)

    # Retrieve current metadata status and metadata info for the user
    bool_metadata = await db.get_metadata(message.from_user.id)
    user_metadata = await db.get_metadata_code(message.from_user.id)

    await ms.delete()

    # Set the metadata status to display in the response
    metadata_text = "No metadata set." if user_metadata is None else f"Your Current Metadata:\n\n➜ `{user_metadata}`"
    
    if bool_metadata:
        # If metadata is enabled, show the metadata info with the ON button
        await message.reply_text(metadata_text, reply_markup=InlineKeyboardMarkup(ON))
    else:
        # If metadata is disabled, show the metadata info with the OFF button
        await message.reply_text(metadata_text, reply_markup=InlineKeyboardMarkup(OFF))

# /metadata query handler
@Client.on_callback_query(filters.regex('.*?(custom_metadata|metadata).*?'))
async def query_metadata(bot: Client, query: CallbackQuery):
    data = query.data

    # Handling metadata toggle
    if data.startswith('metadata_'):
        _bool = data.split('_')[1]
        _bool = bool(int(_bool))

        # Set metadata status based on the callback query
        await db.set_metadata(query.from_user.id, _bool)
        
        # Retrieve updated metadata information
        user_metadata = await db.get_metadata_code(query.from_user.id)
        metadata_text = "No metadata set." if user_metadata is None else f"Your Current Metadata:\n\n➜ `{user_metadata}`"

        # Update the message with new metadata status
        await query.message.edit(
            metadata_text,
            reply_markup=InlineKeyboardMarkup(ON if _bool else OFF)
        )

    # Handling custom metadata
    elif data == 'custom_metadata':
        await query.message.delete()

        try:
            # Asking user for video title with error handling
            try:
                video_title_response = await bot.ask(
                    query.from_user.id,
                    text=Txt.SEND_VIDEO_TITLE,
                    filters=filters.text,
                    timeout=30
                )
            except ListenerTimeout:
                await query.message.reply_text("⚠️ Error!!\n\n**Request timed out.**\nRestart by using /metadata")
                return

            # Asking for audio title
            try:
                audio_title_response = await bot.ask(
                    query.from_user.id,
                    text=Txt.SEND_AUDIO_TITLE,
                    filters=filters.text,
                    timeout=30
                )
            except ListenerTimeout:
                await query.message.reply_text("⚠️ Error!!\n\n**Request timed out.**\nRestart by using /metadata")
                return

            # Asking for subtitle title
            try:
                subtitle_title_response = await bot.ask(
                    query.from_user.id,
                    text=Txt.SEND_SUBTITLE_TITLE,
                    filters=filters.text,
                    timeout=30
                )
            except ListenerTimeout:
                await query.message.reply_text("⚠️ Error!!\n\n**Request timed out.**\nRestart by using /metadata")
                return

            # Store metadata information as a dictionary
            metadata_info = {
                "video_title": video_title_response.text,
                "audio_title": audio_title_response.text,
                "subtitle_title": subtitle_title_response.text
            }

            # Store metadata in the database
            await db.set_metadata_code(query.from_user.id, metadata_info)

            # Notify the user that the metadata has been set successfully
            await query.message.reply_text(
                "Metadata updated successfully ✅",
                reply_markup=InlineKeyboardMarkup(ON)
            )
        except Exception as e:
            print("Error in setting metadata:", e)
            await query.message.reply_text("⚠️ Error occurred while updating metadata. Try again.")
