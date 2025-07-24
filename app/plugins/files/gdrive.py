import asyncio
import json
import os
from collections import defaultdict
from functools import wraps

import aiohttp
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pyrogram.enums import ParseMode
from ub_core import BOT, Config, CustomDB, Message, bot
from ub_core.utils import Download, get_tg_media_details, progress

DB = CustomDB["COMMON_SETTINGS"]

INSTRUCTIONS = """
Credenciais do Gdrive e token de acesso não encontrados!

- Baixe o credentials.json em: https://console.cloud.google.com

<blockquote>Passos:
• Habilite a API do Google Drive.
• Configure a tela de consentimento.
• Selecione app externo.
• Adicione você mesmo na audiência/teste.
• Volte.
• Adicione o escopo do Google Drive em acesso a dados.
• Crie um app desktop e baixe o json na seção de credenciais.</blockquote>

- Envie esse arquivo para suas mensagens salvas e responda ele com .gsetup
"""


class Drive:
    URL_TEMPLATE = "https://drive.google.com/file/d/{media_id}/view?usp=sharing"
    FOLDER_MIME = "application/vnd.google-apps.folder"
    SHORTCUT_MIME = "application/vnd.google-apps.shortcut"
    DRIVE_ROOT_ID = os.getenv("DRIVE_ROOT_ID", "root")

    def __init__(self):
        self._aiohttp_session = None
        self._progress_store: dict[str, dict[str, str | int | asyncio.Task]] = defaultdict(dict)
        self._creds: Credentials | None = None
        self.service = None
        self.files = None
        self.is_authenticated = False

    async def async_init(self):
        if self._aiohttp_session is None:
            self._aiohttp_session = aiohttp.ClientSession()
            Config.EXIT_TASKS.append(self._aiohttp_session.close)
        await self.set_creds()

    @property
    def creds(self):
        if (
            isinstance(self._creds, Credentials)
            and self._creds.expired
            and self._creds.refresh_token
        ):
            self._creds.refresh(Request())
            asyncio.run_coroutine_threadsafe(
                coro=DB.add_data(
                    {"_id": "drive_creds", "creds": json.loads(self._creds.to_json())}
                ),
                loop=bot.loop,
            )
            bot.log.info("Credenciais do Gdrive atualizadas automaticamente")
        return self._creds

    @creds.setter
    def creds(self, creds):
        self._creds = creds

    async def set_creds(self):
        cred_data = await DB.find_one({"_id": "drive_creds"})
        if not cred_data:
            self.is_authenticated = False
            return

        self.creds = Credentials.from_authorized_user_info(
            info=cred_data["creds"], scopes=["https://www.googleapis.com/auth/drive"]
        )
        self.service = build(
            serviceName="drive", version="v3", credentials=self.creds, cache_discovery=False
        )
        self.files = self.service.files()
        self.is_authenticated = True

    def ensure_creds(self, func):
        @wraps(func)
        async def inner(bot: BOT, message: Message):
            if not self.is_authenticated:
                await message.reply(INSTRUCTIONS)
            else:
                await func(bot, message)

        return inner

    async def list_contents(
        self,
        _id: bool = False,
        limit: int = 10,
        file_only: bool = False,
        folder_only: bool = False,
        search_param: str | None = None,
    ) -> list[dict[str, str | int]]:
        """
        :param _id: O ID da pasta para listar arquivos.
        :param limit: Número de resultados para buscar.
        :param file_only: Se True, lista apenas arquivos.
        :param folder_only: Se True, lista apenas pastas.
        :param search_param: Termo para buscar no nome do arquivo/pasta.
        :return: Lista de dicionários contendo id, nome e mimeType.
        """
        return await asyncio.to_thread(self._list, _id, limit, file_only, folder_only, search_param)

    async def upload_from_url(
        self,
        file_url: str,
        is_encoded: bool = False,
        folder_id: str = None,
        message_to_edit: Message = None,
    ):
        try:
            file_id = await self._upload_from_url(file_url, is_encoded, folder_id, message_to_edit)
            if file_id is not None:
                return self.URL_TEMPLATE.format(media_id=file_id)
        except Exception as e:
            return f"Erro:\n{e}"
        finally:
            store = self._progress_store.pop(file_url, {})
            store["done"] = True
            task = store.get("edit_task")
            if isinstance(task, asyncio.Task):
                task.cancel()

    async def upload_from_telegram(
        self, media_message: Message, message_to_edit: Message = None, folder_id: str = None
    ):
        try:
            file_id = await self._upload_from_telegram(media_message, message_to_edit, folder_id)
            if file_id is not None:
                return self.URL_TEMPLATE.format(media_id=file_id)
        except Exception as e:
            return f"Erro:\n{e}"
        finally:
            store = self._progress_store.pop(message_to_edit.task_id, {})
            store["done"] = True
            task = store.get("edit_task")
            if isinstance(task, asyncio.Task):
                task.cancel()

    def _list(
        self,
        _id: bool = False,
        limit: int = 10,
        file_only: bool = False,
        folder_only: bool = False,
        search_param: str | None = None,
    ) -> list[dict[str, str | int]]:

        query_params = ["trashed=false"]

        if folder_only:
            query_params.append(f"mimeType = '{self.FOLDER_MIME}'")
        elif file_only:
            query_params.append(f"mimeType != '{self.FOLDER_MIME}'")

        if search_param is not None:
            if _id:
                query_params.append(f"'{search_param}' in parents")
            else:
                query_params.append(f"name contains '{search_param}'")
        else:
            query_params.append(f"'{self.DRIVE_ROOT_ID}' in parents")

        query = " and ".join(query_params)

        files = []

        fields = "nextPageToken, files(id, name, mimeType, shortcutDetails)"
        result = self.files.list(q=query, pageSize=limit, fields=fields).execute()
        files.extend(result.get("files", []))

        while next_token := result.get("nextPageToken"):
            if len(files) >= limit:
                break
            else:
                file_limit = limit - len(files)
            result = self.files.list(
                q=query, pageSize=file_limit, fields=fields, pageToken=next_token
            ).execute()
            files.extend(result.get("files", []))

        return files[0:limit]
    async def create_file(self, file_name: str, folder_id: str = None) -> str:
        """
        :return: Uma URL para o local do arquivo no Drive.
        """
        headers = {
            "Authorization": f"Bearer {self.creds.token}",
            "Content-Type": "application/json",
            "X-Upload-Content-Type": "application/octet-stream",
        }
        async with self._aiohttp_session.post(
            url="https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable",
            json={"name": file_name, "parents": [folder_id or self.DRIVE_ROOT_ID]},
            headers=headers,
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Falha ao iniciar upload: {text}")
            return resp.headers["Location"]

    async def upload_chunk(self, location, headers, chunk) -> str | None:
        async with self._aiohttp_session.put(location, headers=headers, data=chunk) as put:
            if put.status == 308:
                # Chunk aceito, upload não finalizado
                return None
            elif put.status in (200, 201):
                # Arquivo finalizado
                file = await put.json()
                return file["id"]
            else:
                text = await put.text()
                raise Exception(f"Falha no envio do bloco ({put.status}): {text}")

    async def _upload_from_url(
        self,
        file_url: str,
        is_encoded: bool = False,
        folder_id: str = None,
        message_to_edit: Message = None,
    ):
        async with Download(url=file_url, dir="", is_encoded_url=is_encoded) as downloader:
            store = self._progress_store[file_url]
            store["size"] = downloader.size_bytes
            store["done"] = False
            store["uploaded_size"] = 0
            store["edit_task"] = asyncio.create_task(
                self.progress_worker(store, message_to_edit), name="url_drive_up_prog"
            )

            file_session = downloader.file_response_session
            file_session.raise_for_status()
            drive_location = await self.create_file(downloader.file_name, folder_id)
            start = 0
            buffer = b""
            chunk_size = 524288

            async for chunk in downloader.iter_chunks(chunk_size):
                buffer += chunk
                if len(buffer) < chunk_size:
                    continue
                else:
                    chunk = buffer[:chunk_size]
                    end = start + len(chunk) - 1
                    put_headers = {
                        "Content-Range": f"bytes {start}-{end}/{downloader.size_bytes}",
                        "Authorization": f"Bearer {self.creds.token}",
                    }
                    file_id = await self.upload_chunk(drive_location, put_headers, chunk)
                    start += len(chunk)
                    store["uploaded_size"] += len(chunk)
                    buffer = buffer[chunk_size:]

            if buffer:
                end = start + len(buffer) - 1
                put_headers = {
                    "Content-Range": f"bytes {start}-{end}/{downloader.size_bytes}",
                    "Authorization": f"Bearer {self.creds.token}",
                }
                file_id = await self.upload_chunk(drive_location, put_headers, buffer)
                start = end + 1
                store["uploaded_size"] = start
                buffer = b""

        store["done"] = True
        return file_id

    async def _upload_from_telegram(
        self, media_message: Message, message_to_edit: Message = None, folder_id: str = None
    ):
        media = get_tg_media_details(media_message)

        store = self._progress_store[message_to_edit.task_id]
        store["size"] = getattr(media, "file_size", 0)
        store["done"] = False
        store["uploaded_size"] = 0
        store["edit_task"] = asyncio.create_task(
            self.progress_worker(store, message_to_edit), name="tg_drive_up_prog"
        )

        start = 0
        drive_location = await self.create_file(getattr(media, "file_name"), folder_id)
        file_id = None
        # noinspection PyTypeChecker
        async for chunk in message_to_edit._client.stream_media(message=media_message):
            end = start + len(chunk) - 1
            headers = {
                "Content-Range": f"bytes {start}-{end}/{getattr(media, 'file_size', 0)}",
                "Authorization": f"Bearer {self.creds.token}",
            }
            file_id = await self.upload_chunk(drive_location, headers, chunk)
            start = end + 1
            store["uploaded_size"] = end + 1

        return file_id

    @staticmethod
    async def progress_worker(store: dict, message: Message):
        if not isinstance(message, Message):
            return

        while not store["done"]:
            await progress(
                current_size=store["uploaded_size"],
                total_size=store["size"] or 1,
                response=message,
                action_str="Enviando para o Drive...",
            )
            await asyncio.sleep(5)


drive = Drive()


async def init_task():
    await drive.async_init()


@BOT.add_cmd("gsetup")
async def gdrive_creds_setup(bot: BOT, message: Message):
    """
    CMD: GSETUP
    INFO: Gere e salve o arquivo de credenciais OAuth no bot.
    USO: .gsetup {responda ao arquivo credentials.json}
    """

    try:
        assert message.replied.document.file_name == "credentials.json"
    except (AssertionError, AttributeError):
        await message.reply("Arquivo credentials.json não encontrado.")
        return

    try:
        cred_file = await message.replied.download(in_memory=True)
        cred_file.seek(0)
        flow = InstalledAppFlow.from_client_config(
            json.load(cred_file),
            ["https://www.googleapis.com/auth/drive"],
        )
        flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
        auth_url, state = flow.authorization_url(prompt="consent")

        auth_message = await message.reply(
            f"Acesse esta URL e autorize:\n{auth_url}\n\nResponda esta mensagem com o código em até 30 segundos.",
        )
        code_message = await auth_message.get_response(
            from_user=message.from_user.id, reply_to_message_id=auth_message.id, timeout=30
        )

        await auth_message.delete()

        if not code_message:
            await message.reply("Tempo expirado.")
            return

        await code_message.delete()
        flow.fetch_token(code=code_message.text)
        await DB.add_data({"_id": "drive_creds", "creds": json.loads(flow.credentials.to_json())})
        await drive.set_creds()
        await message.reply("Credenciais salvas!")
    except Exception as e:
        await message.reply(str(e))


@BOT.add_cmd("agcreds")
async def set_drive_creds(bot: BOT, message: Message):
    """
    CMD: AGCREDS
    INFO: Adicione credenciais OAuth já geradas ao bot.
    USO: .agcreds {json das credenciais}
    """
    creds = message.input.strip()

    if not creds:
        await message.reply("Informe as credenciais!")
        return

    try:
        creds_json = json.loads(creds)
        creds = Credentials.from_authorized_user_info(info=creds_json)

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        await DB.add_data({"_id": "drive_creds", "creds": json.loads(creds.to_json())})
        await drive.set_creds()
        await message.reply("Credenciais adicionadas!")
    except Exception as e:
        await message.reply(str(e))


@BOT.add_cmd("rgcreds")
async def remove_drive_creds(bot: BOT, message: Message):
    response = await message.reply(
        "Tem certeza que deseja deletar as credenciais do Drive?\nresponda com y para confirmar"
    )

    resp = await response.get_response(from_user=message.from_user.id)
    if not (resp and resp.text in ("y", "Y")):
        await response.edit("Cancelado!")
        return

    drive.is_authenticated = False
    await DB.delete_data({"_id": "drive_creds"})
    await response.edit("Credenciais deletadas com sucesso!")


@BOT.add_cmd("gls")
@drive.ensure_creds
async def list_drive(bot: BOT, message: Message):
    """
    CMD: GLS
    INFO: Lista arquivos/pastas do Drive
    FLAGS:
        -f: listar apenas arquivos
        -d: listar apenas pastas
        -id: pesquisar por id da pasta
        -l: limitar número de resultados (padrão 10)

    USO:
        .gls [-f|-d]
        .gls [-f|-d] texto (lista arquivos/pastas que combinam)
        .gls -id <folder id>
        .gls [-f|-d] -l 20 (lista 20 resultados)
        .gls -l 20 texto (tenta listar 20 resultados com o texto)
    """
    response = await message.reply("Listando...")
    flags = message.flags
    filtered_input_chunks = message.filtered_input.split(maxsplit=1)

    kwargs = {
        "_id": False,
        "limit": 10,
        "folder_only": False,
        "file_only": False,
        "search_param": None,
    }

    # Buscar por ID
    if "-id" in flags:
        kwargs["_id"] = True
    # listar pastas
    if "-d" in flags:
        kwargs["folder_only"] = True
    # listar arquivos
    if "-f" in flags:
        kwargs["file_only"] = True

    # limitar número de resultados
    if "-l" in flags:
        kwargs["limit"] = int(filtered_input_chunks[0])
        # buscar arquivos/pastas específicos
        if len(filtered_input_chunks) == 2:
            kwargs["search_param"] = filtered_input_chunks[1]
    else:
        # buscar arquivos/pastas específicos
        kwargs["search_param"] = message.filtered_input.strip() or None

    remote_files = await drive.list_contents(**kwargs)

    if not remote_files:
        await response.edit("Nenhum resultado encontrado.")
        return

    folders = []
    files = [""]
    shortcuts = [""]

    for file in remote_files:
        url = drive.URL_TEMPLATE.format(media_id=file["id"])
        mime = file["mimeType"]
        if mime == drive.FOLDER_MIME:
            folders.append(f"📁 <a href={url}>{file['name']}</a>")
        elif mime == drive.SHORTCUT_MIME:
            shortcut_details = file.get("shortcutDetails", {})
            target_id = shortcut_details.get("targetId")
            if target_id:
                url = drive.URL_TEMPLATE.format(media_id=target_id)
            shortcuts.append(f"🔗 <a href={url}>{file['name']}</a>")
        else:
            files.append(f"📄 <a href={url}>{file['name']}</a>")

    list_str = "Resultados:\n\n" + "\n".join(folders + shortcuts + files)

    await response.edit(list_str, parse_mode=ParseMode.HTML)


@BOT.add_cmd(cmd="gup")
@drive.ensure_creds
async def upload_to_drive(bot: BOT, message: Message):
    """
    CMD: GUP
    INFO: Envia arquivo para o Drive
    FLAGS:
        -id: id da pasta
        -e: se a url é codificada
    USO:
        .gup [responda uma mídia | url]
        .gup -id <folder id> [responda uma mídia | url]
    """
    reply = message.replied
    response = await message.reply("Verificando entrada...")

    if reply and reply.media:
        folder_id = message.filtered_input if "-id" in message.flags else None
        upload_coro = drive.upload_from_telegram(reply, response, folder_id=folder_id)

    elif message.filtered_input.startswith("http"):
        if "-id" in message.flags:
            folder_id, file_url = message.filtered_input.split(maxsplit=1)
        else:
            folder_id = None
            file_url = message.filtered_input

        upload_coro = drive.upload_from_url(
            file_url=file_url,
            is_encoded="-e" in message.flags,
            folder_id=folder_id,
            message_to_edit=response,
        )

    else:
        await response.edit("Entrada inválida!")
        return

    await response.edit(await upload_coro)
