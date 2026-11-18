"""
seed_db.py — Initialize payments.db and shipping.db from the lab-provided
schema.sql and seed.sql files.

Run this ONCE from the project root (MSOA-E-com-Demo/) before starting the
services, or after deleting the .db files:

    python seed_db.py

The script is idempotent: it uses CREATE TABLE IF NOT EXISTS and INSERT OR
IGNORE so it is safe to re-run without duplicating data.
"""
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent

SERVICES = [
    {
        "name": "payments",
        "db": BASE / "payments" / "payments.db",
        "schema": BASE / "payments" / "schema.sql",
        "seed": BASE / "payments" / "seed.sql",
    },
    {
        "name": "shipping",
        "db": BASE / "shipping" / "shipping.db",
        "schema": BASE / "shipping" / "schema.sql",
        "seed": BASE / "shipping" / "seed.sql",
    },
]


def init_service(svc: dict):
    db_path = svc["db"]
    schema_path = svc["schema"]
    seed_path = svc["seed"]

    print(f"\n[{svc['name']}] Initialising {db_path} ...")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    if schema_path.exists():
        schema_sql = schema_path.read_text(encoding="utf-8")
        # Make idempotent
        schema_sql = schema_sql.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
        conn.executescript(schema_sql)
        print(f"  ✅ Schema applied from {schema_path.name}")
    else:
        print(f"  ⚠️  {schema_path.name} not found — skipping schema")

    if seed_path.exists():
        seed_sql = seed_path.read_text(encoding="utf-8")
        seed_sql = seed_sql.replace("INSERT INTO ", "INSERT OR IGNORE INTO ")
        conn.executescript(seed_sql)
        print(f"  ✅ Seed data applied from {seed_path.name}")
    else:
        print(f"  ⚠️  {seed_path.name} not found — skipping seed")

    conn.commit()

    # Quick verification
    table = "payments" if svc["name"] == "payments" else "shipments"
    rows = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  📊 {table}: {rows} row(s)")
    conn.close()


if __name__ == "__main__":
    for svc in SERVICES:
        init_service(svc)
    print("\n✅ All databases initialised successfully.")
