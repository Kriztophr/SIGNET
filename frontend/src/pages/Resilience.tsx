import { useState } from "react";
import { api } from "../api/client";
import type { CoverageSnapshot, DriftSignal } from "../api/types";
import { can, useAuth } from "../auth";
import { Card, Empty, ErrorNote, ShortId, StatusBadge, Time, useLoad } from "../components/ui";

export function ResiliencePage() {
  const { user } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const { data: snapshots, error, reload } = useLoad(
    () => api<CoverageSnapshot[]>("/resilience/coverage-snapshots"),
    [],
  );
  const { data: drift } = useLoad(() => api<DriftSignal[]>("/evals/drift-signals"), []);

  async function capture() {
    setActionError(null);
    try {
      await api("/resilience/coverage-snapshots", "POST");
      reload();
    } catch (err) {
      setActionError((err as Error).message);
    }
  }

  return (
    <>
      <header className="page-header">
        <h1>Resilience</h1>
        <p className="muted">
          Can humans still verify, override, and reconstruct critical work?
        </p>
      </header>
      <ErrorNote error={error} />
      <ErrorNote error={actionError} />
      <Card title="Strategic coverage">
        {can(user, "resilience_manager") ? (
          <p>
            <button onClick={capture}>Capture fresh snapshots</button>
          </p>
        ) : null}
        {snapshots && snapshots.length === 0 ? (
          <Empty label="No coverage snapshots captured yet." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Capability</th>
                <th>Qualified</th>
                <th>Required</th>
                <th>Status</th>
                <th>Captured</th>
              </tr>
            </thead>
            <tbody>
              {(snapshots ?? []).map((snapshot) => (
                <tr key={snapshot.id}>
                  <td>
                    <ShortId id={snapshot.critical_capability_id} />
                  </td>
                  <td>{snapshot.qualified_subject_count}</td>
                  <td>{snapshot.minimum_required_count}</td>
                  <td>
                    <StatusBadge status={snapshot.coverage_status} />
                  </td>
                  <td>
                    <Time value={snapshot.captured_at} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Card title="Active drift signals">
        {drift && drift.length === 0 ? (
          <Empty label="No drift detected." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Scope</th>
                <th>Signal</th>
                <th>Strength</th>
                <th>Detected</th>
              </tr>
            </thead>
            <tbody>
              {(drift ?? []).map((signal) => (
                <tr key={signal.id}>
                  <td>
                    {signal.scope_type}:{signal.scope_ref.slice(0, 12)}
                  </td>
                  <td>{signal.signal_type.replaceAll("_", " ")}</td>
                  <td>{signal.signal_strength.toFixed(2)}</td>
                  <td>
                    <Time value={signal.detected_at} />
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
