import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.platform.auth.dependencies import get_current_user, require_roles
from app.platform.auth.models import Role, User
from app.platform.db.session import get_db
from app.resilience.capacity.service import CapacityEvaluationService
from app.resilience.drills.service import CapabilityDrillService
from app.resilience.repositories.resilience import ResilienceRepository
from app.resilience.reversibility.service import ReversibilityAssessmentService
from app.resilience.schemas.resilience import (
    CapabilityCreate,
    CapabilityOut,
    CapacityRunCreate,
    CapacityRunOut,
    CapacityScoreCreate,
    CapacityScoreOut,
    CoverageSnapshotOut,
    DrillCompleteRequest,
    DrillCreate,
    DrillOut,
    ReadinessAssessmentOut,
    ReversibilityCreate,
    ReversibilityOut,
    SuiteCreate,
    SuiteOut,
    ThresholdCreate,
    ThresholdOut,
)
from app.resilience.services.coverage import StrategicCoverageService
from app.resilience.services.policy import ResiliencePolicyService

router = APIRouter(prefix="/resilience", tags=["resilience"])

_manager = require_roles(Role.resilience_manager)


@router.post("/capabilities", response_model=CapabilityOut, status_code=201)
def create_capability(
    body: CapabilityCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> CapabilityOut:
    capability = CapacityEvaluationService(db).create_capability(
        user.tenant_id,
        name=body.name,
        domain=body.domain,
        criticality_level=body.criticality_level,
        description=body.description,
        minimum_required_count=body.minimum_required_count,
        project_id=body.project_id,
    )
    db.commit()
    return capability


@router.get("/capabilities/{capability_id}", response_model=CapabilityOut)
def get_capability(
    capability_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CapabilityOut:
    return ResilienceRepository(db).get_capability(user.tenant_id, capability_id)


@router.post("/suites", response_model=SuiteOut, status_code=201)
def create_suite(
    body: SuiteCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> SuiteOut:
    suite = CapacityEvaluationService(db).create_suite(
        user.tenant_id,
        user.id,
        name=body.name,
        critical_capability_id=body.critical_capability_id,
        rubric_name=body.rubric_name,
        rubric_thresholds=body.rubric_thresholds,
        required_dimensions=(
            [d.value for d in body.required_dimensions] if body.required_dimensions else None
        ),
        cases=[case.model_dump() for case in body.cases],
        project_id=body.project_id,
    )
    db.commit()
    return suite


@router.post("/eval-runs", response_model=CapacityRunOut, status_code=201)
def create_eval_run(
    body: CapacityRunCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> CapacityRunOut:
    run = CapacityEvaluationService(db).create_run(
        user.tenant_id,
        user.id,
        suite_id=body.human_capacity_eval_suite_id,
        subject_type=body.subject_type,
        subject_ref_id=body.subject_ref_id,
        workflow_template_version_id=body.workflow_template_version_id,
        environment_template_version_id=body.environment_template_version_id,
        project_id=body.project_id,
    )
    db.commit()
    return run


@router.get("/eval-runs/{run_id}", response_model=CapacityRunOut)
def get_eval_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CapacityRunOut:
    return ResilienceRepository(db).get_run(user.tenant_id, run_id)


@router.post("/eval-runs/scores", response_model=CapacityScoreOut, status_code=201)
def submit_capacity_score(
    body: CapacityScoreCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> CapacityScoreOut:
    service = CapacityEvaluationService(db)
    run = ResilienceRepository(db).get_run(user.tenant_id, body.human_capacity_run_id)
    score = service.submit_score(
        run,
        user,
        dimension=body.dimension,
        score=body.score,
        evidence=body.evidence,
    )
    db.commit()
    return score


@router.post("/fallback-drills", response_model=DrillOut, status_code=201)
def start_fallback_drill(
    body: DrillCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> DrillOut:
    drill = CapabilityDrillService(db).start_drill(
        user.tenant_id,
        user.id,
        environment_template_version_id=body.environment_template_version_id,
        drill_type=body.drill_type,
        ai_mode=body.ai_mode,
        workflow_template_version_id=body.workflow_template_version_id,
        project_id=body.project_id,
    )
    db.commit()
    return drill


@router.get("/fallback-drills/{drill_id}", response_model=DrillOut)
def get_fallback_drill(
    drill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DrillOut:
    return ResilienceRepository(db).get_drill(user.tenant_id, drill_id)


@router.post(
    "/fallback-drills/{drill_id}/complete",
    response_model=ReadinessAssessmentOut,
)
def complete_fallback_drill(
    drill_id: uuid.UUID,
    body: DrillCompleteRequest,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> ReadinessAssessmentOut:
    drill = ResilienceRepository(db).get_drill(user.tenant_id, drill_id)
    assessment = CapabilityDrillService(db).complete_drill(
        drill,
        readiness_score=body.readiness_score,
        summary=body.summary,
        evidence=body.evidence,
    )
    db.commit()
    return assessment


@router.post("/reversibility-assessments", response_model=ReversibilityOut, status_code=201)
def record_reversibility_assessment(
    body: ReversibilityCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> ReversibilityOut:
    assessment = ReversibilityAssessmentService(db).record_assessment(
        user.tenant_id,
        scope_type=body.scope_type,
        scope_ref=body.scope_ref,
        assessment_score=body.assessment_score,
        evidence=body.evidence,
        project_id=body.project_id,
    )
    db.commit()
    return assessment


@router.get("/reversibility-assessments/{assessment_id}", response_model=ReversibilityOut)
def get_reversibility_assessment(
    assessment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReversibilityOut:
    return ResilienceRepository(db).get_reversibility_assessment(user.tenant_id, assessment_id)


@router.post("/coverage-snapshots", response_model=list[CoverageSnapshotOut], status_code=201)
def capture_coverage_snapshots(
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> list[CoverageSnapshotOut]:
    snapshots = StrategicCoverageService(db).capture_snapshots(user.tenant_id)
    db.commit()
    return snapshots


@router.get("/coverage-snapshots", response_model=list[CoverageSnapshotOut])
def list_coverage_snapshots(
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CoverageSnapshotOut]:
    return ResilienceRepository(db).coverage_snapshots(user.tenant_id, limit)


@router.post("/thresholds", response_model=ThresholdOut, status_code=201)
def create_threshold(
    body: ThresholdCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> ThresholdOut:
    threshold = ResiliencePolicyService(db).create_threshold(
        user.tenant_id,
        scope_type=body.scope_type,
        scope_ref=body.scope_ref,
        metric_name=body.metric_name,
        min_threshold=body.min_threshold,
        policy_action=body.policy_action,
        project_id=body.project_id,
    )
    db.commit()
    return threshold
