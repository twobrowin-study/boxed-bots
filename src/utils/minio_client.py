import asyncio
from dataclasses import dataclass
from io import BytesIO

import filetype
from filetype.types import TYPES as FILE_TYPES
from filetype.types.image import Jpeg
from loguru import logger
from minio import Minio, S3Error
from PIL import Image
from telegram import Document, PhotoSize
from urllib3 import BaseHTTPResponse


@dataclass
class ThumbnailableFileType:
    content_type: str
    extension: str
    thumbnailable: bool


class MinIOClient:
    """
    Обёртка для удобного асинхронного взаимодействия с MINIO
    """

    def __init__(self, host: str, secure: bool, access_key: str, secret_key: str) -> None:  # noqa: FBT001
        self.host = host
        self._client = Minio(self.host, access_key=access_key, secret_key=secret_key, secure=secure)
        self._semaphore = asyncio.Semaphore(50)

    async def _put_object(self, bucket: str, filename: str, bio: BytesIO, content_type: str) -> None:
        """
        Внутренняя функция для асинхроанного помещения файла в заданный бакет
        """

        def _put_object_sync() -> None:
            bio.seek(0)
            self._client.put_object(
                bucket_name=bucket,
                object_name=filename,
                data=bio,
                length=bio.getbuffer().nbytes,
                content_type=content_type,
            )

        await asyncio.get_event_loop().run_in_executor(None, _put_object_sync)

    async def _upload(self, bucket: str, filename: str, bio: BytesIO, content_type: str) -> None:
        """Асинхронное помещение файла в бакет"""
        async with self._semaphore:
            logger.debug(f"Uploading {filename} to MinIO into bukcket {bucket}")
            await self._put_object(bucket, filename, bio, content_type)
        logger.debug(f"Done uploading {filename} to MinIO into bukcket {bucket}")

    async def upload_guessed(self, bucket: str, filename: str, bio: BytesIO) -> None:
        """Поместить файл в бакет с автоматически определённым типом контента"""
        try:
            content_type = filetype.guess_mime(bio)
        except TypeError:
            content_type = None
        bio.seek(0)
        await self._upload(
            bucket=bucket,
            filename=filename,
            bio=bio,
            content_type=content_type or "application/octet-stream",
        )

    def get_thumbnailable_file_type(self, telegram_object: PhotoSize | Document) -> ThumbnailableFileType:
        if type(telegram_object) is PhotoSize:
            file_type = Jpeg()
            return ThumbnailableFileType(
                content_type=file_type.mime,
                extension=file_type.extension,
                thumbnailable=True,
            )

        if type(telegram_object) is Document:
            for file_type in FILE_TYPES:
                if file_type.mime == telegram_object.mime_type:
                    thumbnailable = file_type.mime in [
                        "image/png",
                        "image/jpg",
                        "image/jpeg",
                        "image/tiff",
                        "image/bmp",
                        "image/gif",
                    ]
                    return ThumbnailableFileType(
                        content_type=file_type.mime,
                        extension=file_type.extension,
                        thumbnailable=thumbnailable,
                    )

        return ThumbnailableFileType(
            content_type="application/octet-stream",
            extension="bin",
            thumbnailable=False,
        )

    def get_thumbnail_filename(self, filename_wo_extension: str, thumbnailable_file_type: ThumbnailableFileType) -> str:
        if thumbnailable_file_type.thumbnailable:
            return f"{filename_wo_extension}.thumbnail.{thumbnailable_file_type.extension}"
        return f"{filename_wo_extension}.{thumbnailable_file_type.extension}"

    def get_original_filename(self, thumbnail_filename: str) -> str:
        return thumbnail_filename.replace(".thumbnail", "")

    async def upload_original_and_thumbnail(
        self,
        bucket: str,
        thumbnail_filename: str,
        original_bio: BytesIO,
        thumbnailable_file_type: ThumbnailableFileType,
    ) -> None:
        """Асинхронное помещение файла в бакет и вычисление эскиза если это доступно"""
        original_bio.seek(0)
        filename = self.get_original_filename(thumbnail_filename)
        await self._upload(bucket, filename, original_bio, thumbnailable_file_type.content_type)

        if not thumbnailable_file_type.thumbnailable:
            return

        image_format = thumbnailable_file_type.content_type.removeprefix("image/").upper()

        original_bio.seek(0)
        with Image.open(original_bio, formats=[image_format]) as image:
            image.thumbnail((256, 256))

            thumbnail_bio = BytesIO()
            image.save(thumbnail_bio, format=image_format)

            await self._upload(bucket, thumbnail_filename, thumbnail_bio, thumbnailable_file_type.content_type)

    async def download(self, bucket: str, filename: str) -> tuple[BytesIO | None, str]:
        """Асинхронная загрузка файла из бакета"""
        logger.debug(f"Downloading {filename} from MinIO bucket {bucket}")

        def _get_object() -> BaseHTTPResponse:
            return self._client.get_object(bucket, filename)

        try:
            response = await asyncio.get_event_loop().run_in_executor(None, _get_object)
            logger.debug(f"Done downloading {filename} from MinIO bucket {bucket}")
            file_bytes = BytesIO(response.read())
            content_type = response.getheader("content-type")
        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.debug(f"File {filename} not found in MinIO bucket {bucket}")
                file_bytes = None
                content_type = None
            else:
                raise
        else:
            response.close()
            response.release_conn()

        if not content_type:
            content_type = "application/octet-stream"

        return file_bytes, content_type

    async def create_bucket(self, bucket: str) -> None:
        """
        Асинхронное создание бакета с доступом ко всем файлам по прямым ссылкам без авторизации
        """
        logger.debug(f"Creating MinIO bucket {bucket}")

        def _create_bucket() -> None:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)

        await asyncio.get_event_loop().run_in_executor(None, _create_bucket)
        logger.success(f"Created MinIO bucket {bucket} or updated policyes")
