import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evals.calibration.service import (
    CalibrationExampleService,
    CalibrationRunService,
    suite_judge_monitoring,
)
from app.evals.models.entities import (
    CalibrationExample,
    CalibrationRun,
    CalibrationSplit,
    EvalRunStatus,
)
from app.evals.regressions.service import BaselineService, RegressionPackService
from app.evals.repositories.evals import EvalsRepository
from app.evals.rubrics.service import RubricService
from app.evals.schemas.evals import (
    BaselineCreate,
    BaselineOut,
    CalibrationExampleCreate,
    CalibrationExampleOut,
    CalibrationHarvestRequest,
    CalibrationRunCreate,
    CalibrationRunOut,
    CalibrationSuggestionOut,
    DriftSignalOut,
    EvalResultOut,
    EvalRunCreate,
    EvalRunOut,
    JudgeMonitoringOut,
    RegressionPackCreate,
    RegressionPackOut,
    RegressionPackRunOut,
    ReviewerScoreCreate,
    ReviewerScoreOut,
    RubricCreate,
    RubricOut,
    RubricVersionCreate,
    RubricVersionOut,
    SuiteCreate,
    SuiteOut,
)
from app.evals.services.runs import EvalRunService
from app.evals.services.scoring import EvalScoringService
from app.evals.services.suites import EvalSuiteService
from app.platform.auth.dependencies import get_current_user, require_roles
from app.platform.auth.models import Role, User
from app.platform.db.session import get_db
from app.platform.storage.service import StorageService, get_storage

router = APIRouter(prefix="/evals", tags=["evals"])

_evaluator = require_roles(Role.evaluator)
_scorer = require_roles(Role.evaluator, Role.reviewer)


@router.post("/suites", response_model=SuiteOut, status_code=201)
def create_suite(
    body: SuiteCreate,
    user: User = Depends(_evaluator),
    db: Session = Depends(get_db),
) -> SuiteOut:
    suite = EvalSuiteService(db).create_suite(
        user.tenant_id,
        user.id,
        name=body.name,
        target_type=body.target_type,
        config=body.config,
        cases=[case.model_dump() for case in body.cases],
        project_id=body.project_id,
    )
    db.commit()
    return suite


@router.get("/suites", response_model=list[SuiteOut])
def list_suites(
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SuiteOut]:
    return EvalsRepository(db).list_suites(user.tenant_id, limit)


@router.get("/rubrics", response_model=list[RubricOut])
def list_rubrics(
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RubricOut]:
    return EvalsRepository(db).list_rubrics(user.tenant_id, limit)


