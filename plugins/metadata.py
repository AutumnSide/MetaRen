from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from helper.database import db
from pyromod.exceptions import ListenerTimeout
from config import Txt

# Define metadata toggle button layouts
ON = [[InlineKeyboardButton('Enabled ✅', callback_data='metadata_1')], [InlineKeyboardButton('Set Metadata', callback_data='custom_metadata')]]
OFF = [[InlineKeyboardButton('Disabled ❌', callback_data='metadata_0')], [InlineKeyboardButton('Set Metadata', callback_data='custom_metadata')]]

# Handle /metadata command
@Client.on_message(filters.private & filters.command('metadata'))
async def handle_metadata(bot: Client, message: Message):
    try:
        ms = await message.reply_text("**Please wait...**", reply_to_message_id=message.id)

        # Retrieve metadata information from the database
        bool_metadata = await db.get_metadata(message.from_user.id)
        user_metadata = await db.get_metadata_code(message.from_user.id)

        await ms.delete()

        metadata_text = "Your Current Metadata:\n\n➜ `No metadata set.`" if user_metadata is None else f"Your Current Metadata:\n\n➜ `{user_metadata}`"

        # Choose the correct reply based on metadata state
        if bool_metadata:
            await message.reply_text(metadata_text, reply_markup=InlineKeyboardMarkup(ON))
        else:
            await message.reply_text(metadata_text, reply_markup=InlineKeyboardMarkup(OFF))
    except Exception as e:
        await message.reply_text("⚠️ An error occurred while handling the /metadata command. Please try again later.")
        print("Error in /metadata command:", e)

# Handle callback queries for toggling metadata and setting custom metadata
@Client.on_callback_query(filters.regex('.*?(custom_metadata|metadata).*?'))
async def query_metadata(bot: Client, query: CallbackQuery):
    try:
        data = query.data

        # Handle enabling/disabling metadata
        if data.startswith('metadata_'):
            _bool = bool(int(data.split('_')[1]))
            
            # Update metadata status
            await db.set_metadata(query.from_user.id, _bool)
            user_metadata = await db.get_metadata_code(query.from_user.id)
            metadata_text = "Your Current Metadata:\n\n➜ `No metadata set.`" if user_metadata is None else f"Your Current Metadata:\n\n➜ `{user_metadata}`"

            # Update the InlineKeyboard based on the current status
            await query.message.edit(
                metadata_text,
                reply_markup=InlineKeyboardMarkup(ON if _bool else OFF)
            )

        # Handle setting custom metadata
        elif data == 'custom_metadata':
            await query.message.delete()

            # Define functions to ask user for custom metadata inputs with proper error handling
            def get_user_input(bot, user_id, question, timeout=30):
                try:
                    response = await bot.ask(
                        chat_id=user_id,
                        text=question,
                        filters=filters.text,
                        timeout=timeout
                    )
                    return response.text
                except ListenerTimeout:
                    return None

            video_title = await get_user_input(bot, query.from_user.id, Txt.SEND_VIDEO_TITLE)
            audio_title = await get_user_input(bot, query.from_user.id, Txt.SEND_AUDIO_TITLE)
            subtitle_title = await get_user_input(bot, query.from_user.id, Txt.SEND_SUBTITLE_TITLE)

            if not (video_title and audio_title and subtitle_title):
                await query.message.reply_text("⚠️ Error!! Request timed out or invalid input. Please try again using /metadata.")
                return

            metadata_info = {
                "video_title": video_title,
                "audio_title": audio_title,
                "subtitle_title": subtitle_title
            }

            # Save custom metadata information
            await db.set_metadata_code(query.from_user.id, metadata_info)

            await query.message.reply_text(
                "Metadata updated successfully ✅",
                reply_markup=InlineKeyboardMarkup(ON)
            )
    except Exception as e:
        await query.message.reply_text("⚠️ An error occurred while updating metadata. Please try again later.")
        print("Error in handling metadata:", e)
