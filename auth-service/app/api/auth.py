from fastapi import APIRouter, Cookie, Response

from app.api.dependencies import DBDep, UserDep
from app.core.exceptions import (
    DatabaseNotUnavailableException,
    DatabaseNotUnavailableHTTPException,
    EmailOrPasswordIncorrectException,
    EmailOrPasswordIncorrectHTTPException,
    IncorrectTokenException,
    NoAccessTokenHTTPException,
    RefreshTokenExpiredException,
    RefreshTokenExpiredHTTPException,
    UserAlreadyExistsException,
    UserEmailAlreadyExistsHTTPException,
)
from app.schemas.refresh_tokens import TokenResponse
from app.schemas.users import User, UserRequestAdd
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register_user(db: DBDep, data: UserRequestAdd):
    try:
        new_user = await AuthService(db).register_user(data)
    except UserAlreadyExistsException as ex:
        raise UserEmailAlreadyExistsHTTPException from ex
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex

    return {"user_id": new_user.id}


@router.post("/login", response_model=TokenResponse)
async def login_user(db: DBDep, response: Response, data: UserRequestAdd):
    try:
        tokens = await AuthService(db).login_user(data)
    except EmailOrPasswordIncorrectException as ex:
        raise EmailOrPasswordIncorrectHTTPException from ex
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex

    response.set_cookie(
        key="access_token",
        value=tokens.access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60*15
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60*60*24*30
    )
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    db: DBDep,
    response: Response,
    refresh_token: str | None = Cookie(None)
):
    try:
        tokens = await AuthService(db).refresh_tokens(refresh_token)
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex
    except IncorrectTokenException as ex:
        raise NoAccessTokenHTTPException from ex
    except RefreshTokenExpiredException as ex:
        raise RefreshTokenExpiredHTTPException from ex

    response.set_cookie(
        key="access_token",
        value=tokens.access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60*15
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60*60*24*30
    )
    return tokens


@router.post("/logout")
async def logout(
    db: DBDep,
    response: Response,
    refresh_token: str = Cookie(None)
):
    try:
        await AuthService(db).logout(refresh_token)
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex
    except IncorrectTokenException as ex:
        raise NoAccessTokenHTTPException from ex
    except RefreshTokenExpiredException as ex:
        raise RefreshTokenExpiredHTTPException from ex

    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="lax"
    )
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return {"detail": "Logged out"}


@router.get("/me", response_model=User)
async def get_me(current_user: UserDep):
    return current_user
