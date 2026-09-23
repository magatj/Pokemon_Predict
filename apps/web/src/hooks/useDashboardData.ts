import { useCallback, useEffect, useState } from "react";

import { appConfig } from "../lib/config";
import { type DashboardData, loadDashboardData } from "../lib/data";

export interface DashboardState {
  data: DashboardData | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * Load the published JSON bundle, re-reading it periodically.
 *
 * A scheduled pipeline republishes the files, so a long-lived tab would
 * otherwise keep showing a stale forecast.
 */
export function useDashboardData(): DashboardState {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  // `loading` is flipped on by whoever triggers a reload (an event handler or
  // the refresh timer) rather than inside the effect, which would cause a
  // second render pass on every run.
  const reload = useCallback(() => {
    setLoading(true);
    setNonce((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    loadDashboardData(controller.signal)
      .then((result) => {
        if (!active) return;
        setData(result);
        setError(null);
      })
      .catch((cause: Error) => {
        if (!active || controller.signal.aborted) return;
        setError(cause.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [nonce]);

  useEffect(() => {
    const timer = setInterval(reload, appConfig.refreshIntervalMs);
    return () => clearInterval(timer);
  }, [reload]);

  return { data, loading, error, reload };
}
