import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { LastKnownStatus as Data } from "../lib/types";
import { LastKnownStatus } from "./LastKnownStatus";

function status(overrides: Partial<Data> = {}): Data {
  return {
    availability: "AVAILABLE",
    observedAt: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    source: "PUBLIC_WEB",
    sourceUrl: "https://pokemonmap.com/",
    evidenceClass: "COMMUNITY_TIMESTAMPED",
    product: null,
    purchaseConfirmed: false,
    ageHours: 1,
    ...overrides,
  };
}

describe("LastKnownStatus", () => {
  it("renders nothing when there is no observation at all", () => {
    const { container } = render(<LastKnownStatus status={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a fresh availability report without a stale warning", () => {
    render(<LastKnownStatus status={status()} />);

    expect(screen.getByText(/Product was available/i)).toBeInTheDocument();
    expect(screen.queryByText("STALE")).not.toBeInTheDocument();
  });

  it("shows a sold-out report", () => {
    render(<LastKnownStatus status={status({ availability: "NOT_AVAILABLE" })} />);
    expect(screen.getByText(/Sold out or unavailable/i)).toBeInTheDocument();
  });

  it("marks an old report stale and says it is not predictive", () => {
    render(
      <LastKnownStatus
        status={status({
          ageHours: 24 * 129,
          observedAt: new Date(Date.now() - 129 * 24 * 3600 * 1000).toISOString(),
        })}
      />,
    );

    expect(screen.getByText("STALE")).toBeInTheDocument();
    expect(screen.getByText(/129 days old/i)).toBeInTheDocument();
    expect(screen.getByText(/not what is likely now/i)).toBeInTheDocument();
  });

  it("credits and links the source", () => {
    render(<LastKnownStatus status={status()} />);

    const link = screen.getByRole("link", { name: /community tracker/i });
    expect(link).toHaveAttribute("href", "https://pokemonmap.com/");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("calls out a confirmed purchase and the product seen", () => {
    render(
      <LastKnownStatus
        status={status({ product: "ELITE_TRAINER_BOX", purchaseConfirmed: true })}
      />,
    );

    expect(screen.getByText(/Elite Trainer Box/i)).toBeInTheDocument();
    expect(screen.getByText(/purchase confirmed/i)).toBeInTheDocument();
  });

  it("never presents a known status as a probability", () => {
    const { container } = render(<LastKnownStatus status={status({ ageHours: 24 * 100 })} />);
    expect(container.textContent).not.toMatch(/\d+%/);
  });
});
