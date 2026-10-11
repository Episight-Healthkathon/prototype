"use client";
import {
  IconArrowRight,
  IconSearch,
  IconShieldCheck,
  IconAlertTriangle,
} from "@tabler/icons-react";
import type {
  CaseDetail,
  Evidence,
  InvestigationView,
} from "@episight/shared-types";
import { Badge } from "./system";
import { label } from "@/lib/labels";
import {
  countEvidenceSources,
  reviewGuide,
  reviewPriorities,
} from "@/lib/review-guide";

export function ReviewSummaryCard({
  c,
  investigation,
  evidence,
  evidenceLoading,
  evidenceError,
  evidenceTotal,
  onBrief,
  onEvidence,
}: {
  c: CaseDetail;
  investigation: InvestigationView;
  evidence: Evidence[];
  evidenceLoading: boolean;
  evidenceError: boolean;
  evidenceTotal?: number;
  onBrief: () => void;
  onEvidence: () => void;
}) {
  const { state, run } = investigation;
  const priorities = reviewPriorities(state.requirements);
  const completed = run.run_status === "COMPLETED";
  const failed = run.run_status === "FAILED";
  const loaded = evidence.filter((e) => e.run_id === run.run_id);
  const ready = !evidenceLoading && !evidenceError;
  const groups = [
    {
      title: "Sumber terkait sinyal",
      items: loaded.filter((e) => e.relevance_category === "SUPPORTING_RISK"),
      description:
        "Aturan, data episode, atau catatan terkait pemicu. Belum membuktikan pelanggaran.",
    },
    {
      title: "Sumber konteks medis",
      items: loaded.filter(
        (e) => e.relevance_category === "EXPLAINING_CONTEXT",
      ),
      description:
        "Konteks yang dapat menjelaskan pelayanan berulang. Baca isi dan sikap pernyataannya.",
    },
    {
      title: "Referensi kebijakan",
      items: loaded.filter((e) => e.source_type === "POLICY_SECTION"),
      description:
        "Ketentuan yang ditemukan untuk ditinjau bersama bukti kasus.",
    },
  ];
  const guidance = failed
    ? "Periksa kesalahan pada jejak pemeriksaan, pastikan layanan siap, lalu jalankan ulang."
    : !completed
      ? "Tunggu pemeriksaan sumber selesai. Detail bukti dapat dibuka untuk memantau hasil sementara."
      : priorities.some((r) => r.state === "CONFLICTING")
        ? "Bandingkan sumber yang bertentangan dan klarifikasi perbedaannya sebelum menyimpulkan."
        : priorities.some((r) => r.state === "UNAVAILABLE")
          ? "Identifikasi sumber yang belum tersedia dan tentukan dokumen tambahan yang diperlukan."
          : "Periksa hasil pencarian dan alasan medis yang belum terdokumentasi, lalu cocokkan dengan ketentuan episode.";
  return (
    <section className="exam-summary" aria-labelledby="exam-title">
      <header className="exam-header">
        <div>
          <span className="exam-eyebrow">HASIL PEMERIKSAAN</span>
          <h2 id="exam-title">
            {failed
              ? "Pemeriksaan belum berhasil"
              : completed
                ? "Temuan siap ditinjau"
                : "Pemeriksaan sedang berjalan"}
          </h2>
        </div>
        <div className="exam-status">
          <Badge value={run.run_status} />
          {state.outcome && <Badge value={state.outcome} />}
        </div>
      </header>
      <p className="exam-question">{reviewGuide[c.signal_type].question}</p>
      <div className="exam-source-grid">
        {groups.map((group) => (
          <article className="exam-source" key={group.title}>
            <h3>{group.title}</h3>
            <strong className="exam-count">
              {ready ? countEvidenceSources(group.items) : "—"}
              <span>sumber unik</span>
            </strong>
            <p>
              {evidenceLoading
                ? "Sedang memuat sumber pemeriksaan…"
                : evidenceError
                  ? "Sumber gagal dimuat. Buka detail bukti untuk mencoba lagi."
                  : group.items.length
                    ? group.description
                    : "Belum ada sumber pada kategori ini dalam daftar yang dimuat."}
            </p>
          </article>
        ))}
      </div>
      {ready &&
        evidenceTotal !== undefined &&
        loaded.length < evidenceTotal && (
          <p className="exam-note">
            Ringkasan berdasarkan {loaded.length} dari {evidenceTotal} entri
            bukti yang dimuat.
          </p>
        )}
      <div className="exam-review-grid">
        <div className="exam-attention">
          <div className="exam-section-title">
            <IconSearch size={20} aria-hidden="true" />
            <h3>Perlu ditinjau lebih lanjut</h3>
            <span>{priorities.length}</span>
          </div>
          <p className="exam-caption">
            {priorities.length > 3
              ? `Menampilkan 3 dari ${priorities.length} pemeriksaan penting, dengan konflik dan sumber yang tidak tersedia lebih dahulu.`
              : "Pemeriksaan penting yang belum berstatus terdokumentasi."}
          </p>
          {priorities.length ? (
            <ul className="exam-priorities">
              {priorities.slice(0, 3).map((r) => (
                <li key={r.key}>
                  <strong>{label(r.key)}</strong>
                  <Badge value={r.state} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="exam-note">
              Tidak ada pemeriksaan penting yang belum terdokumentasi pada state
              ini. Bukti tetap perlu dinilai reviewer.
            </p>
          )}
          <p className="exam-note">
            “Tidak ditemukan” adalah hasil pencarian, bukan bukti bahwa kondisi
            medis tidak ada.
          </p>
        </div>
        <aside className="exam-next">
          {failed ? (
            <IconAlertTriangle size={24} aria-hidden="true" />
          ) : (
            <IconShieldCheck size={24} aria-hidden="true" />
          )}
          <span className="exam-eyebrow">TINDAKAN BERIKUTNYA</span>
          <h3>
            {failed
              ? "Telusuri penyebab kegagalan"
              : completed
                ? "Tinjau bukti sebelum menyimpulkan"
                : "Pantau pemeriksaan sumber"}
          </h3>
          <p>{guidance}</p>
          <span className="exam-note">
            Pemeriksaan mesin selesai tidak berarti keputusan reviewer selesai.
          </span>
        </aside>
      </div>
      <footer className="exam-footer">
        <p>Jumlah sumber tidak menentukan benar atau salahnya klaim.</p>
        <div>
          <button className="button" onClick={onEvidence}>
            Periksa detail bukti <IconArrowRight size={18} />
          </button>
          {completed && (
            <button className="text-link" onClick={onBrief}>
              Ringkasan akhir <IconArrowRight size={16} />
            </button>
          )}
        </div>
      </footer>
    </section>
  );
}
