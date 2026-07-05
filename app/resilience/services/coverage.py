import uuid

from sqlalchemy.orm import Session

from app.platform.time.clock import utc_now
from app.resilience.models.entities import CoverageStatus, StrategicCoverageSnapshot
from app.resilience.repositories.resilience import ResilienceRepository


class StrategicCoverageService:
    """Answers: for each critical capability, do enough qualified humans remain?"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = ResilienceRepository(session)

    def capture_snapshots(self, tenant_id: uuid.UUID) -> list[StrategicCoverageSnapshot]:
        snapshots = []
        for capability in self._repo.capabilities_for_tenant(tenant_id):
            qualified = self._repo.qualified_subject_count(capability.id)
            snapshot = StrategicCoverageSnapshot(
                tenant_id=tenant_id,
                project_id=capability.project_id,
                critical_capability_id=capability.id,
                qualified_subject_count=qualified,
                minimum_required_count=capability.minimum_required_count,
                coverage_status=(
                    CoverageStatus.adequate
                    if qualified >= capability.minimum_required_count
                    else CoverageStatus.shortfall
                ),
                captured_at=utc_now(),
            )
            self._session.add(snapshot)
            snapshots.append(snapshot)
        self._session.flush()
        return snapshots

    def minimum_coverage_ratio(self, tenant_id: uuid.UUID) -> float | None:
        """The weakest capability's qualified/required ratio, or None without capabilities."""
        ratios = [
            self._repo.qualified_subject_count(c.id) / c.minimum_required_count
            for c in self._repo.capabilities_for_tenant(tenant_id)
        ]
        return min(ratios) if ratios else None
