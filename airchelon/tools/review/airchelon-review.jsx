import React, { useState, useEffect, useCallback } from "react";
import { Plus, Check, X, ChevronLeft, Sun, Moon, Copy, AlertTriangle } from "lucide-react";

/* ---------------------------------------------------------------
   Airchelon Editorial Control
   Implements the pipeline in docs/airchelon-editorial-operating-system.md
   Stages, risk tiers, review checklist, and audit log are load-bearing:
   the gates below are enforced, not advisory.
----------------------------------------------------------------*/

const STAGES = [
  { key: "ideation", label: "Ideation", note: "Topic proposed, calendar approved" },
  { key: "research", label: "Research", note: "Source list only — not prose" },
  { key: "draft", label: "Draft", note: "Written from sourced research, inline citations" },
  { key: "review", label: "Human review", note: "Mandatory gate" },
  { key: "revision", label: "Revision", note: "Re-check changed sections only" },
  { key: "compliance", label: "Compliance sign-off", note: "Tier 3 only — separate signer" },
  { key: "approval", label: "Final approval", note: "Editor-in-Chief, every tier" },
  { key: "published", label: "Published", note: "Audit entry recorded" },
];

const TIERS = {
  1: { name: "Perspective", desc: "Opinion and commentary. No specific claims about named entities or regulatory positions." },
  2: { name: "Analysis", desc: "Specific data, named companies, factual claims that could be wrong." },
  3: { name: "Regulated guidance", desc: "A reader in a regulated role could act on this as compliance guidance." },
};

/* Pinned model IDs per stage — display defaults only; the recorded value must be
   whatever actually ran, imported from the pipeline scripts' provenance blocks. */
const PROV_STAGES = [
  { key: "research", label: "Research agent", pinned: "claude-sonnet-5" },
  { key: "draft", label: "Drafting agent", pinned: "claude-opus-5" },
  { key: "disclosure", label: "Disclosure agent", pinned: "claude-haiku-4-5-20251001" },
];

const CHECKLIST = [
  { id: "sources", label: "Every factual claim traces to a source in the research file" },
  { id: "tier", label: "Risk tier assigned correctly" },
  { id: "voice", label: "Brand voice checked against the tone-of-voice guidance" },
  { id: "disclosure", label: "AI-involvement disclosure applied where required" },
];
const TIER3_CHECK = { id: "sme", label: "Named compliance or SME reviewer identified, separate from the editorial reviewer" };

const THEMES = {
  dark: {
    bg: "#141316", surface: "#1C1B1F", border: "#34323A",
    text: "#EDEAE2", muted: "#9C9890", accent: "#E08A34", accentHover: "#F2A253",
  },
  light: {
    bg: "#F7F4EE", surface: "#FBF9F5", border: "#DDD8CC",
    text: "#1B1A1E", muted: "#6E6B62", accent: "#B8631A", accentHover: "#965013",
  },
};

const SERIF = "'Newsreader', Georgia, 'Times New Roman', serif";
const SANS = "'IBM Plex Sans', ui-sans-serif, system-ui, sans-serif";
const MONO = "'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, monospace";

const STORAGE_KEY = "airchelon:board:v1";
const uid = () => Math.random().toString(36).slice(2, 9);
const stamp = () => new Date().toISOString();
const shortTime = (iso) => {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { day: "2-digit", month: "short" }) + " " +
      d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
};

