import { describe, expect, it } from "vitest";

import { formatPercent, formatRelative, orderedHours, productLabel } from "./format";

describe("formatRelative", () => {
  const now = new Date("2026-09-23T16:00:00Z");

  it("describes recent times in minutes", () => {
    expect(formatRelative("2026-09-23T15:37:00Z", now)).toBe("23 minutes ago");
  });

  it("uses the singular for one unit", () => {
    expect(formatRelative("2026-09-23T15:00:00Z", now)).toBe("1 hour ago");
  });

  it("rolls up to hours and days", () => {
    expect(formatRelative("2026-09-23T13:00:00Z", now)).toBe("3 hours ago");
    expect(formatRelative("2026-09-20T16:00:00Z", now)).toBe("3 days ago");
  });

  it("handles missing and unparseable input without throwing", () => {
    expect(formatRelative(null, now)).toBe("never");
    expect(formatRelative(undefined, now)).toBe("never");
    expect(formatRelative("nonsense", now)).toBe("unknown");
  });

  it("does not report a future timestamp as negative", () => {
    expect(formatRelative("2026-09-23T17:00:00Z", now)).toBe("just now");
  });
});

describe("formatPercent", () => {
  it("rounds to whole percentages", () => {
    expect(formatPercent(0.723)).toBe("72%");
    expect(formatPercent(0)).toBe("0%");
  });

  it("returns a placeholder for missing values", () => {
    expect(formatPercent(null)).toBe("--");
    expect(formatPercent(undefined)).toBe("--");
    expect(formatPercent(Number.NaN)).toBe("--");
  });
});

describe("productLabel", () => {
  it("maps known products to display names", () => {
    expect(productLabel("ELITE_TRAINER_BOX")).toBe("Elite Trainer Box");
  });

  it("falls back to the raw value", () => {
    expect(productLabel("SOMETHING_NEW")).toBe("SOMETHING_NEW");
    expect(productLabel(null)).toBe("Unknown");
  });
});

describe("orderedHours", () => {
  it("orders days Monday first", () => {
    const hours = {
      sunday: [["06:00", "22:00"]],
      monday: [["05:30", "00:00"]],
    };
    expect(orderedHours(hours).map(([day]) => day)).toEqual(["monday", "sunday"]);
  });

  it("returns nothing when hours are unknown", () => {
    expect(orderedHours(null)).toEqual([]);
  });
});
