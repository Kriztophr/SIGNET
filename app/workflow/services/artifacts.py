import uuid

from sqlalchemy.orm import Session

from app.platform.errors import InvalidStateError
from app.platform.events.bus import get_event_bus
from app.platform.storage.service import StorageService
from app.workflow.models.entities import (
    ActorType,
    Artifact,
    StageRun,
    StageRunStatus,
)
from app.workflow.repositories.workflow import WorkflowRepository
from app.workflow.services.workspace import artifact_key, extension_for


class ArtifactService:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage
        self._repo = WorkflowRepository(session)

    def submit(
        self,
        stage_run: StageRun,
        *,
        artifact_role: str,
        content: str,
        content_type: str,
        created_by_type: ActorType,
        created_by_id: uuid.UUID | None,
        is_human_edited: bool = False,
        source_artifact_id: uuid.UUID | None = None,
        allowed_states: tuple[StageRunStatus, ...] = (StageRunStatus.running,),
    ) -> Artifact:
        if stage_run.status not in allowed_states:
            raise InvalidStateError(
                f"artifacts cannot be submitted to a stage in state {stage_run.status}"
            )
        version = self._repo.next_artifact_version(stage_run.id, artifact_role)
        key = artifact_key(
            stage_run.workflow_run_id,
            stage_run.stage_definition,
            artifact_role,
            version,
            extension_for(content_type),
        )
        storage_uri = self._storage.put_text(key, content)
        artifact = Artifact(
            workflow_run_id=stage_run.workflow_run_id,
            stage_run_id=stage_run.id,
            artifact_role=artifact_role,
            storage_uri=storage_uri,
            content_type=content_type,
            version_number=version,
            is_human_edited=is_human_edited,
            source_artifact_id=source_artifact_id,
            created_by_type=created_by_type,
            created_by_id=created_by_id,
        )
        self._session.add(artifact)
        self._session.flush()
        get_event_bus().publish(
            "workflow.artifact.created",
            {
                "artifact_id": str(artifact.id),
                "workflow_run_id": str(stage_run.workflow_run_id),
                "stage_run_id": str(stage_run.id),
                "artifact_role": artifact_role,
                "version_number": version,
            },
        )
        return artifact

    def get_content(self, artifact: Artifact) -> str:
        return self._storage.get_text(artifact.storage_uri)
