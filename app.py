from flask import Flask, render_template, request, redirect, url_for, flash, abort
from dotenv import load_dotenv
import sqlite3
from pathlib import Path
from datetime import date, datetime
import os

load_dotenv()

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "maintenance.db"

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY no está configurada")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            year TEXT,
            make_model TEXT,
            notes TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            task TEXT NOT NULL,
            last_done TEXT,
            due_date TEXT,
            mileage INTEGER,
            due_mileage INTEGER,
            cost REAL DEFAULT 0,
            status TEXT DEFAULT 'Upcoming',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(asset_id) REFERENCES assets(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            maintenance_id INTEGER NOT NULL,
            reminder_type TEXT NOT NULL
                CHECK(reminder_type IN ('materials', 'maintenance')),
            minutes_before INTEGER NOT NULL
                CHECK(minutes_before >= 0),
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(maintenance_id)
                REFERENCES maintenance(id)
                ON DELETE CASCADE,
            UNIQUE(maintenance_id, reminder_type, minutes_before)
        )
    """)
    conn.commit()

    count = cur.execute("SELECT COUNT(*) AS c FROM assets").fetchone()["c"]
    if count == 0:
        starter_assets = [
            ("Nissan Frontier", "Vehicle", "2010", "Nissan Frontier V6 King Cab SE", "Horn/cruise/buttons and airbag light history."),
            ("Kia Optima", "Vehicle", "2015", "Kia Optima EX", "Headlights, clock spring, rear door lock, paint touch-up."),
            ("Rheem Water Heater", "Appliance", "", "Rheem Smart Water Heater", "S131 maintenance reminder; filter checked clean; set around 120°F."),
            ("Ecobee HVAC", "Home System", "", "Ecobee thermostat + door/window sensors", "Door sensors used to control A/C pause when doors are open."),
            ("Husky Air Compressor", "Tool", "", "Husky C202H", "Poly-V 8-rib belt E112096; original belt marked U4 #05AE69."),
            ("Schwinn Road Bike", "Bike", "", "27 inch Schwinn road bike", "New tires/tubes/rim strip; monitor tube fit and tire bumping issue."),
            ("Garage", "Home Project", "", "Garage redesign", "Epoxy floor, MonsterRax, 3-line lighting layout, storage organization."),
        ]
        cur.executemany("INSERT INTO assets (name, category, year, make_model, notes) VALUES (?, ?, ?, ?, ?)", starter_assets)
        conn.commit()

    conn.close()


def days_until(due_date):
    if not due_date:
        return None
    try:
        due = datetime.strptime(due_date, "%Y-%m-%d").date()
        return (due - date.today()).days
    except ValueError:
        return None


def compute_status(due_date):
    d = days_until(due_date)

    if d is None:
        return "Not Scheduled"

    if d < 0:
        return "Overdue"

    if d <= 14:
        return "Due Soon"

    return "Upcoming"

def validate_maintenance_dates(last_done, due_date):
    if not last_done or not due_date:
        return True

    try:
        last = date.fromisoformat(last_done)
        due = date.fromisoformat(due_date)
    except ValueError:
        return False

    return due > last

REMINDER_OPTIONS = {
    "15m": 15,
    "1h": 60,
    "1d": 1440,
    "3d": 4320,
    "7d": 10080,
    "14d": 20160,
    "30d": 43200,
}
@app.context_processor
def inject_reminder_options():
    return {
        "reminder_options": REMINDER_OPTIONS,
        "selected_reminders": set()
    }

def parse_reminders(form):
    reminders = []

    for reminder_type in ("materials", "maintenance"):
        field = f"reminders_{reminder_type}"
        selected = form.getlist(field)

        for option in selected:
            if option not in REMINDER_OPTIONS:
                raise ValueError(
                    f"Invalid reminder option: {option}"
                )

            reminders.append({
                "reminder_type": reminder_type,
                "minutes_before": REMINDER_OPTIONS[option],
                "message": (
                    "Buy materials for maintenance"
                    if reminder_type == "materials"
                    else "Perform scheduled maintenance"
                )
            })

    return reminders

def save_reminders(conn, maintenance_id, reminders):
    conn.execute(
        "DELETE FROM maintenance_reminders WHERE maintenance_id = ?",
        (maintenance_id,)
    )

    for reminder in reminders:
        conn.execute("""
            INSERT INTO maintenance_reminders
                (maintenance_id, reminder_type,
                 minutes_before, message)
            VALUES (?, ?, ?, ?)
        """, (
            maintenance_id,
            reminder["reminder_type"],
            reminder["minutes_before"],
            reminder["message"]
        ))

def get_reminders(conn, maintenance_id):
    rows = conn.execute("""
        SELECT reminder_type, minutes_before
        FROM maintenance_reminders
        WHERE maintenance_id = ?
    """, (maintenance_id,)).fetchall()

    return {
        (row["reminder_type"], row["minutes_before"])
        for row in rows
    }

@app.before_request
def setup():
    init_db()


@app.route("/")
def dashboard():
    conn = get_db()
    rows = conn.execute("""
        SELECT m.*, a.name AS asset_name, a.category
        FROM maintenance m
        JOIN assets a ON a.id = m.asset_id
        ORDER BY COALESCE(m.due_date, '9999-12-31') ASC, m.created_at DESC
    """).fetchall()
    conn.close()

    items = []
    for r in rows:
        item = dict(r)
        item["days_until"] = days_until(item.get("due_date"))
        item["status"] = compute_status(item.get("due_date"))
        items.append(item)

    has_maintenance = len(items) > 0

    overdue = [i for i in items if i["status"] == "Overdue"]
    due_soon = [i for i in items if i["status"] == "Due Soon"]
    upcoming = [i for i in items if i["status"] == "Upcoming"]
    total_cost = sum(float(i.get("cost") or 0) for i in items)
    not_scheduled = [
        i for i in items
        if i["status"] == "Not Scheduled"
    ]

    return render_template(
        "dashboard.html",
        overdue=overdue,
        due_soon=due_soon,
        upcoming=upcoming[:8],
        not_scheduled=not_scheduled,
        total_cost=total_cost,
        has_maintenance=has_maintenance
    )


@app.route("/assets")
def assets():
    conn = get_db()
    rows = conn.execute("SELECT * FROM assets ORDER BY category, name").fetchall()
    conn.close()
    return render_template("assets.html", assets=rows)


@app.route("/assets/new", methods=["GET", "POST"])
def new_asset():
    if request.method == "POST":
        conn = get_db()
        conn.execute("""
            INSERT INTO assets (name, category, year, make_model, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (
            request.form["name"],
            request.form["category"],
            request.form.get("year"),
            request.form.get("make_model"),
            request.form.get("notes"),
        ))
        conn.commit()
        conn.close()
        flash("Asset added.")
        return redirect(url_for("assets"))
    return render_template("asset_form.html")


