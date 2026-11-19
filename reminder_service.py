
from datetime import datetime, timezone

from reminder_calculator import calculate_reminder_datetime
from reminder_status import get_reminder_status


def get_reminder_statuses(conn, now=None):
    """
    Retrieve reminders and calculate their activation status.

    Read-only: does not modify the database.
    """

    if now is None:
        now = datetime.now(timezone.utc)

    rows = conn.execute("""
        SELECT
            m.id AS maintenance_id,
            m.task,
            m.due_date,
            m.due_time,
            r.reminder_type,
            r.minutes_before
        FROM maintenance_reminders r
        JOIN maintenance m
            ON m.id = r.maintenance_id
        ORDER BY m.id, r.reminder_type, r.minutes_before
    """).fetchall()

    results = []

    for row in rows:
        try:
            activation = calculate_reminder_datetime(
                row["due_date"],
                row["due_time"],
                row["minutes_before"]
            )

            status = get_reminder_status(activation, now)

            results.append({
                "maintenance_id": row["maintenance_id"],
                "task": row["task"],
                "reminder_type": row["reminder_type"],
                "minutes_before": row["minutes_before"],
                "activation": activation,
                "status": status,
            })

        except (ValueError, TypeError) as error:
            results.append({
                "maintenance_id": row["maintenance_id"],
                "task": row["task"],
                "reminder_type": row["reminder_type"],
                "minutes_before": row["minutes_before"],
                "activation": None,
                "status": "Error",
                "error": str(error),
            })

    return results
