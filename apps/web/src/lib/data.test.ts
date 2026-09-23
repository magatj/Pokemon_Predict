import { describe, expect, it } from "vitest";

import { sortMachines, toNearbyMachine } from "./data";
import type { MachineForecast, MachineWithForecast, RawMachine } from "./types";

function rawMachine(overrides: Partial<RawMachine> = {}): RawMachine {
  return {
    id: "rec1",
    retailer: "Safeway",
    name: "Q00001",
    address: "4010 A St SE",
    city: "Auburn",
    state: "WA",
    zip: "98002",
    latitude: 47.27,
    longitude: -122.22,
    source: "pokemon_locator",
    source_authority: "OFFICIAL",
    source_url: "https://vending.pokemon.com/en-us/",
    distance_miles: 6.1,
    discovered_at: "2026-09-23T10:00:00Z",
    last_verified_at: "2026-09-23T10:00:00Z",
    store_hours: null,
    kiosk_listed: true,
    verifications: [],
    aliases: [],
    ...overrides,
  };
}

function forecast(overrides: Partial<MachineForecast> = {}): MachineForecast {
  return {
    machineId: "rec1",
    generatedAt: "2026-09-23T16:00:00Z",
    windowMinutes: 5,
    observationCount: 12,
    minimumObservations: 8,
    status: "OK",
    confidence: "MEDIUM",
    windows: [],
    next: {
      windowStart: "2026-09-23T16:35:00Z",
      windowEnd: "2026-09-23T16:40:00Z",
      localTime: "09:35",
      probability: 0.5,
      rawScore: 0.5,
      sampleScale: 0.5,
      sourceScale: 1,
      horizonScale: 1,
      minutesAhead: 30,
      components: {},
    },
    features: {
      machineId: "rec1",
      observationCount: 12,
      positiveCount: 10,
      negativeCount: 2,
      purchaseCount: 1,
      totalWeight: 8,
      minutesSinceLastAvailable: 30,
      minutesSinceLastNotAvailable: null,
      minutesSinceLastPurchase: null,
      minutesSinceSuspectedRestock: null,
      minutesSinceLastPositive: 30,
      minutePattern: null,
      interval: null,
      hourHitRate: {},
      weekdayHitRate: {},
      weekdayHourHitRate: {},
      nearby: null,
      meanSourceConfidence: 0.8,
      meanMatchConfidence: 1,
      lastObservationAt: "2026-09-23T15:30:00Z",
      lastKnownStatus: null,
    },
    explanation: { reasons: [], signals: {}, reportsUsed: 12 },
    ...overrides,
  };
}

function entry(
  id: string,
  distance: number,
  machineForecast: MachineForecast | null,
): MachineWithForecast {
  const raw = rawMachine({ id, distance_miles: distance });
  return { machine: toNearbyMachine(raw), raw, forecast: machineForecast };
}

describe("toNearbyMachine", () => {
  it("maps stored fields onto the UI shape", () => {
    const machine = toNearbyMachine(rawMachine());
    expect(machine.distanceMiles).toBe(6.1);
    expect(machine.lastVerifiedAt).toBe("2026-09-23T10:00:00Z");
  });

  it("treats a missing distance as infinitely far rather than zero", () => {
    const machine = toNearbyMachine(rawMachine({ distance_miles: null }));
    expect(machine.distanceMiles).toBe(Number.POSITIVE_INFINITY);
  });
});

describe("sortMachines", () => {
  const scoredHigh = entry(
    "high",
    9,
    forecast({
      machineId: "high",
      next: { ...forecast().next!, probability: 0.8, windowStart: "2026-09-23T18:00:00Z" },
    }),
  );
  const scoredLow = entry(
    "low",
    2,
    forecast({
      machineId: "low",
      next: { ...forecast().next!, probability: 0.2, windowStart: "2026-09-23T16:35:00Z" },
    }),
  );
  const noData = entry(
    "none",
    1,
    forecast({
      machineId: "none",
      status: "INSUFFICIENT_DATA",
      next: null,
      observationCount: 3,
      confidence: "LOW",
    }),
  );

  it("ranks by probability", () => {
    const sorted = sortMachines([scoredLow, noData, scoredHigh], "probability");
    expect(sorted.map((item) => item.machine.id)).toEqual(["high", "low", "none"]);
  });

  it("keeps machines without a forecast out of the ranked positions", () => {
    const sorted = sortMachines([noData, scoredHigh], "probability");
    expect(sorted[0]!.machine.id).toBe("high");
  });

  it("ranks by soonest window", () => {
    const sorted = sortMachines([scoredHigh, scoredLow], "soonest");
    expect(sorted.map((item) => item.machine.id)).toEqual(["low", "high"]);
  });

  it("ranks by distance regardless of forecast", () => {
    const sorted = sortMachines([scoredHigh, scoredLow, noData], "distance");
    expect(sorted.map((item) => item.machine.id)).toEqual(["none", "low", "high"]);
  });

  it("ranks by most recently confirmed", () => {
    const stale = entry(
      "stale",
      3,
      forecast({
        machineId: "stale",
        features: { ...forecast().features, lastObservationAt: "2026-09-20T10:00:00Z" },
      }),
    );
    const sorted = sortMachines([stale, scoredHigh], "recentlyConfirmed");
    expect(sorted[0]!.machine.id).toBe("high");
  });

  it("ranks by data confidence", () => {
    const confident = entry("confident", 8, forecast({ machineId: "confident", confidence: "HIGH" }));
    const sorted = sortMachines([noData, confident], "dataConfidence");
    expect(sorted[0]!.machine.id).toBe("confident");
  });

  it("does not mutate the input array", () => {
    const input = [scoredLow, scoredHigh];
    const before = input.map((item) => item.machine.id);
    sortMachines(input, "probability");
    expect(input.map((item) => item.machine.id)).toEqual(before);
  });
});
