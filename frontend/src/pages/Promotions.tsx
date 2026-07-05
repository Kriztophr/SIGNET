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
        <h1>Environment promotions</h1>
        <p className="muted">Evidence-gated promotion of environment versions.</p>
      </header>
      <ErrorNote error={error} />
      <ErrorNote error={actionError} />
      {promotions && promotions.length === 0 ? (
        <Card>
          <Empty label="No promotions requested yet." />
        </Card>
      ) : null}
      {(promotions ?? []).map((promotion) => (
        <Card key={promotion.id}>
          <div className="row spread">
            <div>
              <StatusBadge status={promotion.status} /> promotion{" "}
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
                {expanded === promotion.id ? "Hide evidence" : "Evidence"}
              </button>
              {promotion.status === "approval_pending" && manager ? (
                <button onClick={() => approve(promotion.id)}>Approve</button>
              ) : null}
            </div>
          </div>
          {promotion.decision_reason ? (
            <p className={promotion.status === "blocked" ? "error-note" : "muted"}>
              {promotion.decision_reason}
            </p>
          ) : null}
          {expanded === promotion.id ? (
            <pre className="artifact">{JSON.stringify(promotion.evidence_json, null, 2)}</pre>
          ) : null}
        </Card>
      ))}
    </>
  );
}