@app.route("/maintenance")
def maintenance():
    conn = get_db()
    rows = conn.execute("""
        SELECT m.*, a.name AS asset_name, a.category
        FROM maintenance m
        JOIN assets a ON a.id = m.asset_id
        ORDER BY m.created_at DESC
    """).fetchall()
    conn.close()
    return render_template("maintenance.html", records=rows, compute_status=compute_status)


@app.route("/maintenance/new", methods=["GET", "POST"])
def new_maintenance():
    conn = get_db()
    assets = conn.execute("SELECT * FROM assets ORDER BY name").fetchall()

    if request.method == "POST":
        due_date = request.form.get("due_date") or None
        due_time = request.form.get("due_time") or None
        last_done = request.form.get("last_done") or None

        # 1. Validar fechas
        if not validate_maintenance_dates(last_done, due_date):
            conn.close()
            flash("Due Date must be later than Last Done.")
            return render_template(
                "maintenance_form.html",
                assets=assets,
                record=dict(request.form),
                edit_mode=False
            ), 400

        # 2. Validar recordatorios
        # 2. Validar recordatorios
        try:
            reminders = parse_reminders(request.form)
        except ValueError as error:
            conn.close()
            flash(str(error))
            return redirect(url_for("new_maintenance"))

        # 3. Aquí continúa tu INSERT de mantenimiento

        cursor = conn.execute("""
            INSERT INTO maintenance
            (asset_id, task, last_done, due_date, due_time,
             mileage, due_mileage, cost, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["asset_id"],
            request.form["task"],
            last_done,
            due_date,
            due_time,
            request.form.get("mileage") or None,
            request.form.get("due_mileage") or None,
            request.form.get("cost") or 0,
            compute_status(due_date),
            request.form.get("notes"),
        ))

        save_reminders(conn, cursor.lastrowid, reminders)

        conn.commit()
        conn.close()
        flash("Maintenance record added.")
        return redirect(url_for("dashboard"))
    conn.close()
    return render_template("maintenance_form.html", assets=assets)


@app.route("/maintenance/<int:record_id>/delete", methods=["POST"])
def delete_maintenance(record_id):
    conn = get_db()
    conn.execute("DELETE FROM maintenance WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    flash("Maintenance record deleted.")
    return redirect(url_for("maintenance"))


@app.route("/maintenance/<int:record_id>/edit", methods=["GET", "POST"])
def edit_maintenance(record_id):
    conn = get_db()

    record = conn.execute(
        "SELECT * FROM maintenance WHERE id = ?",
        (record_id,)
    ).fetchone()

    if record is None:
        conn.close()
        abort(404)

    assets = conn.execute(
        "SELECT * FROM assets ORDER BY name"
    ).fetchall()
    selected_reminders = get_reminders(conn, record_id)

    if request.method == "POST":
        last_done = request.form.get("last_done") or None
        due_date = request.form.get("due_date") or None
        due_time = request.form.get("due_time") or None

        # 1. Validar fechas
        if not validate_maintenance_dates(last_done, due_date):
            conn.close()
            flash("Due Date must be later than Last Done.")
            return render_template(
                "maintenance_form.html",
                assets=assets,
                record=record,
                edit_mode=True,
                selected_reminders=selected_reminders
            ), 400

        # 2. Validar recordatorios
        try:
            reminders = parse_reminders(request.form)
        except ValueError as error:
            conn.close()
            flash(str(error))
            return redirect(url_for("edit_maintenance", record_id=record_id))

        # 3. Aquí continúa tu UPDATE
        conn.execute("""
            UPDATE maintenance
            SET asset_id = ?,
                task = ?,
                last_done = ?,
                due_date = ?,
                due_time = ?,
                mileage = ?,
                due_mileage = ?,
                cost = ?,
                status = ?,
                notes = ?
            WHERE id = ?
        """, (
            request.form["asset_id"],
            request.form["task"],
            last_done,
            due_date,
            due_time,
            request.form.get("mileage") or None,
            request.form.get("due_mileage") or None,
            request.form.get("cost") or 0,
            compute_status(due_date),
            request.form.get("notes"),
            record_id
        ))

        save_reminders(conn, record_id, reminders)

        conn.commit()
        conn.close()

        flash("Maintenance record updated successfully.")
        return redirect(url_for("maintenance"))

    conn.close()

    return render_template(
        "maintenance_form.html",
        assets=assets,
        record=record,
        edit_mode=True,
        selected_reminders=selected_reminders
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5050)
