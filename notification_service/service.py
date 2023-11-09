import json
from datetime import datetime
from typing import Any, Generic, TypeAlias, TypeVar, assert_never

from bson import ObjectId
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from notification_service.db import (
    Database,
    InvalidParameters,
    Notification,
    NotificationKey,
    NotificationNotFound,
    UserNotFound,
)
from notification_service.smtp import SmtpRequest, SmtpService


class NotificationRequestPayload(BaseModel):
    """A view of the notification which the user sends through the body of the request.

    Attributes:
        user_id: The ID of the user to whom the notification is sent.
            The number of characters must not exceed 24.
        key: Key type, on which the further logic of service actions with this notification depends.
            'registration' - only send an email to a user;
            'new_message' or 'new_post' - only create a record in the database;
            'new_login' - create both an email to a user and a record in the database.
        target_id: The identifier of the target associated with the notification, if any.
            The number of characters must not exceed 24.
        target_email: mail to which the message is sent.
        data: Additional data associated with the notification, if any.
    """

    user_id: str
    key: NotificationKey
    target_id: str | None = None
    target_email: str | None = None
    data: dict[str, Any] | None = None

    @field_validator("user_id")
    def check_user_id_length(cls, user_id: str):
        assert (
            len(user_id) == 24
        ), "user_id is not a valid ObjectId. Must be 24 characters long."
        return user_id

    @field_validator("target_id")
    def check_target_id_length(cls, target_id: str):
        assert (
            len(target_id) == 24
        ), "target_id is not a valid ObjectId. Must be 24 characters long."
        return target_id

    def to_notification(self) -> Notification:
        """Convert a view of notification from a request to the Notification() model."""

        return Notification(
            id=str(ObjectId()),
            timestamp=int(datetime.utcnow().timestamp()),
            is_new=True,
            user_id=self.user_id,
            key=self.key,
            target_id=self.target_id,
            data=self.data,
        )


T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """A view of successful response from the service.

    Attributes:
        success: a boolean value indicating the success of the operation.
        data: an object of type T containing the successful response data,
            or None if there is no data.
    """

    success: bool = True
    data: T | None = None


class FailureResponse(BaseModel):
    """A view of an error response from the service.

    Attributes:
        success: a boolean value indicating that the operation was unsuccessful.
        error: an object of arbitrary type containing information about the error.
    """

    success: bool = False
    error: Any

    def to_http(self, status_code: int) -> JSONResponse:
        """Convert into a JSONResponse instance with the specified status code."""

        return JSONResponse(self.model_dump(), status_code=status_code)


ServiceResponse: TypeAlias = SuccessResponse | FailureResponse


def make_app(db: Database, smtp: SmtpService) -> FastAPI:
    app = FastAPI()

    @app.post("/create", status_code=201)
    async def create_notification(
        payload: NotificationRequestPayload,
    ) -> ServiceResponse:
        """Create a notification. Based on the value of the `key`, the following actions are performed:
            NotificationKey.REGISTRATION - only send this notification to a user through mail service.
            NotificationKey.NEW_MESSAGE - only create a notification in the database.
            NotificationKey.NEW_POST - only create a notification in the database.
            NotificationKey.NEW_LOGIN - create both an email to a user and a record in the database.

        Args:
            payload: A view of the notification
                which the user sends through the body of the request.

        Returns:
            ServiceResponse: successful response to a user with code status 201.
                If response is not successful - return error code.
        """

        match payload.key:
            case NotificationKey.REGISTRATION:
                await smtp.send_email(SmtpRequest(payload.target_email, payload.key))
            case NotificationKey.NEW_MESSAGE:
                await db.save_notification(payload.to_notification())
            case NotificationKey.NEW_POST:
                await db.save_notification(payload.to_notification())
            case NotificationKey.NEW_LOGIN:
                await db.save_notification(payload.to_notification())
                await smtp.send_email(SmtpRequest(payload.target_email, payload.key))
            case _ as unreachable:
                assert_never(unreachable)

        return SuccessResponse()

    @app.post("/read", status_code=200)
    async def read_notification(user_id: str, notification_id: str) -> ServiceResponse:
        """Read a notification knowing its user_id and notification_id,
        change its status to `is_new = False` and update it in the database.

        Args:
            user_id: ID of the user to whom the notification belongs.
            notification_id: specific notification ID.

        Returns:
            ServiceResponse: if response is successful, return code 200.
                If it is not - code 404 (the user or the notification is not found).
        """

        notification = await db.get_notification(user_id, notification_id)
        if notification.is_new:
            notification.is_new = False
            await db.save_notification(notification)
        return SuccessResponse()

    @app.get("/list", status_code=200)
    async def get_notification_list(
        user_id: str, skip: int, limit: int
    ) -> ServiceResponse:
        """Get a list of notifications by knowing the ID of the user to whom the notifications belong.

        Args:
            user_id: ID of the user to whom the notification belongs.
            skip: the number of notifications that can be skipped.
            limit: the maximum number of notifications that should be returned.

        Returns:
            ServiceResponse: If the response is successful, code 200 is returned with a list of desired notifications.
                If the response is unsuccessful: return code 400 when parameteres like `skip` or `limit` is invalid.
                    code 404 - the user is not found.
        """

        list_notifications = await db.get_notifications(user_id, skip, limit)
        return SuccessResponse(data=list_notifications)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return FailureResponse(error=str(exc)).to_http(400)

    @app.exception_handler(Exception)
    async def unknown_error_handler(request, exc):
        return FailureResponse(error="Internal Server Error").to_http(500)

    @app.exception_handler(UserNotFound)
    async def user_not_found(request, exc):
        return FailureResponse(error="User not found").to_http(404)

    @app.exception_handler(NotificationNotFound)
    async def notifiaction_not_found(request, exc):
        return FailureResponse(error="Notification not found").to_http(404)

    @app.exception_handler(InvalidParameters)
    async def invalid_parameters(request, exc):
        return FailureResponse(error="Invalid parameters").to_http(400)

    return app
