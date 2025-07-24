from pyrogram.types import User
from ub_core.utils.helpers import extract_user_data, get_name

from app import BOT, Config, CustomDB, Message

SUDO = CustomDB["COMMON_SETTINGS"]
SUDO_USERS = CustomDB["SUDO_USERS"]


async def init_task():
    sudo = await SUDO.find_one({"_id": "sudo_switch"}) or {}
    Config.SUDO = sudo.get("value", False)

    async for sudo_user in SUDO_USERS.find():
        config = Config.SUPERUSERS if sudo_user.get("super") else Config.SUDO_USERS
        config.append(sudo_user["_id"])

        if sudo_user.get("disabled"):
            Config.DISABLED_SUPERUSERS.append(sudo_user["_id"])


@BOT.add_cmd(cmd="sudo", allow_sudo=False)
async def sudo(bot: BOT, message: Message):
    """
    CMD: SUDO
    INFO: Ativar/Desativar sudo.
    FLAGS: -c para checar o status do sudo.
    USO:
        .sudo | .sudo -c
    """
    if "-c" in message.flags:
        await message.reply(text=f"Sudo está ativado: <b>{Config.SUDO}</b>!", del_in=8)
        return

    value = not Config.SUDO

    Config.SUDO = value

    await SUDO.add_data({"_id": "sudo_switch", "value": value})

    await (await message.reply(text=f"Sudo está ativado: <b>{value}</b>!", del_in=8)).log()


@BOT.add_cmd(cmd="addsudo", allow_sudo=False)
async def add_sudo(bot: BOT, message: Message) -> Message | None:
    """
    CMD: ADDSUDO
    INFO: Adicionar usuário Sudo.
    FLAGS:
        -temp: para adicionar temporariamente até reiniciar o bot.
        -su: para dar acesso de SuperUsuário.
    USO:
        .addsudo [-temp | -su] [ UID | @ | Responder Mensagem ]
    """
    response = await message.reply("Extraindo informações do usuário...")

    user, _ = await message.extract_user_n_reason()

    if not isinstance(user, User):
        await response.edit("Não foi possível extrair as informações do usuário.")
        return

    if "-su" in message.flags:
        add_list, remove_list = Config.SUPERUSERS, Config.SUDO_USERS
        text = "Super Usuários"
    else:
        add_list, remove_list = Config.SUDO_USERS, Config.SUPERUSERS
        text = "Usuários Sudo"

    if user.id in add_list:
        await response.edit(
            text=f"{get_name(user)} já está no Sudo com os mesmos privilégios!", del_in=5
        )
        return

    response_str = f"#SUDO\n{user.mention} adicionado à lista de {text}."

    add_and_remove(user.id, add_list, remove_list)

    if "-temp" not in message.flags:
        await SUDO_USERS.add_data(
            {
                "_id": user.id,
                **extract_user_data(user),
                "disabled": False,
                "super": "-su" in message.flags,
            }
        )
    else:
        response_str += "\n<b>Temporário</b>: True"

    await response.edit(text=response_str, del_in=5)
    await response.log()


@BOT.add_cmd(cmd="delsudo", allow_sudo=False)
async def remove_sudo(bot: BOT, message: Message) -> Message | None:
    """
    CMD: DELSUDO
    INFO: Remover usuário.
    FLAGS:
        -temp: para remover temporariamente até reiniciar o bot.
        -su: para remover acesso de SuperUsuário.
        -f: remover forçado por id
    USO:
        .delsudo [-temp] [ UID | @ | Responder Mensagem ]
    """

    if "-f" in message.flags:
        await SUDO_USERS.delete_data(id=int(message.filtered_input))
        await message.reply(f"Removido forçadamente {message.filtered_input} dos usuários sudo.")
        return

    response = await message.reply("Extraindo informações do usuário...")
    user, _ = await message.extract_user_n_reason()

    if isinstance(user, str):
        await response.edit(user)
        return

    if not isinstance(user, User):
        await response.edit("Não foi possível extrair as informações do usuário.")
        return

    if user.id not in {*Config.SUDO_USERS, *Config.SUPERUSERS}:
        await response.edit(text=f"{get_name(user)} não está no Sudo!", del_in=5)
        return

    if "-su" in message.flags:
        response_str = f"O acesso de SuperUsuário de {user.mention} foi removido (agora é só Sudo)."
        add_and_remove(user.id, Config.SUDO_USERS, Config.SUPERUSERS)
    else:
        add_and_remove(user.id, remove_list=Config.SUPERUSERS)
        add_and_remove(user.id, remove_list=Config.SUDO_USERS)
        response_str = f"O acesso de {user.mention} ao bot foi removido."

    if "-temp" not in message.flags:
        if "-su" in message.flags:
            await SUDO_USERS.add_data({"_id": user.id, "super": False})
        else:
            await SUDO_USERS.delete_data(id=user.id)
    else:
        response_str += "\n<b>Temporário</b>: True"

    await response.edit(text=response_str, del_in=5)
    await response.log()


def add_and_remove(u_id: int, add_list: list | None = None, remove_list: list | None = None):
    if add_list is not None and u_id not in add_list:
        add_list.append(u_id)

    if remove_list is not None and u_id in remove_list:
        remove_list.remove(u_id)


@BOT.add_cmd(cmd="vsudo")
async def sudo_list(bot: BOT, message: Message):
    """
    CMD: VSUDO
    INFO: Ver usuários Sudo.
    FLAGS: -id para mostrar os UIDs
    USO:
        .vsudo | .vsudo -id
    """
    output: str = ""
    total = 0

    async for user in SUDO_USERS.find():
        output += f'\n<b>• {user["name"]}</b>'

        if "-id" in message.flags:
            output += f'\n  ID: <code>{user["_id"]}</code>'

        output += f'\n  Super: <b>{user.get("super", False)}</b>'

        output += f'\n  Desativado: <b>{user.get("disabled", False)}</b>\n'

        total += 1

    if not total:
        await message.reply("Você não tem nenhum USUÁRIO SUDO.")
        return

    output: str = f"Lista de <b>{total}</b> USUÁRIOS SUDO:\n{output}"
    await message.reply(output, del_in=30, block=True)
