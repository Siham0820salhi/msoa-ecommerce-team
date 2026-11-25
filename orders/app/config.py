import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "orders.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
PORT = int(os.getenv("PORT", "8084"))

# Other services (HTTP/REST only, never their databases)
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8081").rstrip("/")
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8082").rstrip("/")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:8083").rstrip("/")
SHIPPING_URL = os.getenv("SHIPPING_URL", "http://localhost:8086").rstrip("/")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "5"))

# Security
AUTH_MODE = os.getenv("AUTH_MODE", "remote").strip().lower()  # remote | disabled
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "msoa-internal-dev-key")
PAID_REQUIRES_SERVICE_KEY = _flag("PAID_REQUIRES_SERVICE_KEY", "true")

# Business rules
SHIPPING_CHECK_ON_CANCEL = _flag("SHIPPING_CHECK_ON_CANCEL", "true")

# LAB 4
INVENTORY_GRPC_TARGET = os.getenv('INVENTORY_GRPC_TARGET', 'localhost:50051')
GRPC_TIMEOUT = float(os.getenv('GRPC_TIMEOUT', '5'))
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = 'ecommerce.events'
