import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.platform.auth.dependencies import get_current_user, require_roles
from app.platform.auth.models import Role, User
from app.platform.db.session import get_db
from app.platform.observability.correlation import get_correlation_id
from app.platform.storage.service import StorageService, get_storage
from app.workflow.models.entities import ActorType
from app.workflow.repositories.workflow import WorkflowRepository
from app.workflow.schemas.workflow import (
    ArtifactOut,
    ArtifactSubmit,
    ContextManifestOut,
    RunCreate,
    RunOut,
    StageFailRequest,
    StageRunOut,
    TemplateCreate,
    TemplateOut,
    VersionCreate,
    VersionOut,
)
from app.workflow.services.artifacts import ArtifactService
from app.workflow.services.runs import StageExecutionCoordinator, WorkflowRunService
from app.workflow.services.templates import WorkflowTemplateService

router = APIRouter(prefix="/workflow", tags=["workflow"])

_operator = require_roles(Role.operator)


@router.post("/templates", response_model=TemplateOut, status_code=201)
def create_template(
    body: TemplateCreate,
    user: User = Depends(_operator),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> TemplateOut:
    template = WorkflowTemplateService(db, storage).create_template(user.tenant_id, user.id, body)
    db.commit()
    return template


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TemplateOut]:
    return WorkflowRepository(db).list_templates(user.tenant_id, limit)


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RunOut]:
    return WorkflowRepository(db).list_runs(user.tenant_id, limit)


@router.get("/templates/{template_id}", response_model=TemplateOut)
def get_template(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TemplateOut:
    return WorkflowRepository(db).get_template(user.tenant_id, template_id)


@router.get("/templates/{template_id}/versions", response_model=list[VersionOut])
def list_versions(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VersionOut]:
    return WorkflowRepository(db).list_versions(user.tenant_id, template_id)


@router.post("/templates/{template_id}/versions", response_model=VersionOut, status_code=201)
def create_version(
    template_id: uuid.UUID,
    body: VersionCreate,
    user: User = Depends(_operator),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> VersionOut:
    version = WorkflowTemplateService(db, storage).create_version(
        user.tenant_id,
        user.id,
        template_id,
        body.stages,
        body.environment_template_version_id,
    )
    db.commit()
    return version


@router.get("/templates/{template_id}/versions/{version_id}", response_model=VersionOut)
def get_version(
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VersionOut:
    version = WorkflowRepository(db).get_version(user.tenant_id, version_id)
    if version.workflow_template_id != template_id:
        from app.platform.errors import NotFoundError

        raise NotFoundError(f"version {version_id} does not belong to template {template_id}")
    return version


@router.post("/runs", response_model=RunOut, status_code=201)
def create_run(
    body: RunCreate,
    user: User = Depends(_operator),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> RunOut:
    run = WorkflowRunService(db, storage).create_and_start(
        tenant_id=user.tenant_id,
        triggered_by=user.id,
        version_id=body.workflow_template_version_id,
        project_id=body.project_id,
        correlation_id=get_correlation_id(),
    )
    db.commit()
    return run


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunOut:
    return WorkflowRepository(db).get_run(user.tenant_id, run_id)


@router.get("/runs/{run_id}/stages", response_model=list[StageRunOut])
def get_run_stages(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StageRunOut]:
    repo = WorkflowRepository(db)
    run = repo.get_run(user.tenant_id, run_id)
    return repo.stage_runs_for_run(run.id)


@router.get("/stage-runs/{stage_run_id}", response_model=StageRunOut)
def get_stage_run(
    stage_run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StageRunOut:
    return WorkflowRepository(db).get_stage_run(user.tenant_id, stage_run_id)


@router.get("/stage-runs/{stage_run_id}/context-manifest", response_model=ContextManifestOut)
def get_context_manifest(
    stage_run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContextManifestOut:
    return WorkflowRepository(db).get_context_manifest(user.tenant_id, stage_run_id)


@router.get("/stage-runs/{stage_run_id}/artifacts", response_model=list[ArtifactOut])
def list_stage_artifacts(
    stage_run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ArtifactOut]:
    repo = WorkflowRepository(db)
    stage_run = repo.get_stage_run(user.tenant_id, stage_run_id)
    return repo.artifacts_for_stage_run(stage_run.id)


@router.post("/stage-runs/{stage_run_id}/artifacts", response_model=ArtifactOut, status_code=201)
def submit_artifact(
    stage_run_id: uuid.UUID,
    body: ArtifactSubmit,
    user: User = Depends(_operator),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> ArtifactOut:
    stage_run = WorkflowRepository(db).get_stage_run(user.tenant_id, stage_run_id)
    artifact = ArtifactService(db, storage).submit(
        stage_run,
        artifact_role=body.artifact_role,
        content=body.content,
        content_type=body.content_type,
        created_by_type=ActorType.human,
        created_by_id=user.id,
    )
    db.commit()
    return artifact


@router.post("/stage-runs/{stage_run_id}/complete", response_model=RunOut)
def complete_stage(
    stage_run_id: uuid.UUID,
    user: User = Depends(_operator),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> RunOut:
    stage_run = WorkflowRepository(db).get_stage_run(user.tenant_id, stage_run_id)
    run = StageExecutionCoordinator(db, storage).complete_stage(stage_run)
    db.commit()
    return run


@router.post("/stage-runs/{stage_run_id}/fail", response_model=RunOut)
def fail_stage(
    stage_run_id: uuid.UUID,
    body: StageFailRequest,
    user: User = Depends(_operator),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> RunOut:
    stage_run = WorkflowRepository(db).get_stage_run(user.tenant_id, stage_run_id)
    run = StageExecutionCoordinator(db, storage).fail_stage(stage_run, body.error_summary)
    db.commit()
    return run


@router.get("/artifacts/{artifact_id}", response_model=ArtifactOut)
def get_artifact(
    artifact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ArtifactOut:
    return WorkflowRepository(db).get_artifact(user.tenant_id, artifact_id)


@router.get("/artifacts/{artifact_id}/content")
def get_artifact_content(
    artifact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> Response:
    artifact = WorkflowRepository(db).get_artifact(user.tenant_id, artifact_id)
    content = ArtifactService(db, storage).get_content(artifact)
    return Response(content=content, media_type=artifact.content_type)
