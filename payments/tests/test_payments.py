import pytest
from fastapi.testclient import TestClient


# ── 1. Retrieving payments (empty and populated) ─────────────────────────────

def test_list_payments_empty(client: TestClient):
    response = client.get("/api/payments")
    assert response.status_code == 200
    assert response.json() == []


def test_list_payments_returns_all(client: TestClient):
    client.post("/api/payments", json={"orderId": "ord-1", "method": "CARD"})
    client.post("/api/payments", json={"orderId": "ord-2", "method": "CASH"})
    response = client.get("/api/payments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


# ── 2. Successful payment ───────────────────────────────────────────────────

def test_create_payment_success(client: TestClient):
    payload = {"orderId": "ord-100", "method": "CARD", "amount": 49.99}
    response = client.post("/api/payments", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["orderId"] == "ord-100"
    assert data["method"] == "CARD"
    assert data["amount"] == 49.99
    assert data["status"] == "SUCCESS"
    assert "id" in data
    assert "createdAt" in data


def test_create_payment_default_amount(client: TestClient):
    payload = {"orderId": "ord-200", "method": "CARD"}
    response = client.post("/api/payments", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["amount"] == 0.0
    assert data["status"] == "SUCCESS"


# ── 3. Failed payment ───────────────────────────────────────────────────────

def test_create_payment_simulated_failure(client: TestClient):
    payload = {"orderId": "ord-fail", "method": "CARD", "simulateFailure": True}
    response = client.post("/api/payments", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "FAILED"
    assert data["orderId"] == "ord-fail"


# ── 4. Invalid payment method ───────────────────────────────────────────────

def test_create_payment_invalid_method_422(client: TestClient):
    payload = {"orderId": "ord-invalid-method", "method": "BITCOIN"}
    response = client.post("/api/payments", json=payload)
    assert response.status_code == 422


# ── 5. Missing order ID ─────────────────────────────────────────────────────

def test_create_payment_missing_order_id_422(client: TestClient):
    payload = {"method": "CARD", "amount": 50.0}
    response = client.post("/api/payments", json=payload)
    assert response.status_code == 422


def test_create_payment_empty_order_id_422(client: TestClient):
    payload = {"orderId": "", "method": "CARD"}
    response = client.post("/api/payments", json=payload)
    assert response.status_code == 422


# ── 6. Duplicate payment requests ───────────────────────────────────────────

def test_create_payment_duplicate_order_409(client: TestClient):
    payload = {"orderId": "ord-dup", "method": "CARD"}
    r1 = client.post("/api/payments", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/payments", json=payload)
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"]


# ── 7. Retrieving payment by order ID ───────────────────────────────────────

def test_get_payment_by_order_id(client: TestClient):
    client.post("/api/payments", json={"orderId": "ord-abc", "method": "CARD", "amount": 10.0})
    response = client.get("/api/payments/order/ord-abc")
    assert response.status_code == 200
    data = response.json()
    assert data["orderId"] == "ord-abc"
    assert data["amount"] == 10.0
    assert data["status"] == "SUCCESS"


def test_get_payment_by_order_id_not_found_404(client: TestClient):
    response = client.get("/api/payments/order/nonexistent-order")
    assert response.status_code == 404


# ── 8. Database persistence ─────────────────────────────────────────────────

def test_database_persistence(client: TestClient):
    create_resp = client.post("/api/payments", json={"orderId": "ord-persist", "method": "CASH", "amount": 125.0})
    assert create_resp.status_code == 201
    payment_id = create_resp.json()["id"]

    # Verify present in list
    all_resp = client.get("/api/payments")
    assert all_resp.status_code == 200
    found = [p for p in all_resp.json() if p["id"] == payment_id]
    assert len(found) == 1
    assert found[0]["orderId"] == "ord-persist"
    assert found[0]["amount"] == 125.0

    # Verify present via by-order endpoint
    by_order = client.get("/api/payments/order/ord-persist")
    assert by_order.status_code == 200
    assert by_order.json()["id"] == payment_id


# ── Health check ────────────────────────────────────────────────────────────

def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
