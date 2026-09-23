import { Suspense, lazy } from "react";
import { Link, useParams } from "react-router-dom";

import { Disclaimer } from "../components/Disclaimer";
import { ForecastBadge } from "../components/ForecastBadge";
import { LastKnownStatus } from "../components/LastKnownStatus";
import { PokeballMark } from "../components/PokeballMark";
import { ReportForm } from "../components/ReportForm";
import { useDashboardData } from "../hooks/useDashboardData";
import { formatDistance, formatRelative, orderedHours, titleCase } from "../lib/format";
import type { MachineWithForecast } from "../lib/types";

// Recharts is the single largest dependency and only the timeline needs it, so
// it is split out of the dashboard's initial bundle.
const ForecastTimeline = lazy(() =>
  import("../components/ForecastTimeline").then((module) => ({
    default: module.ForecastTimeline,
  })),
);

export function MachineDetail() {
  const { machineId } = useParams<{ machineId: string }>();
  const { data, loading, reload } = useDashboardData();

  const entry = data?.machines.find((candidate) => candidate.machine.id === machineId);

  if (loading && !data) {
    return <p className="empty-note page">Loading machine…</p>;
  }

  if (!entry) {
    return (
      <div className="page">
        <Link className="back-link" to="/">
          ← All machines
        </Link>
        <p className="empty-note">
          No machine with id <code>{machineId}</code> is in the current search area.
        </p>
      </div>
    );
  }

  return <MachineDetailView entry={entry} onReported={reload} />;
}

function MachineDetailView({
  entry,
  onReported,
}: {
  entry: MachineWithForecast;
  onReported: () => void;
}) {
  const { machine, raw, forecast } = entry;
  const features = forecast?.features;
  const hours = orderedHours(raw.store_hours);

  return (
    <div className="page">
      <Link className="back-link" to="/">
        ← All machines
      </Link>

      <header className="hero hero--detail">
        <PokeballMark className="hero__mark" />
        <p className="eyebrow">
          <span className="eyebrow__dot" aria-hidden="true" />
          Machine forecast
        </p>
        <h1 className="hero__title">
          {machine.retailer} — {machine.city}
        </h1>
        <p className="hero__subtitle">
          {machine.address}
          <br />
          {machine.city}, {machine.state} {machine.zip}
        </p>
        <p className="hero__meta">
          {formatDistance(machine.distanceMiles)} from the search centre · machine{" "}
          <code>{machine.name}</code>
        </p>
      </header>

      <section
        className="card card--featured"
        data-forecast-status={forecast?.status.toLowerCase() ?? "none"}
      >
        <ForecastBadge forecast={forecast} />

        {forecast?.status === "OK" && (
          <LastKnownStatus status={forecast.features.lastKnownStatus} />
        )}

        {forecast?.explanation?.reasons?.length ? (
          <div className="why">
            <h3 className="why__title">Why?</h3>
            <ul>
              {forecast.explanation.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            <p className="why__reports">
              Reports used: <strong>{forecast.explanation.reportsUsed}</strong>
            </p>
          </div>
        ) : null}
      </section>

      {forecast && forecast.windows.length > 0 && (
        <section>
          <h2 className="section-title">
            {forecast.status === "NETWORK_PATTERN"
              ? "Best hours across the region"
              : "Upcoming opportunities"}
            {forecast.status === "NETWORK_PATTERN" && (
              <span className="section-title__count">
                Regional pattern, not this machine
              </span>
            )}
          </h2>
          <Suspense fallback={<p className="empty-note">Loading timeline…</p>}>
            <ForecastTimeline windows={forecast.windows} />
          </Suspense>
        </section>
      )}

      <ReportForm machineId={machine.id} onSubmitted={onReported} />

      {features && (
        <section className="card">
          <h2 className="section-title">Observation summary</h2>
          <dl className="stats">
            <Stat label="Observations" value={String(features.observationCount)} />
            <Stat label="Positive reports" value={String(features.positiveCount)} />
            <Stat label="Sold-out reports" value={String(features.negativeCount)} />
            <Stat label="Confirmed purchases" value={String(features.purchaseCount)} />
            <Stat
              label="Last observation"
              value={formatRelative(features.lastObservationAt)}
            />
            <Stat
              label="Minute pattern"
              value={
                features.minutePattern
                  ? `:${String(features.minutePattern.patternMinute).padStart(2, "0")} ±${features.minutePattern.toleranceMinutes}`
                  : "none detected"
              }
            />
            <Stat
              label="Recurring interval"
              value={
                features.interval ? `${features.interval.intervalMinutes} minutes` : "none detected"
              }
            />
            <Stat
              label="Nearby machines active"
              value={
                features.nearby
                  ? `${features.nearby.activeMachineIds.length} in the last ${features.nearby.windowMinutes} min`
                  : "—"
              }
            />
          </dl>
        </section>
      )}

      <section className="card">
        <h2 className="section-title">Data sources for this machine</h2>
        <ul className="sources">
          <li className="sources__item">
            <div className="sources__head">
              <span className="sources__name">Official Pokémon locator</span>
              <span className="status status--healthy">OFFICIAL</span>
            </div>
            <p className="sources__meta">
              Verified {formatRelative(raw.last_verified_at)}
              {raw.source_url ? (
                <>
                  {" · "}
                  <a href={raw.source_url} target="_blank" rel="noreferrer noopener">
                    source
                  </a>
                </>
              ) : null}
            </p>
          </li>

          {raw.verifications.map((verification) => (
            <li key={verification.url ?? verification.verified_at} className="sources__item">
              <div className="sources__head">
                <span className="sources__name">
                  {verification.retailer ?? "Retailer"} website
                </span>
                <span className="status status--healthy">VERIFICATION</span>
              </div>
              <p className="sources__meta">
                Verified {formatRelative(verification.verified_at)} · kiosk listed:{" "}
                {verification.kiosk_listed ? "yes" : "no"} · address match{" "}
                {verification.address_match_score.toFixed(2)}
                {verification.url ? (
                  <>
                    {" · "}
                    <a href={verification.url} target="_blank" rel="noreferrer noopener">
                      store page
                    </a>
                  </>
                ) : null}
              </p>
            </li>
          ))}

          {features && (
            <li className="sources__item">
              <div className="sources__head">
                <span className="sources__name">Observations used</span>
                <span className="status status--healthy">{features.observationCount}</span>
              </div>
              <p className="sources__meta">
                Mean source confidence {features.meanSourceConfidence.toFixed(2)} · mean machine
                match {features.meanMatchConfidence.toFixed(2)}
              </p>
            </li>
          )}
        </ul>
      </section>

      {hours.length > 0 && (
        <section className="card">
          <h2 className="section-title">Store hours</h2>
          <dl className="stats stats--hours">
            {hours.map(([day, intervals]) => (
              <Stat
                key={day}
                label={titleCase(day)}
                value={
                  intervals.length === 0
                    ? "Closed"
                    : intervals.map((pair) => `${pair[0]}–${pair[1]}`).join(", ")
                }
              />
            ))}
          </dl>
          <p className="empty-note">
            Store hours bound when a machine is reachable; they are not a restock schedule.
          </p>
        </section>
      )}

      <Disclaimer />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stats__item">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
