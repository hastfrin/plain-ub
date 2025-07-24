from app import BOT, Message


@BOT.add_cmd(cmd="click")
async def click(bot: BOT, message: Message):
    if not message.input or not message.replied:
        await message.reply("Responda a uma mensagem que contenha um botão e diga qual botão clicar")
        return
    try:
        button_name = message.input.strip()
        button = int(button_name) if button_name.isdigit() else button_name
        await message.replied.click(button)
    except Exception as e:
        await message.reply(str(e), del_in=5)
