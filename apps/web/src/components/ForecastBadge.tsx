import { confidenceLabel, formatPercent, formatWindow } from "../lib/format";
import type { MachineForecast } from "../lib/types";
import { LastKnownStatus } from "./LastKnownStatus";

interface Props {
  forecast: MachineForecast | null;
  compact?: boolean;
}

/**
 * The forecast headline for a machine.
 *
 * Three cases, deliberately distinguishable at a glance:
 *   OK               - scored from this machine's own history.
 *   NETWORK_PATTERN  - scored from the regional population rate, because the
 *                      machine has too little history of its own. Labelled as
 *                      a network pattern and shown at hour resolution.
 *   INSUFFICIENT_DATA- not even a population rate is available.
 *
 * A network figure is never styled like a machine-specific one; conflating the
 * two would be the same failure as inventing a number outright.
 */
export function ForecastBadge({ forecast, compact = false }: Props) {
  if (!forecast) {
    return (
      <div className="forecast-badge forecast-badge--empty">
        <span className="forecast-badge__status">NO FORECAST YET</span>
        <p className="forecast-badge__note">
          This machine has not been through a forecast run.
        </p>
      </div>
    );
  }

  if (forecast.status === "NETWORK_PATTERN") {
    const next = forecast.next;
    const prior = forecast.networkPrior;
    const scope =
      prior?.scope === "REGIONAL"
        ? `within ${prior.regionalRadiusMiles} miles`
        : "across the tracked network";

    return (
      <div className="forecast-badge forecast-badge--network">
        <span className="forecast-badge__status forecast-badge__status--network">
          NETWORK PATTERN
        </span>
        <p className="forecast-badge__note">
          Not enough reports from this machine ({forecast.observationCount}) for its own
          forecast.
        </p>

        {next ? (
          <>
            <span className="forecast-badge__label">Best time to try</span>
            <span className="forecast-badge__window">{formatWindow(next)}</span>
            <div className="forecast-badge__row">
              <span className="forecast-badge__probability forecast-badge__probability--network">
                {formatPercent(next.probability)}
              </span>
              <span className="confidence confidence--low">Network-wide, not this machine</span>
            </div>
          </>
        ) : (
          <p className="forecast-badge__note">No hour stands out in the regional pattern.</p>
        )}

        {prior && (
          <p className="forecast-badge__note forecast-badge__note--muted">
            Based on {prior.sampleCount} community report{prior.sampleCount === 1 ? "" : "s"}{" "}
            {scope}
            {prior.bestHour !== null
              ? `; product was most often in stock around ${String(prior.bestHour).padStart(2, "0")}:00 local`
              : ""}
            .
          </p>
        )}

        <LastKnownStatus status={forecast.features.lastKnownStatus} />
      </div>
    );
  }

  if (forecast.status === "INSUFFICIENT_DATA") {
    const collected = forecast.observationCount;
    const needed = forecast.minimumObservations;
    const progress = Math.min(100, needed > 0 ? (collected / needed) * 100 : 0);

    return (
      <div className="forecast-badge forecast-badge--insufficient">
        <span className="forecast-badge__status">INSUFFICIENT DATA</span>
        <div
          className="forecast-badge__progress"
          role="progressbar"
          aria-valuenow={collected}
          aria-valuemin={0}
          aria-valuemax={needed}
          aria-label="Observations collected"
        >
          <div className="forecast-badge__progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <p className="forecast-badge__note">
          {collected} / {needed} observations collected
        </p>
        <LastKnownStatus status={forecast.features.lastKnownStatus} />
      </div>
    );
  }

  const next = forecast.next;
  if (!next) {
    return (
      <div className="forecast-badge forecast-badge--empty">
        <span className="forecast-badge__status">NO WINDOW ABOVE ZERO</span>
        <p className="forecast-badge__note">
          Nothing in the next {forecast.windowMinutes}-minute windows scored above zero.
        </p>
      </div>
    );
  }

  return (
    <div className="forecast-badge">
      {!compact && <span className="forecast-badge__label">Next predicted availability</span>}
      <span className="forecast-badge__window">{formatWindow(next)}</span>
      <div className="forecast-badge__row">
        <span className="forecast-badge__probability">{formatPercent(next.probability)}</span>
        <span
          className={`confidence confidence--${forecast.confidence.toLowerCase()}`}
          title="Confidence reflects how much evidence supports this machine"
        >
          {confidenceLabel(forecast.confidence)} confidence
        </span>
      </div>
      <p className="forecast-badge__note forecast-badge__note--muted">
        Forecast score, not a guarantee of stock.
      </p>
    </div>
  );
}
