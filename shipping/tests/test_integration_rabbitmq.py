"""
LAB 4 - End-to-end tests against a REAL RabbitMQ broker.

These are skipped automatically when no broker is reachable, so the normal
test run stays offline-friendly. To run them:

    docker compose up -d rabbitmq
    cd shipping && python -m pytest tests/test_integration_rabbitmq.py -v

Covered scenarios (the ones a fake broker cannot prove):
  4. A message published while the consumer is down is NOT lost; it waits in
     the durable queue and is processed when the consumer starts.
  5. Shipping really consumes from RabbitMQ and creates the shipment.
  6. A redelivered message creates no duplicate shipment.
  7. The message is acknowledged only after the commit (an unacked message is
     redelivered after the channel closes).
"""

import json
import uuid

import pytest

pika = pytest.importorskip("pika", reason="pika is required for broker tests")

from app import config  # noqa: E402
from app.events.consumer import ShipmentConsumer, queue_arguments  # noqa: E402
from app.models.shipment import Shipment  # noqa: E402
from tests.conftest import TestingSessionLocal  # noqa: E402

ADDRESS = {"name": "Hasnae ELMIR", "address": "12 Rue Al Andalous", "city": "Rabat"}


def _broker_available() -> bool:
    try:
        connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
        connection.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _broker_available(),
    reason=f"No RabbitMQ at {config.RABBITMQ_URL} (start it with: docker compose up -d rabbitmq)",
)


@pytest.fixture
def queue_name():
    """A throwaway durable queue per test, deleted afterwards."""
    name = f"test.shipment.requests.{uuid.uuid4().hex[:8]}"
    connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
    channel = connection.channel()
    channel.queue_declare(queue=name, durable=True, arguments=queue_arguments())
    yield name
    try:
        channel.queue_delete(queue=name)
        connection.close()
    except Exception:
        pass


def publish(queue_name, event):
    """Publish a persistent message with publisher confirms."""
    connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
    channel = connection.channel()
    channel.confirm_delivery()
    channel.basic_publish(
        exchange="",
        routing_key=queue_name,
        body=json.dumps(event).encode("utf-8"),
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
            message_id=event["eventId"],
            type=event["eventType"],
        ),
        mandatory=True,
    )
    connection.close()


def drain_one(queue_name, monkeypatch, expect_message=True):
    """Run the real consumer callback against the next message in the queue."""
    consumer = ShipmentConsumer(queue=queue_name)
    monkeypatch.setattr("app.events.consumer.SessionLocal", TestingSessionLocal)
    connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
    channel = connection.channel()
    try:
        method, properties, body = channel.basic_get(queue=queue_name, auto_ack=False)
        if method is None:
            assert not expect_message, "expected a message in the queue, found none"
            return None
        consumer._channel = channel
        consumer.on_message(channel, method, properties, body)
        return method
    finally:
        connection.close()


def make_event(order_id="order-int", event_id=None):
    return {
        "eventId": event_id or str(uuid.uuid4()),
        "eventType": "PaymentSucceeded",
        "type": "PaymentSucceeded",
        "paymentId": str(uuid.uuid4()),
        "orderId": order_id,
        "amount": 42.5,
        "method": "CARD",
        "occurredAt": "2026-11-25T10:00:00+00:00",
        "address": dict(ADDRESS),
    }


def _shipments():
    db = TestingSessionLocal()
    try:
        return db.query(Shipment).all()
    finally:
        db.close()


def _queue_depth(queue_name):
    connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
    channel = connection.channel()
    result = channel.queue_declare(
        queue=queue_name, durable=True, passive=True
    )
    depth = result.method.message_count
    connection.close()
    return depth


def test_message_waits_in_queue_while_consumer_is_down(queue_name):
    """Scenario 4: nothing is lost while Shipping is unavailable."""
    publish(queue_name, make_event())
    assert _queue_depth(queue_name) == 1
    assert _shipments() == []


def test_consumer_creates_shipment_from_real_broker(queue_name, monkeypatch):
    """Scenario 5: end-to-end through a real durable queue."""
    event = make_event(order_id="order-e2e")
    publish(queue_name, event)

    drain_one(queue_name, monkeypatch)

    rows = _shipments()
    assert len(rows) == 1
    assert rows[0].order_id == "order-e2e"
    assert rows[0].status == "PREPARING"
    assert rows[0].tracking_number.startswith("MSOA-")
    # Acknowledged: the queue is empty again.
    assert _queue_depth(queue_name) == 0


def test_redelivered_message_creates_no_duplicate(queue_name, monkeypatch):
    """Scenario 6: at-least-once delivery handled idempotently."""
    event = make_event(order_id="order-dup")
    publish(queue_name, event)
    drain_one(queue_name, monkeypatch)

    # Same event id delivered a second time.
    publish(queue_name, event)
    drain_one(queue_name, monkeypatch)

    assert len(_shipments()) == 1
    assert _queue_depth(queue_name) == 0


def test_unacked_message_is_redelivered(queue_name):
    """
    Scenario 7: a message that was never acked is not lost.

    We fetch it, then close the channel without acknowledging, which is what
    happens if the consumer crashes mid-processing. RabbitMQ must give it back.
    """
    publish(queue_name, make_event(order_id="order-noack"))

    connection = pika.BlockingConnection(pika.URLParameters(config.RABBITMQ_URL))
    channel = connection.channel()
    method, _properties, _body = channel.basic_get(queue=queue_name, auto_ack=False)
    assert method is not None
    connection.close()  # no ack: simulate a crash

    assert _shipments() == []
    assert _queue_depth(queue_name) == 1  # back in the queue
