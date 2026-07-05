import uuid

from sqlalchemy.orm import Session

from app.environment.models.entities import (
    DomainSchema,
    EnvironmentTemplate,
    EnvironmentTemplateVersion,
    PolicyProfile,
    PromptProfile,
    ReferenceBundle,
    SetupQuestionnaire,
    ToolProfile,
    WorkspaceBlueprint,
)
from app.environment.repositories.environment import EnvironmentRepository
from app.platform.errors import DomainValidationError
from app.platform.events.bus import get_event_bus
from app.platform.storage.service import StorageService
from app.platform.time.clock import utc_now


class EnvironmentTemplateService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = EnvironmentRepository(session)

    def create_template(
        self,
        tenant_id: uuid.UUID,
        created_by: uuid.UUID,
        *,
        name: str,
        slug: str,
        description: str = "",
        project_id: uuid.UUID | None = None,
    ) -> EnvironmentTemplate:
        if self._repo.get_template_by_slug(tenant_id, slug) is not None:
            raise DomainValidationError(f"environment template slug {slug!r} already exists")
        template = EnvironmentTemplate(
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            slug=slug,
            description=description,
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
        *,
        prompt_profiles: list[dict],
        tool_profiles: list[dict],
        policy_profiles: list[dict],
        domain_schemas: list[dict],
        workspace_blueprint_ref: str | None = None,
    ) -> EnvironmentTemplateVersion:
        template = self._repo.get_template(tenant_id, template_id)
        version = EnvironmentTemplateVersion(
            environment_template_id=template.id,
            version_number=self._repo.next_version_number(template.id),
            workspace_blueprint_ref=workspace_blueprint_ref,
            published_at=utc_now(),
            created_by=created_by,
        )
        self._session.add(version)
        self._session.flush()

        for profile in prompt_profiles:
            self._session.add(
                PromptProfile(
                    environment_template_version_id=version.id,
                    name=profile["name"],
                    instructions_json=profile.get("instructions", {}),
                    style_ref=profile.get("style_ref"),
                )
            )
        for profile in tool_profiles:
            self._session.add(
                ToolProfile(
                    environment_template_version_id=version.id,
                    name=profile["name"],
                    allowed_tools_json=profile.get("allowed_tools", []),
                    adapter_settings_json=profile.get("adapter_settings", {}),
                )
            )
        for profile in policy_profiles:
            self._session.add(
                PolicyProfile(
                    environment_template_version_id=version.id,
                    name=profile["name"],
                    default_gate_settings_json=profile.get("default_gate_settings", {}),
                    default_policy_refs_json=profile.get("default_policy_refs", []),
                )
            )
        for schema in domain_schemas:
            self._session.add(
                DomainSchema(
                    environment_template_version_id=version.id,
                    name=schema["name"],
                    schema_json=schema["schema_definition"],
                )
            )
        self._session.flush()
        get_event_bus().publish(
            "environment.template.versioned",
            {
                "environment_template_id": str(template.id),
                "environment_template_version_id": str(version.id),
                "version_number": version.version_number,
            },
        )
        return self._repo.get_version(tenant_id, version.id)


class ReferenceBundleService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage
        self._repo = EnvironmentRepository(session)

    def create_bundle(
        self,
        tenant_id: uuid.UUID,
        version_id: uuid.UUID,
        *,
        name: str,
        bundle_type: str,
        content: str,
        manifest: dict,
    ) -> ReferenceBundle:
        version = self._repo.get_version(tenant_id, version_id)
        key = (
            f"environments/{version.environment_template_id}"
            f"/v{version.version_number}/bundles/{name}"
        )
        storage_uri = self._storage.put_text(key, content)
        bundle = ReferenceBundle(
            environment_template_version_id=version.id,
            name=name,
            bundle_type=bundle_type,
            storage_uri=storage_uri,
            manifest_json=manifest,
        )
        self._session.add(bundle)
        self._session.flush()
        return bundle


class WorkspaceBlueprintService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = EnvironmentRepository(session)

    def create_blueprint(
        self,
        tenant_id: uuid.UUID,
        version_id: uuid.UUID,
        *,
        name: str,
        blueprint: dict,
    ) -> WorkspaceBlueprint:
        version = self._repo.get_version(tenant_id, version_id)
        record = WorkspaceBlueprint(
            environment_template_version_id=version.id,
            name=name,
            blueprint_json=blueprint,
        )
        self._session.add(record)
        self._session.flush()
        version.workspace_blueprint_ref = str(record.id)
        self._session.flush()
        return record


class DomainSetupService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = EnvironmentRepository(session)

    def create_questionnaire(
        self,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID,
        *,
        name: str,
        questions: list,
        answers: dict,
        project_id: uuid.UUID | None = None,
    ) -> SetupQuestionnaire:
        template = self._repo.get_template(tenant_id, template_id)
        questionnaire = SetupQuestionnaire(
            tenant_id=tenant_id,
            project_id=project_id,
            environment_template_id=template.id,
            name=name,
            questions_json=questions,
            answers_json=answers,
        )
        self._session.add(questionnaire)
        self._session.flush()
        return questionnaire
