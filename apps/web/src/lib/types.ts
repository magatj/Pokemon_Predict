/** Shapes of the JSON the ingestion pipeline publishes. */

export type Availability = "AVAILABLE" | "NOT_AVAILABLE" | "RESTOCK" | "UNKNOWN";

export type ObservationSourceKind = "REDDIT" | "PUBLIC_WEB" | "USER";

export type Product =
  | "BOOSTER_BUNDLE"
  | "BOOSTER_PACK"
  | "ELITE_TRAINER_BOX"
  | "TIN"
  | "COLLECTION_BOX"
  | "OTHER";

export type ForecastStatus = "OK" | "INSUFFICIENT_DATA" | "NETWORK_PATTERN";

export type ConfidenceBand = "HIGH" | "MEDIUM" | "LOW";

export type SourceStatus =
  | "HEALTHY"
  | "STALE"
  | "ERROR"
  | "DISABLED"
  | "RATE_LIMITED"
  | "SKIPPED";

export interface NearbyMachine {
  id: string;
  retailer: string;
  name: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  latitude: number;
  longitude: number;
  distanceMiles: number;
  source: string;
  lastVerifiedAt: string;
}

/** A machine exactly as `machines.json` stores it (snake_case from Python). */
export interface RawMachine {
  id: string;
  retailer: string;
  name: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  latitude: number;
  longitude: number;
  source: string;
  source_authority: string;
  source_url: string | null;
  distance_miles: number | null;
  discovered_at: string | null;
  last_verified_at: string | null;
  store_hours: Record<string, string[][]> | null;
  kiosk_listed: boolean | null;
  verifications: MachineVerification[];
  aliases: string[];
}

export interface MachineVerification {
  source: string;
  retailer: string | null;
  url: string | null;
  verified_at: string;
  kiosk_listed: boolean;
  address_match_score: number;
}

export interface SearchMeta {
  zipCode?: string;
  radiusMiles?: number;
  timezone?: string;
  windowMinutes?: number;
  minimumObservations?: number;
}

export interface MachinesFile {
  generatedAt: string;
  search: SearchMeta;
  machines: RawMachine[];
  /** Set only by the demo seeder; real pipeline output never carries it. */
  demoData?: boolean;
}

export interface ExternalObservation {
  id: string;
  source: ObservationSourceKind;
  sourceUrl?: string | null;
  machineId?: string | null;
  machineMatchConfidence: number;
  retailer?: string | null;
  locationText?: string | null;
  observedAt?: string | null;
  postedAt: string;
  availability: Availability;
  product?: Product | null;
  purchaseConfirmed: boolean;
  evidenceClass: string;
  confidence: number;
}

export interface ObservationsFile {
  generatedAt: string;
  observations: ExternalObservation[];
}

export interface MinutePattern {
  patternMinute: number;
  toleranceMinutes: number;
  support: number;
  sampleCount: number;
  totalSamples: number;
}

export interface IntervalPattern {
  intervalMinutes: number;
  support: number;
  sampleCount: number;
  matchedGaps: number;
  totalGaps: number;
  medianGapMinutes: number;
}

export interface NearbyActivity {
  windowMinutes: number;
  activeByRadiusMiles: Record<string, number>;
  activeMachineIds: string[];
  closestRadiusMiles: number;
  activeClosest: number;
  score: number;
}

/** The most recent real observation for a machine, whatever its age. */
export interface LastKnownStatus {
  availability: Availability;
  observedAt: string;
  source: ObservationSourceKind;
  sourceUrl: string | null;
  evidenceClass: string;
  product: Product | null;
  purchaseConfirmed: boolean;
  ageHours: number;
}

export interface ForecastFeatures {
  machineId: string;
  observationCount: number;
  positiveCount: number;
  negativeCount: number;
  purchaseCount: number;
  totalWeight: number;
  minutesSinceLastAvailable: number | null;
  minutesSinceLastNotAvailable: number | null;
  minutesSinceLastPurchase: number | null;
  minutesSinceSuspectedRestock: number | null;
  minutesSinceLastPositive: number | null;
  minutePattern: MinutePattern | null;
  interval: IntervalPattern | null;
  hourHitRate: Record<string, number>;
  weekdayHitRate: Record<string, number>;
  weekdayHourHitRate: Record<string, number>;
  nearby: NearbyActivity | null;
  meanSourceConfidence: number;
  meanMatchConfidence: number;
  lastObservationAt: string | null;
  lastKnownStatus: LastKnownStatus | null;
}

export interface ForecastExplanation {
  reasons: string[];
  signals: Record<string, string>;
  reportsUsed: number;
}

/** Empirical population rate used when a machine lacks its own history. */
export interface NetworkPrior {
  scope: "REGIONAL" | "NETWORK";
  sampleCount: number;
  machineCount: number;
  positiveCount: number;
  baseRate: number;
  hourRate: Record<string, number>;
  weekdayRate: Record<string, number>;
  bestHour: number | null;
  bestHourRate: number | null;
  regionalRadiusMiles: number;
}

export interface ForecastWindow {
  windowStart: string;
  windowEnd: string;
  localTime: string;
  probability: number;
  rawScore: number;
  sampleScale: number;
  sourceScale: number;
  /** Discount applied because this window is further into the future. */
  horizonScale: number;
  minutesAhead: number;
  /** "NETWORK" when the window was scored from the population prior. */
  basis?: "NETWORK";
  components: Record<string, number>;
  explanation?: ForecastExplanation;
}

export interface MachineForecast {
  machineId: string;
  generatedAt: string;
  windowMinutes: number;
  observationCount: number;
  minimumObservations: number;
  status: ForecastStatus;
  confidence: ConfidenceBand;
  windows: ForecastWindow[];
  next: ForecastWindow | null;
  features: ForecastFeatures;
  explanation: ForecastExplanation;
  networkPrior?: NetworkPrior;
}

export interface ForecastsFile {
  generatedAt: string;
  forecasts: MachineForecast[];
}

export interface SourceHealthEntry {
  name: string;
  status: SourceStatus;
  authority: string;
  checked_at: string;
  records: number;
  message: string;
  reason: string | null;
  last_success_at: string | null;
  details: Record<string, unknown>;
}

export interface SourceHealthFile {
  generatedAt: string;
  sources: SourceHealthEntry[];
}

/** A machine joined with its forecast, which is what the UI renders. */
export interface MachineWithForecast {
  machine: NearbyMachine;
  raw: RawMachine;
  forecast: MachineForecast | null;
}

/** A first-party report captured in the browser. */
export interface UserObservationDraft {
  machineId: string;
  availability: Extract<Availability, "AVAILABLE" | "NOT_AVAILABLE">;
  product?: Product;
  purchased?: boolean;
  observedAt: string;
}

export interface StoredUserObservation extends UserObservationDraft {
  id: string;
  createdAt: string;
  synced: boolean;
}
