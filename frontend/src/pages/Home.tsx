import { Boxes, ClipboardCheck, Gauge, TrendingDown } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { DriftSignal, EvalRun, ReviewTask, WorkflowRun } from "../api/types";
import { useAuth } from "../auth";
import { Card, Empty, ShortId, StatCard, StatusBadge, Time, useLoad } from "../components/ui";

export function HomePage() {
  const { user } = useAuth();
  const { data: runs } = useLoad(() => api<WorkflowRun[]>("/workflow/runs?limit=50"), []);
  const { data: reviews } = useLoad(
    () => api<ReviewTask[]>("/governance/review-tasks?status=open"),
    [],
  );
  const { data: awaiting } = useLoad(
    () => api<EvalRun[]>("/evals/runs?status=awaiting_human_score"),
    [],
  );
  const { data: drift } = useLoad(() => api<DriftSignal[]>("/evals/drift-signals"), []);

  const firstName = (user?.full_name ?? "").split(" ")[0] || "there";
  const active = (runs ?? []).filter((r) =>
    ["running", "paused_for_review", "paused_for_eval"].includes(r.status),
  );

  return (
    <>
      <header className="hero">
        <h1>Welcome, {firstName}!</h1>
        <p>Governed workflows with humans in the loop — here is what needs you.</p>
      </header>

      <div className="grid-4">
        <StatCard
          tone="lime"
          label="Reviews waiting on a human"
          value={reviews?.length ?? "…"}
          icon={<ClipboardCheck size={19} />}
        />
        <StatCard
          tone="lavender"
          label="Evals awaiting scores"
          value={awaiting?.length ?? "…"}
          icon={<Gauge size={19} />}
        />
        <StatCard
          label="Active workflow runs"
          value={active.length}
          icon={<Boxes size={19} />}
        />
        <StatCard
          label="Active drift signals"
          value={drift?.length ?? "…"}
          icon={<TrendingDown size={19} />}
        />
      </div>

      <div className="two-col">
        <Card
          tone="light"
          title="Recent runs"
          actions={<Link className="button-link" to="/runs">See all</Link>}
        >
          {runs && runs.length === 0 ? (
            <Empty label="No workflow runs yet — create a template and start one from Workflows." />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Started</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(runs ?? []).slice(0, 6).map((run) => (
                  <tr key={run.id}>
                    <td className="primary-cell">
                      <ShortId id={run.id} />
                    </td>
                    <td>
                      <StatusBadge status={run.status} />
                    </td>
                    <td>
                      <Time value={run.started_at} />
                    </td>
                    <td style={{ textAlign: "right" }}>
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
        <div>
          <Card title="Review queue" actions={<Link className="button-link" to="/reviews">Open</Link>}>
            {reviews && reviews.length === 0 ? (
              <Empty label="Queue is clear." />
            ) : (
              (reviews ?? []).slice(0, 4).map((task) => (
                <p key={task.id} className="row spread">
                  <span>
                    <ShortId id={task.id} /> <span className="muted">for {task.eligible_role}</span>
                  </span>
                  <Link className="button-link" to={`/reviews/${task.id}`}>
                    Review
                  </Link>
                </p>
              ))
            )}
          </Card>
          <Card title="Get started">
            <p className="muted">
              1. Create a <Link to="/workflows">workflow template</Link> with staged contracts.
              <br />
              2. Start a run and submit stage artifacts.
              <br />
              3. Decide reviews, score <Link to="/evals">evals</Link>, promote{" "}
              <Link to="/promotions">environments</Link>.
            </p>
          </Card>
        </div>
      </div>
    </>
  );
}
