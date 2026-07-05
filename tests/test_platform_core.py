from datetime import UTC

from app.platform.events.bus import EventBus
from app.platform.ids.generator import new_uuid
from app.platform.observability.correlation import CORRELATION_HEADER
from app.platform.time.clock import utc_now


def test_new_uuid_is_v7_and_time_ordered() -> None:
    first, second = new_uuid(), new_uuid()
    assert first.version == 7
    assert second.version == 7
    assert first.int < second.int


def test_utc_now_is_timezone_aware_utc() -> None:
    now = utc_now()
    assert now.tzinfo == UTC


def test_event_bus_delivers_to_subscribers() -> None:
    bus = EventBus()
    received = []
    bus.subscribe("workflow.run.created", received.append)

    event = bus.publish("workflow.run.created", {"run_id": "abc"})

    assert received == [event]
    assert event.payload == {"run_id": "abc"}
    assert event.occurred_at.tzinfo == UTC
    assert event.correlation_id is None  # outside any request context


def test_event_bus_ignores_unrelated_event_types() -> None:
    bus = EventBus()
    received = []
    bus.subscribe("workflow.run.created", received.append)

    bus.publish("workflow.stage.started", {})

    assert received == []


def test_correlation_id_echoed_when_provided(client) -> None:
    response = client.get("/health", headers={CORRELATION_HEADER: "test-cid-123"})
    assert response.headers[CORRELATION_HEADER] == "test-cid-123"


def test_correlation_id_generated_when_absent(client) -> None:
    response = client.get("/health")
    assert len(response.headers[CORRELATION_HEADER]) == 32  # uuid7 hex
