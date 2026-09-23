import { Disclaimer } from "../components/Disclaimer";
import { SourceHealthPanel } from "../components/SourceHealthPanel";
import { useDashboardData } from "../hooks/useDashboardData";
import { formatRelative } from "../lib/format";

/**
 * Source transparency on its own page.
 *
 * Ingestion never fails silently: a source that is off, blocked or missing
 * credentials is listed here with its reason.
 */
export function Sources() {
  const { data, loading } = useDashboardData();

  if (loading && !data) {
    return <p className="empty-note">Loading source health…</p>;
  }

  return (
    <>
      <header className="page-head">
        <h1 className="page-head__title">Data sources</h1>
        <p className="page-head__sub">
          Where every machine and every observation comes from, and what each source is
          allowed to do.
        </p>
        {data && (
          <p className="page-head__meta">
            Last checked {formatRelative(data.generatedAt)}
            <span className="page-head__dot">·</span>
            {data.observationCount} observation{data.observationCount === 1 ? "" : "s"} stored
          </p>
        )}
      </header>

      <SourceHealthPanel sources={data?.sources ?? []} />
      <Disclaimer />
    </>
  );
}
