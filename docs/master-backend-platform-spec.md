# Master Backend Platform Spec
## ICM-Native Governed Agent Workflow, Evals, Environment, and Human Capacity Resilience Platform

## 1. Purpose

This document defines the production-ready backend architecture for a standalone platform that combines governed agent workflows, human-in-the-loop control, evaluation systems, reusable business environments, and strategic human capacity resilience. The platform is designed for organizations that need AI-enabled workflows that remain reviewable, auditable, measurable, reversible, and resilient under failure, policy change, or model degradation.[file:127][web:180][web:208][web:285]

The workflow substrate is based on Interpretable Context Methodology (ICM), which structures execution through staged workspaces, explicit stage contracts, layered context loading, and human-readable intermediate artifacts rather than opaque orchestration logic.[file:127] On top of that substrate, the platform adds governance, evals, environment versioning, and human-capacity measurement so that organizations can manage both output quality and overreliance risk.[web:143][web:217][web:285]

## 2. Strategic intent

The platform is intended to solve five problems at once:
- run sequential AI workflows safely and repeatably,[file:127]
- preserve meaningful human review and intervention,[web:143][web:240]
- evaluate quality and reliability continuously,[web:208][web:226]
- package business-specific operating contexts as reusable governed environments,[web:235][file:127]
- and measure whether human technical capacity is being retained rather than silently eroded by AI dependence.[web:285][web:286]

This last goal is not a side feature. It is treated as a strategic requirement because governance controls, pause mechanisms, manual fallback, and override workflows only remain credible when human capability to use them still exists.[web:285][web:291]

## 3. Scope

This specification covers the backend system only. It defines:
- domain layers,
- modules,
- entities,
- service boundaries,
- event contracts,
- API surfaces,
- state models,
- promotion flows,
- review flows,
- evaluation flows,
- and human capacity resilience mechanisms.

It does not define final visual UI design, pricing plans, enterprise commercial packaging, or infrastructure-as-code implementation details.

## 4. Architectural style

The platform should be implemented as a modular monolith, not as early microservices.[web:243][web:246][web:249] This keeps code boundaries strong while reducing operational sprawl, premature distributed systems complexity, and cross-service coordination overhead. The architecture must be modular enough that services can later be split if needed, but the first production system should optimize for coherence, traceability, and fast iteration.[web:243][web:253]

## 5. Core principles

### 5.1 ICM as workflow substrate
ICM is the execution grammar for staged workflows. Stage ordering, context loading, and artifact handoff should remain explicit and inspectable through structured workspaces and contracts.[file:127]

### 5.2 Human-in-the-loop as architecture
Review gates, approvals, edits, escalations, and overrides are execution states and control boundaries, not optional front-end interactions.[web:143][web:240][web:250]

### 5.3 Evals as a product capability
Evaluation is a first-class subsystem tied to workflow artifacts, traces, baselines, and releases. It is not merely offline benchmarking.[web:208][web:217][web:226]

### 5.4 Environments as reusable operating modes
Business-specific configurations should be represented as versioned environment templates with reusable references, profiles, and policies.[file:127][web:235]

### 5.5 Human capacity resilience as a governance concern
The platform must be able to evaluate whether humans can still verify, override, reconstruct, and resume critical work if AI assistance degrades or fails.[web:285][web:286]

### 5.6 Fail closed on consequential ambiguity
If the platform cannot determine authorization, policy outcome, tenant scope, or input integrity, it must block or pause rather than continue.

### 5.7 Traceability before automation depth
The system should prioritize inspectability, evidence, and controlled progression before richer branching or autonomy features.[file:127][web:180]

## 6. Layer model

The platform is organized into five business layers, with shared infrastructure beneath them.[file:127][web:180][web:285]

