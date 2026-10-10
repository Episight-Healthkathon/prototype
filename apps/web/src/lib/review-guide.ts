import type {
  Evidence,
  Requirement,
  RunSummary,
  SignalType,
} from "@episight/shared-types";

export function orderedRuns(items: RunSummary[]) {
  return [...items].sort(
    (a, b) => Date.parse(b.started_at) - Date.parse(a.started_at),
  );
}

export function countEvidenceSources(evidence: Evidence[]) {
  return new Set(evidence.map((e) => `${e.source_type}:${e.source_id}`)).size;
}
export type EvidenceFilter = "ALL" | "SIGNAL" | "CONTEXT" | "POLICY" | "OTHER";
export function evidenceGroup(e: Evidence): Exclude<EvidenceFilter, "ALL"> {
  if (e.source_type === "POLICY_SECTION") return "POLICY";
  if (e.relevance_category === "SUPPORTING_RISK") return "SIGNAL";
  if (e.relevance_category === "EXPLAINING_CONTEXT") return "CONTEXT";
  return "OTHER";
}

export type ReviewView = "overview" | "workspace" | "evidence" | "brief";
export function parseReviewView(value?: string | null): ReviewView {
  return value === "workspace" || value === "evidence" || value === "brief"
    ? value
    : "overview";
}

export function reviewPriorities(requirements: Requirement[]) {
  // NOT_FOUND is a completed search, but may still require human review;
  // FOUND records evidence and does not establish that a claim is valid.
  const order: Record<Requirement["state"], number> = {
    CONFLICTING: 0,
    UNAVAILABLE: 1,
    FAILED: 2,
    OPEN: 3,
    SKIPPED: 4,
    NOT_FOUND: 5,
    FOUND: 6,
  };
  return requirements
    .filter((r) => r.material && r.state !== "FOUND")
    .sort((a, b) => order[a.state] - order[b.state]);
}

// Participant Guide Healthkathon 2026, page 6. Competition context,
// not a substitute for applicable clinical or claim policy.
export const reviewGuide: Record<
  SignalType,
  {
    title: string;
    definition: string;
    question: string;
  }
> = {
  READMISSION: {
    title: "Readmisi (admisi berulang) · modus 16",
    definition:
      "Klaim atas satu episode yang diklaim lebih dari satu kali seolah lebih dari satu episode.",
    question:
      "Apakah admisi berikutnya merupakan kelanjutan episode sebelumnya atau pelayanan baru dengan indikasi medis?",
  },
  FRAGMENTATION: {
    title: "Services unbundling / fragmentation · modus 9",
    definition:
      "Pemecahan episode yang tidak sesuai indikasi; klaim diagnosis/prosedur yang seharusnya satu paket.",
    question:
      "Apakah diagnosis atau prosedur pada kunjungan terpisah seharusnya satu paket, dan adakah indikasi medis untuk pemisahannya?",
  },
};
