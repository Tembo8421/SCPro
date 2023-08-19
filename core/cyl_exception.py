class CYLTekException(Exception):
    """Exception wrapping any communication errors with the device."""

    def __str__(self) -> str:
        """Return a human readable error."""
        return super().__str__() or str(self.__cause__)

class CYLTekDeviceUnavailableException(CYLTekException):
    """Exception raised when connect to cyl device fails.
    """

class CYLTekDeviceError(CYLTekException):
    """Exception communicating an error delivered by the target device.
    The device given error code and message can be accessed with  `code` and `reason`
    variables.
    """

    def __init__(self, error):
        self.code = error.get('code')
        self.reason = error.get('reason')
        super().__init__(error)

