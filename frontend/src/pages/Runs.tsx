import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, apiText } from "../api/client";
import type { Artifact, ContextManifest, StageRun, WorkflowRun } from "../api/types";
import { can, useAuth } from "../auth";
import { Card, Empty, ErrorNote, ShortId, StatusBadge, Time, useLoad } from "../components/ui";

export function RunsPage() {
  const { data: runs, error } = useLoad(() => api<WorkflowRun[]>("/workflow/runs"), []);
  return (
    <>
      <header className="page-header">
        <h1>Active workflows & runs</h1>
        <p className="muted">Every run, its live state, and inspectable workspace context.</p>
      </header>
      <ErrorNote error={error} />
      <Card>
        {runs && runs.length === 0 ? (
          <Empty label="No workflow runs yet." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Started</th>
                <th>Completed</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(runs ?? []).map((run) => (
                <tr key={run.id}>
                  <td>
                    <ShortId id={run.id} />
                  </td>
                  <td>
                    <StatusBadge status={run.status} />
                  </td>
                  <td>
                    <Time value={run.started_at} />
                  </td>
                  <td>
                    <Time value={run.completed_at} />
                  </td>
                  <td>
                    <Link className="button-link" to={`/runs/${run.id}`}>
                      Inspect
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}

const CANCELLABLE = ["pending", "running", "paused_for_review", "paused_for_eval"];

export function RunDetailPage() {
  const { runId } = useParams();
  const { user } = useAuth();
  const [selectedStage, setSelectedStage] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const { data: run, error, reload: reloadRun } = useLoad(
    () => api<WorkflowRun>(`/workflow/runs/${runId}`),
    [runId],
  );
  const { data: stages, reload: reloadStages } = useLoad(
    () => api<StageRun[]>(`/workflow/runs/${runId}/stages`),
    [runId],
  );

  const activeStage = selectedStage ?? run?.current_stage_run_id ?? stages?.[0]?.id ?? null;

  function refresh() {
    reloadRun();
    reloadStages();
  }

  async function cancelRun() {
    if (!window.confirm("Cancel this run? Open stages fail and any in-flight agent work is stopped.")) {
      return;
    }
    setCancelError(null);
    try {
      await api(`/workflow/runs/${runId}/cancel`, "POST");
      refresh();
    } catch (err) {
      setCancelError((err as Error).message);
    }
  }

  async function exportCompliancePack() {
    if (!runId) return;
    setExportError(null);
    setExporting(true);
    try {
      const packText = await apiText(`/governance/evidence-packs/runs/${runId}`);
      const blob = new Blob([packText], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `signet-evidence-pack-${runId.slice(0, 8)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError((err as Error).message);
    } finally {
      setExporting(false);
    }
  }

  return (
    <>
      <header className="page-header">
        <h1>Run {runId?.slice(0, 8)}</h1>
        <div className="row">
          {run ? <StatusBadge status={run.status} /> : null}
          {/* Auditor-only: matches the backend guard on /governance/evidence-packs. */}
          {can(user, "auditor") ? (
            <button className="accent" disabled={exporting} onClick={exportCompliancePack}>
              {exporting ? "Exporting…" : "Export Compliance Pack"}
            </button>
          ) : null}
          {run && can(user, "operator") && CANCELLABLE.includes(run.status) ? (
            <button className="danger" onClick={cancelRun}>
              Cancel run
            </button>
          ) : null}
        </div>
      </header>
      <ErrorNote error={error} />
      <ErrorNote error={cancelError} />
      <ErrorNote error={exportError} />
      <div className="stage-tabs">
        {(stages ?? []).map((stage, index) => (
          <button
            key={stage.id}
            className={activeStage === stage.id ? "tab active" : "tab"}
            onClick={() => setSelectedStage(stage.id)}
          >
            Stage {index + 1} · {stage.status.replaceAll("_", " ")}
          </button>
        ))}
      </div>
      {activeStage ? (
        <StagePanel key={activeStage} stageRunId={activeStage} onChanged={refresh} />
      ) : null}
    </>
  );
}

function StagePanel({ stageRunId, onChanged }: { stageRunId: string; onChanged: () => void }) {
  const { user } = useAuth();
  const [preview, setPreview] = useState<{ id: string; content: string } | null>(null);
  const [role, setRole] = useState("");
  const [content, setContent] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: stage, reload: reloadStage } = useLoad(
    () => api<StageRun>(`/workflow/stage-runs/${stageRunId}`),
    [stageRunId],
  );
  const { data: manifest } = useLoad(
    () => api<ContextManifest>(`/workflow/stage-runs/${stageRunId}/context-manifest`),
    [stageRunId],
  );
  const { data: artifacts, reload: reloadArtifacts } = useLoad(
    () => api<Artifact[]>(`/workflow/stage-runs/${stageRunId}/artifacts`),
    [stageRunId],
  );

  async function act(action: () => Promise<unknown>) {
    setActionError(null);
    try {
      await action();
      reloadStage();
      reloadArtifacts();
      onChanged();
    } catch (err) {
      setActionError((err as Error).message);
    }
  }

  const running = stage?.status === "running";
  const operator = can(user, "operator");

  return (
    <div className="two-col">
      <div>
        <Card title="Stage">
          <dl>
            <dt>Status</dt>
            <dd>
              <StatusBadge status={stage?.status ?? "…"} />
              {stage ? <span className="muted"> · attempt {stage.attempt_number}</span> : null}
            </dd>
            <dt>Started</dt>
            <dd>
              <Time value={stage?.started_at ?? null} />
            </dd>
            <dt>Completed</dt>
            <dd>
              <Time value={stage?.completed_at ?? null} />
            </dd>
          </dl>
        </Card>
        <Card title="Task Context & Attachments">
          {manifest ? (
            <dl>
              <dt>Workspace identity (layer 0)</dt>
              <dd>
                <code>{manifest.layer0_ref}</code>
                <br />
                <span className="muted">System persona & instructions</span>
              </dd>
              <dt>Stage sequence (layer 1)</dt>
              <dd>
                <code>{manifest.layer1_ref}</code>
                <br />
                <span className="muted">Workflow routing rules</span>
              </dd>
              <dt>Stage contract (layer 2)</dt>
              <dd>
                <code>{manifest.layer2_ref}</code>
                <br />
                <span className="muted">Input specifications & required deliverable rules</span>
              </dd>
              <dt>Previous Stage Deliverables</dt>
              <dd>
                {manifest.layer4_inputs_json.length === 0 ? (
                  <span className="muted">None (initial stage)</span>
                ) : (
                  manifest.layer4_inputs_json.map((input) => (
                    <div key={input.artifact_id}>
                      <code>
                        {input.artifact_role} v{input.version_number}
                      </code>{" "}
                      <span className="muted">from {input.from_stage_key}</span>
                    </div>
                  ))
                )}
              </dd>
              <dt>Token Estimate</dt>
              <dd>{manifest.token_estimate.toLocaleString()}</dd>
            </dl>
          ) : (
            <Empty label="No manifest for this stage." />
          )}
          {stage?.error_summary ? (
            <div className="error-note" style={{ marginTop: "0.8rem", padding: "0.8rem", borderRadius: "6px" }}>
              <strong>⚠️ Agent execution problem</strong>
              <p style={{ margin: "0.4rem 0 0 0" }}>{stage.error_summary}</p>
              {running ? (
                <p className="muted" style={{ margin: "0.4rem 0 0 0" }}>
                  The stage stays open — you can complete it manually by submitting the required
                  deliverable below.
                </p>
              ) : null}
            </div>
          ) : null}
        </Card>
        <Card title="Submitted Deliverables">
          {artifacts && artifacts.length === 0 ? (
            <Empty label="No deliverables submitted yet." />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Version</th>
                  <th>By</th>
                  <th>At</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(artifacts ?? []).map((artifact) => (
                  <tr key={artifact.id}>
                    <td>{artifact.artifact_role}</td>
                    <td>
                      v{artifact.version_number}
                      {artifact.is_human_edited ? " ✎" : ""}
                    </td>
                    <td>{artifact.created_by_type}</td>
                    <td>
                      <Time value={artifact.created_at} />
                    </td>
                    <td>
                      <button
                        className="ghost"
                        onClick={() =>
                          apiText(`/workflow/artifacts/${artifact.id}/content`).then((text) =>
                            setPreview({ id: artifact.id, content: text }),
                          )
                        }
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {preview ? <pre className="artifact">{preview.content}</pre> : null}
        </Card>
      </div>
      <Card title="Stage Actions & Deliverable Submission">
        {!operator ? (
          <Empty label="Operator role required for stage actions." />
        ) : !running ? (
          <Empty label={`Stage is ${stage?.status ?? "…"}; no actions available.`} />
        ) : (
          <>
            <label>
              Deliverable Role Name
              <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="e.g. scope_brief or draft_memo" />
            </label>
            <div className="row spread" style={{ marginBottom: "0.4rem", alignItems: "center" }}>
              <label style={{ margin: 0 }}>Deliverable Content (Markdown)</label>
              <button
                className="ghost"
                type="button"
                style={{ fontSize: "0.85rem", padding: "0.2rem 0.6rem" }}
                onClick={() => {
                  const targetRole = role.trim() || "scope_brief";
                  setRole(targetRole);
                  // Deliberately unmistakable placeholder: submitted artifacts enter the
                  // hash-chained audit record, so a template must never read as real work.
                  setContent(
                    `# [SAMPLE — replace before submitting]: ${targetRole}\n\n## Summary\n[Describe the work actually completed for this stage.]\n\n## Findings & Output\n- [Finding 1]\n- [Finding 2]\n`
                  );
                }}
              >
                Insert template
              </button>
            </div>
            <textarea
              rows={8}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Type or paste markdown deliverable content here..."
            />
            <div style={{ marginTop: "0.6rem" }}>
              <button
                disabled={role.trim() === "" || content === ""}
                onClick={() =>
                  act(() =>
                    api(`/workflow/stage-runs/${stageRunId}/artifacts`, "POST", {
                      artifact_role: role.trim(),
                      content,
                    }),
                  ).then(() => setContent(""))
                }
              >
                Submit Deliverable
              </button>
            </div>
            <hr style={{ margin: "1.2rem 0" }} />
            <div className="row spread">
              <button onClick={() => act(() => api(`/workflow/stage-runs/${stageRunId}/complete`, "POST"))}>
                Complete Stage & Advance
              </button>
              <button
                className="danger"
                onClick={() =>
                  act(() =>
                    api(`/workflow/stage-runs/${stageRunId}/fail`, "POST", {
                      error_summary: "failed by operator from console",
                    }),
                  )
                }
              >
                Fail Stage
              </button>
            </div>
          </>
        )}
        <ErrorNote error={actionError} />
      </Card>
    </div>
  );
}
