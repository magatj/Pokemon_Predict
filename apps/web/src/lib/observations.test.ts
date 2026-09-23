import { beforeEach, describe, expect, it, vi } from "vitest";

import { ObservationSubmissionService } from "./observations";
import type { UserObservationDraft } from "./types";

class MemoryStorage implements Storage {
  private store = new Map<string, string>();

  get length() {
    return this.store.size;
  }
  clear() {
    this.store.clear();
  }
  getItem(key: string) {
    return this.store.get(key) ?? null;
  }
  key(index: number) {
    return [...this.store.keys()][index] ?? null;
  }
  removeItem(key: string) {
    this.store.delete(key);
  }
  setItem(key: string, value: string) {
    this.store.set(key, value);
  }
}

const draft: UserObservationDraft = {
  machineId: "rec1",
  availability: "AVAILABLE",
  product: "BOOSTER_BUNDLE",
  purchased: true,
  observedAt: "2026-09-23T16:00:00Z",
};

describe("ObservationSubmissionService without an endpoint", () => {
  let storage: MemoryStorage;

  beforeEach(() => {
    storage = new MemoryStorage();
  });

  it("stores the report locally", async () => {
    const service = new ObservationSubmissionService(storage, "");
    const result = await service.submit(draft);

    expect(result.outcome).toBe("STORED_LOCALLY");
    expect(service.list("rec1")).toHaveLength(1);
  });

  it("does not claim the report was uploaded", async () => {
    const service = new ObservationSubmissionService(storage, "");
    const result = await service.submit(draft);

    expect(result.message).toContain("Local observation saved");
    expect(result.message).toContain("when the API backend launches");
    expect(result.observation.synced).toBe(false);
  });

  it("records the observation timestamp", async () => {
    const service = new ObservationSubmissionService(storage, "");
    const result = await service.submit(draft);
    expect(result.observation.observedAt).toBe("2026-09-23T16:00:00Z");
    expect(Date.parse(result.observation.createdAt)).not.toBeNaN();
  });

  it("keeps reports separated by machine", async () => {
    const service = new ObservationSubmissionService(storage, "");
    await service.submit(draft);
    await service.submit({ ...draft, machineId: "rec2" });

    expect(service.count("rec1")).toBe(1);
    expect(service.count("rec2")).toBe(1);
    expect(service.count()).toBe(2);
  });

  it("survives corrupt stored data", async () => {
    storage.setItem("pokevend.observations.v1", "{not json");
    const service = new ObservationSubmissionService(storage, "");

    expect(service.list()).toEqual([]);
    await expect(service.submit(draft)).resolves.toBeDefined();
  });
});

describe("ObservationSubmissionService with an endpoint", () => {
  it("reports a successful upload as synced", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, status: 201 } as Response);
    const service = new ObservationSubmissionService(
      new MemoryStorage(),
      "https://api.example.test/api/v1/observations",
      fetchImpl as unknown as typeof fetch,
    );

    const result = await service.submit(draft);

    expect(fetchImpl).toHaveBeenCalledOnce();
    expect(result.outcome).toBe("SYNCED");
    expect(result.observation.synced).toBe(true);
  });

  it("keeps the report and says so when the upload fails", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: false, status: 503 } as Response);
    const storage = new MemoryStorage();
    const service = new ObservationSubmissionService(
      storage,
      "https://api.example.test/api/v1/observations",
      fetchImpl as unknown as typeof fetch,
    );

    const result = await service.submit(draft);

    expect(result.outcome).toBe("STORED_LOCALLY_AFTER_FAILURE");
    expect(result.observation.synced).toBe(false);
    expect(result.message).toContain("503");
    expect(service.count("rec1")).toBe(1);
  });

  it("keeps the report when the network throws", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error("offline"));
    const service = new ObservationSubmissionService(
      new MemoryStorage(),
      "https://api.example.test/api/v1/observations",
      fetchImpl as unknown as typeof fetch,
    );

    const result = await service.submit(draft);
    expect(result.outcome).toBe("STORED_LOCALLY_AFTER_FAILURE");
    expect(result.message).toContain("offline");
  });
});
