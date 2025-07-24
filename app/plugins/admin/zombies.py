import asyncio
from datetime import UTC, datetime, timedelta

from pyrogram.errors import FloodWait

from app import BOT, Message
from app.extra_config import ADMIN_STATUS


@BOT.add_cmd(cmd="zombies")
async def clean_zombies(bot: BOT, message: Message):
    if not message.chat._raw.admin_rights:
        await message.reply("Não é possível limpar zumbis sem ser administrador.")
        return

    zombies = 0
    admin_zombies = 0

    response = await message.reply("Limpando zumbis....\nisso pode levar um tempo")

    async for member in bot.get_chat_members(chat_id=message.chat.id):
        try:
            if member.user.is_deleted:

                if member.status in ADMIN_STATUS:
                    admin_zombies += 1
                    continue

                zombies += 1

                await bot.ban_chat_member(
                    chat_id=message.chat.id,
                    user_id=member.user.id,
                    until_date=datetime.now(UTC) + timedelta(seconds=60),
                )
                await asyncio.sleep(1)

        except FloodWait as e:
            await asyncio.sleep(e.value + 3)

    resp_str = f"Removidos <b>{zombies}</b> zumbis."

    if admin_zombies:
        resp_str += f"\n<b>{admin_zombies}</b> zumbi(s) administrador(es) não removido(s)."

    await response.edit(resp_str)