| Layer | Responsibility | Primary output |
|---|---|---|
| Workflow | Staged execution, context assembly, artifact handoff | Stage artifacts |
| Governance | Policy checks, approvals, review, audit, escalation | Control decisions |
| Evals | Scoring, baselines, regression packs, calibration, drift | Eval results |
| Environment | Reusable templates, profiles, references, promotion | Governed environment versions |
| Human Capacity Resilience | Human capability measurement, fallback readiness, reversibility assessment | Capacity evidence and resilience decisions |

The Human Capacity Resilience layer is conceptually cross-cutting, but it should be implemented as a dedicated module with dependencies on Workflow, Governance, Evals, and Environment.[web:285][web:286]

## 7. Technology baseline

Recommended stack:
- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- Redis
- Celery for asynchronous jobs
- S3-compatible object storage
- OpenTelemetry
- Structured logging
- Nginx or Caddy as edge proxy

The system should support local-first development, a single 4GB VPS MVP deployment, and later migration to managed data/storage infrastructure if usage expands.[web:104][web:275]

## 8. Repository and module structure

```text
app/
  platform/
    auth/
    rbac/
    db/
    settings/
    storage/
    events/
    notifications/
    observability/
    ids/
    time/
  workflow/
    api/
    models/
    repositories/
    services/
    icm/
    contracts/
    schemas/
  governance/
    api/
    models/
    repositories/
    services/
    policies/
    reviews/
    audit/
    schemas/
  evals/
    api/
    models/
    repositories/
    services/
    rubrics/
    regressions/
    calibration/
    schemas/
  environment/
    api/
    models/
    repositories/
    services/
    references/
    profiles/
    promotion/
    schemas/
  resilience/
    api/
    models/
    repositories/
    services/
    drills/
    capacity/
    reversibility/
    schemas/
  tasks/
    celery_app.py
    workflow_tasks.py
    eval_tasks.py
    resilience_tasks.py
```

## 9. Shared platform module

The platform module provides shared infrastructure only.[web:243][web:249]

### 9.1 Responsibilities
- authentication,
- RBAC,
- DB session management,
- storage abstraction,
- event publication,
- notification hooks,
- correlation IDs,
- clock utilities,
- observability instrumentation.

### 9.2 Core services
- `AuthService`
- `RBACService`
- `StorageService`
- `EventBus`
- `NotificationService`
- `CorrelationIdService`
- `ClockService`
- `IdGenerator`

### 9.3 Core APIs
- `POST /auth/login`
- `GET /users/me`
- `GET /health`
- `GET /metrics`

## 10. Workflow module

The Workflow module owns execution and artifact flow and is the closest backend realization of the ICM paper.[file:127]

### 10.1 Responsibilities
- workflow template definition,
- template versioning,
- stage ordering,
- stage contract parsing,
- workspace materialization,
- context assembly,
- workflow run state,
- stage run state,
- artifact persistence,
- handoff control to governance and evals.[file:127]

### 10.2 ICM layer mapping
- Layer 0: workspace identity
- Layer 1: routing
- Layer 2: stage contract
- Layer 3: stable references
- Layer 4: working artifacts[file:127]

### 10.3 Entities
- `WorkflowTemplate`
- `WorkflowTemplateVersion`
- `StageDefinition`
- `StageContract`
- `WorkflowRun`
- `StageRun`
- `Artifact`
- `ContextManifest`
- `ExecutionSnapshot`

### 10.4 Suggested fields

#### WorkflowTemplate
- `id`
- `tenant_id`
- `project_id`
- `name`
- `slug`
- `description`
- `status`
- `created_by`
- `created_at`
- `updated_at`

#### WorkflowTemplateVersion
- `id`
- `workflow_template_id`
- `environment_template_version_id` (nullable)
- `version_number`
- `workspace_blueprint_ref`
- `published_at`
- `created_by`

#### StageDefinition
- `id`
- `workflow_template_version_id`
- `stage_key`
- `display_name`
- `order_index`
- `execution_mode`
- `review_required`
- `eval_required`
- `contract_source_ref`

#### StageContract
- `id`
- `stage_definition_id`
- `source_markdown`
- `parsed_contract_json`
- `schema_version`
- `created_at`

