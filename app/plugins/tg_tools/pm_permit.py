import asyncio
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ChatType
from ub_core.utils.helpers import get_name

from app import BOT, CustomDB, Message, bot, extra_config

PM_USERS = CustomDB["PM_USERS"]
PM_GUARD = CustomDB["COMMON_SETTINGS"]

ALLOWED_USERS: list[int] = []
RECENT_USERS: dict = defaultdict(int)


async def init_task():
    guard = (await PM_GUARD.find_one({"_id": "guard_switch"})) or {}
    extra_config.PM_GUARD = guard.get("value", False)
    [ALLOWED_USERS.append(user_id["_id"]) async for user_id in PM_USERS.find()]


async def pm_permit_filter(_, __, message: Message):
    # Retorne False se:
    if (
        # PM_GUARD está desativado
        not extra_config.PM_GUARD
        # O chat não é privado
        or message.chat.type != ChatType.PRIVATE
        # O chat já está aprovado
        or message.chat.id in ALLOWED_USERS
        # Mensagens salvas
        or message.chat.id == bot.me.id
        # É um bot
        or message.from_user.is_bot
        # Mensagem de serviço do Telegram (ex: OTP)
        or message.from_user.is_support
        # Mensagens de serviço (fixou uma foto, etc)
        or message.service
    ):
        return False
    return True


PERMIT_FILTER = filters.create(pm_permit_filter)


@bot.on_message(PERMIT_FILTER & filters.incoming, group=0)
async def handle_new_pm(bot: BOT, message: Message):
    user_id = message.from_user.id
    if RECENT_USERS[user_id] == 0:
        await bot.log_text(
            text=f"#PMGUARD\n{message.from_user.mention} [{user_id}] te enviou uma mensagem.", type="info"
        )
    RECENT_USERS[user_id] += 1

    if message.chat.is_support:
        return

    if RECENT_USERS[user_id] >= 5:
        await message.reply("Você foi bloqueado por spam.")
        await bot.block_user(user_id)
        RECENT_USERS.pop(user_id)
        await bot.log_text(
            text=f"#PMGUARD\n{message.from_user.mention} [{user_id}] foi bloqueado por spam.",
            type="info",
        )
        return
    if RECENT_USERS[user_id] % 2:
        await message.reply("Você não está autorizado a enviar PM.")


@bot.on_message(PERMIT_FILTER & filters.outgoing, group=2)
async def auto_approve(bot: BOT, message: Message):
    message = Message(message=message)
    ALLOWED_USERS.append(message.chat.id)
    await asyncio.gather(
        PM_USERS.insert_one({"_id": message.chat.id}),
        message.reply(text="Aprovado automaticamente para PM.", del_in=5),
    )


@bot.add_cmd(cmd="pmguard")
async def pm_guard(bot: BOT, message: Message):
    """
    CMD: PMGUARD
    INFO: Ativar/Desativar o PM GUARD.
    FLAGS: -c para checar status.
    USAGE:
        .pmguard | .pmguard -c
    """
    if "-c" in message.flags:
        await message.reply(text=f"PM Guard está ativado: <b>{extra_config.PM_GUARD}</b>", del_in=8)
        return
    value = not extra_config.PM_GUARD
    extra_config.PM_GUARD = value
    await asyncio.gather(
        PM_GUARD.add_data({"_id": "guard_switch", "value": value}),
        message.reply(text=f"PM Guard está ativado: <b>{value}</b>!", del_in=8),
    )


@bot.add_cmd(cmd=["a", "allow"])
async def allow_pm(bot: BOT, message: Message):
    """
    CMD: A | ALLOW
    INFO: Aprova um usuário para enviar PM.
    USAGE: .a|.allow [responda um usuário ou use em PM]
    """
    user_id, name = get_userID_name(message)
    if not user_id:
        await message.reply(
            "Não foi possível extrair o usuário para permitir.\n<code>Informe o id | Responda a um usuário | use em PM.</code>"
        )
        return
    if user_id in ALLOWED_USERS:
        await message.reply(f"{name} já está aprovado.")
        return
    ALLOWED_USERS.append(user_id)
    RECENT_USERS.pop(user_id, 0)
    await asyncio.gather(
        message.reply(text=f"{name} foi aprovado para PM.", del_in=8),
        PM_USERS.insert_one({"_id": user_id}),
    )


@bot.add_cmd(cmd="nopm")
async def no_pm(bot: BOT, message: Message):
    user_id, name = get_userID_name(message)
    if not user_id:
        await message.reply(
            "Não foi possível extrair o usuário para remover permissão.\n<code>Informe o id | Responda a um usuário | use em PM.</code>"
        )
        return
    if user_id not in ALLOWED_USERS:
        await message.reply(f"{name} não está aprovado para PM.")
        return
    ALLOWED_USERS.remove(user_id)
    await asyncio.gather(
        message.reply(text=f"{name} teve o PM removido.", del_in=8), PM_USERS.delete_data(user_id)
    )


def get_userID_name(message: Message) -> tuple:
    if message.filtered_input and message.filtered_input.isdigit():
        user_id = int(message.filtered_input)
        return user_id, user_id
    elif message.replied:
        return message.replied.from_user.id, get_name(message.replied.from_user)
    elif message.chat.type == ChatType.PRIVATE:
        return message.chat.id, get_name(message.chat)
    else:
        return 0, 0
