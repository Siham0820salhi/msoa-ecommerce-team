"""
RabbitMQ publisher with publisher confirms.

Reliability properties provided here:
  * durable queue           -> survives a broker restart
  * persistent messages     -> delivery_mode=2, written to disk
  * publisher confirms      -> confirm_delivery() + a raised exception when the
                               broker does not acknowledge the message, so the
                               outbox row stays PENDING and is retried
"""

import json
import logging
from typing import Any, Dict, Optional

import pika
from pika.exceptions import AMQPError, UnroutableError

from app import config

logger = logging.getLogger(__name__)


class PublishError(RuntimeError):
    """Raised when a message could not be confirmed by the broker."""


def queue_arguments() -> Dict[str, Any]:
    """
    Arguments used when declaring the work queue.

    The Shipping consumer MUST declare the queue with exactly the same
    arguments, otherwise RabbitMQ rejects the second declaration with
    PRECONDITION_FAILED.
    """
    return {"x-dead-letter-exchange": config.RABBITMQ_DLX}


class RabbitMQPublisher:
    """Small blocking publisher. One connection reused across batches."""

    def __init__(self, url: Optional[str] = None, queue: Optional[str] = None):
        self._url = url or config.RABBITMQ_URL
        self._queue = queue or config.RABBITMQ_QUEUE
        self._connection = None
        self._channel = None

    # -- connection handling -------------------------------------------------

    def _is_open(self) -> bool:
        return (
            self._connection is not None
            and self._connection.is_open
            and self._channel is not None
            and self._channel.is_open
        )

    def connect(self) -> None:
        if self._is_open():
            return
        params = pika.URLParameters(self._url)
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        # Durable queue + dead-letter routing for poison messages.
        self._channel.queue_declare(
            queue=self._queue, durable=True, arguments=queue_arguments()
        )
        # Turn on publisher confirms on this channel.
        self._channel.confirm_delivery()
        logger.info("Connected to RabbitMQ, queue '%s' declared durable", self._queue)

    def close(self) -> None:
        try:
            if self._connection is not None and self._connection.is_open:
                self._connection.close()
        except Exception:  # pragma: no cover - best effort cleanup
            pass
        finally:
            self._connection = None
            self._channel = None

    # -- publishing ----------------------------------------------------------

    def publish(self, event: Dict[str, Any]) -> None:
        """
        Publish one event and wait for the broker's confirmation.

        Raises PublishError if the broker refuses or does not confirm, which
        keeps the corresponding outbox row in PENDING state.
        """
        # Connecting is part of publishing: a broker that is down must surface
        # as PublishError like any other failure, so the outbox row stays
        # PENDING and the worker backs off instead of crashing the loop.
        try:
            self.connect()
        except Exception as exc:
            self.close()
            raise PublishError(f"Cannot connect to RabbitMQ: {exc}") from exc

        body = json.dumps(event, ensure_ascii=False).encode("utf-8")
        properties = pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,  # persistent
            message_id=event.get("eventId"),
            type=event.get("eventType"),
        )
        try:
            # With confirm_delivery() enabled, pika raises UnroutableError (or
            # another AMQPError) instead of returning False when the broker
            # does not acknowledge the publish.
            self._channel.basic_publish(
                exchange=config.RABBITMQ_EXCHANGE,
                routing_key=self._queue,
                body=body,
                properties=properties,
                mandatory=True,
            )
        except UnroutableError as exc:
            raise PublishError(f"Message was not routable: {exc}") from exc
        except AMQPError as exc:
            # Drop the connection so the next attempt reconnects cleanly.
            self.close()
            raise PublishError(f"Broker error while publishing: {exc}") from exc
        except Exception as exc:
            self.close()
            raise PublishError(f"Unexpected error while publishing: {exc}") from exc
