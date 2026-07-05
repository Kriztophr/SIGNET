import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  EvalResult,
  EvalRun,
  EvalSuite,
  Rubric,
  RubricVersion,
  WorkflowRun,
} from "../api/types";
import { can, useAuth } from "../auth";
import { Card, Empty, ErrorNote, ShortId, StatusBadge, Time, useLoad } from "../components/ui";

export function EvalsPage() {
  const { user } = useAuth();
  const [setup, setSetup] = useState(false);
  const { data: awaiting, error, reload } = useLoad(
    () => api<EvalRun[]>("/evals/runs?status=awaiting_human_score"),
    [],
  );
  const { data: recent, reload: reloadRecent } = useLoad(
    () => api<EvalRun[]>("/evals/runs?limit=20"),
    [],
  );

  return (
    <>
      <header className="page-header">
        <h1>Evals</h1>
        {can(user, "evaluator") ? (
          <button className="accent" onClick={() => setSetup((s) => !s)}>
            {setup ? "Close" : "New eval run"}
          </button>
        ) : null}
        <p className="sub">Score workflow outputs against versioned rubrics.</p>
      </header>
      <ErrorNote error={error} />
      {setup ? (
        <EvalSetup
          onStarted={() => {
            setSetup(false);
            reload();
            reloadRecent();
          }}
        />
      ) : null}
      <Card tone="light" title="Awaiting your score">
        {awaiting && awaiting.length === 0 ? (
          <Empty label="Nothing awaits scoring." />
        ) : (
          <EvalTable runs={awaiting ?? []} />
        )}
      </Card>
      <Card title="Recent eval runs">
        {recent && recent.length === 0 ? (
          <Empty label="No eval runs yet — start one with 'New eval run'." />
        ) : (
          <EvalTable runs={recent ?? []} />
        )}
      </Card>
    </>
  );
}

