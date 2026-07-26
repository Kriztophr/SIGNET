export type Role =
  | "admin"
  | "operator"
  | "reviewer"
  | "evaluator"
  | "auditor"
  | "environment_manager"
  | "resilience_manager";

export interface User {
  id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface WorkflowTemplate {
  id: string;
  name: string;
  slug: string;
  description: string;
  status: string;
  created_at: string;
}

export interface StageDefinition {
  id: string;
  stage_key: string;
  display_name: string;
  order_index: number;
  review_required: boolean;
  eval_required: boolean;
}

export interface TemplateVersion {
  id: string;
  workflow_template_id: string;
  version_number: number;
  published_at: string | null;
  stages: StageDefinition[];
}

export interface EvalSuite {
  id: string;
  name: string;
  target_type: string;
  config_json: { min_reviewers?: number };
  created_at: string;
}

export interface Rubric {
  id: string;
  name: string;
  description: string;
  versions: RubricVersion[];
}

export interface WorkflowRun {
  id: string;
  status: string;
  current_stage_run_id: string | null;
  workflow_template_version_id: string;
  started_at: string | null;
  completed_at: string | null;
  correlation_id: string | null;
}

export interface StageRun {
  id: string;
  workflow_run_id: string;
  stage_definition_id: string;
  status: string;
  attempt_number: number;
  started_at: string | null;
  completed_at: string | null;
  error_summary: string | null;
}

export interface ContextManifest {
  id: string;
  stage_run_id: string;
  layer0_ref: string;
  layer1_ref: string;
  layer2_ref: string;
  layer3_inputs_json: HandoffInput[];
  layer4_inputs_json: HandoffInput[];
  token_estimate: number;
}

export interface HandoffInput {
  artifact_id: string;
  artifact_role: string;
  version_number: number;
  from_stage_key: string;
  size_bytes?: number;
}

export interface Artifact {
  id: string;
  workflow_run_id: string;
  stage_run_id: string;
  artifact_role: string;
  content_type: string;
  version_number: number;
  is_human_edited: boolean;
  created_by_type: string;
  created_at: string;
}

export interface ReviewTask {
  id: string;
  workflow_run_id: string;
  stage_run_id: string;
  artifact_id: string | null;
  status: string;
  eligible_role: string;
  due_at: string | null;
  created_at: string;
}

export interface EvalRun {
  id: string;
  eval_suite_id: string;
  rubric_version_id: string;
  target_ref_type: string;
  target_ref_id: string;
  workflow_run_id: string | null;
  stage_run_id: string | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface RubricCriterion {
  key: string;
  description?: string;
  weight: number;
}

export interface RubricVersion {
  id: string;
  rubric_id: string;
  version_number: number;
  criteria_json: RubricCriterion[];
  score_scale_json: { min: number; max: number };
  pass_threshold_json: { min_total: number };
}

export interface ReviewerScore {
  id: string;
  reviewer_id: string;
  score_json: Record<string, number>;
  pass_fail: boolean;
  rationale: string;
  submitted_at: string;
}

export interface EvalDecision {
  decision_type: string;
  metrics_json: Record<string, number>;
  rationale: string;
}

export interface EvalResult {
  run: EvalRun;
  decision: EvalDecision | null;
  scores: ReviewerScore[];
}

export interface Promotion {
  id: string;
  environment_template_version_id: string;
  status: string;
  requested_at: string | null;
  approved_at: string | null;
  requirements_json: Record<string, unknown>;
  // Mirrors PromotionEvidenceEvaluator.evaluate() in
  // app/environment/promotion/evidence.py — keep the two in sync.
  evidence_json: {
    regression_packs?: { pack_id: string; passed: boolean; pass_rate?: number }[];
    eval_runs?: {
      total: number;
      passed: number;
      failed: number;
      incomplete: number;
      adjudication: number;
    };
    open_disagreements?: number;
    active_drift_signals?: number;
    resilience?: { thresholds_evaluated: number; breaches: string[] };
    blocking_reasons?: string[];
  };
  decision_reason: string | null;
}

export interface CoverageSnapshot {
  id: string;
  critical_capability_id: string;
  qualified_subject_count: number;
  minimum_required_count: number;
  coverage_status: string;
  captured_at: string;
}

export interface DriftSignal {
  id: string;
  scope_type: string;
  scope_ref: string;
  signal_type: string;
  signal_strength: number;
  detected_at: string;
}
