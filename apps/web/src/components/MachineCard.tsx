import { Link } from "react-router-dom";

import { formatDistance, formatRelative } from "../lib/format";
import type { MachineWithForecast } from "../lib/types";
import { ForecastBadge } from "./ForecastBadge";

interface Props {
  entry: MachineWithForecast;
}

export function MachineCard({ entry }: Props) {
  const { machine, raw, forecast } = entry;
  const lastReport = forecast?.features.lastObservationAt ?? null;

  return (
    <article
      className="card machine-card"
      data-forecast-status={forecast?.status.toLowerCase() ?? "none"}
    >
      <header className="machine-card__header">
        <div>
          <h3 className="machine-card__retailer">
            <Link to={`/machine/${encodeURIComponent(machine.id)}`}>{machine.retailer}</Link>
          </h3>
          <p className="machine-card__address">
            {machine.address}
            <br />
            {machine.city}, {machine.state} {machine.zip}
          </p>
        </div>
        <div className="machine-card__distance">
          <span className="machine-card__distance-value">
            {formatDistance(machine.distanceMiles)}
          </span>
          <span className="machine-card__machine-id">Machine {machine.name}</span>
        </div>
      </header>

      <ForecastBadge forecast={forecast} />

      <footer className="machine-card__footer">
        <span>
          Last report: <strong>{formatRelative(lastReport)}</strong>
        </span>
        {raw.kiosk_listed && (
          <span className="tag tag--verified" title="Retailer lists a Pokemon kiosk at this store">
            Kiosk listed by retailer
          </span>
        )}
        <Link className="machine-card__link" to={`/machine/${encodeURIComponent(machine.id)}`}>
          Details and reporting <span aria-hidden="true">→</span>
        </Link>
      </footer>
    </article>
  );
}
