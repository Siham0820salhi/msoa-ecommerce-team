import os
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL, BASE_DIR


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db():
    """
    Initialise the SQLite database using the official schema.sql and seed.sql
    provided in the lab ZIP file.  The table is created only if it does not
    already exist, and the seed row is inserted with INSERT OR IGNORE so that
    re-starts never duplicate data.
    """
    db_path = BASE_DIR / "payments.db"
    schema_path = BASE_DIR / "schema.sql"
    seed_path = BASE_DIR / "seed.sql"

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    # Apply schema (CREATE TABLE … already idempotent via IF NOT EXISTS)
    if schema_path.exists():
        schema_sql = schema_path.read_text(encoding="utf-8")
        # Make CREATE TABLE idempotent
        schema_sql = schema_sql.replace(
            "CREATE TABLE ", "CREATE TABLE IF NOT EXISTS "
        )
        conn.executescript(schema_sql)

    # Apply seed (INSERT OR IGNORE to avoid duplicate-key errors on restart)
    if seed_path.exists():
        seed_sql = seed_path.read_text(encoding="utf-8")
        seed_sql = seed_sql.replace("INSERT INTO ", "INSERT OR IGNORE INTO ")
        conn.executescript(seed_sql)

    conn.commit()
    conn.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
