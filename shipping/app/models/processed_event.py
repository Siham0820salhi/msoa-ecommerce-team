from sqlalchemy import Column, String

from app.database import Base


class ProcessedEvent(Base):
    """
    Idempotency ledger for consumed messages.

    RabbitMQ guarantees at-least-once delivery, so the same event can arrive
    more than once (broker redelivery after a crash, a retry, a re-publish).
    The event id is recorded in the SAME transaction as the shipment, so a
    duplicate delivery is detected and skipped instead of creating a second
    shipment.
    """

    __tablename__ = "processed_events"

    event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    order_id = Column(String, nullable=False, index=True)
    shipment_id = Column(String, nullable=True)
    processed_at = Column(String, nullable=False)
