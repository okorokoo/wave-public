import aioboto3
from contextlib import asynccontextmanager
from fastapi import UploadFile


class S3Storage:
    def __init__(self):
        # Настройки для локального MinIO
        self.endpoint_url = "http://minio:9000"
        self.access_key = "minioadmin"
        self.secret_key = "minioadminpassword"
        self.bucket_name = "wave-beats"

        # Создаем сессию aioboto3
        self.session = aioboto3.Session()

    @asynccontextmanager
    async def _get_client(self):
        """Контекстный менеджер для безопасного открытия/закрытия сессии"""
        async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
        ) as client:
            yield client

    async def create_bucket_if_not_exists(self):
        """Создает бакет при старте приложения, если его нет"""
        async with self._get_client() as client:
            try:
                await client.head_bucket(Bucket=self.bucket_name)
            except Exception:
                await client.create_bucket(Bucket=self.bucket_name)
                print(f"Bucket '{self.bucket_name}' successfully created!")

    async def upload_file(self, file: UploadFile, s3_path: str) -> str:
        """Загружает файл в S3, возвращает S3-ключ (путь внутри бакета)."""
        async with self._get_client() as client:
            file_content = await file.read()
            await client.put_object(
                Bucket=self.bucket_name,
                Key=s3_path,
                Body=file_content,
                ContentType=file.content_type
            )
        return s3_path

    def _normalize_key(self, url_or_key: str) -> str:
        """Вырезает prefix URL если в БД хранится полный URL вместо ключа."""
        prefix = f"{self.endpoint_url}/{self.bucket_name}/"
        if url_or_key.startswith(prefix):
            return url_or_key[len(prefix):]
        return url_or_key

    async def generate_presigned_url(self, s3_key: str, expires_in: int = 3600) -> str:
        """Генерирует временную ссылку на объект в S3 (по умолчанию — 1 час)."""
        key = self._normalize_key(s3_key)
        async with self._get_client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
