from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from helper.database import db
from pyromod.exceptions import ListenerTimeout
from config import Txt

# Metadata toggle buttons
ON = [[InlineKeyboardButton('Enabled ✅', callback_data='metadata_1')], [InlineKeyboardButton('Set Metadata', callback_data='custom_metadata')]]
OFF = [[InlineKeyboardButton('Disabled ❌', callback_data='metadata_0')], [InlineKeyboardButton('Set Metadata', callback_data='custom_metadata')]]

# /metadata command handler
@Client.on_message(filters.private & filters.command('metadata'))
async def handle_metadata(bot: Client, message: Message):
    try:
        ms = await message.reply_text("**Please wait...**", reply_to_message_id=message.id)

        # Retrieve metadata status and custom metadata information
        bool_metadata = await db.get_metadata(message.from_user.id)
        metadata_info = await db.get_metadata_code(message.from_user.id)

        await ms.delete()

        metadata_text = "No metadata set." if not metadata_info else f"Your Current Metadata:\n\n➜ {metadata_info}"

        # Respond with the appropriate InlineKeyboard based on metadata status
        if bool_metadata:
            await message.reply_text(metadata_text, reply_markup=InlineKeyboardMarkup(ON))
        else:
            await message.reply_text(metadata_text, reply_markup=InlineKeyboardMarkup(OFF))
    except Exception as e:
        await message.reply_text("⚠️ An error occurred while processing the /metadata command. Please try again later.")
        print("Error in /metadata command:", e)

# /metadata callback query handler
@Client.on_callback_query(filters.regex('.*?(custom_metadata|metadata).*?'))
async def query_metadata(bot: Client, query: CallbackQuery):
    try:
        data = query.data

        # Handle metadata toggle
        if data.startswith('metadata_'):
            _bool = bool(int(data.split('_')[1]))

            # Update metadata status
            await db.set_metadata(query.from_user.id, _bool)

            metadata_info = await db.get_metadata_code(query.from_user.id)
            metadata_text = "No metadata set." if not metadata_info else f"Your Current Metadata:\n\n➜ {metadata_info}"

            # Update InlineKeyboard based on the current metadata status
            await query.message.edit(
                metadata_text,
                reply_markup=InlineKeyboardMarkup(ON if _bool else OFF)
            )

        # Handle custom metadata input
        elif data == 'custom_metadata':
            # Function to ask for user input with timeout handling
            async def get_user_input(question_text):
                try:
                    response = await bot.ask(
                        chat_id=query.from_user.id,
                        text=question_text,
                        filters=filters.text,
                        timeout=30
                    )
                    return response.text
                except ListenerTimeout:
                    return None

            # Get video, audio, and subtitle titles from user input
            video_title = await get_user_input(Txt.SEND_VIDEO_TITLE)
            audio_title = await get_user_input(Txt.SEND_AUDIO_TITLE)
            subtitle_title = await get_user_input(Txt.SEND_SUBTITLE_TITLE)

            if not (video_title and audio_title and subtitle_title):
                await query.message.reply_text("⚠️ Timeout or invalid input. Please restart by using /metadata.")
                return

            # Save the metadata information in MongoDB
            metadata_info = {
                "video_title": video_title,
                "audio_title": audio_title,
                "subtitle_title": subtitle_title
            }

            await db.set_metadata_code(query.from_user.id, metadata_info)

            # Confirmation message with the updated metadata status
            await query.message.reply_text(
                "Metadata updated successfully ✅",
                reply_markup=InlineKeyboardMarkup(ON)
            )
    except Exception as e:
        await query.message.reply_text("⚠️ An error occurred while updating metadata. Please try again later.")
        print("Error in query_metadata:", e)
