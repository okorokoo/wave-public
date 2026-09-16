import asyncio
import json
import logging
import os
import subprocess
import uuid

import aio_pika
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.logger import setup_logging
from app.core.s3 import S3Storage
from app.models.models import Beat
from config import settings

setup_logging(debug=settings.DEBUG)
logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

QUEUE_NAME = "beat_processing_queue"
DEFAULT_VOICE_TAG = "assets/voice_tag.mp3"


async def _resolve_voice_tag(s3: S3Storage, voice_tag_key: str | None, beat_id: str) -> tuple[str | None, str | None]:
    """Возвращает (путь к файлу тега, путь для удаления после обработки)."""
    if voice_tag_key:
        local_tag = f"temp_tag_{beat_id}.mp3"
        async with s3._get_client() as client:
            response = await client.get_object(Bucket=s3.bucket_name, Key=voice_tag_key)
            tag_bytes = await response["Body"].read()
        with open(local_tag, "wb") as f:
            f.write(tag_bytes)
        logger.info("Using author voice tag: %s", voice_tag_key)
        return local_tag, local_tag

    if os.path.exists(DEFAULT_VOICE_TAG):
        logger.info("Using default platform voice tag")
        return DEFAULT_VOICE_TAG, None

    logger.warning("No voice tag found, preview will have no watermark")
    return None, None


def _build_ffmpeg_cmd(
    local_input: str,
    tag_file: str | None,
    local_preview: str,
    local_mp3: str,
) -> list[str]:
    """Один вызов FFmpeg → preview (192k + тег) и full MP3 (320k)."""
    if tag_file:
        return [
            "ffmpeg", "-y",
            "-i", local_input,
            "-stream_loop", "-1", "-i", tag_file,
            "-filter_complex", "[0][1]amix=inputs=2:duration=first:dropout_transition=2[mixed]",
            "-map", "[mixed]", "-b:a", "192k", local_preview,
            "-map", "0:a",    "-b:a", "320k", local_mp3,
        ]
    return [
        "ffmpeg", "-y",
        "-i", local_input,
        "-map", "0:a", "-b:a", "192k", local_preview,
        "-map", "0:a", "-b:a", "320k", local_mp3,
    ]


async def _run_ffmpeg(cmd: list[str]) -> None:
    result = await asyncio.to_thread(
        subprocess.run, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr.decode('utf-8', errors='replace')}")


async def _put_object(client, bucket: str, key: str, path: str, cache_control: str | None = None) -> None:
    with open(path, "rb") as f:
        extra = {"CacheControl": cache_control} if cache_control else {}
        await client.put_object(Bucket=bucket, Key=key, Body=f.read(), ContentType="audio/mpeg", **extra)


async def process_audio(task_data: dict) -> None:
    beat_id: str = task_data["beat_id"]
    full_audio_url: str = task_data["full_audio_url"]
    voice_tag_key: str | None = task_data.get("voice_tag_key")

    local_input = f"temp_in_{beat_id}"
    local_preview = f"temp_preview_{beat_id}.mp3"
    local_mp3 = f"temp_mp3_{beat_id}.mp3"
    local_tag_to_cleanup: str | None = None
    uploaded_keys: list[str] = []

    s3 = S3Storage()
    s3_key = s3._normalize_key(full_audio_url)

    try:
        logger.info("Processing beat %s", beat_id)

        # 1. Параллельно: скачиваем WAV и войс-тег
        async def _download_wav() -> None:
            async with s3._get_client() as client:
                response = await client.get_object(Bucket=s3.bucket_name, Key=s3_key)
                audio_bytes = await response["Body"].read()
            with open(local_input, "wb") as f:
                f.write(audio_bytes)

        (_, (tag_file, local_tag_to_cleanup)) = await asyncio.gather(
            _download_wav(),
            _resolve_voice_tag(s3, voice_tag_key, beat_id),
        )

        # 2. Один проход FFmpeg → два файла
        cmd = _build_ffmpeg_cmd(local_input, tag_file, local_preview, local_mp3)
        await _run_ffmpeg(cmd)

        # 3. Параллельная загрузка обоих MP3 в S3
        s3_folder = s3_key.rsplit("/", 1)[0]
        preview_key = f"{s3_folder}/preview_{beat_id}.mp3"
        mp3_key = f"{s3_folder}/mp3_{beat_id}.mp3"

        async with s3._get_client() as client:
            await asyncio.gather(
                _put_object(
                    client, s3.bucket_name, preview_key, local_preview,
                    cache_control="public, max-age=31536000, immutable",
                ),
                _put_object(client, s3.bucket_name, mp3_key, local_mp3),
            )
        uploaded_keys.extend([preview_key, mp3_key])

        # 4. Обновляем БД
        async with async_session() as session:
            async with session.begin():
                beat = await session.get(Beat, uuid.UUID(beat_id))
                if beat:
                    beat.audio_preview_url = preview_key
                    beat.audio_mp3_url = mp3_key
                    beat.is_processed = True

        logger.info("Beat %s processed successfully", beat_id)

    except Exception as e:
        logger.error("Failed to process beat %s: %s", beat_id, e, exc_info=True)
        if uploaded_keys:
            try:
                await s3.delete_objects(uploaded_keys)
                logger.info("Rolled back %d S3 objects for beat %s", len(uploaded_keys), beat_id)
            except Exception as cleanup_err:
                logger.warning("S3 rollback failed for beat %s: %s", beat_id, cleanup_err)
        raise

    finally:
        for path in [local_input, local_preview, local_mp3, local_tag_to_cleanup]:
            if path and os.path.exists(path):
                os.remove(path)


async def on_message(message: aio_pika.IncomingMessage) -> None:
    async with message.process():
        task_data = json.loads(message.body.decode("utf-8"))
        await process_audio(task_data)


async def main() -> None:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.consume(on_message)

    logger.info("Beat worker started, waiting for tasks on queue '%s'", QUEUE_NAME)
    try:
        await asyncio.Future()
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
