import re

from app import BOT, Message


@BOT.add_cmd(cmd="resp")
async def respond(bot: BOT, message: Message):
    """
    CMD: RESP
    INFO: Responde a uma mensagem logada.
    USAGE:
        .resp [chat_id | responda a uma mensagem contendo info] oi
    """
    if message.replied:
        inp_text = message.replied.text
        pattern = r"\((-\d+)\)" if "#TAG" in inp_text else r"\[(\d+)\]"
        match = re.search(pattern=pattern, string=inp_text)
        if match:
            chat_id = match.group(1)
            text = message.input
    elif message.input:
        chat_id, text = message.input.split(" ", maxsplit=1)
    else:
        await message.reply("Não foi possível extrair o chat_id e o texto.")
        return

    await bot.send_message(chat_id=int(chat_id), text=text, disable_preview=True)
