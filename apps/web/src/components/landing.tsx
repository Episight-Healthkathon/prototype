"use client";
import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  IconArrowDown,
  IconArrowLeft,
  IconArrowRight,
  IconArrowUpRight,
  IconChevronRight,
  IconFileText,
  IconGitBranch,
  IconSearch,
  IconShieldCheck,
  IconTimeline,
  IconCheck,
  IconAlertTriangle,
} from "@tabler/icons-react";
import { Badge, Logo, ModeControl } from "./system";
import { scenarios } from "@/lib/labels";
const slides = [
  "Satu rangkaian episode",
  "Dari sinyal ke review",
  "Bukti dan pertanyaan",
  "Brief yang dapat ditelusuri",
];
export function Landing() {
  const [slide, setSlide] = useState(0),
    [scenario, setScenario] = useState(0);
  const selected = scenarios[scenario];
  return (
    <div className="landing">
      <a href="#landing-main" className="skip-link">
        Lewati ke konten
      </a>
      <header className="landing-nav">
        <Logo />
        <nav aria-label="Navigasi landing">
          <a href="#workflow">Cara kerja</a>
          <a href="#scenarios">Contoh kasus</a>
          <Link href="/guide">Panduan</Link>
        </nav>
        <Link className="button compact" href="/cases">
          Buka workspace
          <IconArrowUpRight size={17} />
        </Link>
      </header>
      <main id="landing-main">
        <section className="hero">
          <div className="hero-copy">
            <h1>
              Setiap episode
              <br />
              punya <span>cerita.</span>
              <br />
              Telusuri buktinya.
            </h1>
            <p>
              Sinyal risiko memulai pertanyaan. EPISIGHT menghubungkan episode
              pelayanan, konteks klinis, dan referensi kebijakan menjadi brief
              yang bisa ditinjau manusia.
            </p>
            <div className="hero-actions">
              <Link href="/cases" className="button">
                Mulai review kasus
                <IconArrowRight size={19} />
              </Link>
              <a href="#workflow" className="text-link">
                Lihat cara kerja
                <IconArrowDown size={17} />
              </a>
            </div>
            <div className="hero-proof">
              <IconShieldCheck size={19} />
              <span>Evidence first. Human decision.</span>
            </div>
          </div>
          <div className="hero-preview">
            <div className="preview-bar">
              <span className="mini-brand">Ruang investigasi</span>
              <span className="preview-live">Data sintetis</span>
            </div>
            <div className="preview-case">
              <Badge value="READMISSION" />
              <span className="mono">CASE-RA-0bbfc334</span>
              <h2>
                Dua episode.
                <br />
                Konteks yang saling terhubung.
              </h2>
              <span className="muted">
                PAT-000001 · RS Sintetis Nusantara 01
              </span>
            </div>
            <div className="preview-episodes">
              <div>
                <span className="timeline-dot" />
                <strong>2–6 Mar 2026</strong>
                <span>Rawat inap pertama</span>
                <code>I50.0</code>
              </div>
              <div className="interval-bridge">
                <span>6 hari</span>
                <i />
              </div>
              <div>
                <span className="timeline-dot teal-dot" />
                <strong>12–17 Mar 2026</strong>
                <span>Rawat inap ulang</span>
                <code>I50.0</code>
              </div>
            </div>
            <div className="preview-evidence">
              <div>
                <IconCheck size={20} />
                <span>
                  Konteks darurat<strong>Terdokumentasi</strong>
                </span>
                <IconFileText size={19} />
              </div>
              <div>
                <IconCheck size={20} />
                <span>
                  Kondisi kronis<strong>Terdokumentasi</strong>
                </span>
                <IconFileText size={19} />
              </div>
              <div>
                <IconGitBranch size={20} />
                <span>
                  Sinyal readmission<strong>Tetap terlihat dalam review</strong>
                </span>
                <IconChevronRight size={19} />
              </div>
            </div>
            <Link className="preview-footer" href="/cases/CASE-RA-0bbfc334">
              Telusuri kasus ini
              <IconArrowRight size={18} />
            </Link>
          </div>
        </section>
        <div className="landing-note">
          <span>PROTOTYPE HEALTHKATHON 2026</span>
          <p>
            Investigasi readmission dan fragmentasi episode · Dataset sintetis
            v0.1.0
          </p>
        </div>
        <section id="workflow" className="workflow-section">
          <div className="section-intro">
            <h2>
              Sinyal risiko adalah
              <br />
              awal penelusuran.
            </h2>
            <p>
              Dari pola yang terdeteksi menuju konteks episode, bukti yang dapat
              ditelusuri, dan brief untuk ditinjau manusia.
            </p>
          </div>
          <div
            className="workflow-tabs"
            role="tablist"
            aria-label="Slide cara kerja"
          >
            {slides.map((name, i) => (
              <button
                id={`slide-tab-${i}`}
                role="tab"
                aria-selected={slide === i}
                aria-controls={`slide-panel-${i}`}
                tabIndex={slide === i ? 0 : -1}
                key={name}
                onClick={() => setSlide(i)}
                onKeyDown={(e) => {
                  if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                    e.preventDefault();
                    const next = (i + (e.key === "ArrowRight" ? 1 : 3)) % 4;
                    setSlide(next);
                    document.getElementById(`slide-tab-${next}`)?.focus();
                  }
                }}
              >
                <span>{String(i + 1).padStart(2, "0")}</span>
                {name}
              </button>
            ))}
          </div>
          <div
            className="story-slide"
            role="tabpanel"
            id={`slide-panel-${slide}`}
            aria-labelledby={`slide-tab-${slide}`}
            key={slide}
          >
            {slide === 1 ? (
              <>
                <Image
                  className="reference-slide"
                  src="/brand/workflow-slide.png"
                  width={1672}
                  height={941}
                  alt="Ilustrasi Detect, Reconstruct, Investigate, Review: reviewer menelusuri kasus, timeline, evidence gap dan brief."
                />
                <p className="slide-caption">
                  Ilustrasi alur dari referensi desain. Tanggal dan kartu pada
                  gambar bersifat ilustratif; workspace menggunakan data
                  sintetis 2026 dari API.
                </p>
              </>
            ) : slide === 0 ? (
              <div className="native-slide">
                <div className="slide-copy">
                  <IconTimeline size={35} />
                  <h3>
                    Lihat pelayanan
                    <br />
                    sebagai satu cerita.
                  </h3>
                  <p>
                    Bedakan episode yang memicu sinyal, episode terkait, dan
                    riwayat konteks. Interval dihitung dari akhir episode menuju
                    awal episode berikutnya.
                  </p>
                  <Link className="text-link" href="/cases/CASE-RA-0bbfc334">
                    Buka timeline
                    <IconArrowRight size={17} />
                  </Link>
                </div>
                <div className="story-timeline">
                  <div>
                    <Badge value="RELATED" />
                    <strong>16 Februari 2026</strong>
                    <span>Rawat jalan · EPI-000001</span>
                    <p>Riwayat pelayanan sebelum rangkaian rawat inap.</p>
                  </div>
                  <div>
                    <Badge value="ANCHOR" />
                    <strong>2–6 Maret 2026</strong>
                    <span>Rawat inap · EPI-000002</span>
                  </div>
                  <div className="story-interval">
                    Interval discharge → admission: <b>6 hari</b>
                  </div>
                  <div>
                    <Badge value="ANCHOR" />
                    <strong>12–17 Maret 2026</strong>
                    <span>Rawat inap ulang · EPI-000003</span>
                  </div>
                </div>
              </div>
            ) : slide === 2 ? (
              <div className="native-slide">
                <div className="slide-copy">
                  <IconSearch size={35} />
                  <h3>
                    Pertanyaan yang jelas.
                    <br />
                    Bukti yang terpisah.
                  </h3>
                  <p>
                    Bukti pola risiko, konteks penjelas, dan sumber kebijakan
                    memiliki peran berbeda. Temuan tidak tersedia atau
                    bertentangan tetap terlihat.
                  </p>
                  <Link className="text-link" href="/cases/CASE-RA-608764ca">
                    Periksa dua sumber
                    <IconArrowRight size={17} />
                  </Link>
                </div>
                <div className="gap-preview">
                  <div>
                    <h4>Bukti sinyal risiko</h4>
                    <p>
                      Rawat inap berulang, diagnosis utama yang sama, fasilitas
                      yang sama.
                    </p>
                    <Badge value="FOUND" />
                  </div>
                  <div>
                    <h4>Konteks penjelas</h4>
                    <p>
                      Apakah konteks darurat terdokumentasi secara konsisten?
                    </p>
                    <Badge value="CONFLICTING" />
                  </div>
                  <div className="gap-warning">
                    <IconAlertTriangle size={23} />
                    <p>
                      Triase dan ringkasan pulang berbeda. Kedua sumber perlu
                      ditinjau.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="native-slide">
                <div className="slide-copy">
                  <IconFileText size={35} />
                  <h3>
                    Ringkas untuk review.
                    <br />
                    Lengkap untuk ditelusuri.
                  </h3>
                  <p>
                    Brief mempertahankan sinyal risiko, konteks penjelas,
                    referensi kebijakan, dan ketidakpastian. Klik sumber untuk
                    melihat kutipan dan provenance.
                  </p>
                  <Link className="text-link" href="/cases/CASE-RA-609280ef">
                    Lihat kasus sumber terbatas
                    <IconArrowRight size={17} />
                  </Link>
                </div>
                <div className="brief-preview">
                  <div className="brief-preview-head">
                    <IconFileText size={25} />
                    <h4>Reviewer brief</h4>
                    <Badge value="EVIDENCE_UNAVAILABLE" />
                  </div>
                  <h5>Ketidakpastian yang tersisa</h5>
                  <p>
                    Konteks episode ulang belum dapat dinilai karena sumber
                    klinis tidak tersedia atau dibatasi.
                  </p>
                  <div className="brief-preview-row">
                    Bukti sinyal risiko<span>Referensi sumber</span>
                  </div>
                  <div className="brief-preview-row">
                    Referensi kebijakan<span>Versi & bagian</span>
                  </div>
                  <div className="brief-preview-row">
                    Pemeriksaan berikutnya<span>Untuk reviewer</span>
                  </div>
                  <small>Menunggu peninjauan manusia</small>
                </div>
              </div>
            )}
          </div>
          <div className="slide-controls">
            <span>
              {slide + 1} / {slides.length}
            </span>
            <div>
              <button
                className="icon-button"
                onClick={() => setSlide((slide + 3) % 4)}
                aria-label="Slide sebelumnya"
              >
                <IconArrowLeft size={20} />
              </button>
              <button
                className="icon-button"
                onClick={() => setSlide((slide + 1) % 4)}
                aria-label="Slide berikutnya"
              >
                <IconArrowRight size={20} />
              </button>
            </div>
          </div>
        </section>
        <section id="scenarios" className="scenario-section">
          <div className="section-intro">
            <h2>
              Berbeda konteks.
              <br />
              Berbeda kebutuhan review.
            </h2>
            <p>
              Coba lima alur utama pada data sintetis. Hasil menunjukkan kondisi
              bukti, bukan keputusan atas klaim.
            </p>
          </div>
          <div className="scenario-layout">
            <div className="scenario-list" aria-label="Pilih contoh kasus">
              {scenarios.map((s, i) => (
                <button
                  key={s.id}
                  aria-pressed={scenario === i}
                  className={scenario === i ? "selected" : ""}
                  onClick={() => setScenario(i)}
                >
                  <span>{s.title}</span>
                  <IconChevronRight size={19} />
                </button>
              ))}
            </div>
            <div className="scenario-detail" key={selected.id}>
              <Badge value={selected.signal} />
              <h3>{selected.title}</h3>
              <p>{selected.detail}</p>
              <dl>
                <div>
                  <dt>Pasien</dt>
                  <dd>{selected.patient}</dd>
                </div>
                <div>
                  <dt>Interval minimum</dt>
                  <dd>{selected.interval} hari</dd>
                </div>
              </dl>
              <Link className="button secondary" href={`/cases/${selected.id}`}>
                Telusuri kasus
                <IconArrowRight size={18} />
              </Link>
              <small>Kasus sintetis · {selected.id}</small>
            </div>
          </div>
        </section>
        <section className="landing-close">
          <IconShieldCheck size={36} />
          <h2>
            Lebih banyak konteks.
            <br />
            Review yang lebih jelas.
          </h2>
          <p>
            EPISIGHT membantu menyusun investigasi.
            <br />
            Reviewer tetap memegang keputusan.
          </p>
          <Link className="button" href="/cases">
            Masuk ke workspace
            <IconArrowRight size={19} />
          </Link>
        </section>
      </main>
      <footer className="landing-footer">
        <Logo small />
        <span>Episode integrity investigation copilot</span>
        <ModeControl />
        <p>
          Prototype · Seluruh identitas pasien dan fasilitas bersifat sintetis.
        </p>
      </footer>
    </div>
  );
}
