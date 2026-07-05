import { useEffect, useState, type ReactNode } from "react";

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{status.replaceAll("_", " ")}</span>;
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="card">
      {title ? <h2>{title}</h2> : null}
      {children}
    </section>
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

export function Time({ value }: { value: string | null }) {
  if (!value) return <span className="muted">—</span>;
  return <span>{new Date(value).toLocaleString()}</span>;
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
