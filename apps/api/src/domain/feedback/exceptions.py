class FeedbackNotFoundError(Exception):
    pass


class EmptyFeedbackMessageError(Exception):
    pass


class FeedbackMessageTooLongError(Exception):
    pass


class InvalidNpsScoreError(Exception):
    pass
