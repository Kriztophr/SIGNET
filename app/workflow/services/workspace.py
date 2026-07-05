"""Workspace materialization and context assembly.

Materializes each run's workspace in object storage with the same shape as the
reference ICM workspace (docs/examples/icm-workflow): an identity layer, a routing
layer, and per-stage directories holding the contract, references, and artifacts.
Context manifests record exactly which layer documents a stage run sees.
"""

import uuid

from app.platform.storage.service import StorageService
from app.workflow.models.entities import (
    ContextManifest,
    StageDefinition,
    StageRun,
    WorkflowRun,
    WorkflowTemplateVersion,
)

# Rough chars-per-token divisor for context-size estimates.
_CHARS_PER_TOKEN = 4


def run_root(run_id: uuid.UUID) -> str:
    return f"runs/{run_id}"


def identity_key(run_id: uuid.UUID) -> str:
    return f"{run_root(run_id)}/00_identity/workspace_identity.md"


def routing_key(run_id: uuid.UUID) -> str:
    return f"{run_root(run_id)}/01_routing/router.md"


def stage_dir(run_id: uuid.UUID, stage: StageDefinition) -> str:
    n = stage.order_index
    return f"{run_root(run_id)}/{n + 2:02d}_stage_{n + 1}_{stage.stage_key}"


def stage_contract_key(run_id: uuid.UUID, stage: StageDefinition) -> str:
    return f"{stage_dir(run_id, stage)}/03_contract/contract.md"


def artifact_key(
    run_id: uuid.UUID, stage: StageDefinition, role: str, version: int, ext: str
) -> str:
    return f"{stage_dir(run_id, stage)}/05_artifacts/{role}_v{version}{ext}"


_EXTENSIONS = {
    "text/markdown": ".md",
    "text/plain": ".txt",
    "application/json": ".json",
}


def extension_for(content_type: str) -> str:
    return _EXTENSIONS.get(content_type, ".bin")


class WorkspaceMaterializationService:
    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    def materialize_run(self, run: WorkflowRun, version: WorkflowTemplateVersion) -> None:
        """Write the run's layer-0 identity and layer-1 routing documents."""
        template = version.template
        identity = (
            f"# Workspace identity — run {run.id}\n\n"
            f"| Field | Value |\n|---|---|\n"
            f"| Workflow template | {template.name} (`{template.slug}`) |\n"
            f"| Template version | {version.version_number} |\n"
            f"| Run ID | `{run.id}` |\n"
            f"| Tenant | `{run.tenant_id}` |\n"
            f"| Correlation ID | `{run.correlation_id or ''}` |\n\n"
            f"{template.description}\n\n"
            "This workspace executes one stage at a time. The active stage loads only "
            "its own contract, the stable references, and the artifacts handed off by "
            "the previous stage.\n"
        )
        self._storage.put_text(identity_key(run.id), identity)

        rows = "\n".join(
            f"| {s.order_index + 1} | `{s.stage_key}` | {s.display_name} "
            f"| {'yes' if s.review_required else 'no'} | {'yes' if s.eval_required else 'no'} |"
            for s in version.stages
        )
        routing = (
            f"# Stage router — run {run.id}\n\n"
            "Stages execute strictly in order. A stage may not start until the previous "
            "stage completed and, where required, passed review.\n\n"
            "| # | Stage key | Stage | Review gate | Eval gate |\n"
            "|---|-----------|-------|-------------|----------|\n"
            f"{rows}\n\n"
            "Handoff rule: on completion, the latest artifact of each contracted output "
            "role becomes a layer-4 input of the next stage's context manifest.\n"
        )
        self._storage.put_text(routing_key(run.id), routing)

    def materialize_stage(
        self, run: WorkflowRun, stage: StageDefinition, contract_markdown: str
    ) -> str:
        """Copy the stage contract into the run workspace; returns its layer-2 key."""
        key = stage_contract_key(run.id, stage)
        self._storage.put_text(key, contract_markdown)
        return key


class ContextAssemblyService:
    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    def build_manifest(
        self,
        stage_run: StageRun,
        run: WorkflowRun,
        layer2_key: str,
        layer3_inputs: list[dict],
        layer4_inputs: list[dict],
    ) -> ContextManifest:
        layer0 = identity_key(run.id)
        layer1 = routing_key(run.id)
        estimate = sum(len(self._storage.get_text(key)) for key in (layer0, layer1, layer2_key))
        estimate += sum(int(item.get("size_bytes", 0)) for item in layer3_inputs)
        estimate += sum(int(item.get("size_bytes", 0)) for item in layer4_inputs)
        return ContextManifest(
            stage_run_id=stage_run.id,
            layer0_ref=layer0,
            layer1_ref=layer1,
            layer2_ref=layer2_key,
            layer3_inputs_json=layer3_inputs,
            layer4_inputs_json=layer4_inputs,
            token_estimate=estimate // _CHARS_PER_TOKEN,
        )
