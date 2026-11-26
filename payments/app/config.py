import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "payments.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
PORT = int(os.getenv("PORT", "8085"))

# ---------------------------------------------------------------------------
# LAB 4 - Asynchronous messaging (RabbitMQ) configuration
# ---------------------------------------------------------------------------
# Connection details are environment-based, never hardcoded in the code paths.
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")

# Topology. These MUST match the declarations made by the Shipping consumer,
# otherwise RabbitMQ answers PRECONDITION_FAILED on the second declaration.
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "shipment.requests")
RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "")  # "" = default exchange
RABBITMQ_DLX = os.getenv("RABBITMQ_DLX", "shipment.dlx")

# Background outbox publisher.
OUTBOX_PUBLISHER_ENABLED = os.getenv("OUTBOX_PUBLISHER_ENABLED", "true").lower() == "true"
OUTBOX_POLL_INTERVAL = float(os.getenv("OUTBOX_POLL_INTERVAL", "5"))
OUTBOX_BATCH_SIZE = int(os.getenv("OUTBOX_BATCH_SIZE", "20"))
# Retry backoff bounds, in seconds, used when RabbitMQ is unreachable.
OUTBOX_BACKOFF_MIN = float(os.getenv("OUTBOX_BACKOFF_MIN", "1"))
OUTBOX_BACKOFF_MAX = float(os.getenv("OUTBOX_BACKOFF_MAX", "30"))

# Orders is read (best effort) to enrich the event with the delivery address.
ORDERS_URL = os.getenv("ORDERS_URL", "http://localhost:8084").rstrip("/")
ORDERS_TIMEOUT = float(os.getenv("ORDERS_TIMEOUT", "2"))

# Shared secret for service-to-service calls to Orders (its get_caller()
# accepts X-Service-Key). Must match Orders' INTERNAL_API_KEY.
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "msoa-internal-dev-key")
