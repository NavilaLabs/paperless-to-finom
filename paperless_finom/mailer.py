"""Send a document as an email attachment to Finom's import address."""
from __future__ import annotations

import mimetypes
import smtplib
from email.message import EmailMessage


class Mailer:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_addr: str,
        starttls: bool = True,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_addr = from_addr
        self.starttls = starttls

    def send_document(
        self,
        to_addr: str,
        filename: str,
        content: bytes,
        subject: str | None = None,
        body: str | None = None,
    ) -> None:
        msg = EmailMessage()
        msg["From"] = self.from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject or filename
        msg.set_content(body or f"Invoice attached: {filename}")

        ctype, _ = mimetypes.guess_type(filename)
        maintype, _, subtype = (ctype or "application/octet-stream").partition("/")
        msg.add_attachment(
            content, maintype=maintype, subtype=subtype, filename=filename
        )

        with smtplib.SMTP(self.host, self.port, timeout=60) as smtp:
            smtp.ehlo()
            if self.starttls:
                smtp.starttls()
                smtp.ehlo()
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(msg)
