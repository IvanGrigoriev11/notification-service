from dataclasses import field
from enum import Enum
from typing import Protocol

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pydantic import BaseModel


class NotificationKey(str, Enum):
    """Type of notification."""

    REGISTRATION = "registration"
    NEW_MESSAGE = "new_message"
    NEW_POST = "new_post"
    NEW_LOGIN = "new_login"


class Notification(BaseModel):
    """A pydantic view of user's notification.

    Attributes:
        id: The unique identifier of the notification.
        timestamp: The time when the notification was created.
        is_new: Indicates if the notification is new or not.
        user_id: The ID of the user to whom the notification is sent.
        key: The key representing the type of notification.
        target_id: The identifier of the target associated with the notification, if any.
        data: Additional data associated with the notification, if any.
    """

    id: str
    timestamp: int
    is_new: bool
    user_id: str
    key: NotificationKey
    target_id: str | None = None
    data: dict | None = None


class User(BaseModel):
    """A view of user's notifications.

    Attributes:
        id: The unique identifier of the user.
        notifications: a pydantic view of user's notification.
    """

    id: str
    notifications: list[Notification] = field(default_factory=list)


class Database(Protocol):
    """Database interface."""

    async def get_notification(
        self, user_id: str, notification_id: str
    ) -> Notification:
        """Retrieve a notification document from the database by user ID and notification ID."""

    async def get_notifications(
        self, user_id: str, skip: int, limit: int
    ) -> list[Notification]:
        """Retrieve a list of notification documents from the database by user ID.
        
        Args:
            user_id: The unique identifier of the user.
            skip: Number of notifications that can be skipped.
            limit: Number of notifications that can be limited.
        """

    async def save_notification(self, notification: Notification):
        """Save the notification to the database."""


class MongoDatabase(Database):
    """MongoDB database implementation."""

    def __init__(
        self,
        uri: str,
        db_name: str = "db",
        collection_name: str = "users",
        notifications_limit: int = 3,
    ):
        self.client = AsyncIOMotorClient(uri)
        self._users: AsyncIOMotorCollection = self.client[db_name][collection_name]
        self._notifications_limit = notifications_limit

    async def get_notification(
        self, user_id: str, notification_id: str
    ) -> Notification:
        result = await self.get_records(user_id)
        for res in result:
            if res["notifications"]["$each"][0]["id"] == notification_id:
                return self.convert_notification(res)

        raise NotificationNotFound()

    async def get_notifications(
        self, user_id: str, skip: int, limit: int
    ) -> list[Notification]:
        notifications_data = await self.get_records(user_id)
        notifications_count = len(notifications_data)

        if notifications_count == 0 or skip >= notifications_count:
            return []

        notifications = [self.convert_notification(note) for note in notifications_data]

        return notifications[skip : min(skip + limit, notifications_count)]

    async def save_notification(self, notification: Notification):
        notifications_data = await self.get_records(notification.user_id)
        notifications = [self.convert_notification(note) for note in notifications_data]

        if notifications:
            for note_from_db in notifications:
                if note_from_db.id == notification.id:
                    await self._users.update_one(
                        {"id": notification.user_id},
                        {
                            "$set": {
                                "notifications": {
                                    "$each": [notification.model_dump()],
                                    "$sort": {"timestamp": -1},
                                    "$slice": self._notifications_limit,
                                }
                            }
                        },
                    )

        else:
            await self._users.insert_one(
                {
                    "id": notification.user_id,
                    "notifications": {
                        "$each": [notification.model_dump()],
                        "$sort": {"timestamp": -1},
                        "$slice": self._notifications_limit,
                    },
                }
            )

    async def get_records(self, user_id: str) -> list:
        """Retrieve records for a specific user ID."""

        user_data = self._users.find({"id": user_id})
        return [notification_data async for notification_data in user_data]

    def convert_notification(self, notification: dict) -> Notification:
        """Convert from the database dict object to Notification() model."""

        notification_id = notification["notifications"]["$each"][0]["id"]
        timestamp = notification["notifications"]["$each"][0]["timestamp"]
        is_new = notification["notifications"]["$each"][0]["is_new"]
        user_id = notification["notifications"]["$each"][0]["user_id"]
        key = notification["notifications"]["$each"][0]["key"]
        target_id = notification["notifications"]["$each"][0]["target_id"]
        data = notification["notifications"]["$each"][0]["data"]
        return Notification(
            id=notification_id,
            timestamp=timestamp,
            is_new=is_new,
            user_id=user_id,
            key=key,
            target_id=target_id,
            data=data,
        )


class DatabaseException(Exception):
    ...


class UserNotFound(DatabaseException):
    ...


class NotificationNotFound(DatabaseException):
    ...


class InvalidParameters(DatabaseException):
    ...
