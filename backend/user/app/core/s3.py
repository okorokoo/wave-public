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

    async def upload_file(self, file: UploadFile, s3_path: str) -> str:
        async with self._get_client() as client:
            file_content = await file.read()
            await client.put_object(
                Bucket=self.bucket_name,
                Key=s3_path,
                Body=file_content,
                ContentType=file.content_type,
            )
        return s3_path

    def _normalize_key(self, url_or_key: str) -> str:
        prefix = f"{self.endpoint_url}/{self.bucket_name}/"
        if url_or_key.startswith(prefix):
            return url_or_key[len(prefix) :]
        return url_or_key

    async def generate_presigned_url(self, s3_key: str) -> str:
        key = self._normalize_key(s3_key)
        # Sign with the public endpoint so Host header matches when MinIO validates the signature
        async with self.session.client(
            "s3",
            endpoint_url=settings.S3_PUBLIC_ENDPOINT_URL,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as client:
            url = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRE_SECONDS,
            )
        return url

    async def delete_objects(self, keys: list[str]) -> None:
        normalized = [self._normalize_key(k) for k in keys if k]
        if not normalized:
            return
        async with self._get_client() as client:
            await client.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": [{"Key": k} for k in normalized]},
            )
