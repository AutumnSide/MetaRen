@Client.on_message(filters.private & filters.command("start"))
async def settings(client, message):

  if message.from_user.id in Config.BANNED_USERS:
        await message.reply_text("Sorry, You are banned.")
        return
