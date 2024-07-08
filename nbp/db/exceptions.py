class BaseDBException(Exception):
    """
    Base DB Exception.
    """
    ...


class UpdateUserInfoError(BaseDBException):
    """
    Update User Info Error.
    """
    ...


class UpdateAppointmentInfoError(BaseDBException):
    """
    Update Appointment Info Error.
    """
    ...


class ReadMaxSequenceError(BaseDBException):
    """
    Read Max Sequence Error.
    """
    ...
