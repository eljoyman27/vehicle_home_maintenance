from flask import Flask, render_template, request, redirect, url_for, flash
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

if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY no está configurada")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
        return "Upcoming"
    if d < 0:
        return "Overdue"
    if d <= 14:
        return "Due Soon"
    return "Upcoming"


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

    overdue = [i for i in items if i["status"] == "Overdue"]
    due_soon = [i for i in items if i["status"] == "Due Soon"]
    upcoming = [i for i in items if i["status"] == "Upcoming"]
    total_cost = sum(float(i.get("cost") or 0) for i in items)

    return render_template("dashboard.html", overdue=overdue, due_soon=due_soon, upcoming=upcoming[:8], total_cost=total_cost)


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
        conn.execute("""
            INSERT INTO maintenance
            (asset_id, task, last_done, due_date, mileage, due_mileage, cost, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["asset_id"],
            request.form["task"],
            request.form.get("last_done") or None,
            due_date,
            request.form.get("mileage") or None,
            request.form.get("due_mileage") or None,
            request.form.get("cost") or 0,
            compute_status(due_date),
            request.form.get("notes"),
        ))
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


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
