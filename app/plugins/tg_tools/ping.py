from datetime import datetime

from app import BOT, Message

# Não é meu código
# Provavelmente do Userge/UX/VenomX, sei lá
@BOT.add_cmd(cmd="ping")
async def ping_bot(bot: BOT, message: Message):
    inicio = datetime.now()
    resp: Message = await message.reply("Testando o ping...")
    tempo = (datetime.now() - inicio).microseconds / 1000
    await resp.edit(f"Pong! {tempo} ms.")
