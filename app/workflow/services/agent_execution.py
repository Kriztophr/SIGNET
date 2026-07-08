"""Agent execution of automated stages (spec §28.7; charter 2026-07-08).

An LLM executes a stage under exactly the constraints a human faces: the parsed
stage contract is the system prompt (contracts are law), the ICM context
manifest supplies everything it may read (layers 0–4), its outputs are
submitted as agent-authored artifacts validated against the contract, and the
normal review/eval gates still decide whether the work advances. No agent may
decide a gate.

Failure philosophy: an agent failure never kills the run. The stage is left
``running`` with the error recorded in ``error_summary`` so a human can take
over — the platform degrades to manual execution, which is the resilience
story in miniature. The only true stops are the budget cap (fail closed on
spend) and an operator cancel (kill switch).
"""

from __future__ import annotations

import re
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform.llm.adapter import get_llm_adapter
from app.platform.llm.budget import LLMUsageLedger
from app.platform.settings.config import get_settings
from app.platform.storage.service import StorageService
from app.workflow.models.entities import (
    ActorType,
    ExecutionMode,
    StageRun,
    StageRunStatus,
    WorkflowRunStatus,
)
from app.workflow.services.artifacts import ArtifactService
from app.workflow.services.runs import StageExecutionCoordinator

logger = structlog.get_logger(__name__)

_ARTIFACT_BLOCK = re.compile(
    r"<<<ARTIFACT role=\"(?P<role>[a-z0-9_.-]+)\">>>\n?(?P<content>.*?)<<<END ARTIFACT>>>",
    re.DOTALL,
)

_OUTPUT_INSTRUCTIONS = """\

## Output format (mandatory)
Produce EVERY output listed under '## Outputs' in the contract. Emit each one
as its own block, exactly in this envelope, with nothing outside the blocks:

<<<ARTIFACT role="<artifact_role>">>>
<the complete content of that artifact>
<<<END ARTIFACT>>>

Rules: one block per required role, roles exactly as named in the contract,
markdown content, no commentary before, between, or after the blocks."""


class AgentStageExecutor:
    def __init__(self, session: Session, storage: StorageService) -> None:
        self._session = session
        self._storage = storage

    def execute_stage(self, stage_run_id: uuid.UUID) -> None:
        # Row lock per spec §28.7: one worker owns the stage while acting on it.
        stage_run = self._session.execute(
            select(StageRun).where(StageRun.id == stage_run_id).with_for_update()
        ).scalar_one_or_none()
        if stage_run is None:
            raise LookupError(f"stage run {stage_run_id} not found")

        stage = stage_run.stage_definition
        run = stage_run.run
        log = logger.bind(
            stage_run_id=str(stage_run_id),
            workflow_run_id=str(run.id),
            stage_key=stage.stage_key,
        )

        # Guards — all silent no-ops except budget, which records why it stopped.
        if stage.execution_mode is not ExecutionMode.automated:
            log.info("agent_execution_skipped", reason="stage is manual")
            return
        if stage_run.status is not StageRunStatus.running:
            log.info("agent_execution_skipped", reason=f"stage is {stage_run.status}")
            return
        if run.status is not WorkflowRunStatus.running:
            # Kill switch honoured: a cancelled/paused run is never acted on.
            log.info("agent_execution_skipped", reason=f"run is {run.status}")
            return

        ledger = LLMUsageLedger(self._session)
        try:
            ledger.ensure_within_budget()
            adapter = get_llm_adapter("executor")
            system, user_content = self._build_prompt(stage_run)
            settings = get_settings()
            result = adapter.complete(
                model=settings.llm_executor_model,
                system=system,
                user_content=user_content,
                max_tokens=settings.llm_max_output_tokens,
            )
            ledger.record(
                run.tenant_id,
                result,
                purpose="executor",
                workflow_run_id=run.id,
                stage_run_id=stage_run.id,
            )
            outputs = self._parse_outputs(stage_run, result.text)
        except Exception as exc:  # noqa: BLE001 — degrade to manual, never kill the run
            stage_run.error_summary = (
                f"agent execution failed ({type(exc).__name__}: {exc}); "
                "stage left running for manual completion"
            )
            self._session.flush()
            log.warning("agent_execution_degraded_to_manual", error=str(exc))
            return

        artifacts = ArtifactService(self._session, self._storage)
        for role, content in outputs.items():
            artifacts.submit(
                stage_run,
                artifact_role=role,
                content=content,
                content_type="text/markdown",
                created_by_type=ActorType.agent,
                created_by_id=None,
            )
        stage_run.error_summary = None
        # Completion runs the normal gate logic — review/eval pauses apply to
        # agent work identically; the agent never advances past a gate itself.
        StageExecutionCoordinator(self._session, self._storage).complete_stage(stage_run)
        log.info("agent_execution_completed", artifact_roles=sorted(outputs))

    # ------------------------------------------------------------------ #
    def _build_prompt(self, stage_run: StageRun) -> tuple[str, str]:
        stage = stage_run.stage_definition
        manifest = stage_run.context_manifest
        if manifest is None:
            raise ValueError("stage run has no context manifest")

        contract_md = stage.contract.source_markdown
        system = (
            "You are the executor of one stage in a governed ICM workflow. The stage "
            "contract below is law: do only what it says, produce exactly the outputs "
            "it names, and stay within its boundaries. Your work will be reviewed by "
            "humans and scored against a rubric before it can advance.\n\n"
            f"{contract_md}\n{_OUTPUT_INSTRUCTIONS}"
        )

        sections = [
            "# Layer 0 — workspace identity\n" + self._read(manifest.layer0_ref),
            "# Layer 1 — routing\n" + self._read(manifest.layer1_ref),
        ]
        for entry in manifest.layer4_inputs_json:
            content = self._read(entry["ref"])
            sections.append(
                f"# Handoff input — {entry['artifact_role']} "
                f"(v{entry['version_number']} from stage '{entry['from_stage_key']}')\n{content}"
            )
        sections.append(
            "Execute the stage contract now against the inputs above and emit the "
            "required artifact blocks."
        )
        return system, "\n\n".join(sections)

    def _read(self, ref: str) -> str:
        try:
            return self._storage.get_text(ref)
        except Exception:  # noqa: BLE001 — a missing layer doc degrades, not crashes
            return "(unavailable)"

    def _parse_outputs(self, stage_run: StageRun, text: str) -> dict[str, str]:
        required = {
            output["role"]
            for output in stage_run.stage_definition.contract.parsed_contract_json["outputs"]
        }
        found = {
            match.group("role"): match.group("content").strip()
            for match in _ARTIFACT_BLOCK.finditer(text)
        }
        missing = sorted(required - set(found))
        if missing:
            raise ValueError(f"model response missing contract outputs: {', '.join(missing)}")
        # Only contract-declared roles are submitted — anything extra is dropped.
        return {role: content for role, content in found.items() if role in required}
