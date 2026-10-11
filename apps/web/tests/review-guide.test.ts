import { describe, expect, it } from "vitest";
import type {
  Evidence,
  EvidenceList,
  Requirement,
  RunSummary,
} from "@episight/shared-types";
import { readFileSync } from "node:fs";
import {
  parseReviewView,
  countEvidenceSources,
  orderedRuns,
  evidenceGroup,
  reviewGuide,
  reviewPriorities,
} from "@/lib/review-guide";

function requirement(
  state: Requirement["state"],
  material = true,
): Requirement {
  return {
    key: "CLINICAL_JUSTIFICATION",
    label: "Justifikasi klinis",
    direction: "CONTEXT",
    material,
    state,
    state_explanation: "Penjelasan",
    coverage: {
      searched_sources: 0,
      in_scope_sources: 0,
      unavailable_sources: 0,
    },
    evidence_ids: [],
    attempted_tools: [],
    spawned_by: null,
  };
}

describe("guided review", () => {
  it("partitions every demo evidence entry without hiding policy or neutral sources", () => {
    const queue = JSON.parse(
      readFileSync(
        new URL("../public/demo/cases.list.json", import.meta.url),
        "utf8",
      ),
    ) as { items: { case_id: string }[] };
    for (const c of queue.items) {
      const data = JSON.parse(
        readFileSync(
          new URL(
            `../public/demo/cases/${c.case_id}.evidence.json`,
            import.meta.url,
          ),
          "utf8",
        ),
      ) as EvidenceList;
      for (const e of data.items)
        expect(["SIGNAL", "CONTEXT", "POLICY", "OTHER"]).toContain(
          evidenceGroup(e),
        );
      expect(
        data.items
          .filter((e) => e.source_type === "POLICY_SECTION")
          .every((e) => evidenceGroup(e) === "POLICY"),
      ).toBe(true);
      expect(data.items.map((e) => evidenceGroup(e))).toHaveLength(
        data.items.length,
      );
    }
  });
  it("orders history newest first without changing the original list", () => {
    const earlier = {
      run_id: "old",
      started_at: "2026-10-01T10:00:00+07:00",
    } as RunSummary;
    const latest = {
      run_id: "new",
      started_at: "2026-10-02T10:00:00+07:00",
    } as RunSummary;
    const input = [earlier, latest];
    expect(orderedRuns(input).map((r) => r.run_id)).toEqual(["new", "old"]);
    expect(input[0].run_id).toBe("old");
  });
  it("supports direct links and back navigation to each review stage", () => {
    for (const view of [
      "overview",
      "workspace",
      "evidence",
      "brief",
    ] as const) {
      expect(parseReviewView(view)).toBe(view);
    }
    expect(parseReviewView("unknown")).toBe("overview");
    expect(parseReviewView(null)).toBe("overview");
  });
  it("maps each signal to its specific competition definition", () => {
    expect(reviewGuide.READMISSION.title).toContain("16");
    expect(reviewGuide.READMISSION.definition).toContain("satu episode");
    expect(reviewGuide.FRAGMENTATION.title).toContain("9");
    expect(reviewGuide.FRAGMENTATION.question).toContain("indikasi medis");
  });
  it("keeps every unresolved material state visible, including completed searches", () => {
    const states = [
      "OPEN",
      "NOT_FOUND",
      "UNAVAILABLE",
      "CONFLICTING",
      "FAILED",
      "SKIPPED",
    ] as const;
    expect(
      reviewPriorities(states.map((state) => requirement(state))).map(
        (r) => r.state,
      ),
    ).toEqual([
      "CONFLICTING",
      "UNAVAILABLE",
      "FAILED",
      "OPEN",
      "SKIPPED",
      "NOT_FOUND",
    ]);
  });
  it("does not report documented evidence or optional checks as material gaps", () => {
    expect(
      reviewPriorities([requirement("FOUND"), requirement("OPEN", false)]),
    ).toEqual([]);
  });
  it("counts unique sources rather than evidence statements", () => {
    const data = JSON.parse(
      readFileSync(
        new URL(
          "../public/demo/cases/CASE-FR-4cf97d96.evidence.json",
          import.meta.url,
        ),
        "utf8",
      ),
    ) as EvidenceList;
    const risk = data.items.filter(
      (e) => e.relevance_category === "SUPPORTING_RISK",
    );
    expect(countEvidenceSources(risk)).toBe(2);
    expect(
      countEvidenceSources([
        ...risk,
        { ...risk[0], evidence_id: "duplicate-statement" } as Evidence,
      ]),
    ).toBe(2);
    expect(
      countEvidenceSources(
        data.items.filter((e) => e.relevance_category === "EXPLAINING_CONTEXT"),
      ),
    ).toBe(0);
  });
  it("puts conflicting evidence first without mutating input requirements", () => {
    const input = [requirement("NOT_FOUND"), requirement("CONFLICTING")];
    expect(reviewPriorities(input)[0].state).toBe("CONFLICTING");
    expect(input[0].state).toBe("NOT_FOUND");
  });
});
