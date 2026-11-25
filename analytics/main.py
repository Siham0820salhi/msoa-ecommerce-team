import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from confluent_kafka import Consumer, KafkaError, TopicPartition
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

DB_PATH = Path(__file__).parent / "analytics.db"
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "ecommerce.events")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "analytics")

db_lock = threading.Lock()
stop_event = threading.Event()
consumer_thread: threading.Thread | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db_lock:
        conn = get_conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    received_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS shipments (
                    shipment_key TEXT PRIMARY KEY,
                    status TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_orders INTEGER NOT NULL DEFAULT 0,
                    cancelled_orders INTEGER NOT NULL DEFAULT 0,
                    total_revenue REAL NOT NULL DEFAULT 0.0,
                    shipments_by_status TEXT NOT NULL DEFAULT '{}',
                    events_by_type TEXT NOT NULL DEFAULT '{}',
                    total_events INTEGER NOT NULL DEFAULT 0,
                    last_updated TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO stats (
                    id, total_orders, cancelled_orders, total_revenue,
                    shipments_by_status, events_by_type, total_events, last_updated
                ) VALUES (1, 0, 0, 0.0, '{}', '{}', 0, ?)
                """,
                (utc_now_iso(),),
            )
            conn.commit()
        finally:
            conn.close()


def apply_event(conn: sqlite3.Connection, data: dict, fallback_id: str) -> bool:
    event_id = str(
        data.get("eventId")
        or data.get("event_id")
        or data.get("id")
        or fallback_id
    )
    event_type = str(
        data.get("eventType")
        or data.get("event_type")
        or data.get("type")
        or "Unknown"
    )
    timestamp = str(
        data.get("timestamp")
        or data.get("createdAt")
        or data.get("created_at")
        or utc_now_iso()
    )
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else data
    received_at = utc_now_iso()

    cur = conn.execute(
        """
        INSERT OR IGNORE INTO events (event_id, event_type, timestamp, payload_json, received_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (event_id, event_type, timestamp, json.dumps(payload), received_at),
    )
    if cur.rowcount == 0:
        # Duplicate eventId -> ignore
        return False

    row = conn.execute("SELECT * FROM stats WHERE id = 1").fetchone()
    total_orders = int(row["total_orders"])
    cancelled_orders = int(row["cancelled_orders"])
    total_revenue = float(row["total_revenue"])
    events_by_type = json.loads(row["events_by_type"])
    total_events = int(row["total_events"]) + 1

    events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
    norm = event_type.lower().replace("_", "").replace("-", "")

    if norm in ("ordercreated", "orderplaced"):
        total_orders += 1
    elif norm in ("ordercancelled", "ordercanceled"):
        cancelled_orders += 1
    elif norm in ("paymentsucceeded", "paymentcompleted", "paymentpaid"):
        amount = payload.get("amount")
        if amount is None:
            amount = payload.get("total")
        if amount is not None:
            total_revenue += float(amount)
    elif "shipment" in norm:
        shipment_key = str(
            payload.get("shipmentId")
            or payload.get("id")
            or payload.get("orderId")
            or event_id
        )
        status = payload.get("status")
        if not status:
            if "delivered" in norm:
                status = "DELIVERED"
            elif "transit" in norm:
                status = "IN_TRANSIT"
            elif "shipped" in norm:
                status = "SHIPPED"
            else:
                status = "PREPARING"
        conn.execute(
            "INSERT OR REPLACE INTO shipments (shipment_key, status) VALUES (?, ?)",
            (shipment_key, str(status).upper()),
        )

    ship_rows = conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM shipments GROUP BY status"
    ).fetchall()
    shipments_by_status = {r["status"]: r["cnt"] for r in ship_rows}

    conn.execute(
        """
        UPDATE stats
        SET total_orders = ?,
            cancelled_orders = ?,
            total_revenue = ?,
            shipments_by_status = ?,
            events_by_type = ?,
            total_events = ?,
            last_updated = ?
        WHERE id = 1
        """,
        (
            total_orders,
            cancelled_orders,
            round(total_revenue, 2),
            json.dumps(shipments_by_status),
            json.dumps(events_by_type),
            total_events,
            utc_now_iso(),
        ),
    )
    return True


def process_kafka_message(msg) -> bool:
    raw = msg.value()
    if not raw:
        return False
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False

    if not isinstance(data, dict):
        return False

    fallback_id = f"{msg.topic()}:{msg.partition()}:{msg.offset()}"
    with db_lock:
        conn = get_conn()
        try:
            inserted = apply_event(conn, data, fallback_id)
            conn.commit()
            return inserted
        finally:
            conn.close()


