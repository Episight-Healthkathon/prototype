export const labels: Record<string, string> = {
  FLAGGED: "Belum diinvestigasi",
  INVESTIGATING: "Investigasi berjalan",
  BRIEF_READY: "Brief tersedia",
  INVESTIGATION_FAILED: "Investigasi gagal",
  EVIDENCE_SUFFICIENT: "Bukti cukup untuk ditinjau",
  EVIDENCE_CONFLICTING: "Bukti bertentangan",
  EVIDENCE_UNAVAILABLE: "Bukti tidak tersedia",
  HUMAN_REVIEW_REQUIRED: "Perlu tinjauan manusia",
  READMISSION: "Readmission",
  FRAGMENTATION: "Fragmentasi episode",
  OPEN: "Belum selesai",
  FOUND: "Terdokumentasi",
  NOT_FOUND: "Tidak ditemukan setelah pencarian",
  UNAVAILABLE: "Sumber tidak tersedia",
  CONFLICTING: "Sumber bertentangan",
  FAILED: "Pemeriksaan gagal",
  SKIPPED: "Tidak diperiksa",
  AVAILABLE: "Tersedia",
  RESTRICTED: "Akses dibatasi",
  ANCHOR: "Pemicu sinyal",
  RELATED: "Episode terkait",
  CONTEXT: "Riwayat konteks",
  INPATIENT: "Rawat inap",
  OUTPATIENT: "Rawat jalan",
  EMERGENCY: "Darurat",
  ELECTIVE: "Elektif",
  RISK: "Bukti sinyal risiko",
  CONTEXT_EVIDENCE: "Konteks penjelas",
  EXPLAINING_CONTEXT: "Konteks penjelas",
  SUPPORTING_RISK: "Bukti sinyal risiko",
  NEUTRAL: "Informasi pendukung",
  POLICY: "Referensi kebijakan",
  BACKGROUND: "Informasi pendukung",
  AFFIRMS: "Mendukung pernyataan",
  NEGATES: "Menyangkal pernyataan",
  INFORMS: "Memberi informasi",
  QUEUED: "Dalam antrean",
  RUNNING: "Berjalan",
  COMPLETED: "Selesai",
  OK: "Berhasil",
  EMPTY: "Tidak ada temuan",
  ERROR: "Gagal",
  TIMEOUT: "Batas waktu",
  REJECTED: "Usulan ditolak",
  LLM: "Planner AI",
  LLM_RETRY: "Planner AI · percobaan ulang",
  RULE_FALLBACK: "Fallback aturan",
  RULE: "Planner aturan",
  SUFFICIENT_EVIDENCE: "Bukti cukup untuk peninjauan",
  CONFLICTING_EVIDENCE: "Bukti bertentangan perlu diperiksa",
  REQUIRED_EVIDENCE_UNAVAILABLE: "Sumber wajib tidak tersedia",
  EVIDENCE_PATHS_EXHAUSTED: "Jalur pencarian bukti selesai",
  MAX_STEPS_REACHED: "Batas langkah tercapai",
  TOOL_FAILURE: "Alat pemeriksaan gagal",
  NO_ACTIONABLE_GAP: "Tidak ada pemeriksaan lanjutan yang tersedia",
  INTERRUPTED: "Investigasi terinterupsi",
  CLINICAL_NOTE: "Catatan klinis",
  POLICY_SECTION: "Bagian kebijakan",
  EPISODE_RECORD: "Data episode",
  CLAIM_RECORD: "Data klaim",
  PROVIDER_RECORD: "Data fasilitas",
  SCREENING_RULE: "Aturan screening",
  EPISODE_RELATEDNESS: "Keterkaitan episode",
  DIAGNOSIS_CONSISTENCY: "Konsistensi diagnosis",
  PROCEDURE_RELATIONSHIP: "Keterkaitan tindakan",
  PROVIDER_CONTEXT: "Konteks fasilitas",
  CLINICAL_DOCUMENT_AVAILABILITY: "Ketersediaan dokumen klinis",
  EMERGENCY_CONTEXT: "Konteks darurat",
  CHRONIC_CONDITION_CONTEXT: "Konteks kondisi kronis",
  SCHEDULED_PROCEDURE_CONTEXT: "Konteks tindakan terjadwal",
  SUPPORTING_EXAM_FOLLOWUP_CONTEXT: "Konteks tindak lanjut pemeriksaan",
  CLINICAL_JUSTIFICATION: "Justifikasi klinis",
  RISK_INDICATORS_IN_NOTES: "Indikator risiko pada catatan",
  APPLICABLE_POLICY: "Kebijakan terkait",
  SCHEDULE_CONSISTENCY: "Konsistensi jadwal",
  FULL_RULE_PLANNER: "Aturan + retrieval",
  FULL: "Planner AI + fallback",
  RULES_ONLY: "Aturan saja",
  RULES_RETRIEVAL: "Aturan + pencarian kebijakan",
};
export const label = (value?: string | null) =>
  value ? labels[value] || value.replaceAll("_", " ") : "Belum tersedia";
