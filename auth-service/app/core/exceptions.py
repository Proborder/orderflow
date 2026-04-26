from fastapi import HTTPException


class AuthExceptions(Exception):
    detail = "Неожиданная ошибка"

    def __init__(self, *args):
        super().__init__(self.detail, *args)


class UserAlreadyExistsException(AuthExceptions):
    detail = "Пользователь уже существует"


class DatabaseNotUnavailableException(AuthExceptions):
    detail = "База данных временно недоступна"


class IncorrectTokenException(AuthExceptions):
    detail = "Некорректный токен"


class RefreshTokenExpiredException(AuthExceptions):
    detail = "Срок действия токена истёк"


class EmailOrPasswordIncorrectException(AuthExceptions):
    detail = "Почта или пароль неверный"


class UserIsNotFoundException(AuthExceptions):
    detail = "Пользователь не найден"


class AuthHTTPExceptions(HTTPException):
    status_code = 500
    detail = None

    def __init__(self):
        super().__init__(status_code=self.status_code, detail=self.detail)


class UserEmailAlreadyExistsHTTPException(AuthHTTPExceptions):
    status_code = 409
    detail = "Пользователь с такой почтой уже существует"


class DatabaseNotUnavailableHTTPException(AuthHTTPExceptions):
    status_code = 503
    detail = "База данных временно недоступна"


class EmailOrPasswordIncorrectHTTPException(AuthHTTPExceptions):
    status_code = 401
    detail = "Почта или пароль неверный"


class UserIsNotFoundHTTPException(AuthHTTPExceptions):
    status_code = 401
    detail = "Пользователь не найден"


class NoAccessTokenHTTPException(AuthHTTPExceptions):
    status_code = 401
    detail = "Вы не предоставили токен доступа"


class RefreshTokenExpiredHTTPException(AuthHTTPExceptions):
    status_code = 401
    detail = "Срок действия токена истёк"

class TokenExpiredHTTPException(AuthHTTPExceptions):
    status_code = 401
    detail = "Срок действия токена истёк"
