"""
LAB 4 - Payments side tests (no broker required).

Covered scenarios:
  1. A successful payment records a PaymentSucceeded event in the outbox.
  2. A failed payment records no event.
  3. The payment succeeds even when RabbitMQ / Shipping are unavailable.
  4. The event stays PENDING while the broker is down and is published as
     soon as it comes back.
  8. The existing REST endpoints still behave exactly as before.
"""

import json

import pytest

from app.events.contract import EVENT_TYPE_PAYMENT_SUCCEEDED, build_payment_succeeded
from app.events.outbox_worker import publish_pending_once
from app.events.publisher import PublishError
from app.models.outbox import OutboxEvent
from tests.conftest import TestingSessionLocal


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class FakePublisher:
    """Records published events. Can be told to fail, like a down broker."""

    def __init__(self, fail_with=None):
        self.published = []
        self.fail_with = fail_with

    def publish(self, event):
        if self.fail_with is not None:
            raise self.fail_with
        self.published.append(event)

    def close(self):
        pass


@pytest.fixture(autouse=True)
def no_orders_lookup(monkeypatch):
    """Never touch the real Orders service during unit tests."""
    monkeypatch.setattr(
        "app.events.outbox_worker.fetch_order_address", lambda order_id: None
    )


def _outbox_rows(status=None):
    db = TestingSessionLocal()
    try:
        query = db.query(OutboxEvent)
        if status:
            query = query.filter(OutboxEvent.status == status)
        return query.all()
    finally:
        db.close()


# --------------------------------------------------------------------------
# Scenario 1 - successful payment triggers a shipment event
# --------------------------------------------------------------------------


def test_successful_payment_records_outbox_event(client):
    response = client.post(
        "/api/payments", json={"orderId": "order-1", "amount": 42.5, "method": "CARD"}
    )
    assert response.status_code == 201
    payment = response.json()

    rows = _outbox_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == EVENT_TYPE_PAYMENT_SUCCEEDED
    assert row.status == "PENDING"
    assert row.aggregate_id == "order-1"

    event = json.loads(row.payload)
    # Superset contract: both spellings carry the same value.
    assert event["eventType"] == EVENT_TYPE_PAYMENT_SUCCEEDED
    assert event["type"] == EVENT_TYPE_PAYMENT_SUCCEEDED
    assert event["eventId"] == row.id
    assert event["paymentId"] == payment["id"]
    assert event["orderId"] == "order-1"
    assert event["amount"] == 42.5
    assert event["method"] == "CARD"
    assert event["occurredAt"]


def test_event_carries_no_sensitive_payment_data(client):
    client.post(
        "/api/payments", json={"orderId": "order-2", "amount": 10, "method": "CARD"}
    )
    event = json.loads(_outbox_rows()[0].payload)
    forbidden = {"card", "cardNumber", "pan", "cvv", "token", "iban", "simulateFailure"}
    assert forbidden.isdisjoint(event.keys())


# --------------------------------------------------------------------------
# Scenario 2 - failed payment produces no event
# --------------------------------------------------------------------------


