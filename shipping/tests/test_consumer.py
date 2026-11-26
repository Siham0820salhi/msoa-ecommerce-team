"""
LAB 4 - Shipping side tests (no broker required).

Covered scenarios:
  5. Shipping consumes a PaymentSucceeded event and creates the shipment.
  6. Repeated delivery of the same event creates no duplicate shipment.
  7. A processing failure never acknowledges the message prematurely.
  8. The existing REST endpoints still behave exactly as before.

The AMQP channel is replaced by a recording double, so these tests exercise
the real consumer callback (ack / nack decisions) without a broker.
"""

import json

import pytest

from app.events import handler
from app.events.consumer import ShipmentConsumer
from app.events.handler import (
    PermanentEventError,
    TransientEventError,
    handle_payment_succeeded,
)
from app.events.orders_client import AddressUnavailable
from app.models.processed_event import ProcessedEvent
from app.models.shipment import Shipment
from tests.conftest import TestingSessionLocal

ADDRESS = {"name": "Hasnae ELMIR", "address": "12 Rue Al Andalous", "city": "Rabat"}


def make_event(event_id="evt-1", order_id="order-1", with_address=True, **overrides):
    event = {
        "eventId": event_id,
        "eventType": "PaymentSucceeded",
        "type": "PaymentSucceeded",
        "paymentId": "pay-1",
        "orderId": order_id,
        "amount": 42.5,
        "method": "CARD",
        "occurredAt": "2026-11-25T10:00:00+00:00",
    }
    if with_address:
        event["address"] = dict(ADDRESS)
    event.update(overrides)
    return event


# --------------------------------------------------------------------------
# Test doubles for the AMQP side
# --------------------------------------------------------------------------


class FakeMethod:
    def __init__(self, delivery_tag=1, redelivered=False):
        self.delivery_tag = delivery_tag
        self.redelivered = redelivered


class FakeProperties:
    def __init__(self, headers=None, message_id="evt-1"):
        self.headers = headers
        self.message_id = message_id
        self.content_type = "application/json"
        self.type = "PaymentSucceeded"


class FakeChannel:
    """Records ack / nack calls so tests can assert on them."""

    def __init__(self):
        self.acked = []
        self.nacked = []  # (delivery_tag, requeue)

    def basic_ack(self, delivery_tag):
        self.acked.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue):
        self.nacked.append((delivery_tag, requeue))


@pytest.fixture
def consumer(monkeypatch):
    """A consumer wired to the in-memory test database."""
    c = ShipmentConsumer(url="amqp://unused", queue="shipment.requests")
    monkeypatch.setattr("app.events.consumer.SessionLocal", TestingSessionLocal)
    return c


def deliver(consumer, channel, event, method=None, properties=None):
    consumer.on_message(
        channel,
        method or FakeMethod(),
        properties or FakeProperties(),
        json.dumps(event).encode("utf-8"),
    )


def _shipments():
    db = TestingSessionLocal()
    try:
        return db.query(Shipment).all()
    finally:
        db.close()


# --------------------------------------------------------------------------
# Scenario 5 - the consumer creates the shipment
# --------------------------------------------------------------------------


def test_consuming_event_creates_shipment():
    db = TestingSessionLocal()
    try:
        result = handle_payment_succeeded(db, make_event())
    finally:
        db.close()

    assert result["status"] == "CREATED"
    rows = _shipments()
    assert len(rows) == 1
    shipment = rows[0]
    assert shipment.order_id == "order-1"
    assert shipment.recipient_name == ADDRESS["name"]
    assert shipment.address == ADDRESS["address"]
    assert shipment.city == ADDRESS["city"]
    # Existing lifecycle and tracking-number format preserved.
    assert shipment.status == "PREPARING"
    assert shipment.tracking_number.startswith("MSOA-")


def test_consumer_acks_after_successful_commit(consumer):
    channel = FakeChannel()
    deliver(consumer, channel, make_event())

    assert channel.acked == [1]
    assert channel.nacked == []
    assert len(_shipments()) == 1


def test_address_falls_back_to_orders_when_absent(monkeypatch):
    monkeypatch.setattr(
        handler, "fetch_order_address", lambda order_id: dict(ADDRESS)
    )
    db = TestingSessionLocal()
    try:
        result = handle_payment_succeeded(db, make_event(with_address=False))
    finally:
        db.close()

    assert result["status"] == "CREATED"
    assert _shipments()[0].city == "Rabat"


def test_event_with_team_contract_spelling_is_accepted():
    """The team contract uses 'type' instead of 'eventType'."""
    event = make_event()
    del event["eventType"]
    db = TestingSessionLocal()
    try:
        assert handle_payment_succeeded(db, event)["status"] == "CREATED"
    finally:
        db.close()


# --------------------------------------------------------------------------
# Scenario 6 - duplicate delivery creates no duplicate shipment
# --------------------------------------------------------------------------


def test_same_event_delivered_twice_creates_one_shipment(consumer):
    channel = FakeChannel()
    event = make_event()

    deliver(consumer, channel, event)
    deliver(consumer, channel, event, method=FakeMethod(2, redelivered=True))

    assert len(_shipments()) == 1
    # Both deliveries were acknowledged: a duplicate is a success, not a failure.
    assert channel.acked == [1, 2]
    assert channel.nacked == []


def test_duplicate_is_recorded_in_the_idempotency_ledger():
    db = TestingSessionLocal()
    try:
        handle_payment_succeeded(db, make_event())
        second = handle_payment_succeeded(db, make_event())
    finally:
        db.close()

    assert second["status"] == "DUPLICATE"
    db = TestingSessionLocal()
    try:
        assert db.query(ProcessedEvent).count() == 1
    finally:
        db.close()


