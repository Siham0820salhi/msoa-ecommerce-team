from app import config


def order_url(order_id, suffix=""):
    return f"/api/orders/{order_id}{suffix}"


# ── 1. Health ────────────────────────────────────────────────────────────────

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "orders", "status": "UP"}


# ── 2. Creation ──────────────────────────────────────────────────────────────

def test_create_order_success(client, services, make_order):
    response = make_order(
        items=[{"productId": 1, "quantity": 2}, {"productId": 2, "quantity": 1}]
    )
    assert response.status_code == 201
    data = response.json()
    assert data["userId"] == "user-1"
    assert data["status"] == "PENDING_PAYMENT"
    assert data["total"] == 225.5  # 2 x 100 + 1 x 25.5, prices from Catalog
    assert data["customer"] == {
        "name": "Demo Customer", "address": "123 Main Street", "city": "Casablanca",
    }
    assert data["items"] == [
        {"productId": 1, "name": "Laptop", "price": 100.0, "quantity": 2},
        {"productId": 2, "name": "Mouse", "price": 25.5, "quantity": 1},
    ]
    assert data["id"] and data["createdAt"].endswith("Z")
    assert services.inventory.stock == {1: 8, 2: 4}


def test_create_order_ignores_price_sent_by_frontend(client, make_order):
    response = make_order(items=[{"productId": 1, "quantity": 1, "price": 0.01}])
    assert response.status_code == 201
    assert response.json()["total"] == 100.0
    assert response.json()["items"][0]["price"] == 100.0


def test_create_order_merges_duplicate_products(client, services, make_order):
    response = make_order(
        items=[{"productId": 1, "quantity": 1}, {"productId": 1, "quantity": 2}]
    )
    assert response.status_code == 201
    assert response.json()["items"] == [
        {"productId": 1, "name": "Laptop", "price": 100.0, "quantity": 3}
    ]
    assert services.inventory.stock[1] == 7


def test_create_order_insufficient_stock_creates_nothing(client, services, make_order, user1):
    response = make_order(items=[{"productId": 1, "quantity": 11}])
    assert response.status_code == 409
    assert "Insufficient stock" in response.json()["message"]
    assert services.inventory.stock[1] == 10
    listing = client.get("/api/orders", params={"userId": "user-1"}, headers=user1)
    assert listing.json() == []


def test_create_order_is_all_or_nothing(client, services, make_order):
    response = make_order(
        items=[{"productId": 1, "quantity": 1}, {"productId": 2, "quantity": 99}]
    )
    assert response.status_code == 409
    assert services.inventory.stock == {1: 10, 2: 5}


def test_create_order_unknown_product(client, make_order):
    response = make_order(items=[{"productId": 999, "quantity": 1}])
    assert response.status_code == 404
    assert "message" in response.json()


def test_create_order_inventory_down(client, services, make_order, user1):
    services.inventory.down = True
    response = make_order()
    assert response.status_code == 503
    assert "Inventory" in response.json()["message"]
    services.inventory.down = False
    listing = client.get("/api/orders", params={"userId": "user-1"}, headers=user1)
    assert listing.json() == []


def test_create_order_invalid_bodies(client, user1):
    base = {
        "userId": "user-1",
        "customer": {"name": "A", "address": "B", "city": "C"},
        "items": [{"productId": 1, "quantity": 1}],
    }
    cases = [
        {**base, "items": []},
        {**base, "items": [{"productId": 1, "quantity": 0}]},
        {**base, "items": [{"productId": 1, "quantity": -3}]},
        {**base, "customer": {"name": "A", "address": "B"}},
        {**base, "customer": {"name": "  ", "address": "B", "city": "C"}},
        {k: v for k, v in base.items() if k != "userId"},
    ]
    for payload in cases:
        response = client.post("/api/orders", json=payload, headers=user1)
        assert response.status_code == 400, payload
        assert "message" in response.json()


# ── 3. Authentication and ownership ─────────────────────────────────────────

