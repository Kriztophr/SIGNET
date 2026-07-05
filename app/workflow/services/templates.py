import uuid

from sqlalchemy.orm import Session

from app.platform.errors import DomainValidationError
from app.platform.storage.service import StorageService
from app.platform.time.clock import utc_now
from app.workflow.contracts.parser import CONTRACT_SCHEMA_VERSION, parse_contract
from app.workflow.models.entities import (
    StageContract,
    StageDefinition,
    WorkflowTemplate,
    WorkflowTemplateVersion,
)
from app.workflow.repositories.workflow import WorkflowRepository
from app.workflow.schemas.workflow import StageDefinitionCreate, TemplateCreate


class WorkflowTemplateService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage
        self._repo = WorkflowRepository(session)

    def create_template(
        self, tenant_id: uuid.UUID, created_by: uuid.UUID, data: TemplateCreate
    ) -> WorkflowTemplate:
        if self._repo.get_template_by_slug(tenant_id, data.slug) is not None:
            raise DomainValidationError(f"template slug {data.slug!r} already exists")
        template = WorkflowTemplate(
            tenant_id=tenant_id,
            project_id=data.project_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            created_by=created_by,
        )
        self._session.add(template)
        self._session.flush()
        return template

    def create_version(
        self,
        tenant_id: uuid.UUID,
        created_by: uuid.UUID,
        template_id: uuid.UUID,
        stages: list[StageDefinitionCreate],
        environment_template_version_id: uuid.UUID | None = None,
    ) -> WorkflowTemplateVersion:
        template = self._repo.get_template(tenant_id, template_id)
        self._validate_stage_layout(stages)

        version = WorkflowTemplateVersion(
            workflow_template_id=template.id,
            version_number=self._repo.next_version_number(template.id),
            environment_template_version_id=environment_template_version_id,
            published_at=utc_now(),
            created_by=created_by,
        )
        self._session.add(version)
        self._session.flush()

        for stage_data in stages:
            # Contracts are law: parsing failures reject the whole version (fail closed).
            parsed = parse_contract(stage_data.contract_markdown)
            contract_ref = (
                f"templates/{template.id}/v{version.version_number}"
                f"/contracts/{stage_data.stage_key}.md"
            )
            self._storage.put_text(contract_ref, stage_data.contract_markdown)
            stage = StageDefinition(
                workflow_template_version_id=version.id,
                stage_key=stage_data.stage_key,
                display_name=stage_data.display_name,
                order_index=stage_data.order_index,
                execution_mode=stage_data.execution_mode,
                review_required=stage_data.review_required,
                eval_required=stage_data.eval_required,
                contract_source_ref=contract_ref,
            )
            self._session.add(stage)
            self._session.flush()
            self._session.add(
                StageContract(
                    stage_definition_id=stage.id,
                    source_markdown=stage_data.contract_markdown,
                    parsed_contract_json=parsed,
                    schema_version=CONTRACT_SCHEMA_VERSION,
                )
            )
        self._session.flush()
        return self._repo.get_version(tenant_id, version.id)

    @staticmethod
    def _validate_stage_layout(stages: list[StageDefinitionCreate]) -> None:
        orders = sorted(stage.order_index for stage in stages)
        if orders != list(range(len(stages))):
            raise DomainValidationError("stage order_index values must be 0..n-1 with no gaps")
        keys = [stage.stage_key for stage in stages]
        if len(keys) != len(set(keys)):
            raise DomainValidationError("stage keys must be unique within a version")
