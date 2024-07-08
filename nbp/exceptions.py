class BaseError(Exception):
    """
    Base error class
    """
    pass


class MoreThanOneUserFound(BaseError):
    """
    More than one user was found.
    """
    pass


class MoreThanOneAppointment(BaseError):
    """
    More than one appointment was found.
    """
    pass


class UserParamNotFound(BaseError):
    """
    User model does not have such param.
    """
    pass


class UserNotFound(BaseError):
    """
    User was not found.
    """
    pass


class NoTelegramUpdateObject(BaseError):
    """
    No Telegram Update Object.
    """
    pass


class CalendarError(BaseError):
    """
    Calendar error.
    """
    pass


class CouldNotNotify(BaseError):
    """
    Could not notify user.
    """
    pass


class DropIsProhibited(BaseError):
    """
    Drop Is Prohibited
    """
    pass
