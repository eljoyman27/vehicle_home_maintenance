
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/New_York")


def calculate_reminder_datetime(
    due_date: str,
    due_time: str,
    minutes_before: int
) -> datetime:
    """Calculate reminder activation in New York time."""

    if not isinstance(minutes_before, int) or isinstance(minutes_before, bool):
        raise ValueError("minutes_before must be an integer")

    if minutes_before < 0:
        raise ValueError("minutes_before cannot be negative")

    if not due_date or not due_time:
        raise ValueError("due_date and due_time are required")

    scheduled = datetime.fromisoformat(
        f"{due_date}T{due_time}"
    )

    if scheduled.tzinfo is not None:
        raise ValueError("Expected local date and time without timezone")

    first = scheduled.replace(tzinfo=TIMEZONE, fold=0)
    second = scheduled.replace(tzinfo=TIMEZONE, fold=1)

    if first.utcoffset() != second.utcoffset():
        first_valid = (
            first.astimezone(timezone.utc)
            .astimezone(TIMEZONE)
            .replace(tzinfo=None) == scheduled
        )
        second_valid = (
            second.astimezone(timezone.utc)
            .astimezone(TIMEZONE)
            .replace(tzinfo=None) == scheduled
        )

        if first_valid and second_valid:
            raise ValueError(
                "Scheduled local time is ambiguous due to DST"
            )

    scheduled = scheduled.replace(tzinfo=TIMEZONE)

    # Reject nonexistent local times during DST transitions.
    round_trip = scheduled.astimezone(
        timezone.utc
    ).astimezone(TIMEZONE)

    if round_trip.replace(tzinfo=None) != scheduled.replace(tzinfo=None):
        raise ValueError("Scheduled local time does not exist")

    reminder_utc = (
        scheduled.astimezone(timezone.utc)
        - timedelta(minutes=minutes_before)
    )

    return reminder_utc.astimezone(TIMEZONE)
