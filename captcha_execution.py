class CaptchaError(Exception):
    def __init__(self, message, errors = None):
        super(CaptchaError, self).__init__(message)

        self.errors = errors