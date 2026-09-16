import json
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

    async def upload_file(
            self,
            file: UploadFile,
            s3_path: str,
            content_type: str | None = None,
            cache_control: str | None = None,
    ) -> str:
        async with self._get_client() as client:
            file_content = await file.read()
            extra = {"CacheControl": cache_control} if cache_control else {}
            await client.put_object(
                Bucket=self.bucket_name,
                Key=s3_path,
                Body=file_content,
                ContentType=content_type or file.content_type or 'application/octet-stream',
                **extra,
            )
        return s3_path

    async def set_public_read_policy(self, prefixes: list[str]) -> None:
        """Разрешает анонимное чтение объектов под заданными префиксами (glob-паттерны).

        Используется для публичного контента (обложки, превью), который отдаётся
        по стабильному URL без подписи — чтобы его мог кэшировать браузер и Cloudflare.
        """
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{self.bucket_name}/{prefix}" for prefix in prefixes],
            }],
        }
        async with self._get_client() as client:
            await client.put_bucket_policy(Bucket=self.bucket_name, Policy=json.dumps(policy))

    def get_public_url(self, s3_key: str) -> str:
        """Стабильный (неподписанный) URL для публичного контента — не меняется между запросами,
        поэтому кэшируется браузером и Cloudflare. Требует set_public_read_policy на нужном префиксе."""
        key = self._normalize_key(s3_key)
        return f"{settings.S3_PUBLIC_ENDPOINT_URL}/{self.bucket_name}/{key}"

    def _normalize_key(self, url_or_key: str) -> str:
        prefix = f"{self.endpoint_url}/{self.bucket_name}/"
        if url_or_key.startswith(prefix):
            return url_or_key[len(prefix):]
        return url_or_key

    async def generate_presigned_url(self, s3_key: str, expires_in: int | None = None) -> str:
        key = self._normalize_key(s3_key)
        ttl = expires_in or settings.S3_PRESIGNED_URL_EXPIRE_SECONDS
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
                ExpiresIn=ttl,
            )
        return url

    async def get_object_info(self, url_or_key: str) -> dict:
        key = self._normalize_key(url_or_key)
        async with self._get_client() as client:
            return await client.head_object(Bucket=self.bucket_name, Key=key)

    async def stream_object(self, url_or_key: str):
        key = self._normalize_key(url_or_key)
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as client:
            response = await client.get_object(Bucket=self.bucket_name, Key=key)
            async with response["Body"] as stream:
                async for chunk in stream.content.iter_chunked(65536):
                    yield chunk

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
