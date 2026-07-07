import { useEffect, useState, type ReactNode } from "react";

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{status.replaceAll("_", " ")}</span>;
}

export function Card({
  title,
  children,
  tone,
  actions,
}: {
  title?: string;
  children: ReactNode;
  tone?: "light" | "lime" | "lavender";
  actions?: ReactNode;
}) {
  return (
    <section className={`card${tone ? ` ${tone}` : ""}`}>
      {title || actions ? (
        <div className="row spread" style={{ marginBottom: title ? 0 : 12 }}>
          {title ? <h2>{title}</h2> : <span />}
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function StatCard({
  label,
  value,
  icon,
  tone,
}: {
  label: string;
  value: number | string;
  icon: ReactNode;
  tone?: "lime" | "lavender";
}) {
  return (
    <div className={`stat${tone ? ` ${tone}` : ""}`}>
      <div className="stat-top">
        <span className="stat-icon">{icon}</span>
      </div>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p className="error-note">{error}</p>;
}

export function Empty({ label }: { label: string }) {
  return <p className="empty">{label}</p>;
}

export function ShortId({ id }: { id: string }) {
  return <code title={id}>{id.slice(0, 8)}</code>;
}

const ABSOLUTE_FMT: Intl.DateTimeFormatOptions = {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
};

function relativeTime(then: Date): string {
  const diffMs = then.getTime() - Date.now();
  const abs = Math.abs(diffMs);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["day", 86_400_000],
    ["hour", 3_600_000],
    ["minute", 60_000],
    ["second", 1_000],
  ];
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [unit, ms] of units) {
    if (abs >= ms || unit === "second") {
      return rtf.format(Math.round(diffMs / ms), unit);
    }
  }
  return "just now";
}

/**
 * Renders an evidence timestamp: absolute date+time inline (or relative when
 * asked), with the full localized timestamp + relative phrasing in the tooltip.
 */
export function Time({ value, relative = false }: { value: string | null; relative?: boolean }) {
  if (!value) return <span className="muted">—</span>;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return <span className="muted">—</span>;
  const absolute = date.toLocaleString(undefined, ABSOLUTE_FMT);
  const rel = relativeTime(date);
  return (
    <time dateTime={date.toISOString()} title={`${date.toLocaleString()} · ${rel}`}>
      {relative ? rel : absolute}
    </time>
  );
}

/** Generic data loader hook: fetch on mount / when deps change, expose reload. */
export function useLoad<T>(
  loader: () => Promise<T>,
  deps: unknown[],
): { data: T | null; error: string | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    loader()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { data, error, reload: () => setTick((t) => t + 1) };
}
