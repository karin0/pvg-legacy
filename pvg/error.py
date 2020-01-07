class PvgError(Exception):
    pass

class OperationFailedError(PvgError):
    pass

class BadRequestError(PvgError):
    pass

class DownloadUncompletedError(PvgError):
    pass

class ConfMissing(PvgError):
    pass

class MaxTryLimitExceedError(PvgError):
    pass