def test_different_event_id_same_order_creates_no_second_shipment():
    """A re-published event with a fresh id must not duplicate the shipment."""
    db = TestingSessionLocal()
    try:
        handle_payment_succeeded(db, make_event(event_id="evt-A"))
        result = handle_payment_succeeded(db, make_event(event_id="evt-B"))
    finally:
        db.close()

    assert result["status"] == "DUPLICATE"
    assert len(_shipments()) == 1


def test_shipment_created_earlier_via_rest_is_not_duplicated(client):
    rest = client.post(
        "/api/shipments",
        json={"orderId": "order-1", "address": ADDRESS},
    )
    assert rest.status_code == 201

    db = TestingSessionLocal()
    try:
        result = handle_payment_succeeded(db, make_event())
    finally:
        db.close()

    assert result["status"] == "DUPLICATE"
    assert len(_shipments()) == 1


# --------------------------------------------------------------------------
# Scenario 7 - failures never ack prematurely
# --------------------------------------------------------------------------


def test_transient_failure_does_not_create_shipment(monkeypatch):
    def unavailable(order_id):
        raise AddressUnavailable("Orders unreachable")

    monkeypatch.setattr(handler, "fetch_order_address", unavailable)

    db = TestingSessionLocal()
    try:
        with pytest.raises(TransientEventError):
            handle_payment_succeeded(db, make_event(with_address=False))
    finally:
        db.close()

    assert _shipments() == []


def test_transient_failure_requeues_instead_of_acking(consumer, monkeypatch):
    """
    On a transient failure the message must survive. The consumer re-publishes
    it with an incremented attempt counter and only then settles the original
    delivery, so the event is never dropped.
    """
    def unavailable(order_id):
        raise AddressUnavailable("Orders unreachable")

    monkeypatch.setattr(handler, "fetch_order_address", unavailable)
    monkeypatch.setattr("app.events.consumer.config.CONSUMER_RETRY_DELAY", 0)

    republished = []
    monkeypatch.setattr(
        consumer,
        "_republish_with_attempts",
        lambda body, properties, attempts: republished.append(attempts),
    )

    channel = FakeChannel()
    deliver(consumer, channel, make_event(with_address=False))

    assert republished == [1]  # kept, with attempt counter at 1
    assert _shipments() == []
    assert channel.nacked == []


def test_message_is_dead_lettered_after_max_attempts(consumer, monkeypatch):
    def unavailable(order_id):
        raise AddressUnavailable("Orders unreachable")

    monkeypatch.setattr(handler, "fetch_order_address", unavailable)
    monkeypatch.setattr("app.events.consumer.config.CONSUMER_MAX_ATTEMPTS", 3)

    channel = FakeChannel()
    deliver(
        consumer,
        channel,
        make_event(with_address=False),
        properties=FakeProperties(headers={"x-delivery-attempts": 2}),
    )

    # Third attempt: give up, route to the dead-letter queue.
    assert channel.nacked == [(1, False)]
    assert channel.acked == []
    assert _shipments() == []


def test_unparseable_message_is_dead_lettered(consumer):
    channel = FakeChannel()
    consumer.on_message(channel, FakeMethod(), FakeProperties(), b"not json at all")

    assert channel.nacked == [(1, False)]
    assert channel.acked == []


def test_unsupported_event_type_is_dead_lettered(consumer):
    channel = FakeChannel()
    deliver(consumer, channel, make_event(eventType="OrderCancelled", type="OrderCancelled"))

    assert channel.nacked == [(1, False)]
    assert _shipments() == []


def test_missing_order_id_is_permanent():
    event = make_event()
    del event["orderId"]
    db = TestingSessionLocal()
    try:
        with pytest.raises(PermanentEventError):
            handle_payment_succeeded(db, event)
    finally:
        db.close()


def test_order_unknown_to_orders_is_permanent(monkeypatch):
    """Orders answering 404 is permanent: no address will ever arrive."""
    monkeypatch.setattr(handler, "fetch_order_address", lambda order_id: None)
    db = TestingSessionLocal()
    try:
        with pytest.raises(PermanentEventError):
            handle_payment_succeeded(db, make_event(with_address=False))
    finally:
        db.close()


# --------------------------------------------------------------------------
# Scenario 8 - the existing REST contract is unchanged
# --------------------------------------------------------------------------


def test_existing_rest_endpoints_still_work(client):
    created = client.post(
        "/api/shipments", json={"orderId": "order-rest", "address": ADDRESS}
    )
    assert created.status_code == 201
    body = created.json()
    assert set(body.keys()) == {
        "id",
        "orderId",
        "address",
        "trackingNumber",
        "status",
        "createdAt",
        "updatedAt",
    }

    assert client.get("/api/shipments").status_code == 200
    assert client.get("/api/shipments/order/order-rest").status_code == 200
    assert client.get("/api/shipments/order/missing").status_code == 404

    # Status lifecycle untouched.
    shipment_id = body["id"]
    ok = client.patch(f"/api/shipments/{shipment_id}/status", json={"status": "SHIPPED"})
    assert ok.status_code == 200
    bad = client.patch(
        f"/api/shipments/{shipment_id}/status", json={"status": "DELIVERED"}
    )
    assert bad.status_code == 422


def test_rest_still_works_after_consumer_created_a_shipment(client):
    db = TestingSessionLocal()
    try:
        handle_payment_succeeded(db, make_event(order_id="order-async"))
    finally:
        db.close()

    response = client.get("/api/shipments/order/order-async")
    assert response.status_code == 200
    assert response.json()["status"] == "PREPARING"