@router.get("/suites/{suite_id}", response_model=SuiteOut)
def get_suite(
    suite_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuiteOut:
    return EvalsRepository(db).get_suite(user.tenant_id, suite_id)


@router.post("/rubrics", response_model=RubricOut, status_code=201)
def create_rubric(
    body: RubricCreate,
    user: User = Depends(_evaluator),
    db: Session = Depends(get_db),
) -> RubricOut:
    rubric = RubricService(db).create_rubric(
        user.tenant_id,
        name=body.name,
        description=body.description,
        project_id=body.project_id,
    )
    db.commit()
    return rubric


@router.get("/rubrics/{rubric_id}", response_model=RubricOut)
def get_rubric(
    rubric_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RubricOut:
    return EvalsRepository(db).get_rubric(user.tenant_id, rubric_id)


@router.post("/rubrics/{rubric_id}/versions", response_model=RubricVersionOut, status_code=201)
def create_rubric_version(
    rubric_id: uuid.UUID,
    body: RubricVersionCreate,
    user: User = Depends(_evaluator),
    db: Session = Depends(get_db),
) -> RubricVersionOut:
    version = RubricService(db).create_version(
        user.tenant_id,
        rubric_id,
        criteria=body.criteria,
        score_scale=body.score_scale,
        pass_threshold=body.pass_threshold,
    )
    db.commit()
    return version


@router.post("/runs", response_model=EvalRunOut, status_code=201)
def create_run(
    body: EvalRunCreate,
    user: User = Depends(_evaluator),
    db: Session = Depends(get_db),
) -> EvalRunOut:
    run = EvalRunService(db).create_run(
        user.tenant_id,
        user.id,
        eval_suite_id=body.eval_suite_id,
        rubric_version_id=body.rubric_version_id,
        target_ref_type=body.target_ref_type,
        target_ref_id=body.target_ref_id,
        project_id=body.project_id,
    )
    db.commit()
    return run


@router.get("/runs", response_model=list[EvalRunOut])
def list_runs(
    status: EvalRunStatus | None = None,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EvalRunOut]:
    return EvalsRepository(db).list_runs(user.tenant_id, status, limit)


@router.get("/rubric-versions/{version_id}", response_model=RubricVersionOut)
def get_rubric_version(
    version_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RubricVersionOut:
    return EvalsRepository(db).get_rubric_version(user.tenant_id, version_id)


@router.get("/runs/{run_id}", response_model=EvalRunOut)
def get_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvalRunOut:
    return EvalsRepository(db).get_run(user.tenant_id, run_id)


@router.get("/runs/{run_id}/result", response_model=EvalResultOut)
def get_run_result(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvalResultOut:
    run = EvalsRepository(db).get_run(user.tenant_id, run_id)
    return EvalResultOut(run=run, decision=run.decision, scores=run.scores)


@router.post("/reviewer-scores", response_model=ReviewerScoreOut, status_code=201)
def submit_reviewer_score(
    body: ReviewerScoreCreate,
    user: User = Depends(_scorer),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> ReviewerScoreOut:
    run = EvalsRepository(db).get_run(user.tenant_id, body.eval_run_id)
    score = EvalScoringService(db, storage).submit_score(
        run,
        user,
        score_json=body.score_json,
        rationale=body.rationale,
        is_calibration=body.is_calibration,
    )
    db.commit()
    return score


@router.post("/baselines", response_model=BaselineOut, status_code=201)
def create_baseline(
    body: BaselineCreate,
    user: User = Depends(_evaluator),
    db: Session = Depends(get_db),
) -> BaselineOut:
    baseline = BaselineService(db).create_baseline(
        user.tenant_id,
        name=body.name,
        scope_type=body.scope_type,
        scope_ref=body.scope_ref,
        baseline_data=body.baseline_data,
        project_id=body.project_id,
    )
    db.commit()
    return baseline


@router.post("/regression-packs", response_model=RegressionPackOut, status_code=201)
def create_regression_pack(
    body: RegressionPackCreate,
    user: User = Depends(_evaluator),
    db: Session = Depends(get_db),
) -> RegressionPackOut:
    pack = RegressionPackService(db).create_pack(
        user.tenant_id,
        name=body.name,
        description=body.description,
        eval_suite_ids=body.eval_suite_ids,
        scope_type=body.scope_type,
        scope_ref=body.scope_ref,
        project_id=body.project_id,
    )
    db.commit()
    return pack


@router.get("/regression-packs/{pack_id}", response_model=RegressionPackOut)
def get_regression_pack(
    pack_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RegressionPackOut:
    return EvalsRepository(db).get_regression_pack(user.tenant_id, pack_id)


@router.post("/regression-packs/{pack_id}/run", response_model=RegressionPackRunOut)
def run_regression_pack(
    pack_id: uuid.UUID,
    user: User = Depends(_evaluator),
    db: Session = Depends(get_db),
) -> RegressionPackRunOut:
    pack_run = RegressionPackService(db).run_pack(user.tenant_id, pack_id, user.id)
    db.commit()
    return pack_run


@router.get("/drift-signals", response_model=list[DriftSignalOut])
def list_drift_signals(
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DriftSignalOut]:
    return EvalsRepository(db).drift_signals(user.tenant_id, limit)


# ------------------------------------------------------------------------- #
# Judge calibration (spec §13.2/§13.3; roadmap stage 4b)
# ------------------------------------------------------------------------- #
@router.post("/calibration/examples", response_model=CalibrationExampleOut, status_code=201)
def create_calibration_example(
    body: CalibrationExampleCreate,
    user: User = Depends(_evaluator),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> CalibrationExampleOut:
    example = CalibrationExampleService(db, storage).create_example(
        user.tenant_id,
        user.id,
        rubric_version_id=body.rubric_version_id,
        content=body.content,
        gold_score_json=body.gold_score_json,
        gold_pass_fail=body.gold_pass_fail,
        gold_rationale=body.gold_rationale,
        group_key=body.group_key,
        split=body.split,
        test_set_version=body.test_set_version,
        project_id=body.project_id,
    )
    db.commit()
    return example


@router.post("/calibration/examples/harvest", response_model=CalibrationExampleOut, status_code=201)
def harvest_calibration_example(
    body: CalibrationHarvestRequest,
    user: User = Depends(_evaluator),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> CalibrationExampleOut:
    example = CalibrationExampleService(db, storage).harvest_from_eval_run(
        user.tenant_id,
        user.id,
        eval_run_id=body.eval_run_id,
        split=body.split,
        group_key=body.group_key,
        test_set_version=body.test_set_version,
    )
    db.commit()
    return example


@router.get("/calibration/examples", response_model=list[CalibrationExampleOut])
def list_calibration_examples(
    rubric_version_id: uuid.UUID | None = None,
    split: CalibrationSplit | None = None,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CalibrationExampleOut]:
    stmt = select(CalibrationExample).where(CalibrationExample.tenant_id == user.tenant_id)
    if rubric_version_id is not None:
        stmt = stmt.where(CalibrationExample.rubric_version_id == rubric_version_id)
    if split is not None:
        stmt = stmt.where(CalibrationExample.split == split)
    return list(
        db.scalars(stmt.order_by(CalibrationExample.created_at.desc()).limit(min(limit, 500)))
    )


@router.get("/calibration/suggestions", response_model=list[CalibrationSuggestionOut])
def list_harvest_suggestions(
    limit: int = 50,
    user: User = Depends(_evaluator),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> list[CalibrationSuggestionOut]:
    return CalibrationExampleService(db, storage).harvest_suggestions(
        user.tenant_id, min(limit, 200)
    )


@router.post("/calibration/runs", response_model=CalibrationRunOut, status_code=201)
def create_calibration_run(
    body: CalibrationRunCreate,
    user: User = Depends(_evaluator),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> CalibrationRunOut:
    run = CalibrationRunService(db, storage).create_run(
        user.tenant_id,
        user.id,
        rubric_version_id=body.rubric_version_id,
        split=body.split,
        test_set_version=body.test_set_version,
        project_id=body.project_id,
    )
    db.commit()
    return run


@router.get("/calibration/runs", response_model=list[CalibrationRunOut])
def list_calibration_runs(
    rubric_version_id: uuid.UUID | None = None,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CalibrationRunOut]:
    stmt = select(CalibrationRun).where(CalibrationRun.tenant_id == user.tenant_id)
    if rubric_version_id is not None:
        stmt = stmt.where(CalibrationRun.rubric_version_id == rubric_version_id)
    return list(db.scalars(stmt.order_by(CalibrationRun.created_at.desc()).limit(min(limit, 500))))


@router.get("/calibration/runs/{run_id}", response_model=CalibrationRunOut)
def get_calibration_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> CalibrationRunOut:
    return CalibrationRunService(db, storage).get_run(user.tenant_id, run_id)


@router.get("/calibration/status", response_model=JudgeMonitoringOut)
def judge_monitoring_status(
    suite_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JudgeMonitoringOut:
    """Online judge monitoring for a suite: observed judge fail rate and the
    Rogan-Gladen corrected estimate when a test-split calibration exists."""
    EvalsRepository(db).get_suite(user.tenant_id, suite_id)  # tenant-scoped 404
    return suite_judge_monitoring(db, user.tenant_id, suite_id)
