/**
 * End-to-end check against the real generated bundle.
 *
 * These tests read the actual files the ingestion pipeline wrote into
 * `apps/web/public/data/` and serve them to the dashboard through a stubbed
 * fetch. If a job changes the JSON shape, this fails - which is the point: the
 * published contract and the dashboard cannot drift apart silently.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Dashboard } from "./Dashboard";

const dataDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "public", "data");

function readData(file: string): unknown {
  return JSON.parse(readFileSync(join(dataDir, file), "utf-8"));
}

const machinesFile = readData("machines.json") as {
  machines: { id: string; city: string; distance_miles: number }[];
  search: { zipCode: string; radiusMiles: number };
};
const forecastsFile = readData("forecasts.json") as {
  forecasts: { machineId: string; status: string }[];
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const file = String(url).split("/").pop() ?? "";
      try {
        return {
          ok: true,
          status: 200,
          json: async () => readData(file),
        } as Response;
      } catch {
        return { ok: false, status: 404 } as Response;
      }
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  );
}

describe("Dashboard against the generated data bundle", () => {
  it("has real machines to render", () => {
    // Guards the tests below from passing vacuously on an empty bundle.
    expect(machinesFile.machines.length).toBeGreaterThan(0);
  });

  it("shows the configured search area", async () => {
    renderDashboard();

    expect(await screen.findByText(machinesFile.search.zipCode)).toBeInTheDocument();
    expect(
      screen.getByText(`${machinesFile.search.radiusMiles} miles`),
    ).toBeInTheDocument();
  });

  it("renders every machine in the bundle", async () => {
    renderDashboard();

    await waitFor(() => {
      expect(
        screen.getByText(
          `${machinesFile.machines.length} within ${machinesFile.search.radiusMiles} miles`,
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders machines from more than one city, proving the radius is not name-based", async () => {
    const cities = new Set(machinesFile.machines.map((machine) => machine.city));
    expect(cities.size).toBeGreaterThan(1);

    renderDashboard();
    await screen.findByText(machinesFile.search.zipCode);

    for (const city of cities) {
      expect(screen.getAllByText(new RegExp(city, "i")).length).toBeGreaterThan(0);
    }
  });

  it("keeps every rendered machine inside the configured radius", () => {
    for (const machine of machinesFile.machines) {
      expect(machine.distance_miles).toBeLessThanOrEqual(machinesFile.search.radiusMiles);
    }
  });

  it("shows INSUFFICIENT DATA rather than a number for unscored machines", async () => {
    const unscored = forecastsFile.forecasts.filter(
      (forecast) => forecast.status === "INSUFFICIENT_DATA",
    );
    if (unscored.length === 0) {
      return; // bundle is fully scored; nothing to assert here
    }

    renderDashboard();

    const badges = await screen.findAllByText("INSUFFICIENT DATA");
    expect(badges).toHaveLength(unscored.length);

    for (const badge of badges) {
      const card = badge.closest(".machine-card");
      expect(card).not.toBeNull();
      // An unscored machine must not display a probability anywhere on its card.
      expect(within(card as HTMLElement).queryByText(/^\d+%$/)).toBeNull();
    }
  });

  it("surfaces the real last-known status parsed from community trackers", async () => {
    const withStatus = (
      forecastsFile.forecasts as unknown as {
        features: { lastKnownStatus: { availability: string } | null };
      }[]
    ).filter((forecast) => forecast.features?.lastKnownStatus);

    if (withStatus.length === 0) {
      return; // no community status ingested yet
    }

    renderDashboard();

    // Every machine that has a real observation shows it, even though it has
    // far too little history to be forecast from.
    const panels = await screen.findAllByText("Last known status");
    expect(panels).toHaveLength(withStatus.length);
  });

  it("shows a regional network pattern instead of a bare INSUFFICIENT DATA", async () => {
    const network = forecastsFile.forecasts.filter(
      (forecast) => forecast.status === "NETWORK_PATTERN",
    );
    if (network.length === 0) {
      return; // no prior available in this bundle
    }

    renderDashboard();

    const badges = await screen.findAllByText("NETWORK PATTERN");
    expect(badges).toHaveLength(network.length);

    // Every network figure must be labelled as not machine-specific.
    expect(screen.getAllByText(/Network-wide, not this machine/i)).toHaveLength(
      network.length,
    );
  });

  it("reports source health, including skipped sources and their reason", async () => {
    renderDashboard();

    expect(await screen.findByText("Data sources")).toBeInTheDocument();
    expect(screen.getByText("pokemon_locator")).toBeInTheDocument();

    const health = readData("source-health.json") as {
      sources: { name: string; status: string; reason: string | null }[];
    };
    const skipped = health.sources.filter((source) => source.status !== "HEALTHY");
    for (const source of skipped) {
      expect(screen.getByText(source.name)).toBeInTheDocument();
      if (source.reason) {
        expect(screen.getAllByText(source.reason).length).toBeGreaterThan(0);
      }
    }
  });

  it("always shows the disclaimer", async () => {
    renderDashboard();
    expect(
      await screen.findByText(/Independent community forecasting tool/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Not affiliated with, endorsed by/i)).toBeInTheDocument();
  });

  it("reports a load failure instead of rendering an empty dashboard", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 500 }) as Response),
    );

    renderDashboard();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Could not load forecast data/i);
  });
});
