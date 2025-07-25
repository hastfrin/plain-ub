from urllib.parse import urlparse

from app import BOT, Message


def parse_link(link: str) -> tuple[int | str, int, int]:
    parsed_url: str = urlparse(link).path.strip("/")
    link_chunks = parsed_url.lstrip("c/").split("/")

    thread = "0"
    if len(link_chunks) == 3:
        chat, thread, message = link_chunks
    else:
        chat, message = link_chunks

    if chat.isdigit():
        chat = int(f"-100{chat}")

    if thread.isdigit():
        thread = int(thread)

    return chat, thread, int(message)


@BOT.add_cmd(cmd="gm")
async def get_message(bot: BOT, message: Message):
    """
    CMD: GM
    INFO: Pega uma mensagem pelo link e mostra o JSON/atributo.
    USO:
        .gm t.me/.... | .gm t.me/... texto [Retorna apenas o texto]
    """
    if not message.input:
        await message.reply("Envie um link de mensagem.")
        return

    attr = None

    if len(message.text_list) == 3:
        link, attr = message.text_list[1:]
    else:
        link = message.input.strip()

    remote_message = Message(await bot.get_messages(link=link))

    if not attr:
        await message.reply(f"```\n{remote_message}```")
        return

    await message.reply(f"```\n{getattr(remote_message, attr, None)}```")