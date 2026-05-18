from app.core.rabbitmq import rabbit_client


async def publish_user_created(user_id: str):
    message_body = {"user_id": user_id}

    # Отправляем в очередь 'user_created'
    await rabbit_client.publish(
        routing_key="user_created",
        body=message_body
    )
