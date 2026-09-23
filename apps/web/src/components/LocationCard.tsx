import { orderedHours, titleCase } from "../lib/format";
import type { RawMachine } from "../lib/types";
import { icons } from "./icons";

interface Props {
  machine: RawMachine;
}

/**
 * Where the machine is, plus the store's opening hours.
 *
 * The map is an OpenStreetMap embed: no API key, no tracking script and no
 * per-view billing, which suits a static site. Hours bound when the machine is
 * reachable at all; they are not a restock schedule.
 */
export function LocationCard({ machine }: Props) {
  const { latitude, longitude } = machine;
  const span = 0.008;
  const bbox = [longitude - span, latitude - span / 2, longitude + span, latitude + span / 2]
    .map((value) => value.toFixed(5))
    .join(",");
  const embed = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${latitude},${longitude}`;
  const directions = `https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}`;
  const hours = orderedHours(machine.store_hours);

  return (
    <section className="panel" id="location">
      <header className="panel__head">
        <span className="panel__icon" aria-hidden="true">
          {icons.pin}
        </span>
        <h2 className="panel__title">Location</h2>
        <a
          className="panel__action"
          href={directions}
          target="_blank"
          rel="noreferrer noopener"
        >
          Get directions
        </a>
      </header>

      <div className="location">
        <iframe
          className="location__map"
          title={`Map showing ${machine.retailer} at ${machine.address}`}
          src={embed}
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
        />

        <div className="location__detail">
          <p className="location__name">{machine.retailer}</p>
          <p className="location__address">
            {machine.address}
            <br />
            {machine.city}, {machine.state} {machine.zip}
          </p>

          {hours.length > 0 && (
            <div className="location__hours">
              <h3 className="location__subtitle">Store hours</h3>
              <dl>
                {hours.map(([day, intervals]) => (
                  <div key={day}>
                    <dt>{titleCase(day).slice(0, 3)}</dt>
                    <dd>
                      {intervals.length === 0
                        ? "Closed"
                        : intervals.map((pair) => `${pair[0]}–${pair[1]}`).join(", ")}
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="location__caveat">
                Opening hours bound when the machine is reachable. They are not a restock
                schedule.
              </p>
            </div>
          )}

          <a
            className="button button--ghost"
            href={`https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=18/${latitude}/${longitude}`}
            target="_blank"
            rel="noreferrer noopener"
          >
            Open in maps
          </a>
        </div>
      </div>
    </section>
  );
}
