import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { TemplateVersion, WorkflowRun, WorkflowTemplate } from "../api/types";
import { can, useAuth } from "../auth";
import { Card, ErrorNote, StatusBadge, Time, useLoad } from "../components/ui";

const CONTRACT_SKELETON = `## Identity
You are a <role>. Your only job in this stage is <one sentence>.

## Inputs
- <what this stage receives>

## Procedure
1. <first step>
2. <second step>

## Outputs
- deliverable: deliverable.md — <what it contains>

## Definition of done
- <verifiable completion criterion>

## Failure modes
- <what going wrong looks like>
`;

interface StageDraft {
  stage_key: string;
  display_name: string;
  review_required: boolean;
  eval_required: boolean;
  contract_markdown: string;
}

const emptyStage = (): StageDraft => ({
  stage_key: "",
  display_name: "",
  review_required: false,
  eval_required: false,
  contract_markdown: CONTRACT_SKELETON,
});

export function WorkflowsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: templates, error, reload } = useLoad(
    () => api<WorkflowTemplate[]>("/workflow/templates"),
    [],
  );
  const [building, setBuilding] = useState(false);
  const [busyTemplate, setBusyTemplate] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const operator = can(user, "operator");

  async function startRun(template: WorkflowTemplate) {
    setActionError(null);
    setBusyTemplate(template.id);
    try {
      const versions = await api<TemplateVersion[]>(
        `/workflow/templates/${template.id}/versions`,
      );
      if (versions.length === 0) {
        throw new Error("this template has no published version yet");
      }
      const run = await api<WorkflowRun>("/workflow/runs", "POST", {
        workflow_template_version_id: versions[0].id,
      });
      navigate(`/runs/${run.id}`);
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setBusyTemplate(null);
    }
  }

  return (
    <>
      <header className="page-header">
        <h1>Workflow blueprints</h1>
        {operator ? (
          <button className="accent" onClick={() => setBuilding((b) => !b)}>
            {building ? "Close builder" : "New blueprint"}
          </button>
        ) : null}
        <p className="sub">
          Staged governed workflows: every stage carries a contract, and runs pause for review or
          eval wherever required.
        </p>
      </header>
      <ErrorNote error={error} />
      <ErrorNote error={actionError} />

      {building ? <TemplateBuilder onCreated={() => { setBuilding(false); reload(); }} /> : null}

      {templates && templates.length === 0 && !building ? (
        <Card tone="lime">
          <h2>No blueprints yet</h2>
          <p className="muted">
            A blueprint defines the stages of a governed workflow — scope, draft, review gates,
            eval gates. Create your first one and start a run in under a minute.
          </p>
          {operator ? (
            <button className="on-light" onClick={() => setBuilding(true)}>
              Create your first blueprint
            </button>
          ) : null}
        </Card>
      ) : null}

      {(templates ?? []).map((template) => (
        <Card
          key={template.id}
          tone="light"
          actions={
            operator ? (
              <button
                className="on-light"
                disabled={busyTemplate === template.id}
                onClick={() => startRun(template)}
              >
                {busyTemplate === template.id ? "Starting…" : "Start run"}
              </button>
            ) : undefined
          }
          title={template.name}
        >
          <p className="muted">
            <code>{template.slug}</code> · <StatusBadge status={template.status} /> · created{" "}
            <Time value={template.created_at} />
          </p>
          {template.description ? <p>{template.description}</p> : null}
        </Card>
      ))}
    </>
  );
}

function TemplateBuilder({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [stages, setStages] = useState<StageDraft[]>([
    { ...emptyStage(), stage_key: "scope", display_name: "Scope" },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function patchStage(index: number, patch: Partial<StageDraft>) {
    setStages((all) => all.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  }

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const template = await api<WorkflowTemplate>("/workflow/templates", "POST", {
        name,
        slug,
        description,
      });
      await api(`/workflow/templates/${template.id}/versions`, "POST", {
        stages: stages.map((stage, index) => ({
          stage_key: stage.stage_key,
          display_name: stage.display_name || stage.stage_key,
          order_index: index,
          review_required: stage.review_required,
          eval_required: stage.eval_required,
          contract_markdown: stage.contract_markdown,
        })),
      });
      onCreated();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const valid =
    name.trim() !== "" &&
    /^[a-z0-9][a-z0-9-]*$/.test(slug) &&
    stages.length > 0 &&
    stages.every((s) => /^[a-z0-9][a-z0-9_-]*$/.test(s.stage_key));

  return (
    <Card title="New workflow template">
      <div className="grid-2">
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Research report" />
        </label>
        <label>
          Slug (lowercase, dashes)
          <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="research-report" />
        </label>
      </div>
      <label>
        Description
        <input value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>

      {stages.map((stage, index) => (
        <div className="stage-builder" key={index}>
          <div className="row spread">
            <strong>Stage {index + 1}</strong>
            {stages.length > 1 ? (
              <button
                className="ghost"
                onClick={() => setStages((all) => all.filter((_, i) => i !== index))}
              >
                <Trash2 size={14} /> remove
              </button>
            ) : null}
          </div>
          <div className="grid-2">
            <label>
              Stage key
              <input
                value={stage.stage_key}
                onChange={(e) => patchStage(index, { stage_key: e.target.value })}
                placeholder="scope"
              />
            </label>
            <label>
              Display name
              <input
                value={stage.display_name}
                onChange={(e) => patchStage(index, { display_name: e.target.value })}
                placeholder="Scope"
              />
            </label>
          </div>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={stage.review_required}
              onChange={(e) => patchStage(index, { review_required: e.target.checked })}
            />
            Pause for human review before advancing
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={stage.eval_required}
              onChange={(e) => patchStage(index, { eval_required: e.target.checked })}
            />
            Require a passing eval before advancing
          </label>
          <label>
            Stage contract (markdown — Identity and at least one Output are mandatory)
            <textarea
              rows={10}
              value={stage.contract_markdown}
              onChange={(e) => patchStage(index, { contract_markdown: e.target.value })}
            />
          </label>
        </div>
      ))}

      <div className="row">
        <button className="ghost" onClick={() => setStages((all) => [...all, emptyStage()])}>
          <Plus size={14} /> Add stage
        </button>
        <button className="accent" disabled={busy || !valid} onClick={create}>
          {busy ? "Creating…" : "Create template + version 1"}
        </button>
      </div>
      <ErrorNote error={error} />
    </Card>
  );
}
