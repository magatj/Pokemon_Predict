import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { appConfig } from "../lib/config";
import { ReportForm } from "./ReportForm";

describe("ReportForm", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("requires an availability choice before submitting", () => {
    render(<ReportForm machineId="rec1" />);
    expect(screen.getByRole("button", { name: /submit report/i })).toBeDisabled();
  });

  it("captures an available report with product and purchase", async () => {
    const user = userEvent.setup();
    render(<ReportForm machineId="rec1" />);

    await user.click(screen.getByRole("button", { name: /available now/i }));
    await user.selectOptions(screen.getByLabelText(/what did you see/i), "ELITE_TRAINER_BOX");
    await user.click(screen.getByRole("button", { name: /^yes$/i }));
    await user.click(screen.getByRole("button", { name: /submit report/i }));

    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem(appConfig.localStorageKey) ?? "[]");
      expect(stored).toHaveLength(1);
      expect(stored[0]).toMatchObject({
        machineId: "rec1",
        availability: "AVAILABLE",
        product: "ELITE_TRAINER_BOX",
        purchased: true,
      });
      expect(Date.parse(stored[0].observedAt)).not.toBeNaN();
    });
  });

  it("does not ask about product for a not-available report", async () => {
    const user = userEvent.setup();
    render(<ReportForm machineId="rec1" />);

    await user.click(screen.getByRole("button", { name: /not available/i }));

    expect(screen.queryByLabelText(/what did you see/i)).not.toBeInTheDocument();
  });

  it("tells the user the report stayed local", async () => {
    const user = userEvent.setup();
    render(<ReportForm machineId="rec1" />);

    await user.click(screen.getByRole("button", { name: /available now/i }));
    await user.click(screen.getByRole("button", { name: /submit report/i }));

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(/Local observation saved/i);
    expect(status).not.toHaveTextContent(/uploaded/i);
  });

  it("shows how many reports are held in this browser", async () => {
    const user = userEvent.setup();
    render(<ReportForm machineId="rec1" />);

    await user.click(screen.getByRole("button", { name: /not available/i }));
    await user.click(screen.getByRole("button", { name: /submit report/i }));

    expect(await screen.findByText(/1 report stored in this browser/i)).toBeInTheDocument();
  });

  it("explains why a confirmed purchase matters", async () => {
    const user = userEvent.setup();
    render(<ReportForm machineId="rec1" />);

    await user.click(screen.getByRole("button", { name: /available now/i }));

    expect(screen.getByText(/strongest evidence/i)).toBeInTheDocument();
  });
});