#### WorkflowRun
- `id`
- `tenant_id`
- `project_id`
- `workflow_template_version_id`
- `environment_template_version_id` (nullable)
- `status`
- `current_stage_run_id` (nullable)
- `triggered_by`
- `started_at`
- `completed_at` (nullable)
- `correlation_id`

#### StageRun
- `id`
- `workflow_run_id`
- `stage_definition_id`
- `status`
- `attempt_number`
- `started_at`
- `completed_at` (nullable)
- `review_gate_id` (nullable)
- `context_manifest_id` (nullable)
- `execution_snapshot_id` (nullable)
- `error_summary` (nullable)

#### Artifact
- `id`
- `workflow_run_id`
- `stage_run_id`
- `artifact_role`
- `storage_uri`
- `content_type`
- `version_number`
- `is_human_edited`
- `source_artifact_id` (nullable)
- `created_by_type`
- `created_by_id` (nullable)
- `created_at`

#### ContextManifest
- `id`
- `stage_run_id`
- `layer0_ref`
- `layer1_ref`
- `layer2_ref`
- `layer3_inputs_json`
- `layer4_inputs_json`
- `token_estimate`
- `created_at`

### 10.5 Services
- `WorkflowTemplateService`
- `StageContractService`
- `WorkspaceMaterializationService`
- `ContextAssemblyService`
- `WorkflowRunService`
- `StageExecutionCoordinator`
- `ArtifactService`

### 10.6 APIs
- `POST /workflow/templates`
- `GET /workflow/templates/{id}`
- `POST /workflow/templates/{id}/versions`
- `GET /workflow/templates/{id}/versions/{version_id}`
- `POST /workflow/runs`
- `GET /workflow/runs/{id}`
- `GET /workflow/runs/{id}/stages`
- `GET /workflow/stage-runs/{id}`
- `GET /workflow/stage-runs/{id}/context-manifest`
- `GET /workflow/artifacts/{id}`

## 11. Governance module

The Governance module is the runtime control plane.[web:143][web:180][web:191]

### 11.1 Responsibilities
- policy evaluation,
- review gating,
- approval handling,
- edit acceptance,
- rejection,
- escalation,
- audit event recording,
- control exceptions,
- override pathways.[web:143][web:250]

### 11.2 Entities
- `PolicyRule`
- `PolicyDecision`
- `ApprovalGate`
- `ReviewTask`
- `ReviewDecision`
- `EscalationRule`
- `AuditEvent`
- `ControlException`

### 11.3 Suggested fields

#### PolicyRule
- `id`
- `tenant_id`
- `project_id`
- `name`
- `scope_type`
- `scope_ref`
- `rule_type`
- `rule_expression_json`
- `severity`
- `is_active`
- `created_at`

#### PolicyDecision
- `id`
- `policy_rule_id`
- `workflow_run_id`
- `stage_run_id` (nullable)
- `decision_type`
- `decision_reason`
- `decision_metadata_json`
- `created_at`

#### ApprovalGate
- `id`
- `stage_definition_id`
- `gate_type`
- `required_role`
- `sla_minutes` (nullable)
- `escalation_rule_id` (nullable)
- `enabled`

#### ReviewTask
- `id`
- `workflow_run_id`
- `stage_run_id`
- `artifact_id`
- `approval_gate_id`
- `status`
- `assigned_to` (nullable)
- `eligible_role`
- `created_at`
- `due_at` (nullable)
- `correlation_id`

#### ReviewDecision
- `id`
- `review_task_id`
- `decision_type`
- `rationale`
- `edited_artifact_id` (nullable)
- `decided_by`
- `decided_at`

#### AuditEvent
- `id`
- `tenant_id`
- `project_id`
- `event_type`
- `workflow_run_id` (nullable)
- `stage_run_id` (nullable)
- `review_task_id` (nullable)
- `eval_run_id` (nullable)
- `environment_promotion_id` (nullable)
- `actor_type`
- `actor_id` (nullable)
- `payload_json`
- `occurred_at`
- `correlation_id`

