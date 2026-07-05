import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.platform.errors import NotFoundError
from app.resilience.models.entities import (
    CapabilityProfile,
    CapabilityStatus,
    CriticalCapability,
    FallbackDrill,
    FallbackReadinessAssessment,
    HumanCapacityEvalSuite,
    HumanCapacityRun,
    ResilienceThreshold,
    ReversibilityAssessment,
    StrategicCoverageSnapshot,
)


class ResilienceRepository:
    """All lookups are tenant-scoped, directly or through the owning parent."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_capability(self, tenant_id: uuid.UUID, capability_id: uuid.UUID) -> CriticalCapability:
        capability = self._session.scalar(
            select(CriticalCapability).where(
                CriticalCapability.id == capability_id,
                CriticalCapability.tenant_id == tenant_id,
            )
        )
        if capability is None:
            raise NotFoundError(f"critical capability {capability_id} not found")
        return capability

    def capabilities_for_tenant(self, tenant_id: uuid.UUID) -> list[CriticalCapability]:
        return list(
            self._session.scalars(
                select(CriticalCapability).where(CriticalCapability.tenant_id == tenant_id)
            )
        )

    def get_suite(self, tenant_id: uuid.UUID, suite_id: uuid.UUID) -> HumanCapacityEvalSuite:
        suite = self._session.scalar(
            select(HumanCapacityEvalSuite)
            .where(
                HumanCapacityEvalSuite.id == suite_id,
                HumanCapacityEvalSuite.tenant_id == tenant_id,
            )
            .options(
                selectinload(HumanCapacityEvalSuite.cases),
                selectinload(HumanCapacityEvalSuite.rubric),
                selectinload(HumanCapacityEvalSuite.capability),
            )
        )
        if suite is None:
            raise NotFoundError(f"human capacity eval suite {suite_id} not found")
        return suite

    def get_run(self, tenant_id: uuid.UUID, run_id: uuid.UUID) -> HumanCapacityRun:
        run = self._session.scalar(
            select(HumanCapacityRun)
            .where(
                HumanCapacityRun.id == run_id,
                HumanCapacityRun.tenant_id == tenant_id,
            )
            .options(
                selectinload(HumanCapacityRun.scores),
                selectinload(HumanCapacityRun.suite).selectinload(HumanCapacityEvalSuite.rubric),
            )
        )
        if run is None:
            raise NotFoundError(f"human capacity run {run_id} not found")
        return run

    def get_or_create_profile(
        self,
        capability: CriticalCapability,
        subject_type,
        subject_ref_id: uuid.UUID,
    ) -> CapabilityProfile:
        profile = self._session.scalar(
            select(CapabilityProfile).where(
                CapabilityProfile.critical_capability_id == capability.id,
                CapabilityProfile.subject_type == subject_type,
                CapabilityProfile.subject_ref_id == subject_ref_id,
            )
        )
        if profile is None:
            profile = CapabilityProfile(
                critical_capability_id=capability.id,
                subject_type=subject_type,
                subject_ref_id=subject_ref_id,
            )
            self._session.add(profile)
            self._session.flush()
        return profile

    def qualified_subject_count(self, capability_id: uuid.UUID) -> int:
        return len(
            self._session.scalars(
                select(CapabilityProfile.id).where(
                    CapabilityProfile.critical_capability_id == capability_id,
                    CapabilityProfile.current_status == CapabilityStatus.qualified,
                )
            ).all()
        )

    def get_drill(self, tenant_id: uuid.UUID, drill_id: uuid.UUID) -> FallbackDrill:
        drill = self._session.scalar(
            select(FallbackDrill).where(
                FallbackDrill.id == drill_id, FallbackDrill.tenant_id == tenant_id
            )
        )
        if drill is None:
            raise NotFoundError(f"fallback drill {drill_id} not found")
        return drill

    def get_reversibility_assessment(
        self, tenant_id: uuid.UUID, assessment_id: uuid.UUID
    ) -> ReversibilityAssessment:
        assessment = self._session.scalar(
            select(ReversibilityAssessment).where(
                ReversibilityAssessment.id == assessment_id,
                ReversibilityAssessment.tenant_id == tenant_id,
            )
        )
        if assessment is None:
            raise NotFoundError(f"reversibility assessment {assessment_id} not found")
        return assessment

    def latest_reversibility_for_scope(
        self, tenant_id: uuid.UUID, scope_type: str, scope_ref: str
    ) -> ReversibilityAssessment | None:
        return self._session.scalar(
            select(ReversibilityAssessment)
            .where(
                ReversibilityAssessment.tenant_id == tenant_id,
                ReversibilityAssessment.scope_type == scope_type,
                ReversibilityAssessment.scope_ref == scope_ref,
            )
            .order_by(ReversibilityAssessment.assessed_at.desc())
            .limit(1)
        )

    def latest_readiness_for_environment(
        self, tenant_id: uuid.UUID, environment_template_version_id: uuid.UUID | None
    ) -> FallbackReadinessAssessment | None:
        stmt = (
            select(FallbackReadinessAssessment)
            .join(FallbackDrill, FallbackReadinessAssessment.fallback_drill_id == FallbackDrill.id)
            .where(FallbackReadinessAssessment.tenant_id == tenant_id)
        )
        if environment_template_version_id is not None:
            stmt = stmt.where(
                FallbackDrill.environment_template_version_id == environment_template_version_id
            )
        return self._session.scalar(
            stmt.order_by(FallbackReadinessAssessment.assessed_at.desc()).limit(1)
        )

    def active_thresholds_for_scope(
        self, tenant_id: uuid.UUID, scope_type: str, scope_ref: str
    ) -> list[ResilienceThreshold]:
        return list(
            self._session.scalars(
                select(ResilienceThreshold).where(
                    ResilienceThreshold.tenant_id == tenant_id,
                    ResilienceThreshold.scope_type == scope_type,
                    ResilienceThreshold.scope_ref == scope_ref,
                    ResilienceThreshold.is_active.is_(True),
                )
            )
        )

    def coverage_snapshots(
        self, tenant_id: uuid.UUID, limit: int = 100
    ) -> list[StrategicCoverageSnapshot]:
        return list(
            self._session.scalars(
                select(StrategicCoverageSnapshot)
                .where(StrategicCoverageSnapshot.tenant_id == tenant_id)
                .order_by(StrategicCoverageSnapshot.captured_at.desc())
                .limit(min(limit, 500))
            )
        )
