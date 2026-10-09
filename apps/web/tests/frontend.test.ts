import { readFileSync } from "node:fs";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { createApi, ApiFailure, filterCases } from "../src/lib/api";
import { sourceSegments } from "../src/lib/source";
import { label, scenarios } from "../src/lib/labels";
import type {
  CaseList,
  EvidenceList,
  InvestigationBrief,
  InvestigationView,
} from "@episight/shared-types";
const fixture = <T>(name: string): T =>
  JSON.parse(
    readFileSync(new URL(`../public/demo/${name}`, import.meta.url), "utf8"),
  );
describe("reviewer data invariants", () => {
  it("provides the official 20-case queue with paginated search and sorting", () => {
    const list = fixture<CaseList>("cases.list.json");
    expect(list.total).toBe(20);
    expect(
      list.items.filter((c) => c.signal_type === "READMISSION"),
    ).toHaveLength(13);
    expect(filterCases(list.items, { q: "pat-000001" })[0].case_id).toBe(
      scenarios[0].id,
    );
    expect(
      filterCases(list.items, { signal_type: "FRAGMENTATION" }),
    ).toHaveLength(7);
    const sorted = filterCases(list.items, { sort: "min_interval_days" });
    expect(
      sorted.every(
        (c, i) => !i || c.min_interval_days >= sorted[i - 1].min_interval_days,
      ),
    ).toBe(true);
    expect(
      filterCases(list.items, { progress_status: "BRIEF_READY" }),
    ).toHaveLength(0);
  });
  it("preserves all golden outcomes and complete material citations", () => {
    const outcomes = [
      "EVIDENCE_SUFFICIENT",
      "HUMAN_REVIEW_REQUIRED",
      "EVIDENCE_SUFFICIENT",
      "EVIDENCE_UNAVAILABLE",
      "EVIDENCE_CONFLICTING",
    ];
    for (const [i, c] of scenarios.entries()) {
      const brief = fixture<InvestigationBrief>(`cases/${c.id}.brief.json`);
      expect(brief.outcome).toBe(outcomes[i]);
      const evidence = fixture<EvidenceList>(`cases/${c.id}.evidence.json`);
      const ids = new Set(evidence.items.map((e) => e.evidence_id));
      for (const s of [
        ...brief.case_summary,
        ...brief.supporting_risk_evidence,
        ...brief.explaining_context_evidence,
        ...brief.uncertainty,
        ...brief.suggested_next_review,
      ]) {
        if (s.material) expect(s.evidence_ids.length).toBeGreaterThan(0);
        for (const id of s.evidence_ids) expect(ids.has(id)).toBe(true);
      }
      expect(brief.human_decision_notice).toContain("The reviewer decides.");
      expect(brief.traceability.with_evidence).toBe(
        brief.traceability.material_statements,
      );
    }
  });
  it("keeps missing-source uncertainty and both sides of conflict", () => {
    const missing = fixture<InvestigationBrief>(
      `cases/${scenarios[3].id}.brief.json`,
    );
    expect(missing.remaining_gaps.some((g) => g.state === "UNAVAILABLE")).toBe(
      true,
    );
    const conflict = fixture<InvestigationBrief>(
      `cases/${scenarios[4].id}.brief.json`,
    );
    expect(conflict.conflicts.length).toBeGreaterThan(0);
    expect(conflict.conflicts[0].affirming_evidence_ids.length).toBeGreaterThan(
      0,
    );
    expect(conflict.conflicts[0].negating_evidence_ids.length).toBeGreaterThan(
      0,
    );
    expect(label("UNAVAILABLE")).not.toBe(label("NOT_FOUND"));
    expect(label("NEW_ENUM")).toBe("NEW ENUM");
  });
  it("highlights backend Unicode offsets and safely ignores invalid ranges", () => {
    expect(
      sourceSegments("A 🩺 bukti", { char_start: 2, char_end: 3 }),
    ).toEqual({ before: "A ", marked: "🩺", after: " bukti" });
    expect(
      sourceSegments("bukti", { char_start: 1, char_end: 30 }).marked,
    ).toBe("");
  });
});
describe("offline investigation playback", () => {
  beforeEach(() => {
    const storage = new Map<string, string>();
    vi.stubGlobal("window", {});
    vi.stubGlobal("sessionStorage", {
      getItem: (k: string) => storage.get(k) || null,
      setItem: (k: string, v: string) => storage.set(k, v),
    });
    vi.stubGlobal(
      "fetch",
      async (url: string) =>
        new Response(JSON.stringify(fixture(url.replace("/demo/", ""))), {
          status: 200,
        }),
    );
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-08T10:00:00Z"));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
  it("does not expose a future brief or future evidence during playback", async () => {
    const api = createApi("demo"),
      id = scenarios[0].id;
    await expect(api.investigation(id)).rejects.toMatchObject({
      code: "RUN_NOT_FOUND",
    });
    await api.start(id, "FULL_RULE_PLANNER");
    expect((await api.detail(id)).progress_status).toBe("INVESTIGATING");
    await expect(api.brief(id)).rejects.toMatchObject({
      code: "BRIEF_NOT_READY",
    });
    await expect(api.start(id, "FULL_RULE_PLANNER")).rejects.toMatchObject({
      code: "INVESTIGATION_IN_PROGRESS",
    });
    const running = await api.investigation(id);
    expect(
      (await api.evidence(id)).items.every(
        (e) => e.investigation_step <= running.run.step,
      ),
    ).toBe(true);
    vi.advanceTimersByTime(2300);
    expect((await api.brief(id)).outcome).toBe("EVIDENCE_SUFFICIENT");
    expect((await api.detail(id)).progress_status).toBe("BRIEF_READY");
    expect(
      (
        await api.cases({
          progress_status: "BRIEF_READY",
          limit: 10,
          offset: 0,
        })
      ).total,
    ).toBe(1);
    await expect(api.start(id, "FULL_RULE_PLANNER")).rejects.toBeInstanceOf(
      ApiFailure,
    );
    await api.start(id, "FULL_RULE_PLANNER", true);
    expect((await api.investigation(id)).run.run_status).toBe("RUNNING");
  });
  it("paginates all cases and uses actual engine run summaries", async () => {
    const api = createApi("demo");
    const first = await api.cases({ limit: 10, offset: 0 }),
      last = await api.cases({ limit: 10, offset: 10 });
    expect(first.items).toHaveLength(10);
    expect(last.items).toHaveLength(10);
    expect(
      new Set([...first.items, ...last.items].map((c) => c.case_id)).size,
    ).toBe(20);
    const id = scenarios[4].id;
    await api.start(id, "FULL_RULE_PLANNER");
    vi.advanceTimersByTime(2300);
    const run = fixture<InvestigationView>(
      `cases/${id}.investigation.completed.json`,
    );
    expect((await api.runs(id)).items[0].run_id).toBe(run.run.run_id);
  });
});
