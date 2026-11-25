import json
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer

KAFKA_BOOTSTRAP = "localhost:9092"
KAFKA_TOPIC = "ecommerce.events"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_event(event_type: str, payload: dict) -> dict:
    return {
        "eventId": str(uuid.uuid4()),
        "eventType": event_type,
        "timestamp": now_iso(),
        "payload": payload,
    }


def main():
    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP})

    sample_events = [
        make_event("OrderCreated", {"orderId": "order-101", "userId": "user-1", "total": 8499.0}),
        make_event("PaymentSucceeded", {"paymentId": "pay-101", "orderId": "order-101", "amount": 8499.0}),
        make_event("ShipmentStatusUpdated", {"shipmentId": "ship-101", "orderId": "order-101", "status": "PREPARING"}),
        make_event("ShipmentStatusUpdated", {"shipmentId": "ship-101", "orderId": "order-101", "status": "SHIPPED"}),
        make_event("OrderCreated", {"orderId": "order-102", "userId": "user-1", "total": 599.0}),
        make_event("PaymentSucceeded", {"paymentId": "pay-102", "orderId": "order-102", "amount": 599.0}),
        make_event("ShipmentStatusUpdated", {"shipmentId": "ship-102", "orderId": "order-102", "status": "DELIVERED"}),
        make_event("OrderCreated", {"orderId": "order-103", "userId": "user-2", "total": 349.0}),
        make_event("OrderCancelled", {"orderId": "order-103", "userId": "user-2", "reason": "Customer cancelled"}),
    ]

    for ev in sample_events:
        producer.produce(
            KAFKA_TOPIC,
            key=ev["eventId"].encode("utf-8"),
            value=json.dumps(ev).encode("utf-8"),
        )
        print(f"Sent: {ev['eventType']} ({ev['eventId']})")

    producer.flush()
    print(f"\nDone! {len(sample_events)} events published to '{KAFKA_TOPIC}'.")


if __name__ == "__main__":
    main()