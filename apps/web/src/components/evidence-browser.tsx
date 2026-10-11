"use client";
import { useState } from "react";
import { IconArrowUpRight, IconFileText } from "@tabler/icons-react";
import type { Evidence } from "@episight/shared-types";
import { Badge, Empty, useApp } from "./system";
import { label } from "@/lib/labels";
import {
  countEvidenceSources,
  evidenceGroup,
  type EvidenceFilter,
} from "@/lib/review-guide";
const filters: { key: EvidenceFilter; title: string }[] = [
  { key: "ALL", title: "Semua" },
  { key: "SIGNAL", title: "Terkait sinyal" },
  { key: "CONTEXT", title: "Konteks medis" },
  { key: "POLICY", title: "Kebijakan" },
  { key: "OTHER", title: "Informasi lain" },
];
export function EvidenceBrowser({ evidence }: { evidence: Evidence[] }) {
  const { openEvidence } = useApp();
  const [filter, setFilter] = useState<EvidenceFilter>("ALL");
  const visible = evidence.filter(
    (e) => filter === "ALL" || evidenceGroup(e) === filter,
  );
  return (
    <section className="evidence-browser" aria-labelledby="evidence-title">
      <header className="evidence-browser-heading">
        <div>
          <h2 id="evidence-title">Telusuri temuan dan sumbernya</h2>
          <p>
            {evidence.length} entri bukti dari {countEvidenceSources(evidence)}{" "}
            sumber unik. Kutipan asli dipertahankan.
          </p>
        </div>
        <IconFileText size={25} aria-hidden="true" />
      </header>
      <div
        className="evidence-filter-buttons"
        role="group"
        aria-label="Filter kategori bukti"
      >
        {filters.map((item) => {
          const count =
            item.key === "ALL"
              ? evidence.length
              : evidence.filter((e) => evidenceGroup(e) === item.key).length;
          return (
            <button
              key={item.key}
              aria-pressed={filter === item.key}
              onClick={() => setFilter(item.key)}
            >
              {item.title}
              <span>{count}</span>
            </button>
          );
        })}
      </div>
      <p className="evidence-browser-note">
        Sikap sumber berlaku terhadap pernyataan yang diperiksa, bukan penetapan
        fraud atau keabsahan klaim.
      </p>
      {visible.length ? (
        <div className="evidence-cards">
          {visible.map((e) => (
            <article className="review-evidence-card" key={e.evidence_id}>
              <div className="evidence-card-top">
                <span>
                  {filters.find((f) => f.key === evidenceGroup(e))?.title}
                </span>
                <Badge value={e.stance} />
              </div>
              <h3>{label(e.requirement_key)}</h3>
              <p className="evidence-card-source">{e.source_title}</p>
              <blockquote>{e.source_excerpt}</blockquote>
              <footer>
                <div>
                  <span>{label(e.source_type)}</span>
                  <span>{e.episode_id || "Lintas episode"}</span>
                </div>
                <button
                  className="text-link"
                  onClick={() => openEvidence(e.evidence_id)}
                  aria-label={`Buka sumber ${e.source_title}`}
                >
                  Buka sumber <IconArrowUpRight size={17} />
                </button>
              </footer>
            </article>
          ))}
        </div>
      ) : (
        <Empty title="Belum ada bukti pada kategori ini">
          <p>
            Periksa kategori lain atau status pemeriksaan di bawah. Tidak adanya
            entri bukan bukti bahwa kondisi medis tidak ada.
          </p>
        </Empty>
      )}
    </section>
  );
}
