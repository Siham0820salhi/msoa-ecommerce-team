import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "shipping.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
PORT = int(os.getenv("PORT", "8086"))

# ---------------------------------------------------------------------------
# LAB 4 - Asynchronous messaging (RabbitMQ) configuration
# ---------------------------------------------------------------------------
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")

# Topology. MUST match the declarations made by the Payments publisher,
# otherwise RabbitMQ answers PRECONDITION_FAILED.
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "shipment.requests")
RABBITMQ_DLX = os.getenv("RABBITMQ_DLX", "shipment.dlx")
RABBITMQ_DLQ = os.getenv("RABBITMQ_DLQ", "shipment.requests.dlq")

# At most this many deliveries of the same message before it is dead-lettered.
CONSUMER_MAX_ATTEMPTS = int(os.getenv("CONSUMER_MAX_ATTEMPTS", "5"))
# Seconds to wait before a transient failure is retried.
CONSUMER_RETRY_DELAY = float(os.getenv("CONSUMER_RETRY_DELAY", "2"))
CONSUMER_PREFETCH = int(os.getenv("CONSUMER_PREFETCH", "1"))

# Orders is used as a fallback source for the delivery address when the
# incoming event does not carry one.
ORDERS_URL = os.getenv("ORDERS_URL", "http://localhost:8084").rstrip("/")
ORDERS_TIMEOUT = float(os.getenv("ORDERS_TIMEOUT", "2"))

# Shared secret for service-to-service calls to Orders (its get_caller()
# accepts X-Service-Key). Must match Orders' INTERNAL_API_KEY.
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "msoa-internal-dev-key")
