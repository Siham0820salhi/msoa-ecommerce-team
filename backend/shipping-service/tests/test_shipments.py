import pytest
from fastapi.testclient import TestClient


SAMPLE_PAYLOAD = {
    "orderId": "order-001",
    "address": {
        "name": "Demo Customer",
        "address": "123 Main Street",
        "city": "Casablanca",
    },
}


# ── 1. Successful shipment creation ──────────────────────────────────────────

def test_create_shipment_success(client: TestClient):
    resp = client.post("/api/shipments", json=SAMPLE_PAYLOAD)
    assert resp.status_code == 201
    data = resp.json()
    assert data["orderId"] == "order-001"
    assert data["status"] == "PREPARING"
    assert data["trackingNumber"].startswith("MSOA-")
    assert len(data["trackingNumber"]) == 13  # MSOA- + 8 chars
    assert data["address"]["name"] == "Demo Customer"
    assert data["address"]["address"] == "123 Main Street"
    assert data["address"]["city"] == "Casablanca"
    assert "id" in data
    assert "createdAt" in data
    assert "updatedAt" in data


# ── 2. Retrieving shipments ──────────────────────────────────────────────────

def test_get_all_shipments_empty(client: TestClient):
    resp = client.get("/api/shipments")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_all_shipments(client: TestClient):
    client.post("/api/shipments", json=SAMPLE_PAYLOAD)
    resp = client.get("/api/shipments")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["orderId"] == "order-001"


# ── 3. Retrieving shipment by order ID ───────────────────────────────────────

def test_get_by_order_id_found(client: TestClient):
    client.post("/api/shipments", json=SAMPLE_PAYLOAD)
    resp = client.get("/api/shipments/order/order-001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["orderId"] == "order-001"
    assert data["status"] == "PREPARING"


def test_get_by_order_id_not_found(client: TestClient):
    resp = client.get("/api/shipments/order/nonexistent-order")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ── 4. Updating shipment status & lifecycle ─────────────────────────────────

def test_status_progression(client: TestClient):
    create_resp = client.post("/api/shipments", json=SAMPLE_PAYLOAD)
    shipment_id = create_resp.json()["id"]

    # PREPARING → SHIPPED
    resp = client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "SHIPPED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "SHIPPED"

    # SHIPPED → IN_TRANSIT
    resp = client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "IN_TRANSIT"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_TRANSIT"

    # IN_TRANSIT → DELIVERED
    resp = client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "DELIVERED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "DELIVERED"


# ── 5. Invalid status transitions ───────────────────────────────────────────

def test_invalid_status_transition_jump(client: TestClient):
    create_resp = client.post("/api/shipments", json=SAMPLE_PAYLOAD)
    shipment_id = create_resp.json()["id"]

    # PREPARING → IN_TRANSIT is invalid
    resp = client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "IN_TRANSIT"})
    assert resp.status_code == 422

    # PREPARING → DELIVERED is invalid
    resp = client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "DELIVERED"})
    assert resp.status_code == 422


def test_invalid_status_from_delivered(client: TestClient):
    create_resp = client.post("/api/shipments", json=SAMPLE_PAYLOAD)
    shipment_id = create_resp.json()["id"]

    # Advance to DELIVERED
    client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "SHIPPED"})
    client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "IN_TRANSIT"})
    client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "DELIVERED"})

    # DELIVERED cannot transition further
    resp = client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "SHIPPED"})
    assert resp.status_code == 422


# ── 6. Cancellation support ─────────────────────────────────────────────────

def test_cancel_from_preparing(client: TestClient):
    create_resp = client.post("/api/shipments", json=SAMPLE_PAYLOAD)
    shipment_id = create_resp.json()["id"]

    resp = client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "CANCELLED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_cancel_from_shipped(client: TestClient):
    create_resp = client.post("/api/shipments", json=SAMPLE_PAYLOAD)
    shipment_id = create_resp.json()["id"]

    client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "SHIPPED"})
    resp = client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "CANCELLED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


# ── 7. Missing shipment handling ────────────────────────────────────────────

def test_update_missing_shipment_404(client: TestClient):
    resp = client.patch("/api/shipments/nonexistent-id/status", json={"status": "SHIPPED"})
    assert resp.status_code == 404


# ── 8. Duplicate shipment creation (409) ────────────────────────────────────

def test_duplicate_shipment_409(client: TestClient):
    client.post("/api/shipments", json=SAMPLE_PAYLOAD)
    resp = client.post("/api/shipments", json=SAMPLE_PAYLOAD)
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


# ── 9. Validation of invalid requests (422) ─────────────────────────────────

def test_create_shipment_missing_address_422(client: TestClient):
    resp = client.post("/api/shipments", json={"orderId": "order-missing-addr"})
    assert resp.status_code == 422


def test_create_shipment_empty_order_id_422(client: TestClient):
    resp = client.post("/api/shipments", json={"orderId": "", "address": SAMPLE_PAYLOAD["address"]})
    assert resp.status_code == 422


# ── 10. Database persistence ────────────────────────────────────────────────

def test_database_persistence(client: TestClient):
    create_resp = client.post("/api/shipments", json=SAMPLE_PAYLOAD)
    assert create_resp.status_code == 201
    shipment_id = create_resp.json()["id"]

    all_resp = client.get("/api/shipments")
    ids = [s["id"] for s in all_resp.json()]
    assert shipment_id in ids

    by_order = client.get(f"/api/shipments/order/{SAMPLE_PAYLOAD['orderId']}")
    assert by_order.status_code == 200
    assert by_order.json()["id"] == shipment_id
    assert by_order.json()["trackingNumber"] == create_resp.json()["trackingNumber"]


# ── 11. Health check ────────────────────────────────────────────────────────

def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
