import { formatRelative } from "../lib/format";
import type { SourceHealthEntry } from "../lib/types";

interface Props {
  sources: SourceHealthEntry[];
}

const STATUS_HINTS: Record<string, string> = {
  HEALTHY: "Fetched successfully on the last run",
  STALE: "Last successful fetch is older than expected",
  ERROR: "The last run failed",
  DISABLED: "Turned off in config/sources.yaml",
  RATE_LIMITED: "The source asked us to slow down",
  SKIPPED: "Deliberately not fetched - see the reason",
};

/**
 * Source transparency.
 *
 * Ingestion never fails silently: a source that is off, blocked or broken is
 * shown here with the reason, rather than simply contributing nothing.
 */
export function SourceHealthPanel({ sources }: Props) {
  if (sources.length === 0) {
    return (
      <section className="card source-health-card">
        <h2 className="section-title">Data sources</h2>
        <p className="empty-note">No source health has been recorded yet.</p>
      </section>
    );
  }

  const ordered = [...sources].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <section className="card source-health-card">
      <h2 className="section-title">Data sources</h2>
      <ul className="sources">
        {ordered.map((source) => (
          <li key={source.name} className="sources__item">
            <div className="sources__head">
              <span className="sources__name">{source.name}</span>
              <span
                className={`status status--${source.status.toLowerCase()}`}
                title={STATUS_HINTS[source.status] ?? source.status}
              >
                {source.status}
              </span>
            </div>
            <p className="sources__meta">
              {source.authority} · {source.records} record{source.records === 1 ? "" : "s"} ·
              checked {formatRelative(source.checked_at)}
              {source.last_success_at
                ? ` · last success ${formatRelative(source.last_success_at)}`
                : " · never succeeded"}
            </p>
            {source.message && <p className="sources__message">{source.message}</p>}
            {source.reason && source.status !== "HEALTHY" && (
              <p className="sources__reason">
                <code>SOURCE_SKIPPED</code> reason: <strong>{source.reason}</strong>
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
