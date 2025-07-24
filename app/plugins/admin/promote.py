import asyncio

from pyrogram.enums import ChatMembersFilter, ChatMemberStatus
from pyrogram.errors import FloodWait
from pyrogram.types import ChatPrivileges, User

from app import BOT, Message
from app.extra_config import ADMIN_STATUS

DEMOTE_PRIVILEGES = ChatPrivileges(can_manage_chat=False)

NO_PRIVILEGES = ChatPrivileges(
    can_manage_chat=True,
    can_manage_video_chats=False,
    can_pin_messages=False,
    can_delete_messages=False,
    can_change_info=False,
    can_restrict_members=False,
    can_invite_users=False,
    can_promote_members=False,
    is_anonymous=False,
)


@BOT.add_cmd(cmd=["promote", "demote"])
async def promote_or_demote(bot: BOT, message: Message) -> None:
    """
    CMD: PROMOTE | DEMOTE
    INFO: Adiciona ou remove um administrador.
    FLAGS:
        PROMOTE: -full para permissões completas, -anon para admin anônimo
    USO:
        PROMOTE: .promote [ -anon | -full ] [ UID | REPLY | @ ] Título[Opcional]
        DEMOTE: .demote [ UID | REPLY | @ ]
    """
    promovendo = message.cmd == "promote"
    resposta = await message.reply(
        f"Tentando {'promover' if promovendo else 'rebaixar'}..."
    )

    meu_status = await bot.get_chat_member(chat_id=message.chat.id, user_id=bot.me.id)
    minhas_permissoes = meu_status.privileges

    if not (meu_status.status in ADMIN_STATUS and minhas_permissoes.can_promote_members):
        await resposta.edit("Você não tem permissões suficientes para isso.")
        return

    user, titulo = await message.extract_user_n_reason()
    if not isinstance(user, User):
        await resposta.edit(user, del_in=10)
        return

    minhas_permissoes.can_promote_members = "-full" in message.flags
    minhas_permissoes.is_anonymous = "-anon" in message.flags

    if promovendo:
        final_permissoes = NO_PRIVILEGES if "-wr" in message.flags else minhas_permissoes
    else:
        final_permissoes = DEMOTE_PRIVILEGES

    texto_resposta = f"{'Promovido' if promovendo else 'Rebaixado'}: {user.mention}"

    try:
        await bot.promote_chat_member(
            chat_id=message.chat.id,
            user_id=user.id,
            privileges=final_permissoes
        )
        if promovendo:
            await asyncio.sleep(1)
            await bot.set_administrator_title(
                chat_id=message.chat.id,
                user_id=user.id,
                title=titulo or "Admin"
            )
            if titulo:
                texto_resposta += f"\nTítulo: {titulo}"
            if "-wr" in message.flags:
                texto_resposta += "\nSem permissões adicionais"

        await resposta.edit(text=texto_resposta)
    except Exception as e:
        await resposta.edit(text=str(e), del_in=10, block=True)


@BOT.add_cmd(cmd="demote_all", allow_sudo=False)
async def demote_all(bot: BOT, message: Message):
    me = await bot.get_chat_member(message.chat.id, bot.me.id)
    if me.status != ChatMemberStatus.OWNER:
        await message.reply("Não é possível rebaixar todos sem ser proprietário do chat.")
        return

    resp = await message.reply("Aguarde, rebaixando todos os administradores...")
    count = 0

    async for member in bot.get_chat_members(
        chat_id=message.chat.id,
        filter=ChatMembersFilter.ADMINISTRATORS
    ):
        try:
            await bot.promote_chat_member(
                chat_id=message.chat.id,
                user_id=member.user.id,
                privileges=DEMOTE_PRIVILEGES
            )
        except FloodWait as f:
            await asyncio.sleep(f.value + 10)
            await bot.promote_chat_member(
                chat_id=message.chat.id,
                user_id=member.user.id,
                privileges=DEMOTE_PRIVILEGES
            )
        await asyncio.sleep(0.5)
        count += 1

    await resp.edit(f"Rebaixados <b>{count}</b> administradores em {message.chat.title}.")
    await resp.log()
