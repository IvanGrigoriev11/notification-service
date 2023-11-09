from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import aiosmtplib


@dataclass(frozen=True)
class SmtpRequest:
    """The model of the smtp request to the service.

    Attributes:
        to (str): to which user the message is sent
        message (str): message sent to user
    """

    to: str
    message: str


class SmtpService(Protocol):
    """Interface of mail service."""

    async def send_email(self, request: SmtpRequest) -> None:
        """Send email to user via mail service."""


@dataclass(frozen=True)
class Smtp(SmtpService):
    """Smtp mail implementation."""

    host: str
    port: int
    login: str
    password: str
    email: str
    name: str

    async def send_email(self, request: SmtpRequest) -> None:
        """Send email via smtp service."""

        message = EmailMessage()
        message.set_content(request.message)
        message["From"] = f"{self.name} <{self.email}>"
        message["To"] = request.to

        async with aiosmtplib.SMTP(self.host, self.port) as server:
            await server.send_message(message)
