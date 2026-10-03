class SubscriptionNotFoundError(Exception):
    pass


class PlanDowngradeBlockedError(Exception):
    pass


class PlanLimitsNotFoundError(Exception):
    pass


class PlanPriceNotFoundError(Exception):
    pass


class BillingCycleUnavailableError(Exception):
    pass


class NoBillingAccountError(Exception):
    pass


class CsvExportLimitExceededError(Exception):
    pass


class InvalidStripeWebhookSignatureError(Exception):
    pass