export default function AirchelonReview() {
  const [mode, setMode] = useState("dark");
  const [pieces, setPieces] = useState([]);
  const [user, setUser] = useState("");
  const [openId, setOpenId] = useState(null);
  const [stageFilter, setStageFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [saveError, setSaveError] = useState(null);

  const t = THEMES[mode];

  useEffect(() => {
    (async () => {
      try {
        const res = await window.storage.get(STORAGE_KEY);
        if (res && res.value) {
          const parsed = JSON.parse(res.value);
          setPieces(parsed.pieces || []);
          setUser(parsed.user || "");
          setMode(parsed.mode || "dark");
        }
      } catch {
        /* no saved board yet — start empty */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const persist = useCallback(async (nextPieces, nextUser, nextMode) => {
    try {
      const r = await window.storage.set(
        STORAGE_KEY,
        JSON.stringify({ pieces: nextPieces, user: nextUser, mode: nextMode })
      );
      if (!r) setSaveError("Changes aren't saving. Copy anything important before closing.");
      else setSaveError(null);
    } catch {
      setSaveError("Changes aren't saving. Copy anything important before closing.");
    }
  }, []);

  const commit = (nextPieces) => { setPieces(nextPieces); persist(nextPieces, user, mode); };
  const updatePiece = (id, fn) => commit(pieces.map((p) => (p.id === id ? fn(p) : p)));
  const log = (p, entry) => ({ ...p, audit: [...p.audit, { at: stamp(), by: user || "unnamed", entry }] });

  const setUserName = (v) => { setUser(v); persist(pieces, v, mode); };
  const toggleMode = () => { const m = mode === "dark" ? "light" : "dark"; setMode(m); persist(pieces, user, m); };

  const addPiece = (title) => {
    const p = {
      id: uid(), title, tier: 1, stage: 0, drafter: "", editorialReviewer: "",
      complianceReviewer: "", checks: {}, provenance: {},
      audit: [{ at: stamp(), by: user || "unnamed", entry: "Created at Ideation, Tier 1" }],
    };
    commit([p, ...pieces]);
    setOpenId(p.id);
  };

  const open = pieces.find((p) => p.id === openId);
  const visible = stageFilter === "all" ? pieces : pieces.filter((p) => STAGES[p.stage].key === stageFilter);

  return (
    <div style={{ background: t.bg, color: t.text, fontFamily: SANS, minHeight: "100vh" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
        * { box-sizing: border-box; }
        button:focus-visible, input:focus-visible { outline: 2px solid ${t.accent}; outline-offset: 2px; }
        input::placeholder { color: ${t.muted}; }
      `}</style>

      <div className="mx-auto" style={{ maxWidth: 940, padding: "20px 16px 60px" }}>
        <Header t={t} mode={mode} toggleMode={toggleMode} user={user} setUserName={setUserName} />

        {saveError && (
          <div className="flex items-center gap-2 mb-4" style={{ fontFamily: MONO, fontSize: 12, color: t.accent }}>
            <AlertTriangle size={14} /> {saveError}
          </div>
        )}

        {loading ? (
          <p style={{ fontFamily: MONO, fontSize: 12, color: t.muted }}>Loading board…</p>
        ) : open ? (
          <Detail
            t={t} piece={open} user={user}
            onClose={() => setOpenId(null)}
            update={(fn) => updatePiece(open.id, fn)}
            log={log}
          />
        ) : (
          <Board
            t={t} pieces={visible} all={pieces}
            stageFilter={stageFilter} setStageFilter={setStageFilter}
            onOpen={setOpenId} onAdd={addPiece}
          />
        )}
      </div>
    </div>
  );
}

/* ---------------------------- header ---------------------------- */

function Header({ t, mode, toggleMode, user, setUserName }) {
  return (
    <header className="mb-8" style={{ borderBottom: `1px solid ${t.border}`, paddingBottom: 16 }}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 style={{ fontFamily: SERIF, fontSize: 30, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.1, margin: 0 }}>
            Airchelon <span style={{ color: t.accent }}>Editorial Control</span>
          </h1>
          <p style={{ fontFamily: MONO, fontSize: 11, color: t.muted, marginTop: 6, letterSpacing: "0.04em" }}>
            NOTHING PUBLISHES WITHOUT A NAMED HUMAN SIGN-OFF
          </p>
        </div>
        <button onClick={toggleMode} aria-label="Switch colour mode"
          style={{ background: "none", border: `1px solid ${t.border}`, color: t.muted, padding: 8, cursor: "pointer", lineHeight: 0 }}>
          {mode === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>
      <div className="flex items-center gap-2 mt-4">
        <label style={{ fontFamily: MONO, fontSize: 11, color: t.muted, letterSpacing: "0.04em" }}>SIGNING AS</label>
        <input
          value={user} onChange={(e) => setUserName(e.target.value)} placeholder="your name"
          style={{ background: "transparent", border: "none", borderBottom: `1px solid ${t.border}`,
            color: user ? t.accent : t.muted, fontFamily: MONO, fontSize: 12, padding: "2px 4px", width: 180 }}
        />
      </div>
    </header>
  );
}

/* ---------------------------- board ---------------------------- */

function Board({ t, pieces, all, stageFilter, setStageFilter, onOpen, onAdd }) {
  const [draft, setDraft] = useState("");
  const count = (key) => all.filter((p) => STAGES[p.stage].key === key).length;

  const submit = () => { if (draft.trim()) { onAdd(draft.trim()); setDraft(""); } };

  return (
    <>
      <div className="flex gap-2 mb-6">
        <input
          value={draft} onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Working title of a new piece"
          style={{ flex: 1, background: t.surface, border: `1px solid ${t.border}`, color: t.text,
            fontFamily: SANS, fontSize: 14, padding: "10px 12px" }}
        />
        <button onClick={submit}
          style={{ background: t.accent, color: "#141316", border: "none", padding: "10px 14px",
            fontFamily: MONO, fontSize: 12, fontWeight: 500, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
          <Plus size={14} /> Add
        </button>
      </div>

      <div className="flex flex-wrap gap-1 mb-6">
        <Pill t={t} active={stageFilter === "all"} onClick={() => setStageFilter("all")} label={`All · ${all.length}`} />
        {STAGES.map((s) => (
          <Pill key={s.key} t={t} active={stageFilter === s.key} onClick={() => setStageFilter(s.key)}
            label={`${s.label} · ${count(s.key)}`} />
        ))}
      </div>

      {pieces.length === 0 ? (
        <div style={{ border: `1px dashed ${t.border}`, padding: "40px 20px", textAlign: "center" }}>
          <p style={{ fontFamily: SERIF, fontSize: 18, margin: 0 }}>No pieces in this bay.</p>
          <p style={{ fontFamily: MONO, fontSize: 11, color: t.muted, marginTop: 8, letterSpacing: "0.03em" }}>
            ADD A WORKING TITLE ABOVE TO START THE AUDIT TRAIL AT PIECE #1
          </p>
        </div>
      ) : (
        <div className="flex flex-col" style={{ gap: 1, background: t.border, border: `1px solid ${t.border}` }}>
          {pieces.map((p) => <Strip key={p.id} t={t} p={p} onClick={() => onOpen(p.id)} />)}
        </div>
      )}
    </>
  );
}

function Pill({ t, active, onClick, label }) {
  return (
    <button onClick={onClick}
      style={{ background: active ? t.accent : "transparent", color: active ? "#141316" : t.muted,
        border: `1px solid ${active ? t.accent : t.border}`, fontFamily: MONO, fontSize: 11,
        padding: "4px 9px", cursor: "pointer", letterSpacing: "0.02em" }}>
      {label}
    </button>
  );
}

/* Flight-progress-strip style row: tier band, title, stage, signers */
function Strip({ t, p, onClick }) {
  const tierWidth = { 1: 3, 2: 6, 3: 10 }[p.tier];
  return (
    <button onClick={onClick}
      style={{ display: "flex", alignItems: "stretch", gap: 0, background: t.surface, border: "none",
        cursor: "pointer", textAlign: "left", width: "100%", padding: 0 }}>
      <div style={{ width: tierWidth, background: t.accent, flexShrink: 0 }} />
      <div className="flex-1" style={{ padding: "12px 14px", minWidth: 0 }}>
        <div className="flex items-baseline gap-2 flex-wrap">
          <span style={{ fontFamily: MONO, fontSize: 10, color: t.accent, letterSpacing: "0.06em" }}>T{p.tier}</span>
          <span style={{ fontFamily: SERIF, fontSize: 17, color: t.text, lineHeight: 1.25 }}>{p.title}</span>
        </div>
        <div className="flex gap-3 flex-wrap" style={{ marginTop: 6, fontFamily: MONO, fontSize: 10.5, color: t.muted, letterSpacing: "0.03em" }}>
          <span>{STAGES[p.stage].label.toUpperCase()}</span>
          <span>·</span>
          <span>{p.audit.length} LOG {p.audit.length === 1 ? "ENTRY" : "ENTRIES"}</span>
        </div>
      </div>
    </button>
  );
}

/* ---------------------------- detail ---------------------------- */

function Detail({ t, piece: p, user, onClose, update, log }) {
  const [warn, setWarn] = useState(null);
  const [copied, setCopied] = useState(false);
  const [provPaste, setProvPaste] = useState("");
  const [overrideFlag, setOverrideFlag] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const stage = STAGES[p.stage];
  const items = p.tier === 3 ? [...CHECKLIST, TIER3_CHECK] : CHECKLIST;
  const allChecked = items.every((i) => p.checks[i.id]);
  const prov = p.provenance || {};
  const provComplete = PROV_STAGES.every(
    (s) => prov[s.key] && prov[s.key].model_id && prov[s.key].prompt_commit
  );

  const requireUser = () => {
    if (!user.trim()) { setWarn("Enter your name at the top first. Every action is logged against a named person."); return false; }
    return true;
  };

  const setTier = (n) => {
    if (n < p.tier) { setWarn("Tier can be escalated, not downgraded. Reviewers may raise a piece's risk tier only."); return; }
    if (n === p.tier) return;
    if (!requireUser()) return;
    setWarn(null);
    update((piece) => log({ ...piece, tier: n }, `Tier escalated ${piece.tier} → ${n}`));
  };

  const toggleCheck = (id) => {
    if (!requireUser()) return;
    setWarn(null);
    update((piece) => {
      const on = !piece.checks[id];
      const label = items.find((i) => i.id === id).label;
      return log({ ...piece, checks: { ...piece.checks, [id]: on } }, `${on ? "Checked" : "Cleared"}: ${label}`);
    });
  };

  const advance = () => {
    if (!requireUser()) return;
    const key = stage.key;

    if (key === "review" || key === "revision") {
      if (!allChecked) { setWarn("Every checklist item must be ticked before this piece leaves review."); return; }
      if (!p.editorialReviewer.trim()) { setWarn("Name the editorial reviewer before advancing."); return; }
      const next = p.tier === 3 ? 5 : 6;
      setWarn(null);
      update((piece) => log({ ...piece, stage: next }, `Cleared human review (Tier ${piece.tier}), reviewed by ${piece.editorialReviewer}`));
      return;
    }

    if (key === "compliance") {
      const c = p.complianceReviewer.trim();
      if (!c) { setWarn("Tier 3 requires a named compliance or SME sign-off."); return; }
      if (c.toLowerCase() === p.editorialReviewer.trim().toLowerCase()) {
        setWarn("The compliance signer must be a different person from the editorial reviewer. No single person clears both.");
        return;
      }
      if (!provComplete) {
        setWarn("Tier 3 sign-off requires complete provenance: model ID and prompt commit for research, draft, and disclosure. Import the pipeline scripts' provenance blocks below.");
        return;
      }
      setWarn(null);
      update((piece) => log({ ...piece, stage: 6 }, `Compliance sign-off by ${c}`));
      return;
    }

    if (key === "approval") {
      setWarn(null);
      update((piece) => log({ ...piece, stage: 7 }, `Final approval and publish`));
      return;
    }

    if (key === "published") return;
    setWarn(null);
    update((piece) => log({ ...piece, stage: piece.stage + 1 }, `Advanced to ${STAGES[piece.stage + 1].label}`));
  };

  const sendBack = () => {
    if (!requireUser()) return;
    setWarn(null);
    update((piece) => log({ ...piece, stage: 4 }, "Sent back for revision"));
  };

  const shortHash = (h) => (h && h.length > 12 ? h.slice(0, 12) : h || "—");

  /* Paste-import of the provenance block each pipeline script prints on exit. */
  const importProvenance = () => {
    if (!requireUser()) return;
    let parsed;
    try {
      const raw = provPaste.trim();
      const start = raw.indexOf("{"); const end = raw.lastIndexOf("}");
      parsed = JSON.parse(raw.slice(start, end + 1));
    } catch { setWarn("Could not parse that as JSON. Paste the block exactly as the script printed it."); return; }
    const stages = parsed.airchelon_provenance || parsed;
    const known = PROV_STAGES.filter((s) => stages[s.key] && stages[s.key].model_id);
    if (known.length === 0) { setWarn("No recognised stage (research / draft / disclosure) in that block."); return; }
    setWarn(null);
    setProvPaste("");
    update((piece) => {
      let next = { ...piece, provenance: { ...(piece.provenance || {}) } };
      for (const s of known) {
        next.provenance[s.key] = { ...stages[s.key] };
        next = log(
          next,
          `Provenance recorded — ${s.label}: ${stages[s.key].model_id} @ prompt ${shortHash(stages[s.key].prompt_commit)}`
        );
      }
      return next;
    });
  };

  const setProvField = (stageKey, field, value) =>
    update((piece) => ({
      ...piece,
      provenance: {
        ...(piece.provenance || {}),
        [stageKey]: { ...((piece.provenance || {})[stageKey] || {}), [field]: value },
      },
    }));

  /* An overridden flag with a recorded reason is a defensible judgement; one
     without a record is indistinguishable from a missed flag. Reason required. */
  const recordOverride = () => {
    if (!requireUser()) return;
    if (!overrideFlag.trim()) { setWarn("Quote the flag you are overriding."); return; }
    if (!overrideReason.trim()) { setWarn("An override without a recorded reason is indistinguishable from a missed flag. State the reason."); return; }
    setWarn(null);
    update((piece) =>
      log(piece, `Disclosure flag overridden: "${overrideFlag.trim()}" — reason: ${overrideReason.trim()}`)
    );
    setOverrideFlag("");
    setOverrideReason("");
  };

  const provenance = `Researched by Airchelon's agents, drafted by ${p.drafter || "—"}, reviewed and approved by ${p.editorialReviewer || "—"}${p.tier === 3 && p.complianceReviewer ? `, compliance sign-off by ${p.complianceReviewer}` : ""}.`;

  const copyProvenance = async () => {
    try { await navigator.clipboard.writeText(provenance); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch { setWarn("Copy failed — select the text manually."); }
  };

  const field = (label, value, key, placeholder) => (
    <div className="flex flex-col gap-1">
      <label style={{ fontFamily: MONO, fontSize: 10, color: t.muted, letterSpacing: "0.06em" }}>{label}</label>
      <input value={value} placeholder={placeholder}
        onChange={(e) => update((piece) => ({ ...piece, [key]: e.target.value }))}
        style={{ background: "transparent", border: "none", borderBottom: `1px solid ${t.border}`,
          color: t.text, fontFamily: MONO, fontSize: 12.5, padding: "3px 2px" }} />
    </div>
  );

  return (
    <>
      <button onClick={onClose}
        style={{ background: "none", border: "none", color: t.muted, fontFamily: MONO, fontSize: 11,
          cursor: "pointer", padding: 0, display: "flex", alignItems: "center", gap: 4, marginBottom: 16 }}>
        <ChevronLeft size={13} /> BACK TO BOARD
      </button>

      <h2 style={{ fontFamily: SERIF, fontSize: 26, fontWeight: 600, lineHeight: 1.2, margin: 0 }}>{p.title}</h2>
      <p style={{ fontFamily: MONO, fontSize: 11, color: t.accent, marginTop: 8, letterSpacing: "0.05em" }}>
        {stage.label.toUpperCase()} — {stage.note}
      </p>

      {warn && (
        <div className="flex gap-2 mt-4" style={{ border: `1px solid ${t.accent}`, padding: "10px 12px" }}>
          <AlertTriangle size={15} style={{ color: t.accent, flexShrink: 0, marginTop: 1 }} />
          <p style={{ fontFamily: SANS, fontSize: 13, margin: 0, lineHeight: 1.45 }}>{warn}</p>
        </div>
      )}

      <Section t={t} title="Risk tier">
        <div className="flex flex-col gap-1">
          {[1, 2, 3].map((n) => (
            <button key={n} onClick={() => setTier(n)}
              style={{ display: "flex", gap: 10, textAlign: "left", background: p.tier === n ? t.surface : "transparent",
                border: `1px solid ${p.tier === n ? t.accent : t.border}`, padding: "10px 12px", cursor: "pointer", color: t.text }}>
              <span style={{ fontFamily: MONO, fontSize: 11, color: p.tier === n ? t.accent : t.muted, flexShrink: 0 }}>T{n}</span>
              <span>
                <span style={{ fontFamily: SANS, fontSize: 13.5, fontWeight: 600 }}>{TIERS[n].name}</span>
                <span style={{ display: "block", fontFamily: SANS, fontSize: 12.5, color: t.muted, marginTop: 2, lineHeight: 1.4 }}>{TIERS[n].desc}</span>
              </span>
            </button>
          ))}
        </div>
      </Section>

      <Section t={t} title="Attribution">
        <div className="flex flex-col gap-4">
          {field("DRAFTED BY", p.drafter, "drafter", "agent or writer name")}
          {field("EDITORIAL REVIEWER", p.editorialReviewer, "editorialReviewer", "name")}
          {p.tier === 3 && field("COMPLIANCE / SME SIGNER", p.complianceReviewer, "complianceReviewer", "must differ from reviewer")}
        </div>
      </Section>

      <Section t={t} title="Provenance">
        <p style={{ fontFamily: SANS, fontSize: 12.5, color: t.muted, margin: "0 0 12px", lineHeight: 1.5 }}>
          Pinned model ID and prompt commit hash per stage — what makes a Tier 3 piece
          defensible under audit. Paste the block each pipeline script prints, or fill the
          fields by hand.{p.tier === 3 && !provComplete && " Tier 3 cannot clear compliance sign-off until this is complete."}
        </p>
        <div className="flex flex-col gap-3">
          {PROV_STAGES.map((s) => {
            const rec = prov[s.key] || {};
            return (
              <div key={s.key} style={{ border: `1px solid ${rec.model_id && rec.prompt_commit ? t.accent : t.border}`, padding: "10px 12px" }}>
                <p style={{ fontFamily: MONO, fontSize: 10, color: t.muted, letterSpacing: "0.06em", margin: "0 0 8px" }}>
                  {s.label.toUpperCase()}
                </p>
                <div className="flex flex-wrap gap-4">
                  <div className="flex flex-col gap-1" style={{ minWidth: 220 }}>
                    <label style={{ fontFamily: MONO, fontSize: 10, color: t.muted }}>MODEL ID</label>
                    <input value={rec.model_id || ""} placeholder={s.pinned}
                      onChange={(e) => setProvField(s.key, "model_id", e.target.value)}
                      style={{ background: "transparent", border: "none", borderBottom: `1px solid ${t.border}`,
                        color: t.text, fontFamily: MONO, fontSize: 12, padding: "3px 2px" }} />
                  </div>
                  <div className="flex flex-col gap-1" style={{ minWidth: 220, flex: 1 }}>
                    <label style={{ fontFamily: MONO, fontSize: 10, color: t.muted }}>PROMPT COMMIT</label>
                    <input value={rec.prompt_commit || ""} placeholder="git hash of the prompt that ran"
                      onChange={(e) => setProvField(s.key, "prompt_commit", e.target.value)}
                      style={{ background: "transparent", border: "none", borderBottom: `1px solid ${t.border}`,
                        color: t.text, fontFamily: MONO, fontSize: 12, padding: "3px 2px" }} />
                  </div>
                </div>
                {rec.source_file_sha256 && (
                  <p style={{ fontFamily: MONO, fontSize: 10.5, color: t.muted, margin: "8px 0 0" }}>
                    source sha256 {shortHash(rec.source_file_sha256)} {rec.generated_at ? `· ${shortTime(rec.generated_at)}` : ""}
                  </p>
                )}
              </div>
            );
          })}
        </div>
        <div className="flex flex-col gap-2" style={{ marginTop: 14 }}>
          <textarea
            value={provPaste} onChange={(e) => setProvPaste(e.target.value)} rows={3}
            placeholder='Paste a provenance block: { "airchelon_provenance": { "research": { ... } } }'
            style={{ background: t.surface, border: `1px solid ${t.border}`, color: t.text,
              fontFamily: MONO, fontSize: 11.5, padding: "8px 10px", resize: "vertical" }}
          />
          <button onClick={importProvenance}
            style={{ alignSelf: "flex-start", background: "transparent", border: `1px solid ${t.border}`,
              color: t.muted, fontFamily: MONO, fontSize: 11, padding: "6px 12px", cursor: "pointer" }}>
            Import and record in audit log
          </button>
        </div>
      </Section>

      <Section t={t} title="Review checklist">
        <div className="flex flex-col gap-1">
          {items.map((i) => {
            const on = !!p.checks[i.id];
            return (
              <button key={i.id} onClick={() => toggleCheck(i.id)}
                style={{ display: "flex", gap: 10, alignItems: "flex-start", background: "transparent",
                  border: "none", padding: "7px 0", cursor: "pointer", textAlign: "left", color: t.text }}>
                <span style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1, border: `1px solid ${on ? t.accent : t.border}`,
                  background: on ? t.accent : "transparent", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {on && <Check size={12} color="#141316" strokeWidth={3} />}
                </span>
                <span style={{ fontFamily: SANS, fontSize: 13.5, lineHeight: 1.45, color: on ? t.text : t.muted }}>{i.label}</span>
              </button>
            );
          })}
        </div>
      </Section>

      <Section t={t} title="Disclosure flag overrides">
        <p style={{ fontFamily: SANS, fontSize: 12.5, color: t.muted, margin: "0 0 10px", lineHeight: 1.5 }}>
          Overriding a flag from the disclosure agent is a judgement call, and it is only
          defensible if the reason is on the record. Quote the flag, state the reason.
        </p>
        <div className="flex flex-col gap-3">
          <input value={overrideFlag} onChange={(e) => setOverrideFlag(e.target.value)}
            placeholder="The flag being overridden, quoted from the flag list"
            style={{ background: t.surface, border: `1px solid ${t.border}`, color: t.text,
              fontFamily: SANS, fontSize: 13, padding: "8px 10px" }} />
          <input value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)}
            placeholder="Why this flag does not apply (required)"
            style={{ background: t.surface, border: `1px solid ${t.border}`, color: t.text,
              fontFamily: SANS, fontSize: 13, padding: "8px 10px" }} />
          <button onClick={recordOverride}
            style={{ alignSelf: "flex-start", background: "transparent", border: `1px solid ${t.border}`,
              color: t.muted, fontFamily: MONO, fontSize: 11, padding: "6px 12px", cursor: "pointer" }}>
            Record override in audit log
          </button>
        </div>
      </Section>

      <Section t={t} title="Advance">
        <div className="flex flex-wrap gap-2">
          {stage.key !== "published" && (
            <button onClick={advance}
              style={{ background: t.accent, color: "#141316", border: "none", padding: "10px 16px",
                fontFamily: MONO, fontSize: 12, fontWeight: 500, cursor: "pointer" }}>
              {stage.key === "approval" ? "Approve and publish" : stage.key === "compliance" ? "Record compliance sign-off" : "Advance"}
            </button>
          )}
          {(stage.key === "review" || stage.key === "compliance" || stage.key === "approval") && (
            <button onClick={sendBack}
              style={{ background: "transparent", color: t.muted, border: `1px solid ${t.border}`,
                padding: "10px 16px", fontFamily: MONO, fontSize: 12, cursor: "pointer" }}>
              Send back for revision
            </button>
          )}
        </div>
        {stage.key === "published" && (
          <div style={{ marginTop: 12, border: `1px solid ${t.border}`, padding: "12px 14px" }}>
            <p style={{ fontFamily: MONO, fontSize: 10, color: t.muted, letterSpacing: "0.06em", margin: 0 }}>PUBLIC PROVENANCE TAG</p>
            <p style={{ fontFamily: SERIF, fontSize: 15, lineHeight: 1.5, margin: "8px 0 10px" }}>{provenance}</p>
            <button onClick={copyProvenance}
              style={{ background: "transparent", border: `1px solid ${t.border}`, color: t.muted,
                fontFamily: MONO, fontSize: 11, padding: "5px 10px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
              <Copy size={12} /> {copied ? "Copied" : "Copy"}
            </button>
          </div>
        )}
      </Section>

      <Section t={t} title="Audit log">
        <div className="flex flex-col" style={{ gap: 0 }}>
          {[...p.audit].reverse().map((a, idx) => (
            <div key={idx} style={{ display: "flex", gap: 12, padding: "8px 0", borderTop: idx === 0 ? "none" : `1px solid ${t.border}` }}>
              <span style={{ fontFamily: MONO, fontSize: 10.5, color: t.muted, flexShrink: 0, width: 92 }}>{shortTime(a.at)}</span>
              <span style={{ fontFamily: SANS, fontSize: 13, lineHeight: 1.45 }}>
                {a.entry} <span style={{ color: t.muted }}>— {a.by}</span>
              </span>
            </div>
          ))}
        </div>
      </Section>
    </>
  );
}

function Section({ t, title, children }) {
  return (
    <section style={{ marginTop: 32 }}>
      <h3 style={{ fontFamily: MONO, fontSize: 10.5, color: t.muted, letterSpacing: "0.09em",
        borderBottom: `1px solid ${t.border}`, paddingBottom: 7, marginBottom: 14, textTransform: "uppercase" }}>
        {title}
      </h3>
      {children}
    </section>
  );
}