function EvalSetup({ onStarted }: { onStarted: () => void }) {
  const { data: suites, reload: reloadSuites } = useLoad(
    () => api<EvalSuite[]>("/evals/suites"),
    [],
  );
  const { data: rubrics, reload: reloadRubrics } = useLoad(
    () => api<Rubric[]>("/evals/rubrics"),
    [],
  );
  const { data: runs } = useLoad(() => api<WorkflowRun[]>("/workflow/runs?limit=50"), []);

  const [suiteId, setSuiteId] = useState("");
  const [rubricVersionId, setRubricVersionId] = useState("");
  const [stageRunId, setStageRunId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Quick-create fields
  const [suiteName, setSuiteName] = useState("Stage output quality");
  const [minReviewers, setMinReviewers] = useState("1");
  const [rubricName, setRubricName] = useState("Quality rubric");
  const [criteria, setCriteria] = useState("accuracy:2, clarity:1");
  const [passTotal, setPassTotal] = useState("10");

  const gated = (runs ?? []).filter((r) => r.status === "paused_for_eval");

  async function quickCreateSuite() {
    setError(null);
    try {
      const suite = await api<EvalSuite>("/evals/suites", "POST", {
        name: suiteName,
        target_type: "stage_run",
        config: { min_reviewers: Number(minReviewers) || 1 },
        cases: [
          { name: "assess the output", prompt_or_instruction: "Score the stage output." },
        ],
      });
      setSuiteId(suite.id);
      reloadSuites();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function quickCreateRubric() {
    setError(null);
    try {
      const parsed = criteria.split(",").map((chunk) => {
        const [key, weight] = chunk.split(":").map((s) => s.trim());
        return { key, weight: Number(weight) || 1 };
      });
      const rubric = await api<Rubric>("/evals/rubrics", "POST", { name: rubricName });
      const version = await api<RubricVersion>(
        `/evals/rubrics/${rubric.id}/versions`,
        "POST",
        {
          criteria: parsed,
          score_scale: { min: 0, max: 5 },
          pass_threshold: { min_total: Number(passTotal) || 1 },
        },
      );
      setRubricVersionId(version.id);
      reloadRubrics();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function startEvalRun() {
    setBusy(true);
    setError(null);
    try {
      await api("/evals/runs", "POST", {
        eval_suite_id: suiteId,
        rubric_version_id: rubricVersionId,
        target_ref_type: "stage_run",
        target_ref_id: stageRunId.trim(),
      });
      onStarted();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Start an eval run">
      <div className="grid-2">
        <div>
          <label>
            Suite
            <select value={suiteId} onChange={(e) => setSuiteId(e.target.value)}>
              <option value="">— choose a suite —</option>
              {(suites ?? []).map((suite) => (
                <option key={suite.id} value={suite.id}>
                  {suite.name} (min {suite.config_json.min_reviewers ?? 1} reviewer)
                </option>
              ))}
            </select>
          </label>
          {suites && suites.length === 0 ? (
            <div className="stage-builder">
              <p className="muted">No suites yet — create one:</p>
              <label>
                Suite name
                <input value={suiteName} onChange={(e) => setSuiteName(e.target.value)} />
              </label>
              <label>
                Minimum reviewers
                <input value={minReviewers} onChange={(e) => setMinReviewers(e.target.value)} />
              </label>
              <button className="ghost" onClick={quickCreateSuite}>
                Create suite
              </button>
            </div>
          ) : null}
        </div>
        <div>
          <label>
            Rubric version
            <select value={rubricVersionId} onChange={(e) => setRubricVersionId(e.target.value)}>
              <option value="">— choose a rubric version —</option>
              {(rubrics ?? []).flatMap((rubric) =>
                rubric.versions.map((version) => (
                  <option key={version.id} value={version.id}>
                    {rubric.name} v{version.version_number}
                  </option>
                )),
              )}
            </select>
          </label>
          {rubrics && rubrics.length === 0 ? (
            <div className="stage-builder">
              <p className="muted">No rubrics yet — create one (scale 0–5):</p>
              <label>
                Rubric name
                <input value={rubricName} onChange={(e) => setRubricName(e.target.value)} />
              </label>
              <label>
                Criteria (key:weight, comma-separated)
                <input value={criteria} onChange={(e) => setCriteria(e.target.value)} />
              </label>
              <label>
                Pass at weighted total ≥
                <input value={passTotal} onChange={(e) => setPassTotal(e.target.value)} />
              </label>
              <button className="ghost" onClick={quickCreateRubric}>
                Create rubric
              </button>
            </div>
          ) : null}
        </div>
      </div>
      <label>
        Target stage run
        {gated.length > 0 ? (
          <select value={stageRunId} onChange={(e) => setStageRunId(e.target.value)}>
            <option value="">— choose a stage awaiting eval —</option>
            {gated.map((run) => (
              <option key={run.id} value={run.current_stage_run_id ?? ""}>
                run {run.id.slice(0, 8)} — current stage (paused for eval)
              </option>
            ))}
          </select>
        ) : (
          <input
            value={stageRunId}
            onChange={(e) => setStageRunId(e.target.value)}
            placeholder="stage run id (find it in the run inspector)"
          />
        )}
      </label>
      <ErrorNote error={error} />
      <button
        className="accent"
        disabled={busy || !suiteId || !rubricVersionId || !stageRunId}
        onClick={startEvalRun}
      >
        {busy ? "Starting…" : "Start eval run"}
      </button>
    </Card>
  );
}

function EvalTable({ runs }: { runs: EvalRun[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Run</th>
          <th>Target</th>
          <th>Status</th>
          <th>Started</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => (
          <tr key={run.id}>
            <td>
              <ShortId id={run.id} />
            </td>
            <td>
              {run.target_ref_type} <ShortId id={run.target_ref_id} />
            </td>
            <td>
              <StatusBadge status={run.status} />
            </td>
            <td>
              <Time value={run.started_at} />
            </td>
            <td>
              <Link className="button-link" to={`/evals/${run.id}`}>
                Open
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function EvalDetailPage() {
  const { runId } = useParams();
  const { user } = useAuth();
  const [scores, setScores] = useState<Record<string, string>>({});
  const [rationale, setRationale] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: result, error, reload } = useLoad(
    () => api<EvalResult>(`/evals/runs/${runId}/result`),
    [runId],
  );
  const [rubric, setRubric] = useState<RubricVersion | null>(null);

  useEffect(() => {
    if (!result) return;
    api<RubricVersion>(`/evals/rubric-versions/${result.run.rubric_version_id}`).then(setRubric);
  }, [result?.run.rubric_version_id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit() {
    if (!rubric) return;
    setBusy(true);
    setActionError(null);
    try {
      const score_json: Record<string, number> = {};
      for (const criterion of rubric.criteria_json) {
        score_json[criterion.key] = Number(scores[criterion.key]);
      }
      await api("/evals/reviewer-scores", "POST", {
        eval_run_id: runId,
        score_json,
        rationale,
      });
      setRationale("");
      setScores({});
      reload();
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const run = result?.run;
  const awaiting = run?.status === "awaiting_human_score";
  const mayScore = can(user, "evaluator", "reviewer");
  const allFilled =
    rubric?.criteria_json.every((c) => scores[c.key] !== undefined && scores[c.key] !== "") ??
    false;

  return (
    <>
      <header className="page-header">
        <h1>Eval run</h1>
        {run ? <StatusBadge status={run.status} /> : null}
      </header>
      <ErrorNote error={error} />
      {run ? (
        <div className="two-col">
          <div>
            <Card title="Target">
              <dl>
                <dt>Target</dt>
                <dd>
                  {run.target_ref_type} <code>{run.target_ref_id}</code>
                </dd>
                {run.workflow_run_id ? (
                  <>
                    <dt>Workflow run</dt>
                    <dd>
                      <Link to={`/runs/${run.workflow_run_id}`}>{run.workflow_run_id}</Link>
                    </dd>
                  </>
                ) : null}
              </dl>
              {rubric ? (
                <p className="muted">
                  Rubric v{rubric.version_number} · scale {rubric.score_scale_json.min}–
                  {rubric.score_scale_json.max} · pass at ≥ {rubric.pass_threshold_json.min_total}{" "}
                  weighted total
                </p>
              ) : null}
            </Card>
            {result.decision ? (
              <Card title="Decision">
                <p>
                  <StatusBadge status={result.decision.decision_type} />{" "}
                  {result.decision.rationale}
                </p>
              </Card>
            ) : null}
            {result.scores.length > 0 ? (
              <Card title={`Scores (${result.scores.length})`}>
                {result.scores.map((score) => (
                  <p key={score.id}>
                    <StatusBadge status={score.pass_fail ? "pass" : "fail"} /> {score.rationale}
                  </p>
                ))}
              </Card>
            ) : null}
          </div>
          <Card title="Submit your score">
            {!awaiting ? (
              <Empty label="This run is not awaiting scores." />
            ) : !mayScore ? (
              <Empty label="Your role cannot submit scores." />
            ) : rubric ? (
              <>
                {rubric.criteria_json.map((criterion) => (
                  <label key={criterion.key}>
                    {criterion.key} (weight {criterion.weight})
                    {criterion.description ? (
                      <span className="muted"> — {criterion.description}</span>
                    ) : null}
                    <input
                      type="number"
                      min={rubric.score_scale_json.min}
                      max={rubric.score_scale_json.max}
                      step="any"
                      value={scores[criterion.key] ?? ""}
                      onChange={(e) =>
                        setScores((s) => ({ ...s, [criterion.key]: e.target.value }))
                      }
                    />
                  </label>
                ))}
                <label>
                  Rationale
                  <textarea
                    rows={3}
                    value={rationale}
                    onChange={(e) => setRationale(e.target.value)}
                  />
                </label>
                <ErrorNote error={actionError} />
                <button disabled={busy || !allFilled || rationale.trim() === ""} onClick={submit}>
                  {busy ? "Submitting…" : "Submit score"}
                </button>
              </>
            ) : null}
          </Card>
        </div>
      ) : null}
    </>
  );
}
