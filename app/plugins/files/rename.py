import asyncio
import shutil
import time
from pathlib import Path

from ub_core.utils.downloader import Download, DownloadedFile

from app import BOT, Message, bot
from app.plugins.files.download import telegram_download
from app.plugins.files.upload import upload_to_tg


@bot.add_cmd(cmd="rename")
async def rename(bot: BOT, message: Message):
    """
    CMD: RENAME
    INFO: Faça upload de arquivos com nome personalizado
    FLAGS: -s para spoiler
    USO:
        .rename [url | responda a uma mensagem] nome_do_arquivo.ext
    """
    input = message.filtered_input

    response = await message.reply("Verificando entrada...")

    if not message.replied or not message.replied.media or not message.filtered_input:
        await response.edit(
            "Entrada inválida...\nResponda a uma mensagem com mídia ou envie um link e um nome de arquivo no comando."
        )
        return

    dl_path = Path("downloads") / str(time.time())

    await response.edit("Entrada verificada... Iniciando download...")

    if message.replied:
        dl_obj: None = None
        download_coro = telegram_download(
            message=message.replied, dir_name=dl_path, file_name=input, response=response
        )

    else:
        url, file_name = input.split(maxsplit=1)
        dl_obj: Download = await Download.setup(
            url=url, dir=dl_path, message_to_edit=response, custom_file_name=file_name
        )
        download_coro = dl_obj.download()

    try:
        downloaded_file: DownloadedFile = await download_coro
        await upload_to_tg(file=downloaded_file, message=message, response=response)
        shutil.rmtree(dl_path, ignore_errors=True)

    except asyncio.exceptions.CancelledError:
        await response.edit("Cancelado...")

    except TimeoutError:
        await response.edit("Tempo limite de download...")

    except Exception as e:
        await response.edit(str(e))

    finally:
        if dl_obj:
            await dl_obj.close()