### 11.4 Services
- `PolicyEngine`
- `GovernanceDecisionService`
- `ReviewTaskService`
- `ApprovalService`
- `EscalationService`
- `AuditService`

### 11.5 APIs
- `POST /governance/policies`
- `GET /governance/policies/{id}`
- `POST /governance/review-tasks`
- `GET /governance/review-tasks/{id}`
- `POST /governance/review-tasks/{id}/approve`
- `POST /governance/review-tasks/{id}/edit`
- `POST /governance/review-tasks/{id}/reject`
- `POST /governance/review-tasks/{id}/escalate`
- `GET /governance/audit-events`

## 12. Evals module

The Evals module is the quality and reliability measurement plane.[web:208][web:217][web:242]

### 12.1 Responsibilities
- eval suite definition,
- eval execution,
- rubric versioning,
- reviewer scoring,
- calibration,
- baseline management,
- regression pack execution,
- drift detection,
- eval decision support,
- release evidence generation.[web:208][web:226]

### 12.2 Entities
- `EvalSuite`
- `EvalCase`
- `EvalRun`
- `EvalTarget`
- `Rubric`
- `RubricVersion`
- `ReviewerScore`
- `Scorecard`
- `Baseline`
- `RegressionPack`
- `RegressionPackRun`
- `DriftSignal`
- `EvalDecision`
- `CalibrationSession`
- `CalibrationExample`
- `DisagreementRecord`

### 12.3 Suggested fields

#### EvalSuite
- `id`
- `tenant_id`
- `project_id`
- `name`
- `target_type`
- `suite_type`
- `config_json`
- `created_at`

#### EvalCase
- `id`
- `eval_suite_id`
- `name`
- `prompt_or_instruction`
- `expected_shape_json` (nullable)
- `weight`
- `order_index`

#### EvalRun
- `id`
- `tenant_id`
- `project_id`
- `eval_suite_id`
- `target_ref_type`
- `target_ref_id`
- `workflow_run_id` (nullable)
- `stage_run_id` (nullable)
- `artifact_id` (nullable)
- `environment_template_version_id` (nullable)
- `status`
- `started_at`
- `completed_at` (nullable)
- `triggered_by`
- `correlation_id`

#### Rubric
- `id`
- `tenant_id`
- `project_id`
- `name`
- `description`
- `created_at`

#### RubricVersion
- `id`
- `rubric_id`
- `version_number`
- `criteria_json`
- `score_scale_json`
- `pass_threshold_json`
- `published_at`

#### ReviewerScore
- `id`
- `eval_run_id`
- `rubric_version_id`
- `reviewer_id`
- `score_json`
- `pass_fail`
- `rationale`
- `is_calibration`
- `submitted_at`

#### Baseline
- `id`
- `tenant_id`
- `project_id`
- `name`
- `scope_type`
- `scope_ref`
- `baseline_data_json`
- `created_at`

#### RegressionPack
- `id`
- `tenant_id`
- `project_id`
- `name`
- `description`
- `eval_suite_refs_json`
- `scope_type`
- `scope_ref`
- `created_at`

#### DriftSignal
- `id`
- `tenant_id`
- `project_id`
- `scope_type`
- `scope_ref`
- `signal_type`
- `signal_strength`
- `evidence_json`
- `detected_at`

### 12.4 Services
- `EvalSuiteService`
- `EvalRunService`
- `RubricService`
- `EvalScoringService`
- `BaselineService`
- `RegressionPackService`
- `DriftAnalysisService`
- `ReviewerCalibrationService`
- `EvalDecisionService`

### 12.5 APIs
- `POST /evals/suites`
- `GET /evals/suites/{id}`
- `POST /evals/runs`
- `GET /evals/runs/{id}`
- `GET /evals/results/{id}`
- `POST /evals/baselines`
- `POST /evals/regression-packs`
- `POST /evals/regression-packs/{id}/run`
- `GET /evals/drift-signals`
- `POST /evals/reviewer-scores`
- `POST /evals/calibration-sessions`

