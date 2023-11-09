import os

import uvicorn

from notification_service.db import MongoDatabase
from notification_service.service import make_app
from notification_service.smtp import Smtp

db = MongoDatabase(os.environ["DB_URI"])
smtp = Smtp(
    host=os.environ["SMTP_HOST"],
    port=int(os.environ["SMTP_PORT"]),
    login=os.environ["SMTP_LOGIN"],
    password=os.environ["SMTP_PASSWORD"],
    email=os.environ["SMTP_EMAIL"],
    name=os.environ["SMTP_NAME"],
)
app = uvicorn.run(make_app(db, smtp), host="0.0.0.0", port=8000)
