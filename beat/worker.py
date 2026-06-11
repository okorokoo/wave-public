import asyncio
import json
import os
import subprocess
import uuid

import aio_pika
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.s3 import S3Storage
from app.models.models import Beat
from config import settings

DATABASE_URL = settings.database_url
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

RABBITMQ_URL = settings.rabbitmq_url
QUEUE_NAME = "beat_processing_queue"


async def process_audio(task_data: dict):
    beat_id = task_data["beat_id"]
    full_audio_url = task_data["full_audio_url"]
    filename = task_data["filename"]

    # Локальные временные файлы для обработки
    local_input = f"temp_in_{beat_id}_{filename}"
    local_output = f"temp_out_{beat_id}.mp3"
    tag_file = "assets/voice_tag.mp3"  # Положи сюда свой аудио-тег

    s3 = S3Storage()

    try:
        print(f" [--->] Начинаем обработку бита {beat_id}")

        # 1. Скачиваем оригинал из S3 во временный файл
        # Для простоты можно использовать библиотеку httpx или boto3 клиент
        async with s3._get_client() as client:
            s3_key = full_audio_url.replace(f"{s3.endpoint_url}/{s3.bucket_name}/", "")
            response = await client.get_object(Bucket=s3.bucket_name, Key=s3_key)
            audio_bytes = await response["Body"].read()
            with open(local_input, "wb") as f:
                f.write(audio_bytes)

        # 2. Проверяем наличие тега, если нет - создаем тишину или берем дефолтный
        if not os.path.exists(tag_file):
            os.makedirs("assets", exist_ok=True)
            # Если тега нет, воркер просто скопирует файл (для теста)
            print(" [!] Файл тега не найден в assets/voice_tag.mp3, делаем копию без защиты")
            cmd = f"ffmpeg -y -i {local_input} -b:a 192k {local_output}"
        else:
            # 3. Магия FFmpeg: наложение зацикленного вотермарка
            cmd = (
                f"ffmpeg -y -i {local_input} -stream_loop -1 -i {tag_file} "
                f'-filter_complex "amix=inputs=2:duration=first:dropout_transition=2" '
                f"-b:a 192k {local_output}"
            )

        # Запускаем ffmpeg в подпроцессе
        process = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            raise Exception(f"FFmpeg error: {process.stderr.decode('utf-8')}")

        # 4. Загружаем защищенный превью-файл обратно в S3
        s3_folder = s3_key.rsplit("/", 1)[0]  # beats/{beat_folder_id}
        preview_s3_key = f"{s3_folder}/preview_{beat_id}.mp3"
        async with s3._get_client() as client:
            with open(local_output, "rb") as f:
                await client.put_object(
                    Bucket=s3.bucket_name,
                    Key=preview_s3_key,
                    Body=f.read(),
                    ContentType="audio/mpeg"
                )

        # 5. Обновляем статус и ключ превью в базе данных PostgreSQL
        async with async_session() as session:
            async with session.begin():
                beat_uuid = uuid.UUID(beat_id)
                beat = await session.get(Beat, beat_uuid)
                if beat:
                    beat.audio_preview_url = preview_s3_key  # храним S3-ключ, не URL
                    beat.is_processed = True
                    session.add(beat)
                await session.commit()

        print(f" [✓] Бит {beat_id} успешно обработан и защищен!")

    except Exception as e:
        print(f" [X] Ошибка при обработке бита {beat_id}: {e}")
        raise e
    finally:
        # Чистим за собой временные файлы
        for file in [local_input, local_output]:
            if os.path.exists(file):
                os.remove(file)


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

    print(" [*] Воркер обработки аудио успешно запущен. Ожидание задач...")
    try:
        await asyncio.Future()  # Работаем бесконечно
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
