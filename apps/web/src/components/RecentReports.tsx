import { formatClock, formatRelative, productLabel } from "../lib/format";
import type { ExternalObservation } from "../lib/types";
import { icons } from "./icons";

interface Props {
  observations: ExternalObservation[];
  limit?: number;
}

const SOURCE_LABELS: Record<string, string> = {
  USER: "You",
  REDDIT: "Reddit",
  PUBLIC_WEB: "Tracker",
};

const STATUS_LABELS: Record<string, string> = {
  AVAILABLE: "Available",
  RESTOCK: "Restocked",
  NOT_AVAILABLE: "Not available",
  UNKNOWN: "Unknown",
};

/**
 * The raw observations behind a machine's forecast.
 *
 * Status is a word first and a colour second, so the table is readable without
 * relying on red/green discrimination.
 */
export function RecentReports({ observations, limit = 8 }: Props) {
  const rows = observations.slice(0, limit);

  return (
    <section className="panel">
      <header className="panel__head">
        <span className="panel__icon" aria-hidden="true">
          {icons.doc}
        </span>
        <h2 className="panel__title">Recent reports</h2>
        {observations.length > rows.length && (
          <span className="panel__meta">
            showing {rows.length} of {observations.length}
          </span>
        )}
      </header>

      {rows.length === 0 ? (
        <p className="empty-note">
          No reports for this machine yet. Yours would be the first — and the
          forecast below is the regional pattern until there are enough.
        </p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Status</th>
                <th scope="col">Product</th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((observation) => {
                const when = observation.observedAt ?? observation.postedAt;
                const positive =
                  observation.availability === "AVAILABLE" ||
                  observation.availability === "RESTOCK";
                return (
                  <tr key={observation.id}>
                    <td>
                      <span className="table__time">{formatClock(when)}</span>
                      <span className="table__ago">{formatRelative(when)}</span>
                    </td>
                    <td>
                      <span
                        className={`pill pill--${positive ? "good" : "bad"}`}
                      >
                        {STATUS_LABELS[observation.availability] ?? observation.availability}
                      </span>
                      {observation.purchaseConfirmed && (
                        <span className="pill pill--strong" title="Purchase confirmed">
                          Bought
                        </span>
                      )}
                    </td>
                    <td className="table__muted">
                      {observation.product ? productLabel(observation.product) : "—"}
                    </td>
                    <td className="table__muted">
                      {observation.sourceUrl ? (
                        <a href={observation.sourceUrl} target="_blank" rel="noreferrer noopener">
                          {SOURCE_LABELS[observation.source] ?? observation.source}
                        </a>
                      ) : (
                        (SOURCE_LABELS[observation.source] ?? observation.source)
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
