/** Display formatting helpers. */

import type { ConfidenceBand, ForecastWindow } from "./types";

/** "2:37 PM" in the viewer's local time. */
export function formatClock(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

/** "2:37 – 2:42 PM" for a forecast window. */
export function formatWindow(window: Pick<ForecastWindow, "windowStart" | "windowEnd">): string {
  const start = new Date(window.windowStart);
  const end = new Date(window.windowEnd);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return "--";

  const startParts = start.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const endParts = end.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const sameMeridiem = startParts.slice(-2) === endParts.slice(-2);

  return sameMeridiem
    ? `${startParts.replace(/\s?[AP]M$/i, "")} – ${endParts}`
    : `${startParts} – ${endParts}`;
}

/** "23 minutes ago", "3 hours ago", "just now". */
export function formatRelative(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "never";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "unknown";

  const seconds = Math.round((now.getTime() - then.getTime()) / 1000);
  if (seconds < 0) return "just now";
  if (seconds < 60) return "just now";

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;

  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;

  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return `${Math.round(value * 100)}%`;
}

export function formatDistance(miles: number): string {
  if (!Number.isFinite(miles)) return "--";
  return `${miles.toFixed(1)} miles`;
}

export function confidenceLabel(band: ConfidenceBand): string {
  return band.charAt(0) + band.slice(1).toLowerCase();
}

const PRODUCT_LABELS: Record<string, string> = {
  BOOSTER_BUNDLE: "Booster Bundle",
  BOOSTER_PACK: "Booster Pack",
  ELITE_TRAINER_BOX: "Elite Trainer Box",
  TIN: "Tin",
  COLLECTION_BOX: "Collection Box",
  OTHER: "Other",
};

export function productLabel(product: string | null | undefined): string {
  if (!product) return "Unknown";
  return PRODUCT_LABELS[product] ?? product;
}

const SIGNAL_LABELS: Record<string, string> = {
  minutePattern: "Minute pattern",
  interval: "Interval",
  historicalHits: "Historical hits",
  recentActivity: "Recent activity",
  nearbyActivity: "Nearby activity",
  sampleConfidence: "Sample confidence",
  basis: "Basis",
  networkReports: "Network reports",
  machineReports: "This machine",
  scope: "Scope",
};

export function signalLabel(key: string): string {
  return SIGNAL_LABELS[key] ?? key;
}

const COMPONENT_LABELS: Record<string, string> = {
  minute_pattern: "Minute pattern",
  interval: "Recurring interval",
  historical_hit_rate: "Historical hit rate",
  recency: "Recency",
  weekday_hour: "Weekday + hour",
  nearby_activity: "Nearby activity",
};

export function componentLabel(key: string): string {
  return COMPONENT_LABELS[key] ?? key;
}

const DAY_ORDER = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

/** Order a store-hours map Monday-first for display. */
export function orderedHours(
  hours: Record<string, string[][]> | null | undefined,
): [string, string[][]][] {
  if (!hours) return [];
  return DAY_ORDER.filter((day) => day in hours).map((day) => [day, hours[day] ?? []]);
}

export function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
