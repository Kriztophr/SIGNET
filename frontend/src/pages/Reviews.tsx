import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, apiText } from "../api/client";
import type { Artifact, ReviewTask } from "../api/types";
import { can, useAuth } from "../auth";
import { Card, Empty, ErrorNote, ShortId, StatusBadge, Time, useLoad } from "../components/ui";

export function ReviewsPage() {
  const { data: tasks, error } = useLoad(
    () => api<ReviewTask[]>("/governance/review-tasks?status=open"),
    [],
  );
  return (
    <>
      <header className="page-header">
        <h1>Approval queue</h1>
        <p className="muted">Open approval tasks awaiting a reviewer decision.</p>
      </header>
      <ErrorNote error={error} />
      <Card>
        {tasks && tasks.length === 0 ? (
          <Empty label="No open approval tasks. The queue is clear." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Task</th>
                <th>Run</th>
                <th>Required reviewer role</th>
                <th>Opened</th>
                <th>Due</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(tasks ?? []).map((task) => (
                <tr key={task.id}>
                  <td>
                    <ShortId id={task.id} />
                  </td>
                  <td>
                    <Link to={`/runs/${task.workflow_run_id}`}>
                      <ShortId id={task.workflow_run_id} />
                    </Link>
                  </td>
                  <td>{task.eligible_role}</td>
                  <td>
                    <Time value={task.created_at} />
                  </td>
                  <td>
                    <Time value={task.due_at} />
                  </td>
                  <td>
                    <Link className="button-link" to={`/reviews/${task.id}`}>
                      Review
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

type Decision = "approve" | "edit" | "reject" | "escalate";

export function ReviewDetailPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [rationale, setRationale] = useState("");
  const [decision, setDecision] = useState<Decision>("approve");
  const [editedContent, setEditedContent] = useState("");
  const [artifactContent, setArtifactContent] = useState<string | null>(null);
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: task, error } = useLoad(
    () => api<ReviewTask>(`/governance/review-tasks/${taskId}`),
    [taskId],
  );

  useEffect(() => {
    if (!task?.artifact_id) return;
    api<Artifact>(`/workflow/artifacts/${task.artifact_id}`).then(setArtifact);
    apiText(`/workflow/artifacts/${task.artifact_id}/content`).then((content) => {
      setArtifactContent(content);
      setEditedContent(content);
    });
  }, [task?.artifact_id]);

  async function submit() {
    if (!task) return;
    setBusy(true);
    setActionError(null);
    const body: Record<string, unknown> = { rationale };
    if (decision === "edit") {
      body.artifact_role = artifact?.artifact_role;
      body.content = editedContent;
    }
    try {
      await api(`/governance/review-tasks/${task.id}/${decision}`, "POST", body);
      navigate("/reviews");
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const decidable = task && (task.status === "open" || task.status === "in_progress");
  const mayDecide = can(user, "reviewer");

  return (
    <>
      <header className="page-header">
        <h1>Review task</h1>
        {task ? <StatusBadge status={task.status} /> : null}
      </header>
      <ErrorNote error={error} />
      {task ? (
        <div className="two-col">
          <Card title={`Artifact under review${artifact ? ` — ${artifact.artifact_role} v${artifact.version_number}` : ""}`}>
            {artifactContent === null ? (
              <Empty label="This task has no anchored artifact." />
            ) : (
              <pre className="artifact">{artifactContent}</pre>
            )}
            <p className="muted">
              Workflow run <Link to={`/runs/${task.workflow_run_id}`}>{task.workflow_run_id.slice(0, 8)}</Link>{" "}
              · eligible role: {task.eligible_role}
            </p>
          </Card>
          <Card title="Decision">
            {!decidable ? (
              <Empty label={`This task is already ${task.status}.`} />
            ) : !mayDecide ? (
              <Empty label="Your role cannot decide review tasks." />
            ) : (
              <>
                <div className="decision-tabs">
                  {(["approve", "edit", "reject", "escalate"] as Decision[]).map((d) => (
                    <button
                      key={d}
                      className={decision === d ? "tab active" : "tab"}
                      onClick={() => setDecision(d)}
                    >
                      {d}
                    </button>
                  ))}
                </div>
                {decision === "edit" ? (
                  <label>
                    Edited artifact ({artifact?.artifact_role})
                    <textarea
                      rows={10}
                      value={editedContent}
                      onChange={(e) => setEditedContent(e.target.value)}
                    />
                  </label>
                ) : null}
                <label>
                  Rationale (required, recorded in the audit trail)
                  <textarea
                    rows={3}
                    value={rationale}
                    onChange={(e) => setRationale(e.target.value)}
                  />
                </label>
                <ErrorNote error={actionError} />
                <button disabled={busy || rationale.trim() === ""} onClick={submit}>
                  {busy ? "Submitting…" : `Submit ${decision}`}
                </button>
              </>
            )}
          </Card>
        </div>
      ) : null}
    </>
  );
}