def test_requires_authentication(client):
    assert client.get("/api/orders", params={"userId": "user-1"}).status_code == 401
    assert client.get("/api/orders/abc").status_code == 401
    response = client.post("/api/orders", json={})
    assert response.status_code == 401
    assert response.json()["message"] == "Authentication required"


def test_invalid_token_and_invalid_service_key(client):
    bad_token = client.get(
        "/api/orders", params={"userId": "user-1"}, headers={"Authorization": "Bearer nope"}
    )
    assert bad_token.status_code == 401
    bad_key = client.get("/api/orders/abc", headers={"X-Service-Key": "wrong"})
    assert bad_key.status_code == 401


def test_cannot_create_order_for_another_user(client, make_order, user1):
    response = make_order(user_id="user-2", headers=user1)
    assert response.status_code == 403


def test_list_orders_only_returns_own_orders(client, make_order, user1, user2):
    make_order(headers=user1, user_id="user-1")
    make_order(headers=user2, user_id="user-2")
    mine = client.get("/api/orders", params={"userId": "user-1"}, headers=user1)
    assert mine.status_code == 200
    assert [o["userId"] for o in mine.json()] == ["user-1"]


def test_list_orders_requires_user_id_and_matching_user(client, user1):
    assert client.get("/api/orders", headers=user1).status_code == 400
    other = client.get("/api/orders", params={"userId": "user-2"}, headers=user1)
    assert other.status_code == 403


def test_get_order_owner_other_user_and_unknown(client, make_order, user1, user2):
    order_id = make_order().json()["id"]
    assert client.get(order_url(order_id), headers=user1).status_code == 200
    assert client.get(order_url(order_id), headers=user2).status_code == 403
    missing = client.get(order_url("does-not-exist"), headers=user1)
    assert missing.status_code == 404
    assert "message" in missing.json()


def test_auth_disabled_mode_for_development(client, monkeypatch):
    monkeypatch.setattr(config, "AUTH_MODE", "disabled")
    payload = {
        "userId": "user-1",
        "customer": {"name": "A", "address": "B", "city": "C"},
        "items": [{"productId": 1, "quantity": 1}],
    }
    assert client.post("/api/orders", json=payload).status_code == 201


# ── 4. Status transitions ───────────────────────────────────────────────────

def test_full_lifecycle(client, make_order, user1, service):
    order_id = make_order().json()["id"]

    paid = client.patch(order_url(order_id, "/status"), json={"status": "PAID"}, headers=service)
    assert paid.status_code == 200 and paid.json()["status"] == "PAID"

    shipped = client.patch(order_url(order_id, "/status"), json={"status": "SHIPPED"}, headers=user1)
    assert shipped.status_code == 200 and shipped.json()["status"] == "SHIPPED"

    delivered = client.patch(order_url(order_id, "/status"), json={"status": "DELIVERED"}, headers=user1)
    assert delivered.status_code == 200 and delivered.json()["status"] == "DELIVERED"

    assert client.post(order_url(order_id, "/cancel"), headers=user1).status_code == 409


def test_only_payments_service_can_mark_paid(client, make_order, user1):
    order_id = make_order().json()["id"]
    response = client.patch(order_url(order_id, "/status"), json={"status": "PAID"}, headers=user1)
    assert response.status_code == 403
    assert client.get(order_url(order_id), headers=user1).json()["status"] == "PENDING_PAYMENT"


def test_invalid_transition_is_conflict(client, make_order, service):
    order_id = make_order().json()["id"]
    response = client.patch(order_url(order_id, "/status"), json={"status": "DELIVERED"}, headers=service)
    assert response.status_code == 409
    assert "PENDING_PAYMENT" in response.json()["message"]


def test_unknown_status_value_is_bad_request(client, make_order, service):
    order_id = make_order().json()["id"]
    response = client.patch(order_url(order_id, "/status"), json={"status": "WHATEVER"}, headers=service)
    assert response.status_code == 400
    missing = client.patch(order_url(order_id, "/status"), json={}, headers=service)
    assert missing.status_code == 400


