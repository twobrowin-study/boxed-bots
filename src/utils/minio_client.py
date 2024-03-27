import asyncio
from io import BytesIO
from minio import Minio, S3Error
from loguru import logger
import json
import filetype

class MinIOClient:
    """
    Обёртка для удобного асинхронного взаимодействия с MINIO
    """

    def __init__(self, access_key: str, secret_key: str) -> None:
        self._client = Minio('localhost:9000',
            access_key=access_key,
            secret_key=secret_key,
            secure=False
        )
        self._semaphore = asyncio.Semaphore(50)

    def _gues_content_type(self, bio: BytesIO) -> str:
        """
        Попробовать угадать MIME тип файла или разочароваться и вернуть application/octet-stream
        """
        bio.seek(0)
        try:
            return filetype.guess_mime(bio)
        except Exception:
            return 'application/octet-stream'

    async def _put_object(self, bucket: str, filename: str, bio: BytesIO) -> None:
        """
        Внутренняя функция для асинхроанного помещения файла в заданный бакет
        """
        def _put_object_sync():
            content_type = self._gues_content_type(bio)
            bio.seek(0)
            self._client.put_object(
                bucket_name=bucket,
                object_name=filename,
                data=bio,
                length=bio.getbuffer().nbytes,
                content_type=content_type
            )
        await asyncio.get_event_loop().run_in_executor(None, _put_object_sync)

    async def upload(self, bucket: str, filename: str, bio: BytesIO) -> None:
        """
        Асинхронное помещение файла в бакет
        """
        async with self._semaphore:
            logger.info(f"Uploading {filename} to MinIO into bukcket {bucket}")
            await self._put_object(bucket, filename, bio)
        logger.success(f"Done uploading {filename} to MinIO into bukcket {bucket}")

    async def download(self, bucket: str, filename: str) -> BytesIO | None:
        """
        Асинхронная загрузка файла из бакета
        """
        logger.info(f"Downloading {filename} from MinIO bucket {bucket}")

        def _get_object():
            return self._client.get_object(bucket, filename)

        try:
            response = await asyncio.get_event_loop().run_in_executor(None, _get_object)
            logger.success(f"Done downloading {filename} from MinIO {bucket}")
            file_bytes = BytesIO(response.read())
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.info(f"File {filename} not found in MinIO {bucket}")
                file_bytes = None
            else:
                raise e
        else:
            response.close()
            response.release_conn()

        return file_bytes
    
    async def create_bucket(self, bucket: str) -> None:
        """
        Асинхронное создание бакета с доступом ко всем файлам по прямым ссылкам без авторизации
        """
        logger.info(f"Creating MinIO bucket {bucket}")
        def _create_bucket():
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{bucket}/*",
                    },
                ],
            }
            self._client.set_bucket_policy(bucket, json.dumps(policy))
        await asyncio.get_event_loop().run_in_executor(None, _create_bucket)
        logger.success(f"Created MinIO bucket {bucket} or updated policyes")
