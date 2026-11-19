
from datetime import datetime, timezone


def get_reminder_status(activation_datetime, now=None):
    """
    Determine whether a reminder is scheduled or due.

    Returns:
        "Scheduled" - Activation time is in the future.
        "Due"       - Activation time has arrived or passed.
    """

    if activation_datetime.tzinfo is None:
        raise ValueError(
            "Activation datetime must include timezone"
        )

    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError(
            "Current datetime must include timezone"
        )

    if activation_datetime <= now:
        return "Due"

    return "Scheduled"
