import { type FormEvent, useMemo, useState } from "react";

import { createSubmissionService, type SubmissionResult } from "../lib/observations";
import type { Product } from "../lib/types";
import { icons } from "./icons";

const PRODUCTS: { value: Product; label: string }[] = [
  { value: "BOOSTER_BUNDLE", label: "Booster Bundle" },
  { value: "BOOSTER_PACK", label: "Booster Pack" },
  { value: "ELITE_TRAINER_BOX", label: "Elite Trainer Box" },
  { value: "TIN", label: "Tin" },
  { value: "COLLECTION_BOX", label: "Collection Box" },
  { value: "OTHER", label: "Other" },
];

interface Props {
  machineId: string;
  onSubmitted?: (result: SubmissionResult) => void;
}

/**
 * First-party reporting.
 *
 * A confirmed purchase is the strongest observation available: it proves the
 * machine actually dispensed at that moment, which no community post can.
 */
export function ReportForm({ machineId, onSubmitted }: Props) {
  const service = useMemo(() => createSubmissionService(), []);
  const [availability, setAvailability] = useState<"AVAILABLE" | "NOT_AVAILABLE" | null>(null);
  const [product, setProduct] = useState<Product>("BOOSTER_BUNDLE");
  const [purchased, setPurchased] = useState<boolean | null>(null);
  const [result, setResult] = useState<SubmissionResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [localCount, setLocalCount] = useState(() => service.count(machineId));

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!availability) return;

    setSubmitting(true);
    const submission = await service.submit({
      machineId,
      availability,
      // The timestamp is recorded automatically; it is the point of the report.
      observedAt: new Date().toISOString(),
      ...(availability === "AVAILABLE" ? { product } : {}),
      ...(availability === "AVAILABLE" && purchased !== null ? { purchased } : {}),
    });
    setSubmitting(false);
    setResult(submission);
    setLocalCount(service.count(machineId));
    setAvailability(null);
    setPurchased(null);
    onSubmitted?.(submission);
  }

  return (
    <section className="card report" id="report">
      <header className="panel__head">
        <span className="panel__icon" aria-hidden="true">{icons.pencil}</span>
        <h2 className="report__title">Submit an observation</h2>
      </header>
      <p className="report__hint">
        Your reports are what make the forecast work. The time is recorded automatically.
      </p>

      <form onSubmit={handleSubmit}>
        <fieldset className="report__fieldset">
          <legend>Is product available right now?</legend>
          <div className="report__choices">
            <button
              type="button"
              className={`choice choice--available ${availability === "AVAILABLE" ? "choice--selected" : ""}`}
              onClick={() => setAvailability("AVAILABLE")}
              aria-pressed={availability === "AVAILABLE"}
            >
              <span className="choice__symbol" aria-hidden="true">✓</span> Available now
            </button>
            <button
              type="button"
              className={`choice choice--unavailable ${availability === "NOT_AVAILABLE" ? "choice--selected" : ""}`}
              onClick={() => {
                setAvailability("NOT_AVAILABLE");
                setPurchased(null);
              }}
              aria-pressed={availability === "NOT_AVAILABLE"}
            >
              <span className="choice__symbol" aria-hidden="true">−</span> Not available
            </button>
          </div>
        </fieldset>

        {availability === "AVAILABLE" && (
          <>
            <fieldset className="report__fieldset">
              <legend>
                <label htmlFor="report-product">What did you see?</label>
              </legend>
              <select
                id="report-product"
                value={product}
                onChange={(event) => setProduct(event.target.value as Product)}
              >
                {PRODUCTS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </fieldset>

            <fieldset className="report__fieldset">
              <legend>Did you successfully purchase it?</legend>
              <div className="report__choices">
                <button
                  type="button"
                  className={`choice ${purchased === true ? "choice--selected" : ""}`}
                  onClick={() => setPurchased(true)}
                  aria-pressed={purchased === true}
                >
                  Yes
                </button>
                <button
                  type="button"
                  className={`choice ${purchased === false ? "choice--selected" : ""}`}
                  onClick={() => setPurchased(false)}
                  aria-pressed={purchased === false}
                >
                  No
                </button>
              </div>
              <p className="report__hint">
                A confirmed purchase is the strongest evidence: it proves the machine could
                actually dispense at that moment.
              </p>
            </fieldset>
          </>
        )}

        <button type="submit" className="button" disabled={!availability || submitting}>
          {submitting ? "Saving…" : "Submit report"}
        </button>
      </form>

      {result && (
        <p
          className={`report__result report__result--${result.outcome === "SYNCED" ? "synced" : "local"}`}
          role="status"
        >
          {result.message}
        </p>
      )}

      {localCount > 0 && (
        <p className="report__count">
          {localCount} report{localCount === 1 ? "" : "s"} stored in this browser for this machine.
        </p>
      )}
    </section>
  );
}
