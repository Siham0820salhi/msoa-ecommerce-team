"""Best-effort Kafka publication after successful database commit."""
import json
import logging
import uuid
from datetime import datetime, timezone
from threading import Lock
from app import config

logger = logging.getLogger('orders')
_producer = None
_lock = Lock()


def build_event(event_type, order):
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    payload = {'orderId': order.id, 'userId': order.user_id, 'total': order.total}
    if event_type == 'OrderCreated':
        payload['items'] = [{'productId': i.product_id, 'quantity': i.quantity,
                             'name': i.name, 'price': i.price} for i in order.items]
    return {'eventId': str(uuid.uuid4()), 'type': event_type, 'source': 'orders',
            'orderId': order.id, 'occurredAt': timestamp, 'payload': payload,
            'eventType': event_type, 'timestamp': timestamp}


def publish(event_type, order):
    global _producer
    try:
        event = build_event(event_type, order)
        with _lock:
            if _producer is None:
                from kafka import KafkaProducer
                _producer = KafkaProducer(bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
                    api_version_auto_timeout_ms=1000, max_block_ms=1500,
                    request_timeout_ms=3000, acks='all', retries=0)
            producer = _producer
        producer.send(config.KAFKA_TOPIC, key=order.id.encode('utf-8'),
                      value=json.dumps(event).encode('utf-8')).get(timeout=4)
    except Exception:
        logger.exception('Kafka publication failed (%s); order operation remains committed', event_type)
