from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.models.models import EmailOutbox
from config import settings


def make_verification_email(to_email: str, token: str) -> EmailOutbox:
    link = f"{settings.BASE_URL}/verify-email?token={token}"
    return EmailOutbox(
        to_email=to_email,
        subject="Подтверждение email — Wave",
        body_plain=f"Подтвердите email, перейдя по ссылке:\n{link}\n\nСсылка действительна 24 часа.",
        body_html=(
            f"<p>Подтвердите email, перейдя по ссылке:</p>"
            f'<p><a href="{link}">{link}</a></p>'
            f"<p>Ссылка действительна 24 часа.</p>"
        ),
    )


async def send_email(to_email: str, subject: str, body_plain: str, body_html: str) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email
    message.attach(MIMEText(body_plain, "plain"))
    message.attach(MIMEText(body_html, "html"))

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
    )