## 13. Reviewer scoring and calibration model

The platform must support a production-grade reviewer-scoring and calibration system rather than assuming reviewer consistency.[web:217][web:218][web:222]

### 13.1 Reviewer scoring workflow
1. Reviewer opens an eval-linked artifact or stage output.
2. Platform shows artifact, context, rubric version, and any baseline comparison.[web:217]
3. Reviewer submits structured criterion scores and rationale.
4. Platform records pass/fail, confidence, and free-text judgment.
5. If multiple reviewers disagree materially, a disagreement record is created.
6. If needed, adjudication is triggered.

### 13.2 Calibration model
The system should support:
- golden examples,
- overlap scoring,
- reviewer agreement checks,
- calibration sessions,
- drift in reviewer strictness or leniency,
- periodic re-certification for sensitive domains.[web:218][web:222]

### 13.3 Calibration entities
- `CalibrationSession`
- `CalibrationExample`
- `ReviewerCalibrationRecord`
- `AgreementMetric`
- `AdjudicationTask`

### 13.4 Calibration services
- `ReviewerCalibrationService`
- `AgreementAnalysisService`
- `AdjudicationService`

## 14. Environment module

The Environment module is the reusable business operating context and versioned configuration plane.[file:127][web:235]

### 14.1 Responsibilities
- environment template management,
- versioning,
- reference bundle management,
- prompt and tool profile resolution,
- policy profile defaults,
- workspace blueprint generation,
- promotion readiness tracking.[file:127][web:235]

### 14.2 Entities
- `EnvironmentTemplate`
- `EnvironmentTemplateVersion`
- `ReferenceBundle`
- `PromptProfile`
- `ToolProfile`
- `PolicyProfile`
- `DomainSchema`
- `WorkspaceBlueprint`
- `SetupQuestionnaire`
- `EnvironmentPromotion`

### 14.3 Suggested fields

#### EnvironmentTemplate
- `id`
- `tenant_id`
- `project_id`
- `name`
- `slug`
- `description`
- `status`
- `created_by`
- `created_at`

#### EnvironmentTemplateVersion
- `id`
- `environment_template_id`
- `version_number`
- `workspace_blueprint_ref`
- `published_at`
- `created_by`

#### ReferenceBundle
- `id`
- `environment_template_version_id`
- `name`
- `bundle_type`
- `storage_uri`
- `manifest_json`
- `created_at`

#### PromptProfile
- `id`
- `environment_template_version_id`
- `name`
- `instructions_json`
- `style_ref` (nullable)
- `created_at`

#### ToolProfile
- `id`
- `environment_template_version_id`
- `name`
- `allowed_tools_json`
- `adapter_settings_json`
- `created_at`

#### PolicyProfile
- `id`
- `environment_template_version_id`
- `name`
- `default_gate_settings_json`
- `default_policy_refs_json`
- `created_at`

#### EnvironmentPromotion
- `id`
- `environment_template_version_id`
- `status`
- `requested_by`
- `requested_at`
- `approved_by` (nullable)
- `approved_at` (nullable)
- `evidence_json`
- `decision_reason` (nullable)

### 14.4 Services
- `EnvironmentTemplateService`
- `ReferenceBundleService`
- `ProfileResolutionService`
- `WorkspaceBlueprintService`
- `DomainSetupService`
- `EnvironmentPromotionService`

### 14.5 APIs
- `POST /environment/templates`
- `GET /environment/templates/{id}`
- `POST /environment/templates/{id}/versions`
- `POST /environment/reference-bundles`
- `GET /environment/reference-bundles/{id}`
- `POST /environment/workspace-blueprints`
- `GET /environment/workspace-blueprints/{id}`
- `POST /environment/promotions`
- `GET /environment/promotions/{id}`

## 15. Human Capacity Resilience module