def kafka_consumer_loop() -> None:
    consumer: Consumer | None = None
    while not stop_event.is_set():
        try:
            if consumer is None:
                consumer = Consumer(
                    {
                        "bootstrap.servers": KAFKA_BOOTSTRAP,
                        "group.id": KAFKA_GROUP_ID,
                        "auto.offset.reset": "earliest",
                        "enable.auto.commit": True,
                    }
                )
                consumer.subscribe([KAFKA_TOPIC])

            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                time.sleep(2.0)
                continue

            process_kafka_message(msg)
        except Exception:
            if consumer is not None:
                try:
                    consumer.close()
                except Exception:
                    pass
                consumer = None
            time.sleep(3.0)

    if consumer is not None:
        try:
            consumer.close()
        except Exception:
            pass


def read_summary_from_db() -> dict:
    with db_lock:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM stats WHERE id = 1").fetchone()
        finally:
            conn.close()

    return {
        "totalOrders": int(row["total_orders"]),
        "cancelledOrders": int(row["cancelled_orders"]),
        "totalRevenue": round(float(row["total_revenue"]), 2),
        "shipmentsByStatus": json.loads(row["shipments_by_status"]),
        "eventsByType": json.loads(row["events_by_type"]),
        "totalEvents": int(row["total_events"]),
        "lastUpdated": row["last_updated"],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_thread
    init_db()
    stop_event.clear()
    consumer_thread = threading.Thread(target=kafka_consumer_loop, daemon=True)
    consumer_thread.start()
    yield
    stop_event.set()
    if consumer_thread is not None:
        consumer_thread.join(timeout=3.0)


app = FastAPI(title="Analytics Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"message": "Invalid request"})


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"message": "Internal server error"})


@app.get("/health")
def health():
    return {"service": "analytics", "status": "UP"}


@app.get("/api/analytics/summary")
def get_summary():
    return read_summary_from_db()


@app.get("/api/analytics/events")
def get_events():
    with db_lock:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT event_id, event_type, timestamp, payload_json, received_at "
                "FROM events ORDER BY rowid DESC"
            ).fetchall()
        finally:
            conn.close()

    return [
        {
            "eventId": r["event_id"],
            "eventType": r["event_type"],
            "timestamp": r["timestamp"],
            "payload": json.loads(r["payload_json"]),
            "receivedAt": r["received_at"],
        }
        for r in rows
    ]


@app.post("/api/analytics/replay")
def replay_events():
    replay_consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP,
            "group.id": f"analytics-replay-{uuid.uuid4().hex[:8]}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )

    try:
        try:
            metadata = replay_consumer.list_topics(KAFKA_TOPIC, timeout=5.0)
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={"message": f"Kafka broker unavailable: {exc}"},
            )

        topic_meta = metadata.topics.get(KAFKA_TOPIC)
        partitions_to_read: list[TopicPartition] = []
        target_end_offsets: dict[int, int] = {}

        if topic_meta is not None and topic_meta.partitions:
            for pid in topic_meta.partitions:
                low, high = replay_consumer.get_watermark_offsets(
                    TopicPartition(KAFKA_TOPIC, pid), timeout=5.0
                )
                if high > low:
                    partitions_to_read.append(TopicPartition(KAFKA_TOPIC, pid, low))
                    target_end_offsets[pid] = high - 1

        replayed_messages: list[tuple[dict, str]] = []
        if partitions_to_read:
            replay_consumer.assign(partitions_to_read)
            remaining = dict(target_end_offsets)
            deadline = time.time() + 15.0

            while remaining and time.time() < deadline:
                msg = replay_consumer.poll(timeout=0.5)
                if msg is None:
                    continue
                if msg.error():
                    continue

                pid = msg.partition()
                offset = msg.offset()
                if pid in remaining and offset >= remaining[pid]:
                    remaining.pop(pid, None)

                raw = msg.value()
                if not raw:
                    continue
                try:
                    data = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if isinstance(data, dict):
                    replayed_messages.append((data, f"{msg.topic()}:{pid}:{offset}"))

        with db_lock:
            conn = get_conn()
            try:
                conn.execute("DELETE FROM events")
                conn.execute("DELETE FROM shipments")
                conn.execute(
                    """
                    UPDATE stats
                    SET total_orders = 0,
                        cancelled_orders = 0,
                        total_revenue = 0.0,
                        shipments_by_status = '{}',
                        events_by_type = '{}',
                        total_events = 0,
                        last_updated = ?
                    WHERE id = 1
                    """,
                    (utc_now_iso(),),
                )
                replayed_count = 0
                for data, fallback_id in replayed_messages:
                    if apply_event(conn, data, fallback_id):
                        replayed_count += 1
                conn.commit()
            finally:
                conn.close()

        summary = read_summary_from_db()
        return {
            "success": True,
            "replayedEvents": replayed_count,
            "summary": summary,
        }
    finally:
        replay_consumer.close()