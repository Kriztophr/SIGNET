import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.environment.repositories.environment import EnvironmentRepository
from app.environment.schemas.environment import (
    PromotionCreate,
    PromotionOut,
    ReferenceBundleCreate,
    ReferenceBundleOut,
    TemplateCreate,
    TemplateOut,
    VersionCreate,
    VersionOut,
    WorkspaceBlueprintCreate,
    WorkspaceBlueprintOut,
)
from app.environment.services.promotion import EnvironmentPromotionService
from app.environment.services.templates import (
    EnvironmentTemplateService,
    ReferenceBundleService,
    WorkspaceBlueprintService,
)
from app.platform.auth.dependencies import get_current_user, require_roles
from app.platform.auth.models import Role, User
from app.platform.db.session import get_db
from app.platform.storage.service import StorageService, get_storage

router = APIRouter(prefix="/environment", tags=["environment"])

_manager = require_roles(Role.environment_manager)


@router.post("/templates", response_model=TemplateOut, status_code=201)
def create_template(
    body: TemplateCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> TemplateOut:
    template = EnvironmentTemplateService(db).create_template(
        user.tenant_id,
        user.id,
        name=body.name,
        slug=body.slug,
        description=body.description,
        project_id=body.project_id,
    )
    db.commit()
    return template


@router.get("/templates/{template_id}", response_model=TemplateOut)
def get_template(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TemplateOut:
    return EnvironmentRepository(db).get_template(user.tenant_id, template_id)


@router.post("/templates/{template_id}/versions", response_model=VersionOut, status_code=201)
def create_version(
    template_id: uuid.UUID,
    body: VersionCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> VersionOut:
    version = EnvironmentTemplateService(db).create_version(
        user.tenant_id,
        user.id,
        template_id,
        prompt_profiles=[p.model_dump() for p in body.prompt_profiles],
        tool_profiles=[p.model_dump() for p in body.tool_profiles],
        policy_profiles=[p.model_dump() for p in body.policy_profiles],
        domain_schemas=[s.model_dump() for s in body.domain_schemas],
        workspace_blueprint_ref=body.workspace_blueprint_ref,
    )
    db.commit()
    return version


@router.get("/versions/{version_id}", response_model=VersionOut)
def get_version(
    version_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VersionOut:
    return EnvironmentRepository(db).get_version(user.tenant_id, version_id)


@router.post("/reference-bundles", response_model=ReferenceBundleOut, status_code=201)
def create_reference_bundle(
    body: ReferenceBundleCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> ReferenceBundleOut:
    bundle = ReferenceBundleService(db, storage).create_bundle(
        user.tenant_id,
        body.environment_template_version_id,
        name=body.name,
        bundle_type=body.bundle_type,
        content=body.content,
        manifest=body.manifest,
    )
    db.commit()
    return bundle


@router.get("/reference-bundles/{bundle_id}", response_model=ReferenceBundleOut)
def get_reference_bundle(
    bundle_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReferenceBundleOut:
    return EnvironmentRepository(db).get_reference_bundle(user.tenant_id, bundle_id)


@router.post("/workspace-blueprints", response_model=WorkspaceBlueprintOut, status_code=201)
def create_workspace_blueprint(
    body: WorkspaceBlueprintCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> WorkspaceBlueprintOut:
    blueprint = WorkspaceBlueprintService(db).create_blueprint(
        user.tenant_id,
        body.environment_template_version_id,
        name=body.name,
        blueprint=body.blueprint,
    )
    db.commit()
    return blueprint


@router.get("/workspace-blueprints/{blueprint_id}", response_model=WorkspaceBlueprintOut)
def get_workspace_blueprint(
    blueprint_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceBlueprintOut:
    return EnvironmentRepository(db).get_workspace_blueprint(user.tenant_id, blueprint_id)


@router.post("/promotions", response_model=PromotionOut, status_code=201)
def create_promotion(
    body: PromotionCreate,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> PromotionOut:
    promotion = EnvironmentPromotionService(db).request_promotion(
        user.tenant_id,
        user.id,
        version_id=body.environment_template_version_id,
        requirements=body.requirements,
        project_id=body.project_id,
    )
    db.commit()
    return promotion


@router.get("/promotions", response_model=list[PromotionOut])
def list_promotions(
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PromotionOut]:
    return EnvironmentRepository(db).list_promotions(user.tenant_id, limit)


@router.get("/promotions/{promotion_id}", response_model=PromotionOut)
def get_promotion(
    promotion_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PromotionOut:
    return EnvironmentRepository(db).get_promotion(user.tenant_id, promotion_id)


@router.post("/promotions/{promotion_id}/approve", response_model=PromotionOut)
def approve_promotion(
    promotion_id: uuid.UUID,
    user: User = Depends(_manager),
    db: Session = Depends(get_db),
) -> PromotionOut:
    promotion = EnvironmentPromotionService(db).approve(user.tenant_id, promotion_id, user)
    db.commit()
    return promotion
