from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.clients import auth_client, catalog_client, inventory_client, shipping_client, events
from app.database import Base, get_db
from app.errors import ApiError
from app.main import app

# In-memory SQLite with StaticPool so all connections share the same memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

SERVICE_KEY = "test-service-key"
TOKENS = {
    "Bearer token-user-1": {"id": "user-1", "role": "CUSTOMER"},
    "Bearer token-user-2": {"id": "user-2", "role": "CUSTOMER"},
}


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- fake versions of the other microservices (no network in unit tests) ----------
class FakeInventory:
    def __init__(self):
        self.stock = {1: 10, 2: 5}
        self.release_calls = 0
        self.down = False
        self.fail_release = False

    def reserve(self, items):
        if self.down:
            raise ApiError(503, "Inventory service unavailable")
        wanted = {}
        for it in items:
            wanted[it["productId"]] = wanted.get(it["productId"], 0) + it["quantity"]
        for pid, qty in wanted.items():  # check everything first: atomic
            if pid not in self.stock:
                raise ApiError(404, f"Unknown product: {pid}")
            if self.stock[pid] < qty:
                raise ApiError(
                    409,
                    f"Insufficient stock for product {pid} "
                    f"(requested {qty}, available {self.stock[pid]})",
                )
        for pid, qty in wanted.items():
            self.stock[pid] -= qty

    def release(self, items):
        if self.down or self.fail_release:
            raise ApiError(502, "Inventory could not release the stock")
        self.release_calls += 1
        for it in items:
            self.stock[it["productId"]] += it["quantity"]


class FakeCatalog:
    products = {
        1: {"id": 1, "name": "Laptop", "price": 100.0},
        2: {"id": 2, "name": "Mouse", "price": 25.5},
    }

    def get_product(self, product_id):
        if product_id not in self.products:
            raise ApiError(404, f"Product not found: {product_id}")
        return self.products[product_id]


class FakeShipping:
    def __init__(self):
        self.statuses = {}  # orderId -> shipment status

    def get_shipment_status(self, order_id):
        return self.statuses.get(order_id)


@pytest.fixture
def services(monkeypatch):
    inventory, catalog, shipping = FakeInventory(), FakeCatalog(), FakeShipping()
    published = []
    monkeypatch.setattr(events, "publish", lambda kind, order: published.append(events.build_event(kind, order)))

    def fake_verify(authorization):
        user = TOKENS.get(authorization)
        if user is None:
            raise ApiError(401, "Invalid or expired token")
        return user

    monkeypatch.setattr(auth_client, "verify_token", fake_verify)
    monkeypatch.setattr(catalog_client, "get_product", catalog.get_product)
    monkeypatch.setattr(inventory_client, "reserve", inventory.reserve)
    monkeypatch.setattr(inventory_client, "release", inventory.release)
    monkeypatch.setattr(shipping_client, "get_shipment_status", shipping.get_shipment_status)
    monkeypatch.setattr(config, "AUTH_MODE", "remote")
    monkeypatch.setattr(config, "INTERNAL_API_KEY", SERVICE_KEY)
    monkeypatch.setattr(config, "PAID_REQUIRES_SERVICE_KEY", True)
    monkeypatch.setattr(config, "SHIPPING_CHECK_ON_CANCEL", True)
    return SimpleNamespace(inventory=inventory, catalog=catalog, shipping=shipping, published=published)


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(services):
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def user1():
    return {"Authorization": "Bearer token-user-1"}


@pytest.fixture
def user2():
    return {"Authorization": "Bearer token-user-2"}


@pytest.fixture
def service():
    return {"X-Service-Key": SERVICE_KEY}


@pytest.fixture
def make_order(client, user1):
    def _make(items=None, headers=None, user_id="user-1"):
        payload = {
            "userId": user_id,
            "customer": {"name": "Demo Customer", "address": "123 Main Street", "city": "Casablanca"},
            "items": items or [{"productId": 1, "quantity": 2}],
        }
        return client.post("/api/orders", json=payload, headers=headers or user1)

    return _make
