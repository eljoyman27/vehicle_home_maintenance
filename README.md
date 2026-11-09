# Home & Vehicle Maintenance Manager

A simple Flask + SQLite web app to track maintenance for vehicles, home systems, appliances, tools, bikes, and projects.

## Included starter assets
- 2010 Nissan Frontier
- 2015 Kia Optima EX
- Rheem Water Heater
- Ecobee HVAC / door sensors
- Husky C202H Air Compressor
- Schwinn Road Bike
- Garage project

The Infiniti Q50 is intentionally not included in the starter household assets.

## How to run

```bash
cd home_vehicle_maintenance_app
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Next upgrade ideas
- Edit existing maintenance records
- Upload receipts/photos
- Email or text reminders
- Mileage-based automatic reminders
- Export to Excel/PDF
- User login for sharing with family
