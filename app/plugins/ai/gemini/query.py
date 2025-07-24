from pyrogram.enums import ParseMode
from pyrogram.types import InputMediaAudio, InputMediaPhoto

from app import BOT, Message, bot
from app.plugins.ai.gemini import AIConfig, Response, async_client
from app.plugins.ai.gemini.utils import create_prompts, run_basic_check


@bot.add_cmd(cmd="ai")
@run_basic_check
async def question(bot: BOT, message: Message):
    """
    CMD: AI
    INFO: Faça uma pergunta à IA Gemini ou obtenha informações sobre a mensagem/mídia respondida.
    FLAGS:
        -s: usar busca
        -i: editar/gerar imagens
        -a: gerar áudio
            -m: voz masculina
            -f: voz feminina
        -sp: criar fala entre duas pessoas

    USO:
        .ai qual é o sentido da vida.
        .ai [responder a uma mensagem] (envia texto respondido como consulta)
        .ai [responder a mensagem] [prompt extra relacionado à mensagem respondida]

        .ai [responder a imagem | vídeo | gif]
        .ai [responder a imagem | vídeo | gif] [prompt personalizado]

        .ai -a [-m|-f] <texto para falar> (padrão voz feminina)

        .ai -sp TTS a seguinte conversa entre Joe e Jane:
            Joe: Como vai hoje, Jane?
            Jane: Nada mal, e você?
    """

    reply = message.replied
    prompt = message.filtered_input.strip()

    if reply and reply.media:
        resp_str = "<code>Processando... isso pode levar um tempo.</code>"
    else:
        resp_str = "<code>Entrada recebida... gerando resposta.</code>"

    message_response = await message.reply(resp_str)

    try:
        prompts = await create_prompts(message=message)
    except AssertionError as e:
        await message_response.edit(e)
        return

    kwargs = AIConfig.get_kwargs(flags=message.flags)

    response = await async_client.models.generate_content(contents=prompts, **kwargs)

    response = Response(response)

    text = response.text_with_sources()

    if response.image:
        await message_response.edit_media(
            media=InputMediaPhoto(media=response.image_file, caption=f"**>\n•> {prompt}<**")
        )
        return

    if response.audio:
        if isinstance(message, Message):
            await message.reply_voice(
                voice=response.audio_file,
                waveform=response.audio_file.waveform,
                duration=response.audio_file.duration,
                caption=f"**>\n•> {prompt}<**",
            )
        else:
            await message_response.edit_media(
                media=InputMediaAudio(
                    media=response.audio_file,
                    caption=f"**>\n•> {prompt}<**",
                    duration=response.audio_file.duration,
                )
            )
        return

    await message_response.edit(
        text=f"**>\n•> {prompt}<**\n{text}",
        parse_mode=ParseMode.MARKDOWN,
        disable_preview=True,
    )