This module is designed to address strategic capacity maintenance and overreliance risk directly. It evaluates whether humans can still verify, override, reconstruct, and resume critical work without full AI dependence.[web:285][web:286][web:291]

### 15.1 Responsibilities
- define critical human capabilities,
- run human-capacity eval suites,
- measure verification skill,
- measure override readiness,
- measure reconstruction ability,
- assess fallback readiness,
- assess reversibility capacity,
- provide strategic coverage reporting,
- trigger resilience-aware governance decisions.

### 15.2 Core concepts
- verification capacity: ability to identify flaws in AI outputs,
- override capacity: ability to confidently reject or modify AI outputs,
- reconstruction capacity: ability to perform or reconstruct task logic with reduced AI support,
- fallback readiness: ability for a person or team to continue during AI outage,
- reversibility capacity: ability to restore human-led operation when automation must be reduced or paused.[web:285]

### 15.3 Entities
- `CriticalCapability`
- `CapabilityProfile`
- `HumanCapacityEvalSuite`
- `HumanCapacityEvalCase`
- `HumanCapacityRun`
- `CapabilityRubric`
- `VerificationScore`
- `OverrideScore`
- `ReconstructionScore`
- `FallbackReadinessAssessment`
- `ReversibilityAssessment`
- `ReviewerCompetencyRecord`
- `FallbackDrill`
- `StrategicCoverageSnapshot`
- `ResilienceThreshold`
- `ResilienceDecision`

### 15.4 Suggested fields

#### CriticalCapability
- `id`
- `tenant_id`
- `project_id`
- `name`
- `domain`
- `criticality_level`
- `description`
- `created_at`

#### CapabilityProfile
- `id`
- `critical_capability_id`
- `subject_type` (person, team, environment)
- `subject_ref_id`
- `current_status`
- `last_assessed_at`

#### HumanCapacityRun
- `id`
- `tenant_id`
- `project_id`
- `human_capacity_eval_suite_id`
- `subject_type`
- `subject_ref_id`
- `workflow_template_version_id` (nullable)
- `environment_template_version_id` (nullable)
- `status`
- `started_at`
- `completed_at` (nullable)
- `triggered_by`
- `correlation_id`

#### FallbackDrill
- `id`
- `tenant_id`
- `project_id`
- `environment_template_version_id`
- `workflow_template_version_id` (nullable)
- `drill_type`
- `ai_mode` (off, reduced, delayed)
- `status`
- `started_at`
- `completed_at` (nullable)
- `summary_json`

#### ReversibilityAssessment
- `id`
- `tenant_id`
- `project_id`
- `scope_type`
- `scope_ref`
- `assessment_score`
- `evidence_json`
- `assessed_at`

#### StrategicCoverageSnapshot
- `id`
- `tenant_id`
- `project_id`
- `critical_capability_id`
- `qualified_subject_count`
- `minimum_required_count`
- `coverage_status`
- `captured_at`

#### ResilienceThreshold
- `id`
- `tenant_id`
- `project_id`
- `scope_type`
- `scope_ref`
- `metric_name`
- `min_threshold`
- `policy_action`
- `created_at`

### 15.5 Services
- `CapacityEvaluationService`
- `FallbackReadinessService`
- `ReversibilityAssessmentService`
- `StrategicCoverageService`
- `ResiliencePolicyService`
- `CapabilityDrillService`

### 15.6 APIs
- `POST /resilience/capabilities`
- `GET /resilience/capabilities/{id}`
- `POST /resilience/eval-runs`
- `GET /resilience/eval-runs/{id}`
- `POST /resilience/fallback-drills`
- `GET /resilience/fallback-drills/{id}`
- `GET /resilience/coverage-snapshots`
- `POST /resilience/thresholds`
- `GET /resilience/reversibility-assessments/{id}`

## 16. Workflow-to-eval and environment linkage

The platform must preserve strong relational linkage between workflow execution, evaluation, governance, environment versioning, and resilience assessment.[cite:201][file:127][web:208]

