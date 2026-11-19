
from app import get_db
from reminder_calculator import calculate_reminder_datetime


def test_reminders():
    conn = get_db()

    try:
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

        print(f"\nTotal reminders: {len(rows)}\n")

        for row in rows:
            try:
                result = calculate_reminder_datetime(
                    row["due_date"],
                    row["due_time"],
                    row["minutes_before"]
                )

                print(
                    f"{row['task']} | "
                    f"{row['reminder_type']} | "
                    f"{row['minutes_before']} minutes | "
                    f"Activation: {result}"
                )

            except (ValueError, TypeError) as error:
                print(
                    f"{row['task']} | "
                    f"ERROR: {error}"
                )
    finally:
        conn.close()


if __name__ == "__main__":
    test_reminders()
