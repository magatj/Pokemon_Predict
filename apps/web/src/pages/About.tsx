import { Disclaimer } from "../components/Disclaimer";
import { icons } from "../components/icons";

/** How the forecast is produced, in plain language. */
export function About() {
  return (
    <>
      <header className="page-head">
        <h1 className="page-head__title">How it works</h1>
        <p className="page-head__sub">
          What the numbers mean, and what they deliberately do not claim.
        </p>
      </header>

      <div className="split">
        <section className="panel">
          <header className="panel__head">
            <span className="panel__icon" aria-hidden="true">
              {icons.pin}
            </span>
            <h2 className="panel__title">Finding machines</h2>
          </header>
          <p className="prose">
            Machines come from the official Pokémon locator&apos;s public JSON API. That
            endpoint returns at most 20 results per query, so the search area is split into a
            grid and the results merged — which finds machines a single query silently drops.
          </p>
          <p className="prose">
            Every machine is then measured from the search centroid with the Haversine
            formula. City names never decide inclusion: a machine in a neighbouring town
            inside the radius is kept, and one in the search ZIP&apos;s own city outside it is
            dropped.
          </p>
        </section>

        <section className="panel">
          <header className="panel__head">
            <span className="panel__icon" aria-hidden="true">
              {icons.clock}
            </span>
            <h2 className="panel__title">Predicting availability</h2>
          </header>
          <p className="prose">
            The question is not when a machine was restocked, but when it can next actually
            dispense. Observations feed minute-of-hour clustering, recurring-interval
            detection and recency decay, combined into an explainable score.
          </p>
          <p className="prose">
            Newer evidence outweighs older: a report from months ago counts for almost
            nothing, which is why a machine can show a stale last-known status and still have
            no forecast of its own.
          </p>
        </section>
      </div>

      <section className="panel">
        <header className="panel__head">
          <span className="panel__icon" aria-hidden="true">
            {icons.pulse}
          </span>
          <h2 className="panel__title">What the labels mean</h2>
        </header>

        <dl className="definitions">
          <div>
            <dt>
              <span className="pill pill--good">Forecast</span>
            </dt>
            <dd>
              Scored from this machine&apos;s own reports. Shown in five-minute windows,
              because the pattern is that precise.
            </dd>
          </div>
          <div>
            <dt>
              <span className="pill pill--info">Regional pattern</span>
            </dt>
            <dd>
              This machine has too little history, so the figure is the empirical rate across
              community reports in the surrounding region. It is shown by the hour, capped
              well below what real machine history can earn, and is <strong>not</strong>{" "}
              specific to this machine.
            </dd>
          </div>
          <div>
            <dt>
              <span className="pill pill--warn">Collecting</span>
            </dt>
            <dd>
              Not even a regional pattern is available. No probability is shown at all — an
              invented number would look exactly like a real one.
            </dd>
          </div>
        </dl>
      </section>

      <section className="panel">
        <header className="panel__head">
          <span className="panel__icon" aria-hidden="true">
            {icons.doc}
          </span>
          <h2 className="panel__title">How you can help</h2>
        </header>
        <p className="prose">
          A confirmed purchase is the strongest evidence there is: it proves the machine
          actually dispensed at that moment, which no third-party status can. Reports from any
          machine page take effect on the next forecast run.
        </p>
        <p className="prose muted">
          Reports are stored in your browser until a submission endpoint is configured. The
          app will never tell you something was uploaded when it was not.
        </p>
      </section>

      <Disclaimer />
    </>
  );
}