def test_failed_payment_records_no_outbox_event(client):
    response = client.post(
        "/api/payments",
        json={
            "orderId": "order-fail",
            "amount": 10,
            "method": "CARD",
            "simulateFailure": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "FAILED"
    assert _outbox_rows() == []


# --------------------------------------------------------------------------
# Scenario 3 - payment succeeds while the broker / Shipping are unavailable
# --------------------------------------------------------------------------


def test_payment_succeeds_when_broker_is_down(client):
    """
    Nothing in the request path talks to RabbitMQ, so a broker outage cannot
    affect the customer's response. The event is simply left PENDING.
    """
    response = client.post(
        "/api/payments", json={"orderId": "order-3", "amount": 99, "method": "PAYPAL"}
    )
    assert response.status_code == 201
    assert response.json()["status"] == "SUCCESS"
    assert len(_outbox_rows("PENDING")) == 1


def test_publish_failure_leaves_event_pending(client):
    client.post(
        "/api/payments", json={"orderId": "order-4", "amount": 15, "method": "CARD"}
    )
    broken = FakePublisher(fail_with=PublishError("broker down"))

    with pytest.raises(PublishError):
        publish_pending_once(publisher=broken, session_factory=TestingSessionLocal)

    rows = _outbox_rows()
    assert len(rows) == 1
    assert rows[0].status == "PENDING"  # not lost, not marked published
    assert rows[0].attempts == 1
    assert "broker down" in rows[0].last_error


# --------------------------------------------------------------------------
# Scenario 4 - the pending event is published once the broker is back
# --------------------------------------------------------------------------


def test_pending_event_is_published_when_broker_returns(client):
    client.post(
        "/api/payments", json={"orderId": "order-5", "amount": 20, "method": "CARD"}
    )

    # Broker down: the event survives.
    broken = FakePublisher(fail_with=PublishError("broker down"))
    with pytest.raises(PublishError):
        publish_pending_once(publisher=broken, session_factory=TestingSessionLocal)
    assert _outbox_rows()[0].status == "PENDING"

    # Broker back: the same event is published, exactly once.
    working = FakePublisher()
    count = publish_pending_once(
        publisher=working, session_factory=TestingSessionLocal
    )
    assert count == 1
    assert len(working.published) == 1
    assert working.published[0]["orderId"] == "order-5"

    row = _outbox_rows()[0]
    assert row.status == "PUBLISHED"
    assert row.published_at is not None
    assert row.last_error is None

    # A second drain publishes nothing: no duplicate emission.
    again = FakePublisher()
    assert publish_pending_once(publisher=again, session_factory=TestingSessionLocal) == 0
    assert again.published == []


def test_worker_enriches_event_with_address_when_orders_is_reachable(
    client, monkeypatch
):
    monkeypatch.setattr(
        "app.events.outbox_worker.fetch_order_address",
        lambda order_id: {"name": "Hasnae", "address": "12 Rue A", "city": "Rabat"},
    )
    client.post(
        "/api/payments", json={"orderId": "order-6", "amount": 30, "method": "CARD"}
    )
    publisher = FakePublisher()
    publish_pending_once(publisher=publisher, session_factory=TestingSessionLocal)

    sent = publisher.published[0]
    assert sent["address"] == {
        "name": "Hasnae",
        "address": "12 Rue A",
        "city": "Rabat",
    }
    # The stored payload matches what actually went on the wire.
    assert json.loads(_outbox_rows()[0].payload)["address"] == sent["address"]


def test_worker_publishes_without_address_when_orders_is_down(client):
    """Orders being unreachable must not block the event (Shipping falls back)."""
    client.post(
        "/api/payments", json={"orderId": "order-7", "amount": 30, "method": "CARD"}
    )
    publisher = FakePublisher()
    publish_pending_once(publisher=publisher, session_factory=TestingSessionLocal)

    assert "address" not in publisher.published[0]
    assert _outbox_rows()[0].status == "PUBLISHED"


# --------------------------------------------------------------------------
# Scenario 8 - the existing REST contract is unchanged
# --------------------------------------------------------------------------


def test_existing_rest_endpoints_still_work(client):
    created = client.post(
        "/api/payments", json={"orderId": "order-8", "amount": 55, "method": "CASH"}
    )
    assert created.status_code == 201
    body = created.json()
    # Exactly the LAB 3 response shape, no new fields leaked into it.
    assert set(body.keys()) == {"id", "orderId", "amount", "method", "status", "createdAt"}

    assert client.get("/api/payments").status_code == 200
    assert client.get("/api/payments/order/order-8").status_code == 200
    assert client.get("/api/payments/order/nope").status_code == 404
    assert client.get("/health").json() == {"service": "payments", "status": "UP"}

    # Duplicate order still conflicts.
    duplicate = client.post(
        "/api/payments", json={"orderId": "order-8", "amount": 55, "method": "CASH"}
    )
    assert duplicate.status_code == 409


def test_outbox_endpoint_exposes_event_state(client):
    client.post(
        "/api/payments", json={"orderId": "order-9", "amount": 5, "method": "CARD"}
    )
    response = client.get("/api/payments/outbox")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["orderId"] == "order-9"
    assert rows[0]["status"] == "PENDING"


def test_build_payment_succeeded_is_stable():
    class FakePayment:
        id = "pay-1"
        order_id = "order-x"
        amount = 12.0
        method = "CARD"
        created_at = "2026-11-25T10:00:00+00:00"

    event = build_payment_succeeded(FakePayment(), event_id="evt-1")
    assert event == {
        "eventId": "evt-1",
        "eventType": "PaymentSucceeded",
        "type": "PaymentSucceeded",
        "paymentId": "pay-1",
        "orderId": "order-x",
        "amount": 12.0,
        "method": "CARD",
        "occurredAt": "2026-11-25T10:00:00+00:00",
    }


# --------------------------------------------------------------------------
# Regression: the REAL publisher must report a down broker as PublishError
# --------------------------------------------------------------------------


def test_real_publisher_raises_publish_error_when_broker_is_absent(client):
    """
    Regression test. connect() used to sit outside the error handling, so a
    missing broker escaped as a raw pika exception: the outbox bookkeeping
    (attempts / last_error) was skipped and the worker logged a traceback.
    Points at a closed port, so no broker is needed to run this.
    """
    from app.events.publisher import RabbitMQPublisher

    client.post(
        "/api/payments", json={"orderId": "order-down", "amount": 7, "method": "CARD"}
    )
    publisher = RabbitMQPublisher(url="amqp://guest:guest@127.0.0.1:1/%2F")

    with pytest.raises(PublishError):
        publish_pending_once(publisher=publisher, session_factory=TestingSessionLocal)

    row = _outbox_rows()[0]
    assert row.status == "PENDING"
    assert row.attempts == 1
    assert "Cannot connect to RabbitMQ" in row.last_error
