import { Suspense, lazy } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { Disclaimer } from "../components/Disclaimer";
import { LastKnownStatus } from "../components/LastKnownStatus";
import { LocationCard } from "../components/LocationCard";
import { MachinePhoto } from "../components/MachinePhoto";
import { ProgressRing } from "../components/ProgressRing";
import { RecentReports } from "../components/RecentReports";
import { ReportForm } from "../components/ReportForm";
import { StatCard } from "../components/StatCard";
import { TrackerMascot } from "../components/TrackerMascot";
import { icons } from "../components/icons";
import { useDashboardData } from "../hooks/useDashboardData";
import { observationsForMachine } from "../lib/data";
import {
  confidenceLabel,
  formatDistance,
  formatPercent,
  formatRelative,
  formatWindow,
  productLabel,
} from "../lib/format";
import type { ExternalObservation, MachineWithForecast } from "../lib/types";

// Recharts is the single largest dependency and only the timeline needs it, so
// it is split out of the dashboard's initial bundle.
const ForecastTimeline = lazy(() =>
  import("../components/ForecastTimeline").then((module) => ({
    default: module.ForecastTimeline,
  })),
);

export function MachineDetail() {
  const { machineId } = useParams<{ machineId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { data, loading, error, reload } = useDashboardData();

  const selectedId = machineId ?? searchParams.get("machine");
  const entry = selectedId
    ? data?.machines.find((candidate) => candidate.machine.id === selectedId)
    : data?.machines[0];

  if (loading && !data) {
    return <p className="empty-note">Loading machine…</p>;
  }

  if (error && !data) {
    return (
      <div className="banner banner--error" role="alert">
        <p>Could not load machine data: {error}</p>
        <button className="button" type="button" onClick={reload}>Retry</button>
      </div>
    );
  }

  if (!entry) {
    return (
      <>
        <Link className="back-link" to="/machines/list">
          ← All machines
        </Link>
        <p className="empty-note">
          {selectedId
            ? <>No machine with id <code>{selectedId}</code> is in the current search area.</>
            : "No machines are in the current search area."}
        </p>
      </>
    );
  }

  return (
    <>
      <div className="machine-picker">
        <label htmlFor="selected-machine">
          <span>Select a machine</span>
          <select
            id="selected-machine"
            value={entry.machine.id}
            onChange={(event) => navigate(`/machines?machine=${encodeURIComponent(event.target.value)}`)}
          >
            {data?.machines.map(({ machine }) => (
              <option key={machine.id} value={machine.id}>
                {machine.retailer} · {machine.city} · {machine.address}
              </option>
            ))}
          </select>
        </label>
        <Link className="back-link" to="/machines/list">View all machines →</Link>
      </div>
      <MachineDetailView
        key={entry.machine.id}
        entry={entry}
        observations={observationsForMachine(data?.observations ?? [], entry.machine.id)}
        onReported={reload}
      />
    </>
  );
}

function MachineDetailView({
  entry,
  observations,
  onReported,
}: {
  entry: MachineWithForecast;
  observations: ExternalObservation[];
  onReported: () => void;
}) {
  const { machine, raw, forecast } = entry;
  const features = forecast?.features;
  const next = forecast?.next ?? null;
  const isNetwork = forecast?.status === "NETWORK_PATTERN";
  const runnerUp = forecast?.windows?.[1] ?? null;
  const known = features?.lastKnownStatus ?? null;

  return (
    <>
      <header className="page-head">
        <TrackerMascot />

        <div className="page-head__row">
          <span className="page-head__pin" aria-hidden="true">
            {icons.pin}
          </span>
          <div>
            <h1 className="page-head__title">
              {machine.retailer} — {machine.city}
            </h1>
            <p className="page-head__sub">
              {machine.address}, {machine.city}, {machine.state} {machine.zip}
            </p>
            <p className="page-head__meta">
              Machine ID: <code>{machine.name}</code>
              <span className="page-head__dot">·</span>
              {formatDistance(machine.distanceMiles)} away
              {raw.kiosk_listed && (
                <span className="pill pill--good pill--inline">Kiosk listed by retailer</span>
              )}
            </p>
          </div>
        </div>
      </header>

      {/* -- headline forecast -------------------------------------------- */}
      <div className="forecast-feature">
      <section className="hero-card">
        <div className="hero-card__main">
          <header className="panel__head">
            <span className="panel__icon" aria-hidden="true">
              {icons.clock}
            </span>
            <h2 className="panel__title">
              {isNetwork ? "Best time to try" : "Next predicted availability"}
            </h2>
            {isNetwork && <span className="pill pill--info">Regional pattern</span>}
          </header>

          {next ? (
            <>
              <p className={`hero-card__window ${isNetwork ? "hero-card__window--muted" : ""}`}>
                {formatWindow(next)}
              </p>
              <p className="hero-card__date">
                {new Date(next.windowStart).toLocaleDateString(undefined, {
                  weekday: "long",
                  month: "short",
                  day: "numeric",
                })}
              </p>

              <dl className="hero-card__rows">
                {runnerUp && (
                  <div className="hero-card__row">
                    <span className="hero-card__row-icon" aria-hidden="true">
                      {icons.calendar}
                    </span>
                    <div>
                      <dt>Next best window</dt>
                      <dd>
                        {formatWindow(runnerUp)}{" "}
                        <span className="muted">({formatPercent(runnerUp.probability)})</span>
                      </dd>
                    </div>
                  </div>
                )}

                <div className="hero-card__row">
                  <span className="hero-card__row-icon" aria-hidden="true">
                    {icons.pulse}
                  </span>
                  <div>
                    <dt>Typical pattern</dt>
                    <dd>
                      {features?.minutePattern
                        ? `:${String(features.minutePattern.patternMinute).padStart(2, "0")} past each hour`
                        : isNetwork
                          ? "Not enough history from this machine"
                          : "No repeating pattern found"}
                    </dd>
                    <p className="hero-card__row-note">
                      {features?.minutePattern
                        ? `Seen in ${features.minutePattern.sampleCount} of ${features.minutePattern.totalSamples} positive reports`
                        : `${forecast?.observationCount ?? 0} of ${forecast?.minimumObservations ?? 8} reports collected`}
                    </p>
                  </div>
                </div>
              </dl>

              <LastKnownStatus status={known} />
            </>
          ) : (
            <p className="empty-note">No window scored above zero in the forecast horizon.</p>
          )}
        </div>

        <div className="hero-card__side">
          {next && (
            <ProgressRing
              value={next.probability}
              label={isNetwork ? "Network-wide score" : "Forecast score"}
              muted={isNetwork}
              size={144}
            />
          )}
          {isNetwork && forecast?.networkPrior && (
            <p className="hero-card__caveat">
              From {forecast.networkPrior.sampleCount} community reports within{" "}
              {forecast.networkPrior.regionalRadiusMiles} miles — not specific to this machine.
            </p>
          )}
        </div>
      </section>
      <MachinePhoto />
      </div>

      {/* -- stat row ------------------------------------------------------ */}
      <div className="stat-row">
        <StatCard
          icon={icons.signal}
          title="Machine status"
          value={raw.kiosk_listed ? "Listed" : "Unconfirmed"}
          tone={raw.kiosk_listed ? "good" : "muted"}
          dot
          detail={`Verified ${formatRelative(raw.last_verified_at)}`}
        />
        <StatCard
          icon={icons.box}
          title="Last confirmed product"
          value={known?.product ? productLabel(known.product) : "None reported"}
          tone={known?.product ? "default" : "muted"}
          detail={
            known
              ? `${formatRelative(known.observedAt)}${
                  known.purchaseConfirmed ? " · purchase confirmed" : ""
                }`
              : "No product has been reported here"
          }
        />
        <StatCard
          icon={icons.clock}
          title="Average interval"
          value={features?.interval ? `~${features.interval.intervalMinutes} minutes` : "Unknown"}
          tone={features?.interval ? "default" : "muted"}
          detail={
            features?.interval
              ? `Support ${Math.round(features.interval.support * 100)}%`
              : "Needs repeat sightings to detect"
          }
        />
        <StatCard
          icon={icons.pulse}
          title="Data confidence"
          value={forecast ? confidenceLabel(forecast.confidence) : "—"}
          tone={
            forecast?.confidence === "HIGH"
              ? "good"
              : forecast?.confidence === "MEDIUM"
                ? "warn"
                : "muted"
          }
          detail={`Based on ${forecast?.observationCount ?? 0} report${
            forecast?.observationCount === 1 ? "" : "s"
          }`}
        />
      </div>

      {/* -- timeline + reporting ------------------------------------------ */}
      <div className="split split--forecast">
        <section className="panel">
          <header className="panel__head">
            <span className="panel__icon" aria-hidden="true">
              {icons.pulse}
            </span>
            <h2 className="panel__title">
              {isNetwork ? "Best hours across the region" : "Availability timeline"}
            </h2>
            {isNetwork && <span className="panel__meta">not this machine</span>}
          </header>

          {forecast && forecast.windows.length > 0 ? (
            <Suspense fallback={<p className="empty-note">Loading timeline…</p>}>
              <ForecastTimeline windows={forecast.windows} />
            </Suspense>
          ) : (
            <p className="empty-note">No scored windows yet.</p>
          )}
        </section>

        <ReportForm machineId={machine.id} onSubmitted={onReported} />
      </div>

      {/* -- evidence ------------------------------------------------------ */}
      <div className="split split--evidence">
        <RecentReports observations={observations} />
        <LocationCard machine={raw} />
      </div>

      {forecast?.explanation?.reasons?.length ? (
        <section className="panel">
          <header className="panel__head">
            <span className="panel__icon" aria-hidden="true">
              {icons.doc}
            </span>
            <h2 className="panel__title">Why this prediction</h2>
          </header>
          <ul className="reason-list">
            {forecast.explanation.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <p className="panel__foot">
            Reports used: <strong>{forecast.explanation.reportsUsed}</strong>
          </p>
        </section>
      ) : null}

      <Disclaimer />
    </>
  );
}
