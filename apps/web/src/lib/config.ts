/**
 * Client-side configuration.
 *
 * The authoritative values live in `config/forecast_config.yaml` and are
 * embedded in the generated `machines.json`. These are the defaults used before
 * that file loads, and for local development.
 */

export const locationConfig = {
  zipCode: "98092",
  radiusMiles: 10,
};

export const appConfig = {
  /** Where the ingestion pipeline publishes its JSON bundle. */
  dataPath: "data",
  /** Refresh interval for re-reading the generated JSON, in milliseconds. */
  refreshIntervalMs: 5 * 60 * 1000,
  /**
   * Optional external endpoint for community observation submissions.
   * Empty on GitLab Pages: static hosting cannot accept writes, so reports are
   * stored locally until the API backend exists. See ObservationSubmissionService.
   */
  submissionEndpoint: (import.meta.env.VITE_SUBMISSION_ENDPOINT as string | undefined) ?? "",
  localStorageKey: "pokevend.observations.v1",
};

/** Resolve a data file against the deployment base path. */
export function dataUrl(file: string): string {
  const base = import.meta.env.BASE_URL || "/";
  return `${base.replace(/\/$/, "")}/${appConfig.dataPath}/${file}`;
}
