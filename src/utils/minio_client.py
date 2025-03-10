import asyncio
from io import BytesIO

from loguru import logger
from minio import Minio, S3Error
from PIL import Image
from urllib3 import BaseHTTPResponse


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

    async def upload(self, bucket: str, filename: str, bio: BytesIO, content_type: str) -> None:
        """
        Асинхронное помещение файла в бакет
        """
        async with self._semaphore:
            logger.debug(f"Uploading {filename} to MinIO into bukcket {bucket}")
            await self._put_object(bucket, filename, bio, content_type)
        logger.debug(f"Done uploading {filename} to MinIO into bukcket {bucket}")

    async def upload_w_thumbnail(self, bucket: str, thumbnail_filename: str, bio: BytesIO, content_type: str) -> None:
        """
        Асинхронное помещение файла в бакет

        Если файл является изображением - вычисляется также уменьшенная версия и помещается рядом
        """
        bio.seek(0)
        full_filename = thumbnail_filename.replace(".thumbnail", "")
        await self.upload(bucket, full_filename, bio, content_type)

        if not content_type.startswith("image"):
            return

        image_format = content_type.removeprefix("image/").upper()

        bio.seek(0)
        with Image.open(bio, formats=[image_format]) as image:
            image.thumbnail((256, 256))

            thumbnail_bio = BytesIO()
            image.save(thumbnail_bio, format=image_format)

            await self.upload(bucket, thumbnail_filename, thumbnail_bio, content_type)

    async def download(self, bucket: str, filename: str) -> tuple[BytesIO | None, str]:
        """
        Асинхронная загрузка файла из бакета
        """
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