def test_status_update_of_another_users_order_is_forbidden(client, make_order, user2):
    order_id = make_order().json()["id"]
    response = client.patch(order_url(order_id, "/status"), json={"status": "SHIPPED"}, headers=user2)
    assert response.status_code == 403


# ── 5. Cancellation ─────────────────────────────────────────────────────────

def test_cancel_pending_order_restores_stock_once(client, services, make_order, user1):
    order_id = make_order(items=[{"productId": 1, "quantity": 3}]).json()["id"]
    assert services.inventory.stock[1] == 7

    cancelled = client.post(order_url(order_id, "/cancel"), headers=user1)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert services.inventory.stock[1] == 10
    assert services.inventory.release_calls == 1

    again = client.post(order_url(order_id, "/cancel"), headers=user1)
    assert again.status_code == 409
    assert services.inventory.stock[1] == 10  # no inflated stock
    assert services.inventory.release_calls == 1


def test_cancel_paid_order_without_shipment(client, services, make_order, user1, service):
    order_id = make_order().json()["id"]
    client.patch(order_url(order_id, "/status"), json={"status": "PAID"}, headers=service)
    response = client.post(order_url(order_id, "/cancel"), headers=user1)
    assert response.status_code == 200
    assert services.inventory.release_calls == 1


def test_cancel_paid_order_with_shipment_in_preparation(client, services, make_order, user1, service):
    order_id = make_order().json()["id"]
    client.patch(order_url(order_id, "/status"), json={"status": "PAID"}, headers=service)
    services.shipping.statuses[order_id] = "PREPARING"
    assert client.post(order_url(order_id, "/cancel"), headers=user1).status_code == 200


def test_cannot_cancel_when_shipment_already_left(client, services, make_order, user1, service):
    order_id = make_order().json()["id"]
    client.patch(order_url(order_id, "/status"), json={"status": "PAID"}, headers=service)
    services.shipping.statuses[order_id] = "SHIPPED"
    response = client.post(order_url(order_id, "/cancel"), headers=user1)
    assert response.status_code == 409
    assert "shipped" in response.json()["message"]
    assert services.inventory.release_calls == 0
    assert client.get(order_url(order_id), headers=user1).json()["status"] == "PAID"


def test_cannot_cancel_shipped_order(client, services, make_order, user1, service):
    order_id = make_order().json()["id"]
    client.patch(order_url(order_id, "/status"), json={"status": "PAID"}, headers=service)
    client.patch(order_url(order_id, "/status"), json={"status": "SHIPPED"}, headers=service)
    response = client.post(order_url(order_id, "/cancel"), headers=user1)
    assert response.status_code == 409
    assert services.inventory.release_calls == 0


def test_cancel_other_users_order_is_forbidden(client, services, make_order, user2):
    order_id = make_order().json()["id"]
    assert client.post(order_url(order_id, "/cancel"), headers=user2).status_code == 403
    assert services.inventory.release_calls == 0


def test_cancel_unknown_order(client, user1):
    assert client.post(order_url("nope", "/cancel"), headers=user1).status_code == 404


def test_cancel_retry_after_inventory_failure(client, services, make_order, user1):
    order_id = make_order(items=[{"productId": 1, "quantity": 2}]).json()["id"]

    services.inventory.fail_release = True
    failed = client.post(order_url(order_id, "/cancel"), headers=user1)
    assert failed.status_code == 502
    assert client.get(order_url(order_id), headers=user1).json()["status"] == "PENDING_PAYMENT"

    services.inventory.fail_release = False
    retried = client.post(order_url(order_id, "/cancel"), headers=user1)
    assert retried.status_code == 200
    assert services.inventory.release_calls == 1
    assert services.inventory.stock[1] == 10


def test_status_endpoint_cancel_also_releases_stock(client, services, make_order, user1):
    order_id = make_order(items=[{"productId": 2, "quantity": 2}]).json()["id"]
    response = client.patch(order_url(order_id, "/status"), json={"status": "CANCELLED"}, headers=user1)
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert services.inventory.stock[2] == 5
    assert services.inventory.release_calls == 1
