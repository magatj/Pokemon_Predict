/**
 * Loading and joining the generated JSON bundle.
 *
 * The dashboard reads static files only. Everything expensive - discovery,
 * distance filtering, forecasting - already happened in the CI pipeline.
 */

import { dataUrl } from "./config";
import type {
  ExternalObservation,
  ForecastsFile,
  MachineWithForecast,
  MachinesFile,
  NearbyMachine,
  ObservationsFile,
  RawMachine,
  SearchMeta,
  SourceHealthFile,
} from "./types";

export class DataLoadError extends Error {
  constructor(
    message: string,
    readonly file: string,
  ) {
    super(message);
    this.name = "DataLoadError";
  }
}

async function fetchJson<T>(file: string, signal?: AbortSignal): Promise<T> {
  const url = dataUrl(file);
  let response: Response;
  try {
    response = await fetch(url, { signal, cache: "no-cache" });
  } catch (cause) {
    throw new DataLoadError(`Could not reach ${url} (${(cause as Error).message})`, file);
  }
  if (!response.ok) {
    throw new DataLoadError(`${url} returned HTTP ${response.status}`, file);
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new DataLoadError(`${url} did not contain valid JSON`, file);
  }
}

/** Convert a stored machine record into the UI-facing shape. */
export function toNearbyMachine(raw: RawMachine): NearbyMachine {
  return {
    id: raw.id,
    retailer: raw.retailer,
    name: raw.name,
    address: raw.address,
    city: raw.city,
    state: raw.state,
    zip: raw.zip,
    latitude: raw.latitude,
    longitude: raw.longitude,
    distanceMiles: raw.distance_miles ?? Number.POSITIVE_INFINITY,
    source: raw.source,
    lastVerifiedAt: raw.last_verified_at ?? "",
  };
}

export interface DashboardData {
  generatedAt: string;
  search: SearchMeta;
  /** True when the loaded bundle came from the synthetic demo seeder. */
  demoData: boolean;
  machines: MachineWithForecast[];
  observationCount: number;
  /** Every published observation, newest first. */
  observations: ExternalObservation[];
  sources: SourceHealthFile["sources"];
  /** Files that could not be loaded; the UI says so rather than showing nothing. */
  errors: string[];
}

/**
 * Load every published file and join machines to their forecasts.
 *
 * Machines and forecasts are required. Observations and source health are
 * supplementary: if they fail the dashboard still renders, with the failure
 * reported instead of hidden.
 */
export async function loadDashboardData(signal?: AbortSignal): Promise<DashboardData> {
  const errors: string[] = [];

  const [machinesFile, forecastsFile] = await Promise.all([
    fetchJson<MachinesFile>("machines.json", signal),
    fetchJson<ForecastsFile>("forecasts.json", signal),
  ]);

  let observations: ExternalObservation[] = [];
  try {
    const file = await fetchJson<ObservationsFile>("observations.json", signal);
    observations = [...(file.observations ?? [])].sort((a, b) =>
      (b.observedAt ?? b.postedAt).localeCompare(a.observedAt ?? a.postedAt),
    );
  } catch (error) {
    errors.push((error as Error).message);
  }

  let sources: SourceHealthFile["sources"] = [];
  try {
    const health = await fetchJson<SourceHealthFile>("source-health.json", signal);
    sources = health.sources ?? [];
  } catch (error) {
    errors.push((error as Error).message);
  }

  const forecastsById = new Map(
    (forecastsFile.forecasts ?? []).map((forecast) => [forecast.machineId, forecast]),
  );

  const machines: MachineWithForecast[] = (machinesFile.machines ?? []).map((raw) => ({
    machine: toNearbyMachine(raw),
    raw,
    forecast: forecastsById.get(raw.id) ?? null,
  }));

  return {
    generatedAt: machinesFile.generatedAt ?? forecastsFile.generatedAt,
    search: machinesFile.search ?? {},
    demoData: machinesFile.demoData === true,
    machines,
    observationCount: observations.length,
    observations,
    sources,
    errors,
  };
}

/** Observations confidently attributed to one machine, newest first. */
export function observationsForMachine(
  observations: ExternalObservation[],
  machineId: string,
  minMatchConfidence = 0.7,
): ExternalObservation[] {
  return observations.filter(
    (observation) =>
      observation.machineId === machineId &&
      observation.machineMatchConfidence >= minMatchConfidence,
  );
}

export type SortKey =
  | "probability"
  | "soonest"
  | "distance"
  | "recentlyConfirmed"
  | "dataConfidence";

export const sortOptions: { key: SortKey; label: string }[] = [
  { key: "probability", label: "Highest predicted probability" },
  { key: "soonest", label: "Soonest predicted window" },
  { key: "distance", label: "Nearest" },
  { key: "recentlyConfirmed", label: "Most recently confirmed" },
  { key: "dataConfidence", label: "Highest data confidence" },
];

const CONFIDENCE_ORDER: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };

/**
 * Sort machines for display.
 *
 * Machines without a forecast always sink to the bottom of a forecast-based
 * sort instead of being treated as a zero-probability prediction.
 */
export function sortMachines(
  machines: MachineWithForecast[],
  key: SortKey,
): MachineWithForecast[] {
  const sorted = [...machines];
  const hasForecast = (entry: MachineWithForecast) =>
    entry.forecast?.status === "OK" && entry.forecast.next !== null;

  switch (key) {
    case "distance":
      return sorted.sort((a, b) => a.machine.distanceMiles - b.machine.distanceMiles);

    case "probability":
      return sorted.sort((a, b) => {
        if (hasForecast(a) !== hasForecast(b)) return hasForecast(a) ? -1 : 1;
        const delta = (b.forecast?.next?.probability ?? 0) - (a.forecast?.next?.probability ?? 0);
        return delta !== 0 ? delta : a.machine.distanceMiles - b.machine.distanceMiles;
      });

    case "soonest":
      return sorted.sort((a, b) => {
        if (hasForecast(a) !== hasForecast(b)) return hasForecast(a) ? -1 : 1;
        const aStart = a.forecast?.next?.windowStart ?? "";
        const bStart = b.forecast?.next?.windowStart ?? "";
        return aStart.localeCompare(bStart);
      });

    case "recentlyConfirmed":
      return sorted.sort((a, b) => {
        const aSeen = a.forecast?.features.lastObservationAt ?? "";
        const bSeen = b.forecast?.features.lastObservationAt ?? "";
        if (aSeen === bSeen) return a.machine.distanceMiles - b.machine.distanceMiles;
        if (!aSeen) return 1;
        if (!bSeen) return -1;
        return bSeen.localeCompare(aSeen);
      });

    case "dataConfidence":
      return sorted.sort((a, b) => {
        const aRank = CONFIDENCE_ORDER[a.forecast?.confidence ?? "LOW"] ?? 0;
        const bRank = CONFIDENCE_ORDER[b.forecast?.confidence ?? "LOW"] ?? 0;
        if (aRank !== bRank) return bRank - aRank;
        const delta =
          (b.forecast?.observationCount ?? 0) - (a.forecast?.observationCount ?? 0);
        return delta !== 0 ? delta : a.machine.distanceMiles - b.machine.distanceMiles;
      });

    default:
      return sorted;
  }
}
