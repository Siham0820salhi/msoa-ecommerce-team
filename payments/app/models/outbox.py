from sqlalchemy import Column, String, Integer, Text, CheckConstraint, Index

from app.database import Base


class OutboxEvent(Base):
    """
    Transactional outbox.

    A row is inserted in the SAME database transaction as the payment itself.
    Either both the payment and its event are stored, or neither is: the event
    can never be lost because RabbitMQ happened to be down when the payment was
    accepted. A separate background worker drains this table.
    """

    __tablename__ = "outbox_events"

    # The event id is also the RabbitMQ message id, which is what makes
    # consumer-side idempotency possible.
    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    # Aggregate the event belongs to (the order), handy for debugging/replay.
    aggregate_id = Column(String, nullable=False, index=True)
    payload = Column(Text, nullable=False)  # JSON document, serialised
    status = Column(String, nullable=False, default="PENDING")
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(String, nullable=False)
    published_at = Column(String, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','PUBLISHED','FAILED')",
            name="check_outbox_status_valid",
        ),
        Index("idx_outbox_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<OutboxEvent {self.id} {self.event_type} {self.status}>"
