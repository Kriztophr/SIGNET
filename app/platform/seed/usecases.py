"""Seed four enterprise use-case starter packs.

Each pack is a self-contained, ready-to-run governed workflow:

* an **environment template + version** (prompt / tool / policy profiles + a
  domain schema for the deliverable),
* a **workflow template + version** whose stages carry ICM contracts and the
  right human-review / eval gates, bound to that environment version,
* a **rubric + version** whose criteria match the domain, and
* an **eval suite** targeting stage runs.

Usage (inside the api container or a dev shell)::

    ICM_SEED_ADMIN_EMAIL=you@example.com python -m app.platform.seed.usecases

Idempotent: a use case whose workflow-template slug already exists is skipped,
so re-running only fills in what is missing. Everything is created inside the
admin user's tenant, authored as that user.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from app.environment.services.templates import EnvironmentTemplateService
from app.evals.models.entities import EvalTargetType
from app.evals.rubrics.service import RubricService
from app.evals.services.suites import EvalSuiteService
from app.platform.auth.service import AuthService
from app.platform.db.session import get_sessionmaker
from app.platform.storage.service import get_storage
from app.workflow.models.entities import ExecutionMode
from app.workflow.schemas.workflow import StageDefinitionCreate, TemplateCreate
from app.workflow.services.templates import WorkflowTemplateService

SCORE_SCALE = {"min": 0, "max": 5}


# --------------------------------------------------------------------------- #
# Contract authoring helper
# --------------------------------------------------------------------------- #
@dataclass
class Contract:
    identity: str
    outputs: list[tuple[str, str, str]]  # (role, filename, description)
    inputs: list[str] = field(default_factory=list)
    procedure: list[str] = field(default_factory=list)
    definition_of_done: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)

    def to_markdown(self, title: str) -> str:
        lines = [f"# Contract: {title}", "", "## Identity", self.identity.strip(), ""]

        def section(heading: str, items: list[str]) -> None:
            if not items:
                return
            lines.append(f"## {heading}")
            lines.extend(f"- {item}" for item in items)
            lines.append("")

        section("Inputs", self.inputs)
        if self.procedure:
            lines.append("## Procedure")
            lines.extend(f"{i}. {step}" for i, step in enumerate(self.procedure, start=1))
            lines.append("")
        lines.append("## Outputs")
        for role, filename, desc in self.outputs:
            lines.append(f"- {role}: {filename} — {desc}")
        lines.append("")
        section("Definition of done", self.definition_of_done)
        section("Failure modes", self.failure_modes)
        return "\n".join(lines).strip() + "\n"


@dataclass
class Stage:
    stage_key: str
    display_name: str
    contract: Contract
    review_required: bool = False
    eval_required: bool = False


@dataclass
class UseCase:
    slug: str
    name: str
    description: str
    prompt_profile: dict
    tool_profile: dict
    policy_profile: dict
    domain_schema: dict
    rubric_name: str
    rubric_criteria: list[dict]
    rubric_pass_min_total: float
    suite_name: str
    suite_min_reviewers: int
    suite_cases: list[dict]
    stages: list[Stage]


# --------------------------------------------------------------------------- #
# The four enterprise use cases
# --------------------------------------------------------------------------- #
USE_CASES: list[UseCase] = [
    # 1) Regulated financial analyst report ---------------------------------- #
    UseCase(
        slug="financial-analyst-report",
        name="Regulated financial analyst report",
        description=(
            "Draft an investment/credit memo under a mandatory compliance-review gate "
            "and a rubric eval for factual accuracy and citation integrity before publication."
        ),
        prompt_profile={
            "name": "analyst-drafting",
            "instructions": {
                "voice": "precise, hedged, regulator-facing",
                "must": [
                    "cite every figure",
                    "flag material assumptions",
                    "no forward-looking guarantees",
                ],
            },
        },
        tool_profile={
            "name": "market-data-readonly",
            "allowed_tools": ["market_data.read", "filings.search", "calculator"],
            "adapter_settings": {"pii": "deny", "network": "allowlist"},
        },
        policy_profile={
            "name": "compliance-gated",
            "default_gate_settings": {"require_review": True, "require_eval": True},
            "default_policy_refs": [
                "policy://compliance/disclosure",
                "policy://compliance/citations",
            ],
        },
        domain_schema={
            "name": "investment_memo",
            "schema_definition": {
                "type": "object",
                "required": ["thesis", "figures", "risks", "citations"],
                "properties": {
                    "thesis": {"type": "string"},
                    "figures": {"type": "array"},
                    "risks": {"type": "array"},
                    "citations": {"type": "array", "minItems": 1},
                },
            },
        },
        rubric_name="Memo accuracy & citations",
        rubric_criteria=[
            {
                "key": "factual_accuracy",
                "description": "Every figure is correct and sourced",
                "weight": 3,
            },
            {"key": "citation_integrity", "description": "Claims trace to a citation", "weight": 2},
            {"key": "risk_disclosure", "description": "Material risks are disclosed", "weight": 2},
            {"key": "clarity", "description": "Readable by the target committee", "weight": 1},
        ],
        rubric_pass_min_total=28,  # of max 40
        suite_name="Memo quality gate",
        suite_min_reviewers=2,
        suite_cases=[
            {
                "name": "accuracy",
                "prompt_or_instruction": "Verify each figure against its cited source.",
            },
            {
                "name": "disclosure",
                "prompt_or_instruction": "Confirm all material risks are disclosed.",
            },
        ],
        stages=[
            Stage(
                "scope",
                "Scope",
                Contract(
                    identity=(
                        "You are a lead analyst. Your only job in this stage is to fix the "
                        "memo's mandate and boundaries."
                    ),
                    inputs=["engagement brief", "target entity identifier"],
                    procedure=[
                        "Restate the decision the memo must support",
                        "List in-scope instruments and the as-of date",
                        "Name the review committee",
                    ],
                    outputs=[
                        (
                            "scope_brief",
                            "scope_brief.md",
                            "one-page mandate, boundaries, and as-of date",
                        )
                    ],
                    definition_of_done=["the decision, entity, and as-of date are unambiguous"],
                    failure_modes=["scope creep into unrelated instruments", "missing as-of date"],
                ),
            ),
            Stage(
                "draft",
                "Draft memo",
                Contract(
                    identity=(
                        "You are an analyst drafting the memo strictly within the signed scope."
                    ),
                    inputs=["signed scope_brief.md", "market data (read-only)"],
                    procedure=[
                        "Build the thesis",
                        "Attach every figure to a citation",
                        "Enumerate material risks",
                    ],
                    outputs=[
                        ("draft_memo", "draft_memo.md", "full memo with inline citations"),
                        ("figure_log", "figure_log.md", "each figure mapped to its source"),
                    ],
                    definition_of_done=[
                        "every figure in the memo appears in figure_log with a source"
                    ],
                    failure_modes=["uncited figures", "forward-looking guarantees"],
                ),
            ),
            Stage(
                "compliance_review",
                "Compliance review",
                Contract(
                    identity=(
                        "You are a compliance reviewer. You approve, edit, or reject the "
                        "draft against disclosure policy."
                    ),
                    inputs=["draft_memo.md", "figure_log.md"],
                    procedure=[
                        "Check every claim against the citation",
                        "Verify required disclosures",
                        "Record a decision",
                    ],
                    outputs=[("review_note", "review_note.md", "decision and any mandated edits")],
                    definition_of_done=["a recorded approve/edit/reject decision with rationale"],
                    failure_modes=["approving an uncited material claim"],
                ),
                review_required=True,
            ),
            Stage(
                "quality_eval",
                "Quality eval",
                Contract(
                    identity=(
                        "You are the eval harness gate. This stage exists so the memo is "
                        "scored against the rubric before release."
                    ),
                    inputs=["reviewed draft_memo.md"],
                    procedure=[
                        "Submit the memo for rubric scoring",
                        "Block on a failing weighted total",
                    ],
                    outputs=[
                        ("eval_target", "eval_target.md", "the memo snapshot scored by the rubric")
                    ],
                    definition_of_done=["a passing rubric decision is on record"],
                    failure_modes=["releasing below the pass threshold"],
                ),
                eval_required=True,
            ),
            Stage(
                "finalize",
                "Finalize",
                Contract(
                    identity=(
                        "You are the publisher. You package the approved, evaluated memo "
                        "for the committee."
                    ),
                    inputs=["approved and passing draft_memo.md"],
                    procedure=["Freeze the version", "Attach the review note and eval decision"],
                    outputs=[
                        ("final_memo", "final_memo.md", "committee-ready, evidence-stamped memo")
                    ],
                    definition_of_done=["final memo carries its review and eval evidence"],
                    failure_modes=["publishing a version that skipped a gate"],
                ),
            ),
        ],
    ),
    # 2) Legal contract drafting & review ------------------------------------ #
    UseCase(
        slug="legal-contract-review",
        name="Legal contract drafting & review",
        description=(
            "Generate contract clauses and a redline behind a required lawyer-review gate and a "
            "risk/completeness eval, emphasising human override before execution."
        ),
        prompt_profile={
            "name": "contract-drafting",
            "instructions": {
                "voice": "plain-English legal",
                "must": ["define every defined term", "no unbounded indemnities"],
            },
        },
        tool_profile={
            "name": "clause-library",
            "allowed_tools": ["clause_library.search", "precedent.lookup"],
            "adapter_settings": {"jurisdiction": "required"},
        },
        policy_profile={
            "name": "counsel-gated",
            "default_gate_settings": {"require_review": True, "require_eval": True},
            "default_policy_refs": ["policy://legal/redline", "policy://legal/risk-caps"],
        },
        domain_schema={
            "name": "contract_package",
            "schema_definition": {
                "type": "object",
                "required": ["clauses", "defined_terms", "risk_flags"],
                "properties": {
                    "clauses": {"type": "array"},
                    "defined_terms": {"type": "array"},
                    "risk_flags": {"type": "array"},
                },
            },
        },
        rubric_name="Contract risk & completeness",
        rubric_criteria=[
            {"key": "risk_exposure", "description": "No uncapped or one-sided risk", "weight": 3},
            {"key": "completeness", "description": "All required clauses present", "weight": 2},
            {
                "key": "term_consistency",
                "description": "Defined terms used consistently",
                "weight": 2,
            },
            {"key": "readability", "description": "Plain-English clarity", "weight": 1},
        ],
        rubric_pass_min_total=28,
        suite_name="Redline risk gate",
        suite_min_reviewers=1,
        suite_cases=[
            {
                "name": "risk",
                "prompt_or_instruction": "Flag any uncapped indemnity or one-sided liability.",
            },
            {
                "name": "completeness",
                "prompt_or_instruction": "Confirm all required clauses are present.",
            },
        ],
        stages=[
            Stage(
                "intake",
                "Intake",
                Contract(
                    identity=(
                        "You are contracts counsel intake. You capture the deal shape "
                        "and governing law."
                    ),
                    inputs=["deal term sheet"],
                    procedure=[
                        "Record parties, governing law, and deal type",
                        "List required clause families",
                    ],
                    outputs=[
                        (
                            "deal_brief",
                            "deal_brief.md",
                            "parties, jurisdiction, and required clauses",
                        )
                    ],
                    definition_of_done=["governing law and required clause families are fixed"],
                    failure_modes=["missing governing law"],
                ),
            ),
            Stage(
                "draft_clauses",
                "Draft clauses",
                Contract(
                    identity=(
                        "You are a drafter assembling clauses from the library within "
                        "the deal brief."
                    ),
                    inputs=["deal_brief.md", "clause library"],
                    procedure=[
                        "Assemble required clauses",
                        "Define every defined term",
                        "Produce a redline vs. precedent",
                    ],
                    outputs=[
                        ("draft_contract", "draft_contract.md", "assembled contract"),
                        ("redline", "redline.md", "changes vs. precedent"),
                    ],
                    definition_of_done=["every defined term is defined and used consistently"],
                    failure_modes=["unbounded indemnities", "undefined terms"],
                ),
            ),
            Stage(
                "lawyer_review",
                "Lawyer review",
                Contract(
                    identity=(
                        "You are the responsible lawyer. You approve, edit, or reject "
                        "the draft — your override is final."
                    ),
                    inputs=["draft_contract.md", "redline.md"],
                    procedure=[
                        "Assess risk exposure",
                        "Edit or reject unacceptable terms",
                        "Record the decision",
                    ],
                    outputs=[
                        (
                            "counsel_decision",
                            "counsel_decision.md",
                            "approve/edit/reject with rationale",
                        )
                    ],
                    definition_of_done=["a recorded counsel decision"],
                    failure_modes=["approving uncapped risk"],
                ),
                review_required=True,
            ),
            Stage(
                "risk_eval",
                "Risk eval",
                Contract(
                    identity=(
                        "You are the eval gate. The contract is scored for risk and "
                        "completeness before execution."
                    ),
                    inputs=["reviewed draft_contract.md"],
                    procedure=["Submit for rubric scoring", "Block on failing risk score"],
                    outputs=[
                        ("eval_target", "eval_target.md", "contract snapshot scored by the rubric")
                    ],
                    definition_of_done=["a passing rubric decision is on record"],
                    failure_modes=["executing below threshold"],
                ),
                eval_required=True,
            ),
            Stage(
                "execute",
                "Execute",
                Contract(
                    identity=(
                        "You are the closer. You package the approved, evaluated "
                        "contract for signature."
                    ),
                    inputs=["approved and passing draft_contract.md"],
                    procedure=["Freeze the version", "Attach counsel decision and eval evidence"],
                    outputs=[
                        (
                            "execution_package",
                            "execution_package.md",
                            "signature-ready package with evidence",
                        )
                    ],
                    definition_of_done=["package carries counsel and eval evidence"],
                    failure_modes=["sending an unreviewed version to signature"],
                ),
            ),
        ],
    ),
    # 3) Customer-support policy responses ----------------------------------- #
    UseCase(
        slug="support-policy-response",
        name="Customer-support policy responses",
        description=(
            "High-volume macro/response generation graded against a tone+accuracy rubric with "
            "sampling-based review, emphasising throughput and drift detection."
        ),
        prompt_profile={
            "name": "support-voice",
            "instructions": {
                "voice": "warm, concise, on-policy",
                "must": ["never promise refunds outside policy"],
            },
        },
        tool_profile={
            "name": "kb-readonly",
            "allowed_tools": ["kb.search", "order.lookup"],
            "adapter_settings": {"pii": "mask"},
        },
        policy_profile={
            "name": "sampling-gated",
            "default_gate_settings": {
                "require_review": True,
                "require_eval": True,
                "review_sampling_rate": 0.2,
            },
            "default_policy_refs": ["policy://support/refunds", "policy://support/tone"],
        },
        domain_schema={
            "name": "support_response",
            "schema_definition": {
                "type": "object",
                "required": ["answer", "policy_refs", "tone"],
                "properties": {
                    "answer": {"type": "string"},
                    "policy_refs": {"type": "array"},
                    "tone": {"type": "string"},
                },
            },
        },
        rubric_name="Response tone & accuracy",
        rubric_criteria=[
            {"key": "policy_accuracy", "description": "Answer matches policy", "weight": 3},
            {"key": "tone", "description": "Warm and on-brand", "weight": 2},
            {"key": "resolution", "description": "Actually resolves the ask", "weight": 2},
        ],
        rubric_pass_min_total=25,  # of max 35
        suite_name="Response quality gate",
        suite_min_reviewers=1,
        suite_cases=[
            {
                "name": "policy",
                "prompt_or_instruction": "Confirm the answer matches current policy.",
            },
            {"name": "tone", "prompt_or_instruction": "Rate warmth and brand fit."},
        ],
        stages=[
            Stage(
                "classify",
                "Classify",
                Contract(
                    identity=(
                        "You are triage. You classify the ticket and pull the governing policy."
                    ),
                    inputs=["customer message"],
                    procedure=["Classify intent", "Retrieve the governing policy passage"],
                    outputs=[("triage", "triage.md", "intent label and cited policy passage")],
                    definition_of_done=["intent and governing policy are identified"],
                    failure_modes=["misclassifying a refund request"],
                ),
            ),
            Stage(
                "draft_response",
                "Draft response",
                Contract(
                    identity="You are a support agent drafting the reply strictly on policy.",
                    inputs=["triage.md", "knowledge base (read-only)"],
                    procedure=["Draft the reply", "Cite the policy passages relied on"],
                    outputs=[("response", "response.md", "customer-ready reply with policy_refs")],
                    definition_of_done=["every commitment traces to a cited policy"],
                    failure_modes=["promising outside policy"],
                ),
            ),
            Stage(
                "sampling_review",
                "Sampling review",
                Contract(
                    identity="You are QA. You review sampled replies and approve, edit, or reject.",
                    inputs=["response.md"],
                    procedure=["Review the sampled reply", "Record a decision"],
                    outputs=[("qa_note", "qa_note.md", "approve/edit/reject with rationale")],
                    definition_of_done=["a recorded QA decision on sampled replies"],
                    failure_modes=["passing an off-policy promise"],
                ),
                review_required=True,
            ),
            Stage(
                "tone_accuracy_eval",
                "Tone & accuracy eval",
                Contract(
                    identity=(
                        "You are the eval gate. The reply is scored for tone and policy accuracy."
                    ),
                    inputs=["reviewed response.md"],
                    procedure=["Submit for rubric scoring", "Feed failures to drift detection"],
                    outputs=[
                        ("eval_target", "eval_target.md", "reply snapshot scored by the rubric")
                    ],
                    definition_of_done=["a passing rubric decision is on record"],
                    failure_modes=["shipping a failing reply"],
                ),
                eval_required=True,
            ),
            Stage(
                "publish",
                "Publish",
                Contract(
                    identity="You are dispatch. You send the approved, evaluated reply.",
                    inputs=["approved and passing response.md"],
                    procedure=["Send the reply", "Log the evidence trail"],
                    outputs=[("sent_reply", "sent_reply.md", "delivered reply with evidence")],
                    definition_of_done=["reply carries QA and eval evidence"],
                    failure_modes=["sending an unreviewed reply"],
                ),
            ),
        ],
    ),
    # 4) Clinical / pharma protocol drafting --------------------------------- #
    UseCase(
        slug="clinical-protocol-drafting",
        name="Clinical / pharma protocol drafting",
        description=(
            "Highly-regulated protocol drafting with strict reviewer competency, a safety "
            "eval, and an "
            "explicit reversibility check — exercises the resilience layer hardest."
        ),
        prompt_profile={
            "name": "protocol-drafting",
            "instructions": {
                "voice": "GCP-compliant, unambiguous",
                "must": ["state endpoints", "state stopping rules"],
            },
        },
        tool_profile={
            "name": "literature-readonly",
            "allowed_tools": ["pubmed.search", "guideline.lookup"],
            "adapter_settings": {"phi": "deny"},
        },
        policy_profile={
            "name": "gcp-gated",
            "default_gate_settings": {
                "require_review": True,
                "require_eval": True,
                "reviewer_competency": "clinical",
            },
            "default_policy_refs": ["policy://clinical/gcp", "policy://clinical/safety"],
        },
        domain_schema={
            "name": "study_protocol",
            "schema_definition": {
                "type": "object",
                "required": ["objective", "endpoints", "safety", "stopping_rules"],
                "properties": {
                    "objective": {"type": "string"},
                    "endpoints": {"type": "array"},
                    "safety": {"type": "array"},
                    "stopping_rules": {"type": "array", "minItems": 1},
                },
            },
        },
        rubric_name="Protocol safety & rigor",
        rubric_criteria=[
            {
                "key": "safety",
                "description": "Safety monitoring and stopping rules are sound",
                "weight": 3,
            },
            {
                "key": "scientific_rigor",
                "description": "Endpoints and design are valid",
                "weight": 3,
            },
            {
                "key": "gcp_compliance",
                "description": "Meets GCP documentation standards",
                "weight": 2,
            },
            {"key": "clarity", "description": "Executable without ambiguity", "weight": 1},
        ],
        rubric_pass_min_total=32,  # of max 45
        suite_name="Protocol safety gate",
        suite_min_reviewers=2,
        suite_cases=[
            {
                "name": "safety",
                "prompt_or_instruction": "Assess safety monitoring and stopping rules.",
            },
            {"name": "rigor", "prompt_or_instruction": "Assess endpoint validity and design."},
        ],
        stages=[
            Stage(
                "scope",
                "Scope",
                Contract(
                    identity=(
                        "You are the study lead. You fix the protocol's objective and population."
                    ),
                    inputs=["research question", "regulatory context"],
                    procedure=["State the primary objective", "Define the population and phase"],
                    outputs=[
                        ("protocol_scope", "protocol_scope.md", "objective, population, and phase")
                    ],
                    definition_of_done=["objective and population are unambiguous"],
                    failure_modes=["vague or shifting objective"],
                ),
            ),
            Stage(
                "draft_protocol",
                "Draft protocol",
                Contract(
                    identity="You are a medical writer drafting the protocol within scope.",
                    inputs=["protocol_scope.md", "literature (read-only)"],
                    procedure=[
                        "Specify endpoints",
                        "Specify safety monitoring",
                        "Specify stopping rules",
                    ],
                    outputs=[
                        ("draft_protocol", "draft_protocol.md", "full protocol"),
                        ("safety_annex", "safety_annex.md", "safety monitoring and stopping rules"),
                    ],
                    definition_of_done=["at least one explicit stopping rule is defined"],
                    failure_modes=["missing stopping rules", "undefined endpoints"],
                ),
            ),
            Stage(
                "medical_review",
                "Medical review",
                Contract(
                    identity=(
                        "You are a qualified medical reviewer. You approve, edit, or "
                        "reject on clinical grounds."
                    ),
                    inputs=["draft_protocol.md", "safety_annex.md"],
                    procedure=["Assess safety and rigor", "Record a competency-gated decision"],
                    outputs=[
                        (
                            "medical_decision",
                            "medical_decision.md",
                            "approve/edit/reject with rationale",
                        )
                    ],
                    definition_of_done=["a recorded decision by a competent reviewer"],
                    failure_modes=["approving without a stopping rule"],
                ),
                review_required=True,
            ),
            Stage(
                "safety_eval",
                "Safety eval",
                Contract(
                    identity="You are the eval gate. The protocol is scored for safety and rigor.",
                    inputs=["reviewed draft_protocol.md"],
                    procedure=["Submit for rubric scoring", "Block on a failing safety score"],
                    outputs=[
                        ("eval_target", "eval_target.md", "protocol snapshot scored by the rubric")
                    ],
                    definition_of_done=["a passing rubric decision is on record"],
                    failure_modes=["advancing an unsafe protocol"],
                ),
                eval_required=True,
            ),
            Stage(
                "reversibility_check",
                "Reversibility check",
                Contract(
                    identity=(
                        "You are the resilience officer. You confirm the study can be "
                        "halted and reconstructed by humans."
                    ),
                    inputs=["approved draft_protocol.md", "safety_annex.md"],
                    procedure=[
                        "Confirm the stopping rules are executable",
                        "Confirm a human can reconstruct the decision trail",
                    ],
                    outputs=[
                        (
                            "reversibility_note",
                            "reversibility_note.md",
                            "halt-and-reconstruct assessment",
                        )
                    ],
                    definition_of_done=["a documented, executable path to halt and reconstruct"],
                    failure_modes=["an irreversible design with no human fallback"],
                ),
            ),
            Stage(
                "approve",
                "Approve",
                Contract(
                    identity=(
                        "You are the sponsor sign-off. You release the reviewed, "
                        "evaluated, reversible protocol."
                    ),
                    inputs=["passing and reversible draft_protocol.md"],
                    procedure=["Freeze the version", "Attach all evidence"],
                    outputs=[
                        (
                            "approved_protocol",
                            "approved_protocol.md",
                            "sponsor-approved protocol with full evidence",
                        )
                    ],
                    definition_of_done=[
                        "protocol carries review, eval, and reversibility evidence"
                    ],
                    failure_modes=["approving without reversibility evidence"],
                ),
            ),
        ],
    ),
]


# --------------------------------------------------------------------------- #
# Seeding
# --------------------------------------------------------------------------- #
def seed_use_cases(session, tenant_id, created_by) -> list[str]:
    """Create every use-case pack that does not already exist. Returns a log."""
    storage = get_storage()
    workflow_svc = WorkflowTemplateService(session, storage)
    env_svc = EnvironmentTemplateService(session)
    rubric_svc = RubricService(session)
    suite_svc = EvalSuiteService(session)

    log: list[str] = []
    for uc in USE_CASES:
        if workflow_svc._repo.get_template_by_slug(tenant_id, uc.slug) is not None:
            log.append(f"skip  {uc.slug} (already exists)")
            continue

        # Environment template + version, bound into the workflow version.
        env_template = env_svc.create_template(
            tenant_id,
            created_by,
            name=f"{uc.name} environment",
            slug=f"{uc.slug}-env",
            description=uc.description,
        )
        env_version = env_svc.create_version(
            tenant_id,
            created_by,
            env_template.id,
            prompt_profiles=[uc.prompt_profile],
            tool_profiles=[uc.tool_profile],
            policy_profiles=[uc.policy_profile],
            domain_schemas=[uc.domain_schema],
        )

        # Workflow template + gated version.
        template = workflow_svc.create_template(
            tenant_id,
            created_by,
            TemplateCreate(name=uc.name, slug=uc.slug, description=uc.description),
        )
        stages = [
            StageDefinitionCreate(
                stage_key=s.stage_key,
                display_name=s.display_name,
                order_index=i,
                execution_mode=ExecutionMode.manual,
                review_required=s.review_required,
                eval_required=s.eval_required,
                contract_markdown=s.contract.to_markdown(f"{uc.name} — {s.display_name}"),
            )
            for i, s in enumerate(uc.stages)
        ]
        workflow_svc.create_version(
            tenant_id,
            created_by,
            template.id,
            stages,
            environment_template_version_id=env_version.id,
        )

        # Rubric + version.
        rubric = rubric_svc.create_rubric(
            tenant_id, name=uc.rubric_name, description=uc.description
        )
        rubric_svc.create_version(
            tenant_id,
            rubric.id,
            criteria=uc.rubric_criteria,
            score_scale=SCORE_SCALE,
            pass_threshold={"min_total": uc.rubric_pass_min_total},
        )

        # Eval suite.
        suite_svc.create_suite(
            tenant_id,
            created_by,
            name=uc.suite_name,
            target_type=EvalTargetType.stage_run,
            config={"min_reviewers": uc.suite_min_reviewers},
            cases=uc.suite_cases,
        )

        log.append(
            f"seed  {uc.slug}: {len(uc.stages)} stages, "
            f"{len(uc.rubric_criteria)}-criterion rubric, suite '{uc.suite_name}'"
        )
    return log


def main() -> int:
    email = os.environ.get("ICM_SEED_ADMIN_EMAIL", "kriztophr@outlook.com")
    with get_sessionmaker()() as session:
        admin = AuthService(session).get_by_email(email)
        if admin is None:
            print(f"admin user {email!r} not found; set ICM_SEED_ADMIN_EMAIL", file=sys.stderr)
            return 1
        log = seed_use_cases(session, admin.tenant_id, admin.id)
        session.commit()
    for line in log:
        print(line)
    print(f"done — {sum(1 for line in log if line.startswith('seed'))} use case(s) seeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