### 16.1 Mandatory linkage rules
- Every `EvalRun` must be traceable to an artifact, stage run, workflow run, or environment version.
- Every `ReviewerScore` must be traceable to an eval run, rubric version, and reviewer.
- Every `EnvironmentPromotion` must be traceable to relevant eval evidence, governance decisions, and resilience thresholds.
- Every `HumanCapacityRun` and `FallbackDrill` must be traceable to environment or workflow scope when applicable.

### 16.2 Why this matters
This linkage lets the platform answer:
- which workflow version introduced a regression,
- which environment version was approved under what evidence,
- which reviewers are calibrated,
- whether humans can still safely operate without the AI path,
- and whether a system remains strategically reversible.[web:208][web:217][web:285]

## 17. Environment promotion model

Promotion must be explicit, evidence-based, and policy-aware.[web:235]

### 17.1 Promotion states
- `draft`
- `under_evaluation`
- `approval_pending`
- `approved`
- `deprecated`
- `blocked`

### 17.2 Promotion requirements
An environment version may only be approved if:
- required regression packs pass,
- required rubric thresholds are met,
- governance review requirements are satisfied,
- resilience thresholds are met where applicable,
- no blocking drift signal is active,
- no unresolved critical review disagreement remains.[web:208][web:217][web:235][web:285]

### 17.3 Promotion evidence
The promotion evidence package should include:
- linked workflow versions,
- linked eval runs,
- reviewer score summaries,
- regression pack results,
- audit records,
- resilience assessments,
- strategic coverage snapshot if the environment is designated critical.

## 18. Reviewer disagreement and adjudication

The platform must not assume reviewer agreement. Disagreement handling should be explicit and durable.[web:217][web:218]

### 18.1 Disagreement triggers
Create a `DisagreementRecord` when:
- reviewers differ on pass/fail,
- criterion variance crosses threshold,
- calibration confidence is low,
- or one reviewer flags material ambiguity.

### 18.2 Adjudication flow
1. Disagreement recorded.
2. Adjudication task created.
3. Senior reviewer or domain lead resolves final score.
4. Calibration impact recorded for involved reviewers.
5. If recurring, revise rubric or examples.

## 19. Internal event model

Recommended domain events:
- `workflow.run.created`
- `workflow.stage.started`
- `workflow.artifact.created`
- `workflow.stage.completed`
- `workflow.stage.failed`
- `governance.policy.evaluated`
- `governance.review.requested`
- `governance.review.approved`
- `governance.review.edited`
- `governance.review.rejected`
- `governance.review.escalated`
- `evals.run.started`
- `evals.result.recorded`
- `evals.calibration.completed`
- `evals.drift.detected`
- `environment.template.versioned`
- `environment.promotion.requested`
- `environment.promotion.approved`
- `resilience.capacity.assessed`
- `resilience.drill.completed`
- `resilience.threshold.breached`

## 20. Permission model

Recommended roles:
- `admin`
- `operator`
- `reviewer`
- `evaluator`
- `auditor`
- `environment_manager`
- `resilience_manager`

Examples:
- only `environment_manager` or `admin` can approve promotions,
- only `reviewer` or `admin` can approve review tasks,
- only `evaluator`, `reviewer`, or `admin` can submit reviewer scores,
- only `resilience_manager` or `admin` can run strategic drills in protected environments,
- only `auditor` or `admin` can inspect full audit streams if restricted.

## 21. Persistence design

### 21.1 PostgreSQL
Use Postgres for all transactional state, including:
- templates,
- versions,
- runs,
- stage metadata,
- review tasks,
- evals,
- scores,
- promotions,
- resilience records,
- audit events.

### 21.2 Object storage
Use object storage for:
- stage contracts,
- artifacts,
- reference bundles,
- workspace snapshots,
- exported reports,
- evidence packages.

### 21.3 Redis
Use Redis for:
- Celery broker,
- short-lived locks,
- queue counters,
- ephemeral coordination state.

## 22. Observability and evidence

