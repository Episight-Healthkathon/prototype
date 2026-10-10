import type { SignalType } from "@episight/shared-types";

// Participant Guide Healthkathon 2026, page 6. Competition context,
// not a substitute for applicable clinical or claim policy.
export const reviewGuide: Record<SignalType, {
  title: string;
  definition: string;
  question: string;
}> = {
  READMISSION: {
    title: "Readmisi (admisi berulang) · modus 16",
    definition: "Klaim atas satu episode yang diklaim lebih dari satu kali seolah lebih dari satu episode.",
    question: "Apakah admisi berikutnya merupakan kelanjutan episode sebelumnya atau pelayanan baru dengan indikasi medis?",
  },
  FRAGMENTATION: {
    title: "Services unbundling / fragmentation · modus 9",
    definition: "Pemecahan episode yang tidak sesuai indikasi; klaim diagnosis/prosedur yang seharusnya satu paket.",
    question: "Apakah diagnosis atau prosedur pada kunjungan terpisah seharusnya satu paket, dan adakah indikasi medis untuk pemisahannya?",
  },
};
