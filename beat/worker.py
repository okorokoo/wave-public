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

DATABASE_URL = settings.database_url
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

RABBITMQ_URL = settings.rabbitmq_url
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
        return DEFAULT_VOICE_TAG, None  # дефолтный не удаляем

    logger.warning("No voice tag found, preview will have no watermark")
    return None, None


async def process_audio(task_data: dict):
    beat_id = task_data["beat_id"]
    full_audio_url = task_data["full_audio_url"]
    voice_tag_key = task_data.get("voice_tag_key")

    local_input = f"temp_in_{beat_id}"
    local_output = f"temp_out_{beat_id}.mp3"
    local_tag_to_cleanup = None

    s3 = S3Storage()

    try:
        logger.info("Processing beat %s", beat_id)

        # 1. Скачиваем оригинал из S3
        async with s3._get_client() as client:
            s3_key = full_audio_url.replace(f"{s3.endpoint_url}/{s3.bucket_name}/", "")
            response = await client.get_object(Bucket=s3.bucket_name, Key=s3_key)
            audio_bytes = await response["Body"].read()
            with open(local_input, "wb") as f:
                f.write(audio_bytes)

        # 2. Определяем войс-тег
        tag_file, local_tag_to_cleanup = await _resolve_voice_tag(s3, voice_tag_key, beat_id)

        # 3. Формируем FFmpeg команду
        if tag_file:
            cmd = [
                "ffmpeg", "-y",
                "-i", local_input,
                "-stream_loop", "-1",
                "-i", tag_file,
                "-filter_complex", "amix=inputs=2:duration=first:dropout_transition=2",
                "-b:a", "192k",
                local_output,
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-i", local_input,
                "-b:a", "192k",
                local_output,
            ]

        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            raise Exception(f"FFmpeg error: {process.stderr.decode('utf-8')}")

        # 4. Загружаем превью в S3
        s3_folder = s3_key.rsplit("/", 1)[0]
        preview_s3_key = f"{s3_folder}/preview_{beat_id}.mp3"
        async with s3._get_client() as client:
            with open(local_output, "rb") as f:
                await client.put_object(
                    Bucket=s3.bucket_name,
                    Key=preview_s3_key,
                    Body=f.read(),
                    ContentType="audio/mpeg"
                )

        # 5. Обновляем БД
        async with async_session() as session:
            async with session.begin():
                beat = await session.get(Beat, uuid.UUID(beat_id))
                if beat:
                    beat.audio_preview_url = preview_s3_key
                    beat.is_processed = True
                    session.add(beat)
                await session.commit()

        logger.info("Beat %s processed successfully", beat_id)

    except Exception as e:
        logger.error("Failed to process beat %s: %s", beat_id, e, exc_info=True)
        raise e
    finally:
        for path in [local_input, local_output, local_tag_to_cleanup]:
            if path and os.path.exists(path):
                os.remove(path)


async def on_message(message: aio_pika.IncomingMessage):
    """Callback-функция при получении нового сообщения из RabbitMQ"""
    async with message.process():  # Автоматически подтверждает (ACK) сообщение при успешном выходе
        task_data = json.loads(message.body.decode("utf-8"))
        await process_audio(task_data)


async def main():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()

    # QOS контролирует, сколько задач воркер может взять одновременно (1 воркер = 1 задача)
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.consume(on_message)

    logger.info("Beat worker started, waiting for tasks on queue '%s'", QUEUE_NAME)
    try:
        await asyncio.Future()  # Работаем бесконечно
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
