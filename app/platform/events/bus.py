from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog

from app.platform.observability.correlation import get_correlation_id
from app.platform.time.clock import utc_now

logger = structlog.get_logger("events")


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime
    correlation_id: str | None


Handler = Callable[[DomainEvent], None]


class EventBus:
    """In-process, synchronous domain event bus.

    Handlers run in the publisher's transaction context, so a failing handler
    fails the operation that emitted the event (fail closed). Extension point:
    swap delivery for an outbox table + Celery fan-out without touching publishers.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event_type: str, payload: dict[str, Any]) -> DomainEvent:
        event = DomainEvent(
            event_type=event_type,
            payload=payload,
            occurred_at=utc_now(),
            correlation_id=get_correlation_id(),
        )
        logger.info("domain_event", event_type=event_type, payload=payload)
        for handler in self._subscribers[event_type]:
            handler(event)
        return event


_bus = EventBus()


def get_event_bus() -> EventBus:
    return _bus
