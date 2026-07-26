import { useState } from "react";
import { api } from "../api/client";
import type { Promotion } from "../api/types";
import { can, useAuth } from "../auth";
import { Card, Empty, ErrorNote, ShortId, StatusBadge, Time, useLoad } from "../components/ui";

export function PromotionsPage() {
  const { user } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const { data: promotions, error, reload } = useLoad(
    () => api<Promotion[]>("/environment/promotions"),
    [],
  );

  async function approve(promotionId: string) {
    setActionError(null);
    try {
      await api(`/environment/promotions/${promotionId}/approve`, "POST");
      reload();
    } catch (err) {
      setActionError((err as Error).message);
    }
  }

  const manager = can(user, "environment_manager");

  return (
    <>
      <header className="page-header">
        <h1>Release gate checklists</h1>
        <p className="muted">Evidence-gated release of environment versions.</p>
      </header>
      <ErrorNote error={error} />
      <ErrorNote error={actionError} />
      {promotions && promotions.length === 0 ? (
        <Card>
          <Empty label="No release gates requested yet." />
        </Card>
      ) : null}
      {(promotions ?? []).map((promotion) => (
        <Card key={promotion.id}>
          <div className="row spread">
            <div>
              <StatusBadge status={promotion.status} /> release gate{" "}
              <ShortId id={promotion.id} /> for environment version{" "}
              <ShortId id={promotion.environment_template_version_id} />
              <p className="muted">
                requested <Time value={promotion.requested_at} />
                {promotion.approved_at ? (
                  <>
                    {" "}
                    · approved <Time value={promotion.approved_at} />
                  </>
                ) : null}
              </p>
            </div>
            <div className="row">
              <button className="ghost" onClick={() => setExpanded(expanded === promotion.id ? null : promotion.id)}>
                {expanded === promotion.id ? "Hide checklist" : "Checklist"}
              </button>
              {promotion.status === "approval_pending" && manager ? (
                <button onClick={() => approve(promotion.id)}>Approve release</button>
              ) : null}
            </div>
          </div>
          {promotion.decision_reason ? (
            <p className={promotion.status === "blocked" ? "error-note" : "muted"}>
              {promotion.decision_reason}
            </p>
          ) : null}
          {expanded === promotion.id ? (
            <div className="evidence-panel" style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid var(--border)" }}>
              <div className="grid-2">
                <div>
                  <strong>Evaluation Evidence</strong>
                  {promotion.evidence_json?.eval_evidence ? (
                    <ul className="muted" style={{ paddingLeft: "1.2rem", margin: "0.4rem 0" }}>
                      <li>Total eval runs: {String((promotion.evidence_json.eval_evidence as Record<string, unknown>).total_runs ?? 0)}</li>
                      <li>Passed runs: {String((promotion.evidence_json.eval_evidence as Record<string, unknown>).passed_runs ?? 0)}</li>
                      <li>Failed runs: {String((promotion.evidence_json.eval_evidence as Record<string, unknown>).failed_runs ?? 0)}</li>
                      <li>Pass rate: {typeof (promotion.evidence_json.eval_evidence as Record<string, unknown>).pass_rate === "number" ? `${((promotion.evidence_json.eval_evidence as Record<string, unknown>).pass_rate as number * 100).toFixed(0)}%` : "N/A"}</li>
                    </ul>
                  ) : (
                    <p className="muted">No evaluation history evaluated.</p>
                  )}
                </div>
                <div>
                  <strong>Disagreements & Drift</strong>
                  <ul className="muted" style={{ paddingLeft: "1.2rem", margin: "0.4rem 0" }}>
                    <li>Open split decisions: {String((promotion.evidence_json?.disagreement_evidence as Record<string, unknown> | undefined)?.open_disagreements ?? 0)}</li>
                    <li>Active drift signals: {String((promotion.evidence_json?.drift_evidence as Record<string, unknown> | undefined)?.active_drift_signals ?? 0)}</li>
                  </ul>
                </div>
              </div>
              {Array.isArray(promotion.evidence_json?.blocking_reasons) && promotion.evidence_json.blocking_reasons.length > 0 ? (
                <div style={{ marginTop: "0.5rem" }}>
                  <strong className="danger-text">Blocking Reasons ({promotion.evidence_json.blocking_reasons.length})</strong>
                  <ul className="error-note" style={{ paddingLeft: "1.2rem", margin: "0.4rem 0" }}>
                    {promotion.evidence_json.blocking_reasons.map((reason: string, idx: number) => (
                      <li key={idx}>{reason}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <details style={{ marginTop: "0.8rem" }}>
                <summary className="muted" style={{ cursor: "pointer" }}>Raw JSON evidence payload</summary>
                <pre className="artifact">{JSON.stringify(promotion.evidence_json, null, 2)}</pre>
              </details>
            </div>
          ) : null}
        </Card>
      ))}
    </>
  );
}
