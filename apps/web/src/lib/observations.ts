/**
 * First-party observation capture.
 *
 * GitLab Pages is static hosting and cannot accept writes, so a report is saved
 * in the browser and clearly labelled as local. It is never described as
 * uploaded unless a submission endpoint is configured and actually accepted it.
 *
 * When the AWS backend lands, only `submissionEndpoint` changes; the dashboard
 * components keep calling this same service.
 */

import { appConfig } from "./config";
import type { StoredUserObservation, UserObservationDraft } from "./types";

export type SubmissionOutcome = "SYNCED" | "STORED_LOCALLY" | "STORED_LOCALLY_AFTER_FAILURE";

export interface SubmissionResult {
  outcome: SubmissionOutcome;
  observation: StoredUserObservation;
  message: string;
}

const LOCAL_ONLY_MESSAGE =
  "Local observation saved. Community synchronization will be enabled when the API backend launches.";

function readAll(storage: Storage): StoredUserObservation[] {
  try {
    const raw = storage.getItem(appConfig.localStorageKey);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as StoredUserObservation[]) : [];
  } catch {
    // Corrupt or unavailable storage must not break reporting.
    return [];
  }
}

function writeAll(storage: Storage, observations: StoredUserObservation[]): void {
  try {
    storage.setItem(appConfig.localStorageKey, JSON.stringify(observations));
  } catch {
    // Quota exceeded or storage disabled; the caller still gets its result.
  }
}

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `obs-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export class ObservationSubmissionService {
  constructor(
    private readonly storage: Storage,
    private readonly endpoint: string = appConfig.submissionEndpoint,
    private readonly fetchImpl: typeof fetch = globalThis.fetch?.bind(globalThis),
  ) {}

  /** Every report captured in this browser, newest first. */
  list(machineId?: string): StoredUserObservation[] {
    const all = readAll(this.storage);
    const filtered = machineId ? all.filter((entry) => entry.machineId === machineId) : all;
    return [...filtered].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  count(machineId?: string): number {
    return this.list(machineId).length;
  }

  /**
   * Record an observation.
   *
   * With no endpoint configured the report is stored locally and reported as
   * local. With an endpoint, a failed POST still keeps the report rather than
   * losing it, and says that it is not yet synced.
   */
  async submit(draft: UserObservationDraft): Promise<SubmissionResult> {
    const observation: StoredUserObservation = {
      ...draft,
      id: newId(),
      createdAt: new Date().toISOString(),
      synced: false,
    };

    if (!this.endpoint) {
      this.persist(observation);
      return {
        outcome: "STORED_LOCALLY",
        observation,
        message: LOCAL_ONLY_MESSAGE,
      };
    }

    try {
      const response = await this.fetchImpl(this.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(observation),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      observation.synced = true;
      this.persist(observation);
      return {
        outcome: "SYNCED",
        observation,
        message: "Report submitted. Thank you - confirmed sightings are the strongest signal.",
      };
    } catch (error) {
      this.persist(observation);
      return {
        outcome: "STORED_LOCALLY_AFTER_FAILURE",
        observation,
        message: `Saved locally. Upload failed (${(error as Error).message}) and will be retried later.`,
      };
    }
  }

  private persist(observation: StoredUserObservation): void {
    const all = readAll(this.storage);
    all.push(observation);
    writeAll(this.storage, all);
  }

  clear(): void {
    writeAll(this.storage, []);
  }
}

/** Default instance backed by localStorage. */
export function createSubmissionService(): ObservationSubmissionService {
  return new ObservationSubmissionService(globalThis.localStorage);
}
