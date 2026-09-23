import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MachineForecast } from "../lib/types";
import { ForecastBadge } from "./ForecastBadge";

function baseForecast(overrides: Partial<MachineForecast> = {}): MachineForecast {
  return {
    machineId: "rec1",
    generatedAt: "2026-09-23T16:00:00Z",
    windowMinutes: 5,
    observationCount: 18,
    minimumObservations: 8,
    status: "OK",
    confidence: "HIGH",
    windows: [],
    next: {
      windowStart: "2026-09-23T21:37:00Z",
      windowEnd: "2026-09-23T21:42:00Z",
      localTime: "14:37",
      probability: 0.72,
      rawScore: 0.8,
      sampleScale: 0.6,
      sourceScale: 1,
      horizonScale: 1,
      minutesAhead: 30,
      components: {},
    },
    features: {
      machineId: "rec1",
      observationCount: 18,
      positiveCount: 14,
      negativeCount: 4,
      purchaseCount: 2,
      totalWeight: 10,
      minutesSinceLastAvailable: 20,
      minutesSinceLastNotAvailable: null,
      minutesSinceLastPurchase: null,
      minutesSinceSuspectedRestock: null,
      minutesSinceLastPositive: 20,
      minutePattern: null,
      interval: null,
      hourHitRate: {},
      weekdayHitRate: {},
      weekdayHourHitRate: {},
      nearby: null,
      meanSourceConfidence: 0.85,
      meanMatchConfidence: 1,
      lastObservationAt: "2026-09-23T15:40:00Z",
      lastKnownStatus: null,
    },
    explanation: { reasons: [], signals: {}, reportsUsed: 18 },
    ...overrides,
  };
}

describe("ForecastBadge", () => {
  it("shows the probability and confidence for a scored machine", () => {
    render(<ForecastBadge forecast={baseForecast()} />);

    expect(screen.getByText("72%")).toBeInTheDocument();
    expect(screen.getByText(/High confidence/i)).toBeInTheDocument();
  });

  it("calls the number a forecast score rather than a guarantee", () => {
    render(<ForecastBadge forecast={baseForecast()} />);
    expect(screen.getByText(/Forecast score, not a guarantee/i)).toBeInTheDocument();
  });

  it("shows collection progress instead of a percentage below the threshold", () => {
    render(
      <ForecastBadge
        forecast={baseForecast({
          status: "INSUFFICIENT_DATA",
          observationCount: 3,
          minimumObservations: 8,
          next: null,
        })}
      />,
    );

    expect(screen.getByText("INSUFFICIENT DATA")).toBeInTheDocument();
    expect(screen.getByText("3 / 8 observations collected")).toBeInTheDocument();
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
  });

  it("labels a network-pattern forecast as not machine-specific", () => {
    render(
      <ForecastBadge
        forecast={baseForecast({
          status: "NETWORK_PATTERN",
          observationCount: 1,
          confidence: "LOW",
          networkPrior: {
            scope: "REGIONAL",
            sampleCount: 93,
            machineCount: 40,
            positiveCount: 18,
            baseRate: 0.19,
            hourRate: { "16": 0.47 },
            weekdayRate: { "2": 0.2 },
            bestHour: 16,
            bestHourRate: 0.47,
            regionalRadiusMiles: 250,
          },
        })}
      />,
    );

    expect(screen.getByText("NETWORK PATTERN")).toBeInTheDocument();
    expect(screen.getByText(/Network-wide, not this machine/i)).toBeInTheDocument();
    expect(screen.getByText(/93 community reports within 250 miles/i)).toBeInTheDocument();
    expect(screen.getByText(/most often in stock around 16:00 local/i)).toBeInTheDocument();
  });

  it("says how little history the machine itself has", () => {
    render(
      <ForecastBadge
        forecast={baseForecast({ status: "NETWORK_PATTERN", observationCount: 1 })}
      />,
    );
    expect(screen.getByText(/Not enough reports from this machine \(1\)/i)).toBeInTheDocument();
  });

  it("never invents a number when there is no forecast at all", () => {
    render(<ForecastBadge forecast={null} />);

    expect(screen.getByText("NO FORECAST YET")).toBeInTheDocument();
    expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument();
  });

  it("handles a scored machine with no window above zero", () => {
    render(<ForecastBadge forecast={baseForecast({ next: null })} />);
    expect(screen.getByText("NO WINDOW ABOVE ZERO")).toBeInTheDocument();
  });

  it("exposes collection progress to assistive technology", () => {
    render(
      <ForecastBadge
        forecast={baseForecast({
          status: "INSUFFICIENT_DATA",
          observationCount: 3,
          minimumObservations: 8,
          next: null,
        })}
      />,
    );

    const progress = screen.getByRole("progressbar");
    expect(progress).toHaveAttribute("aria-valuenow", "3");
    expect(progress).toHaveAttribute("aria-valuemax", "8");
  });
});