Every consequential action must include:
- `tenant_id`
- `project_id`
- `correlation_id`
- actor identity or system actor type
- time of occurrence
- related workflow, eval, environment, or resilience object IDs

Instrument metrics for:
- workflow stage duration,
- review queue latency,
- review edit rate,
- eval pass rate,
- regression failure rate,
- environment promotion success rate,
- drift detection frequency,
- fallback drill completion time,
- strategic coverage shortfall.

## 23. Security and isolation

- all repository queries must be tenant-scoped,
- artifacts must be isolated by tenant/project/run,
- secrets must never appear in audit payloads or context manifests,
- tool permissions must be allowlist-driven by environment and stage,
- resilience drills in sensitive environments must be access-controlled,
- ambiguous authorization or policy evaluation must fail closed.

## 24. State models

### 24.1 WorkflowRun states
- `pending`
- `running`
- `paused_for_review`
- `paused_for_eval`
- `completed`
- `failed`
- `cancelled`

### 24.2 StageRun states
- `pending`
- `ready`
- `running`
- `awaiting_review`
- `awaiting_eval`
- `approved`
- `failed`
- `completed`

### 24.3 ReviewTask states
- `open`
- `in_progress`
- `approved`
- `edited`
- `rejected`
- `escalated`
- `expired`

### 24.4 EvalRun states
- `pending`
- `running`
- `awaiting_human_score`
- `completed`
- `failed`

### 24.5 EnvironmentPromotion states
- `draft`
- `under_evaluation`
- `approval_pending`
- `approved`
- `deprecated`
- `blocked`

## 25. API design rules

- use REST for first release,
- keep request/response schemas explicit,
- make all mutation endpoints idempotent where feasible,
- require correlation IDs for asynchronous workflows,
- version public APIs,
- separate internal event models from public API contracts,
- avoid leaking internal storage paths in responses.

## 26. Execution model

Use Celery for durable asynchronous tasks once the MVP proves the synchronous path.[web:104][web:271]

Task categories:
- stage execution,
- eval execution,
- regression pack execution,
- environment promotion evaluation,
- resilience drill execution,
- notification dispatch.

## 27. MVP definition

The smallest useful product should include:
- one workflow template model,
- one sequential ICM execution path,
- one review gate,
- one rubric-scored eval flow,
- one regression pack flow,
- one environment template versioning path,
- one promotion path,
- one human-capacity drill path,
- minimum audit and evidence capture.

## 28. MVP build order

1. Platform core.
2. Workflow module with ICM workspace materialization.[file:127]
3. Governance module with approve/edit/reject and audit.[web:143]
4. Evals module with rubric scoring and reviewer scoring.[web:208][web:217]
5. Environment module with versioning and promotion.[web:235]
6. Human Capacity Resilience module with one fallback drill and one reversibility assessment.[web:285]
7. Celery-based execution and async orchestration.[web:104]
8. Calibration, disagreement, and drift refinement.[web:218]

## 29. Non-goals for first production release

- high-concurrency multi-agent real-time collaboration,
- broad autonomous branching systems,
- national-scale strategic resilience planning,
- automated source rewriting from eval failures,
- advanced ML-only reviewer replacement,
- multi-region active-active deployment.

## 30. Future extensions

- semantic debugging of stage outputs,[file:127]
- section-level provenance tags,[file:127]
- AI-off drill scheduling,
- reviewer calibration cohorts,
- policy simulation before deployment,
- environment promotion pipelines integrated with CI/CD,[web:235]
- automated resilience risk scoring,
- edit-to-source recommendation engine.

## 31. Final architectural principle

Workflow produces behavior. Governance constrains behavior. Evals measure behavior. Environment shapes future behavior. Human Capacity Resilience ensures that humans remain able to verify, override, reconstruct, and resume critical work when automation fails, drifts, or must be paused.[file:127][web:285][web:286]

That is the full platform, and each layer should be implemented as a durable, evidence-producing system rather than a convenience wrapper around model calls.[file:127][web:180][web:208]
