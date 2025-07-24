from app import BOT, Config, CustomDB, Message

DB = CustomDB["SUDO_CMD_LIST"]


async def init_task():
    async for sudo_cmd in DB.find():
        cmd_object = Config.CMD_DICT.get(sudo_cmd["_id"])
        if cmd_object:
            cmd_object.loaded = True


@BOT.add_cmd(cmd="addscmd", allow_sudo=False)
async def add_scmd(bot: BOT, message: Message):
    """
    CMD: ADDSCMD
    INFO: Adiciona comandos Sudo.
    FLAGS: -all para adicionar todos instantaneamente.
    USO:
        .addscmd ping | .addscmd -all
    """
    if "-all" in message.flags:
        cmds = []

        for cmd_name, cmd_object in Config.CMD_DICT.items():
            if cmd_object.sudo:
                cmd_object.loaded = True
                cmds.append({"_id": cmd_name})

        await DB.drop()
        await DB.insert_many(cmds)

        await (await message.reply("Todos os comandos foram adicionados ao Sudo!")).log()
        return

    cmd_name = message.filtered_input
    cmd_object = Config.CMD_DICT.get(cmd_name)

    response = await message.reply(f"Adicionando <b>{cmd_name}</b> ao sudo...")

    if not cmd_object:
        await response.edit(text=f"<b>{cmd_name}</b> não é um comando válido.", del_in=10)
        return

    elif not cmd_object.sudo:
        await response.edit(text=f"<b>{cmd_name}</b> está desabilitado para usuários sudo.", del_in=10)
        return

    elif cmd_object.loaded:
        await response.edit(text=f"<b>{cmd_name}</b> já está no Sudo!", del_in=10)
        return

    resp_str = f"#SUDO\n<b>{cmd_name}</b> adicionado ao Sudo!"

    if "-temp" in message.flags:
        resp_str += "\nTemp: True"
    else:
        await DB.add_data(data={"_id": cmd_name})

    cmd_object.loaded = True

    await (await response.edit(resp_str)).log()


@BOT.add_cmd(cmd="delscmd", allow_sudo=False)
async def del_scmd(bot: BOT, message: Message):
    """
    CMD: DELSCMD
    INFO: Remove comandos Sudo.
    FLAGS: -all para remover todos instantaneamente.
    USO:
        .delscmd ping | .delscmd -all
    """
    if "-all" in message.flags:

        for cmd_object in Config.CMD_DICT.values():
            cmd_object.loaded = False

        await DB.drop()
        await (await message.reply("Todos os comandos removidos do Sudo!")).log()
        return

    cmd_name = message.filtered_input
    cmd_object = Config.CMD_DICT.get(cmd_name)

    if not cmd_object:
        return

    response = await message.reply(f"Removendo <b>{cmd_name}</b> do sudo...")

    if not cmd_object.loaded:
        await response.edit(f"<b>{cmd_name}</b> não está no Sudo!")
        return

    cmd_object.loaded = False
    resp_str = f"#SUDO\n<b>{cmd_name}</b> removido do Sudo!"

    if "-temp" in message.flags:
        resp_str += "\nTemp: True"
    else:
        await DB.delete_data(cmd_name)

    await (await response.edit(resp_str)).log()


@BOT.add_cmd(cmd="vscmd")
async def view_sudo_cmd(bot: BOT, message: Message):
    cmds = [cmd_name for cmd_name, cmd_obj in Config.CMD_DICT.items() if cmd_obj.loaded]

    if not cmds:
        await message.reply("Nenhum comando no SUDO!")
        return

    await message.reply(
        text=f"Lista de <b>{len(cmds)}</b>:\n <pre language=json>{cmds}</pre>",
        del_in=30,
        block=False,
    )
