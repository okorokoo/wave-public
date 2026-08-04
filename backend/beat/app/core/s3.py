import logging
from contextlib import asynccontextmanager

import aioboto3
from fastapi import UploadFile

from config import settings

logger = logging.getLogger(__name__)


class S3Storage:
    def __init__(self):
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.access_key = settings.S3_ACCESS_KEY
        self.secret_key = settings.S3_SECRET_KEY
        self.bucket_name = settings.S3_BUCKET_NAME
        self.session = aioboto3.Session()

    @asynccontextmanager
    async def _get_client(self):
        async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
        ) as client:
            yield client

    async def create_bucket_if_not_exists(self):
        async with self._get_client() as client:
            try:
                await client.head_bucket(Bucket=self.bucket_name)
            except Exception:
                await client.create_bucket(Bucket=self.bucket_name)
                logger.info("S3 bucket '%s' created", self.bucket_name)

    async def check_connection(self) -> None:
        async with self._get_client() as client:
            await client.head_bucket(Bucket=self.bucket_name)

    async def upload_file(self, file: UploadFile, s3_path: str, content_type: str | None = None) -> str:
        async with self._get_client() as client:
            file_content = await file.read()
            await client.put_object(
                Bucket=self.bucket_name,
                Key=s3_path,
                Body=file_content,
                ContentType=content_type or file.content_type or 'application/octet-stream',
            )
        return s3_path

    def _normalize_key(self, url_or_key: str) -> str:
        prefix = f"{self.endpoint_url}/{self.bucket_name}/"
        if url_or_key.startswith(prefix):
            return url_or_key[len(prefix):]
        return url_or_key

    async def generate_presigned_url(self, s3_key: str, expires_in: int | None = None) -> str:
        key = self._normalize_key(s3_key)
        ttl = expires_in or settings.S3_PRESIGNED_URL_EXPIRE_SECONDS
        async with self._get_client() as client:
            url = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=ttl,
            )
        if settings.S3_PUBLIC_ENDPOINT_URL != self.endpoint_url:
            url = url.replace(self.endpoint_url, settings.S3_PUBLIC_ENDPOINT_URL, 1)
        return url

    async def delete_objects(self, keys: list[str]) -> None:
        normalized_keys = [
            self._normalize_key(key)
            for key in keys
            if key
        ]
        if not normalized_keys:
            return

        async with self._get_client() as client:
            await client.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": [{"Key": key} for key in normalized_keys]},
            )
