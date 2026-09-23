import { formatRelative, productLabel } from "../lib/format";
import type { LastKnownStatus as LastKnownStatusData } from "../lib/types";

interface Props {
  status: LastKnownStatusData | null;
}

const LABELS: Record<string, string> = {
  AVAILABLE: "Product was available",
  NOT_AVAILABLE: "Sold out or unavailable",
  RESTOCK: "Restocked",
  UNKNOWN: "Unknown",
};

const SOURCE_LABELS: Record<string, string> = {
  USER: "your report",
  REDDIT: "a Reddit report",
  PUBLIC_WEB: "a community tracker",
};

/** Beyond this the report says what was once true, not what is likely now. */
const STALE_AFTER_HOURS = 48;

/**
 * The most recent real observation, shown even when there is too little
 * history to forecast.
 *
 * "Sold out, reported four months ago" is genuine information and far more
 * useful than a bare INSUFFICIENT DATA. It is labelled with its age and, once
 * stale, explicitly marked as not predictive - the forecast engine already
 * discounts it to nearly nothing through recency decay.
 */
export function LastKnownStatus({ status }: Props) {
  if (!status) return null;

  const stale = status.ageHours > STALE_AFTER_HOURS;
  const days = Math.round(status.ageHours / 24);
  const tone = status.availability === "NOT_AVAILABLE" ? "negative" : "positive";

  return (
    <div className={`known-status known-status--${stale ? "stale" : tone}`}>
      <div className="known-status__head">
        <span className="known-status__label">Last known status</span>
        {stale && (
          <span className="known-status__stale-tag" title="Too old to predict from">
            STALE
          </span>
        )}
      </div>

      <p className="known-status__value">
        {LABELS[status.availability] ?? status.availability}
        {status.product ? ` — ${productLabel(status.product)}` : ""}
        {status.purchaseConfirmed ? " (purchase confirmed)" : ""}
      </p>

      <p className="known-status__meta">
        Reported {formatRelative(status.observedAt)} via{" "}
        {status.sourceUrl ? (
          <a href={status.sourceUrl} target="_blank" rel="noreferrer noopener">
            {SOURCE_LABELS[status.source] ?? status.source}
          </a>
        ) : (
          (SOURCE_LABELS[status.source] ?? status.source)
        )}
        .
      </p>

      {stale && (
        <p className="known-status__caveat">
          This is {days} day{days === 1 ? "" : "s"} old, so it describes what was true then,
          not what is likely now.
        </p>
      )}
    </div>
  );
}
