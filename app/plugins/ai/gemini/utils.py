import asyncio
import shutil
import time
from functools import wraps
from mimetypes import guess_type

from google.genai.types import File, Part
from ub_core.utils import get_tg_media_details

from app import BOT, Message, extra_config
from app.plugins.ai.gemini import DB_SETTINGS, AIConfig, async_client


def run_basic_check(function):
    @wraps(function)
    async def wrapper(bot: BOT, message: Message):
        if not extra_config.GEMINI_API_KEY:
            await message.reply(
                "Chave de API do Gemini não encontrada."
                "\nObtenha em <a href='https://makersuite.google.com/app/apikey'>AQUI</a> "
                "e defina a variável GEMINI_API_KEY."
            )
            return

        if not (message.input or message.replied):
            await message.reply("<code>Faça uma pergunta ou responda a uma mensagem</code>")
            return
        await function(bot, message)

    return wrapper


async def save_file(message: Message, check_size: bool = True) -> File | None:
    media = get_tg_media_details(message)

    if check_size:
        assert getattr(media, "file_size", 0) <= 1048576 * 25, "O tamanho do arquivo excede 25 MB."

    download_dir = f"downloads/{time.time()}/"
    try:
        downloaded_file: str = await message.download(download_dir)
        uploaded_file = await async_client.files.upload(
            file=downloaded_file,
            config={
                "mime_type": getattr(media, "mime_type", None) or guess_type(downloaded_file)[0]
            },
        )
        while uploaded_file.state.name == "PROCESSING":
            await asyncio.sleep(5)
            uploaded_file = await async_client.files.get(name=uploaded_file.name)

        return uploaded_file

    finally:
        shutil.rmtree(download_dir, ignore_errors=True)


PROMPT_MAP = {
    "video": "Resuma o vídeo e áudio do arquivo",
    "photo": "Resuma o arquivo de imagem",
    "voice": (
        "\nNão resuma."
        "\nTranscreva o áudio para o alfabeto inglês COMO ESTÁ."
        "\nTraduza apenas se o áudio não estiver em inglês."
        "\nSe o áudio estiver em hindi: transcreva para hinglish sem traduzir."
    ),
}
PROMPT_MAP["audio"] = PROMPT_MAP["voice"]


async def create_prompts(
    message: Message, is_chat: bool = False, check_size: bool = True
) -> list[File, str] | list[Part]:

    default_media_prompt = "Analise o arquivo e explique."
    input_prompt = message.filtered_input or "responda"

    # Conversacional
    if is_chat:
        if message.media:
            prompt = message.caption or PROMPT_MAP.get(message.media.value) or default_media_prompt
            text_part = Part.from_text(text=prompt)
            uploaded_file = await save_file(message=message, check_size=check_size)
            file_part = Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)
            return [text_part, file_part]

        return [Part.from_text(text=message.text)]

    # Uso único
    if reply := message.replied:
        if reply.media:
            prompt = (
                message.filtered_input or PROMPT_MAP.get(reply.media.value) or default_media_prompt
            )
            text_part = Part.from_text(text=prompt)
            uploaded_file = await save_file(message=reply, check_size=check_size)
            file_part = Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)
            return [text_part, file_part]

        return [Part.from_text(text=input_prompt), Part.from_text(text=str(reply.text))]

    return [Part.from_text(text=input_prompt)]


@BOT.add_cmd(cmd="llms")
async def list_ai_models(bot: BOT, message: Message):
    """
    CMD: LIST MODELS
    INFO: Lista e altera modelos da Gemini.
    USO: .llms
    """
    model_list = [
        model.name.lstrip("models/")
        async for model in await async_client.models.list(config={"query_base": True})
        if "generateContent" in model.supported_actions
    ]

    model_str = "\n\n".join(model_list)

    update_str = (
        f"<b>Modelo Atual</b>: <code>"
        f"{AIConfig.TEXT_MODEL if "-i" not in message.flags else AIConfig.IMAGE_MODEL}</code>"
        f"\n\n<blockquote expandable=True><pre language=text>{model_str}</pre></blockquote>"
        "\n\nResponda a esta mensagem com o <code>nome do modelo</code> para mudar de modelo."
    )

    model_info_response = await message.reply(update_str)

    model_response = await model_info_response.get_response(
        timeout=60, reply_to_message_id=model_info_response.id, from_user=message.from_user.id
    )

    if not model_response:
        await model_info_response.delete()
        return

    if model_response.text not in model_list:
        await model_info_response.edit("<code>Modelo inválido... Tente novamente</code>")
        return

    if "-i" in message.flags:
        data_key = "image_model_name"
        AIConfig.IMAGE_MODEL = model_response.text
    else:
        data_key = "model_name"
        AIConfig.TEXT_MODEL = model_response.text

    await DB_SETTINGS.add_data({"_id": "gemini_model_info", data_key: model_response.text})
    resp_str = f"{model_response.text} salvo como modelo."
    await model_info_response.edit(resp_str)
    await bot.log_text(text=resp_str, type=f"ai_{data_key}")
