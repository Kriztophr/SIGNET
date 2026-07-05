import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { EvalResult, EvalRun, RubricVersion } from "../api/types";
import { can, useAuth } from "../auth";
import { Card, Empty, ErrorNote, ShortId, StatusBadge, Time, useLoad } from "../components/ui";

export function EvalsPage() {
  const { data: awaiting, error } = useLoad(
    () => api<EvalRun[]>("/evals/runs?status=awaiting_human_score"),
    [],
  );
  const { data: recent } = useLoad(() => api<EvalRun[]>("/evals/runs?limit=20"), []);

  return (
    <>
      <header className="page-header">
        <h1>Evals</h1>
        <p className="muted">Runs awaiting human scores, and recent activity.</p>
      </header>
      <ErrorNote error={error} />
      <Card title="Awaiting your score">
        {awaiting && awaiting.length === 0 ? (
          <Empty label="Nothing awaits scoring." />
        ) : (
          <EvalTable runs={awaiting ?? []} />
        )}
      </Card>
      <Card title="Recent eval runs">
        <EvalTable runs={recent ?? []} />
      </Card>
    </>
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
