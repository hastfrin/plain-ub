from base64 import b64decode
from io import BytesIO
from os import environ

import openai
from pyrogram.enums import ParseMode
from pyrogram.types import InputMediaPhoto

from app import BOT, Message
from app.plugins.ai.gemini.config import SYSTEM_INSTRUCTION

OPENAI_CLIENT = environ.get("OPENAI_CLIENT", "")
OPENAI_MODEL = environ.get("OPENAI_MODEL", "gpt-4o")

AI_CLIENT = getattr(openai, f"Async{OPENAI_CLIENT}OpenAI")

if AI_CLIENT == openai.AsyncAzureOpenAI:
    text_init_kwargs = dict(
        api_key=environ.get("AZURE_OPENAI_API_KEY"),
        api_version=environ.get("OPENAI_API_VERSION"),
        azure_endpoint=environ.get("AZURE_OPENAI_ENDPOINT"),
        azure_deployment=environ.get("AZURE_DEPLOYMENT"),
    )
    image_init_kwargs = dict(
        api_key=environ.get("DALL_E_API_KEY"),
        api_version=environ.get("DALL_E_API_VERSION"),
        azure_endpoint=environ.get("DALL_E_ENDPOINT"),
        azure_deployment=environ.get("DALL_E_DEPLOYMENT"),
    )
else:
    text_init_kwargs = dict(
        api_key=environ.get("OPENAI_API_KEY"), base_url=environ.get("OPENAI_BASE_URL")
    )
    image_init_kwargs = dict(
        api_key=environ.get("DALL_E_API_KEY"), base_url=environ.get("DALL_E_ENDPOINT")
    )

try:
    TEXT_CLIENT = AI_CLIENT(**text_init_kwargs)
except:
    TEXT_CLIENT = None

try:
    DALL_E_CLIENT = AI_CLIENT(**image_init_kwargs)
except:
    DALL_E_CLIENT = None


@BOT.add_cmd(cmd="gpt")
async def chat_gpt(bot: BOT, message: Message):
    """
    CMD: GPT
    INFO: Faça uma pergunta ao ChatGPT.

    CONFIGURAÇÃO:
        Para usar este comando você precisa definir uma destas variáveis.

            Cliente Padrão:
                OPENAI_API_KEY = sua chave de API
                OPENAI_MODEL = modelo (opcional, padrão gpt-4o)
                OPENAI_BASE_URL = endpoint customizado (opcional)

            Cliente Azure:
                OPENAI_CLIENT="Azure"
                OPENAI_API_VERSION = sua versão
                OPENAI_MODEL = seu modelo Azure
                AZURE_OPENAI_API_KEY = sua chave
                AZURE_OPENAI_ENDPOINT = seu endpoint Azure
                AZURE_DEPLOYMENT = seu deployment Azure

    USO:
        .gpt oi
        .gpt [responda a uma mensagem]
    """
    if TEXT_CLIENT is None:
        await message.reply("Credenciais OpenAI não definidas ou inválidas.\nVerifique a ajuda.")
        return

    reply_text = message.replied.text if message.replied else ""
    prompt = f"{reply_text}\n\n\n{message.input}".strip()

    if not prompt:
        await message.reply("Faça uma pergunta ou responda a uma mensagem.")
        return

    chat_completion = await TEXT_CLIENT.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
        model=OPENAI_MODEL,
    )

    response = chat_completion.choices[0].message.content
    await message.reply(text=f"**>\n••> {prompt}<**\n" + response, parse_mode=ParseMode.MARKDOWN)


@BOT.add_cmd(cmd="igen")
async def chat_igen(bot: BOT, message: Message):
    """
    CMD: IGEN
    INFO: Gere imagens usando DALL·E.

    CONFIGURAÇÃO:
        Para usar este comando você precisa definir uma destas variáveis.

            Cliente Padrão:
                DALL_E_API_KEY = sua chave de API
                DALL_E_ENDPOINT = endpoint customizado (opcional)

            Cliente Azure:
                OPENAI_CLIENT="Azure"
                DALL_E_API_KEY = sua chave
                DALL_E_API_VERSION = sua versão
                DALL_E_ENDPOINT = seu endpoint Azure
                DALL_E_DEPLOYMENT = seu deployment Azure

    FLAGS:
        -v: estilo vibrante (padrão)
        -n: estilo mais natural
        -s: enviar como spoiler
        -p: saída retrato
        -l: saída paisagem

    USO:
        .igen gatos na lua
    """
    if DALL_E_CLIENT is None:
        await message.reply("Credenciais OpenAI não definidas ou inválidas.\nVerifique a ajuda.")
        return

    prompt = message.filtered_input.strip()
    if not prompt:
        await message.reply("Forneça um prompt para gerar a imagem.")
        return

    response = await message.reply("Gerando imagem...")

    if "-p" in message.flags:
        output_res = "1024x1792"
    elif "-l" in message.flags:
        output_res = "1792x1024"
    else:
        output_res = "1024x1024"

    try:
        generated_image = await DALL_E_CLIENT.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=output_res,
            quality="hd",
            response_format="b64_json",
            style="natural" if "-n" in message.flags else "vivid",
        )
    except Exception:
        await response.edit("Algo deu errado... Verifique o canal de logs.")
        raise

    image_io = BytesIO(b64decode(generated_image.data[0].b64_json))
    image_io.name = "photo.png"

    await response.edit_media(
        InputMediaPhoto(
            media=image_io,
            caption=f"**>\n{prompt}\n<**",
            has_spoiler="-s" in message.flags,
        )
    )