export function tone(value?: string | null) {
  if (
    [
      "CONFLICTING",
      "EVIDENCE_CONFLICTING",
      "FAILED",
      "ERROR",
      "INVESTIGATION_FAILED",
    ].includes(value || "")
  )
    return "rose";
  if (
    [
      "UNAVAILABLE",
      "RESTRICTED",
      "EVIDENCE_UNAVAILABLE",
      "HUMAN_REVIEW_REQUIRED",
      "NOT_FOUND",
    ].includes(value || "")
  )
    return "amber";
  if (
    [
      "FOUND",
      "EVIDENCE_SUFFICIENT",
      "BRIEF_READY",
      "AVAILABLE",
      "COMPLETED",
      "OK",
    ].includes(value || "")
  )
    return "teal";
  if (
    ["INVESTIGATING", "RUNNING", "ANCHOR", "READMISSION"].includes(value || "")
  )
    return "blue";
  return "neutral";
}
export const date = (value?: string | null, time = false) =>
  value
    ? new Intl.DateTimeFormat("id-ID", {
        day: "numeric",
        month: "short",
        year: "numeric",
        ...(time
          ? { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta" }
          : { timeZone: "Asia/Jakarta" }),
      }).format(new Date(value))
    : "Tanggal tidak tersedia";
export const humanNotice =
  "EPISIGHT menyusun bukti untuk peninjauan. Penetapan hasil dan keputusan klaim tetap menjadi tanggung jawab reviewer.";
export const scenarios = [
  {
    id: "CASE-RA-0bbfc334",
    title: "Konteks di balik readmission",
    detail:
      "Dua rawat inap, interval 6 hari. Telusuri konteks darurat dan kondisi kronis.",
    patient: "PAT-000001",
    signal: "READMISSION",
    interval: 6,
  },
  {
    id: "CASE-FR-83f41f66",
    title: "Tiga kunjungan, satu rangkaian",
    detail:
      "Rangkaian rawat jalan dengan interval 3 dan 4 hari. Konteks penjelas belum ditemukan.",
    patient: "PAT-000002",
    signal: "FRAGMENTATION",
    interval: 3,
  },
  {
    id: "CASE-RA-d7840713",
    title: "Rencana tindakan yang berlanjut",
    detail:
      "Hubungkan rencana tindakan dengan prosedur yang dilakukan pada episode berikutnya.",
    patient: "PAT-000003",
    signal: "READMISSION",
    interval: 14,
  },
  {
    id: "CASE-RA-609280ef",
    title: "Ketika sumber belum tersedia",
    detail:
      "Catatan episode ulang tidak tersedia atau dibatasi. Ketidakpastian harus tetap terlihat.",
    patient: "PAT-000004",
    signal: "READMISSION",
    interval: 11,
  },
  {
    id: "CASE-RA-608764ca",
    title: "Dua sumber, dua keterangan",
    detail:
      "Catatan triase dan ringkasan pulang memberikan konteks berbeda. Periksa kedua sisi.",
    patient: "PAT-000005",
    signal: "READMISSION",
    interval: 6,
  },
];
