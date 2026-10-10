import { describe, expect, it } from "vitest";
import type { Requirement } from "@episight/shared-types";
import {
  parseReviewView,
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
    ).toEqual(states);
  });
  it("does not report documented evidence or optional checks as material gaps", () => {
    expect(
      reviewPriorities([requirement("FOUND"), requirement("OPEN", false)]),
    ).toEqual([]);
  });
});
