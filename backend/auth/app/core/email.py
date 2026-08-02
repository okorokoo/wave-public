from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from config import settings


async def send_verification_email(to_email: str, token: str) -> None:
    link = f"{settings.BASE_URL}/auth/v1/verify-email?token={token}"

    message = MIMEMultipart("alternative")
    message["Subject"] = "Подтверждение email — Wave"
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email

    message.attach(MIMEText(
        f"Подтвердите email, перейдя по ссылке:\n{link}\n\nСсылка действительна 24 часа.",
        "plain"
    ))
    message.attach(MIMEText(
        f"<p>Подтвердите email, перейдя по ссылке:</p>"
        f'<p><a href="{link}">{link}</a></p>'
        f"<p>Ссылка действительна 24 часа.</p>",
        "html"
    ))

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
    )
