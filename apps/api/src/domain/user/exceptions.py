class EmailAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class InvalidOrExpiredTokenError(Exception):
    pass


class OAuthAccountConflictError(Exception):
    pass


class PasswordNotSetError(Exception):
    pass


class PasswordAlreadySetError(Exception):
    pass


class CannotDeleteSelfError(Exception):
    pass
