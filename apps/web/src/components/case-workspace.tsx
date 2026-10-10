"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  IconArrowLeft,
  IconArrowRight,
  IconArrowUpRight,
  IconCalendar,
  IconCheck,
  IconChevronDown,
  IconFileText,
  IconHistory,
  IconPlayerPlay,
  IconPrinter,
  IconRefresh,
  IconSearch,
  IconShieldCheck,
  IconTimeline,
  IconAlertTriangle,
  IconBuildingHospital,
} from "@tabler/icons-react";
import type {
  BriefStatement,
  CaseDetail,
  EpisodeTimeline,
  Evidence,
  InvestigationBrief,
  InvestigationMode,
  InvestigationView,
  Requirement,
  RunSummary,
} from "@episight/shared-types";
import { ApiFailure } from "@/lib/api";
import {
  Badge,
  Empty,
  ErrorState,
  EvidenceLinks,
  Loading,
  Notice,
  useApp,
  useResource,
} from "./system";
import { date, humanNotice, label } from "@/lib/labels";
import { reviewGuide } from "@/lib/review-guide";
type View = "overview" | "workspace" | "brief";
function useInvestigation(id: string, runId: string, revision: number) {
  const { api, mode } = useApp();
  const [data, setData] = useState<InvestigationView | null>(null),
    [error, setError] = useState<Error | null>(null),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    setLoading(true);
    setError(null);
    setData(null);
    const poll = async () => {
      try {
        const value = await api.investigation(id, runId || undefined);
        if (!alive) return;
        setData(value);
        setError(null);
        setLoading(false);
        if (["RUNNING", "QUEUED"].includes(value.run.run_status))
          timer = setTimeout(poll, 1000);
      } catch (e) {
        if (!alive) return;
        setLoading(false);
        if (e instanceof ApiFailure && e.code === "RUN_NOT_FOUND") {
          setData(null);
          return;
        }
        setError(
          e instanceof Error ? e : new Error("Investigasi belum dapat dimuat"),
        );
      }
    };
    void poll();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [api, mode, id, runId, revision]);
  return { data, error, loading };
}
export function CaseWorkspace({
  id,
  initialView = "overview",
}: {
  id: string;
  initialView?: string;
}) {
  const { api, mode } = useApp();
  const [view, setView] = useState<View>(
      ["overview", "workspace", "brief"].includes(initialView)
        ? (initialView as View)
        : "overview",
    ),
    [revision, setRevision] = useState(0),
    [runId, setRunId] = useState(""),
    [starting, setStarting] = useState(false),
    [startError, setStartError] = useState<Error | null>(null),
    [investigationMode, setInvestigationMode] =
      useState<InvestigationMode>("FULL_RULE_PLANNER");
  const inv = useInvestigation(id, runId, revision),
    running =
      !!inv.data && ["QUEUED", "RUNNING"].includes(inv.data.run.run_status),
    completed = inv.data?.run.run_status === "COMPLETED";
  const key = `${mode}:${id}:${revision}:${inv.data?.run.run_status || "initial"}`;
  const detail = useResource(() => api.detail(id), `detail:${key}`),
    timeline = useResource(() => api.timeline(id), `timeline:${key}`);
  const ev = useResource(
    () => api.evidence(id, runId || undefined),
    `evidence:${key}:${runId}:${inv.data?.run.step || 0}`,
  );
  const brief = useResource<InvestigationBrief | null>(
    () =>
      completed ? api.brief(id, runId || undefined) : Promise.resolve(null),
    `brief:${key}:${runId}`,
  );
  const runs = useResource(() => api.runs(id), `runs:${key}`);
  const navigate = (v: View) => {
    setView(v);
    window.history.replaceState(null, "", `?view=${v}`);
  };
  useEffect(() => {
    const pop = () => {
      const v = new URLSearchParams(window.location.search).get("view");
      setView(v === "workspace" || v === "brief" ? v : "overview");
    };
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);
  const refresh = () => setRevision((v) => v + 1);
  const start = async (rerun = false) => {
    setStarting(true);
    setStartError(null);
    try {
      await api.start(
        id,
        mode === "demo" ? "FULL_RULE_PLANNER" : investigationMode,
        rerun,
      );
      setRunId("");
      navigate("workspace");
      refresh();
    } catch (e) {
      if (e instanceof ApiFailure && e.code === "INVESTIGATION_IN_PROGRESS") {
        navigate("workspace");
        refresh();
      } else if (
        e instanceof ApiFailure &&
        e.code === "INVESTIGATION_ALREADY_COMPLETED"
      ) {
        navigate("brief");
        refresh();
      } else
        setStartError(
          e instanceof Error ? e : new Error("Investigasi gagal dimulai"),
        );
    } finally {
      setStarting(false);
    }
  };
  if (detail.loading && !detail.data)
    return <Loading label="Memuat konteks kasus…" />;
  if (detail.error)
    return (
      <>
        <Link href="/cases" className="text-link">
          <IconArrowLeft size={17} />
          Antrean kasus
        </Link>
        <ErrorState error={detail.error} retry={detail.reload} />
      </>
    );
  const c = detail.data;
  if (!c) return null;
  // A selected run may have a null outcome; never inherit a newer run's result.
  const runState = view !== "overview" ? inv.data?.state : null;
  const activeOutcome = runState ? runState.outcome : c.outcome;
  const activeProgress = runState
    ? runState.progress_status
    : c.progress_status;
  return (
    <>
      <Link href="/cases" className="back-link">
        <IconArrowLeft size={17} />
        Antrean kasus
      </Link>
      <div className="page-heading case-heading">
        <div>
          <div className="case-topline">
            <Badge value={c.signal_type} />
            <span className="mono">{id}</span>
          </div>
          <h1>
            {c.patient_id}
            <span className="case-title-divider">/</span>
            {c.provider.name}
          </h1>
          <p>
            <IconCalendar size={16} />
            Tanggal indeks {date(c.index_date)} · {c.episode_count} episode
            pemicu · interval minimum {c.min_interval_days} hari
          </p>
        </div>
        <div className="case-status">
          <Badge
            value={
              running && view !== "overview" ? "INVESTIGATING" : activeProgress
            }
          />
          {activeOutcome && <Badge value={activeOutcome} />}
        </div>
      </div>
      <Notice>{humanNotice}</Notice>
      <nav className="case-tabs" aria-label="Tahap review kasus">
        {(
          [
            { id: "overview", title: "Konteks & timeline", icon: IconTimeline },
            { id: "workspace", title: "Investigasi", icon: IconSearch },
            { id: "brief", title: "Reviewer brief", icon: IconFileText },
          ] as const
        ).map((t) => (
          <button
            key={t.id}
            aria-current={view === t.id ? "page" : undefined}
            className={view === t.id ? "active" : ""}
            onClick={() => navigate(t.id)}
          >
            <t.icon size={19} />
            {t.title}
            {t.id === "workspace" && running && (
              <span className="running-dot" />
            )}
          </button>
        ))}
      </nav>
      {runId && view !== "overview" && (
        <Notice>
          Run yang dipilih: <span className="mono">{runId}</span>. Bukti dan
          brief mengikuti run ini.
        </Notice>
      )}
      {startError && (
        <div className="inline-error" role="alert">
          <p>{startError.message}</p>
          {startError instanceof ApiFailure && startError.requestId && (
            <small>Request ID: {startError.requestId}</small>
          )}
          <button className="text-link" onClick={() => setStartError(null)}>
            Tutup
          </button>
        </div>
      )}
      {view === "overview" ? (
        <>
          <Overview c={c} />
          <ModusContext c={c} />
          {timeline.loading ? (
            <Loading />
          ) : timeline.error ? (
            <ErrorState error={timeline.error} retry={timeline.reload} />
          ) : (
            timeline.data && <Timeline timeline={timeline.data} />
          )}
          <div className="section-action">
            <p>
              {completed
                ? "Investigasi selesai. Bukti dan brief tersedia untuk ditinjau."
                : "Lanjutkan dari konteks episode ke pemeriksaan bukti."}
            </p>
            <button
              className="button"
              onClick={() => navigate(completed ? "brief" : "workspace")}
            >
              {completed ? "Buka reviewer brief" : "Buka investigasi"}
              <IconArrowRight size={18} />
            </button>
          </div>
        </>
      ) : view === "workspace" ? (
        <>
          <div className="run-toolbar">
            <div>
              <h2>Workspace investigasi</h2>
              <p>
                {mode === "demo"
                  ? "Pemutaran hasil engine aturan + retrieval; tidak menjalankan AI atau API baru."
                  : "Pemeriksaan berjalan di backend. State diperbarui melalui polling."}
              </p>
            </div>
            <div className="run-controls">
              {mode === "live" && !running && (
                <label>
                  Mode
                  <select
                    value={investigationMode}
                    onChange={(e) =>
                      setInvestigationMode(e.target.value as InvestigationMode)
                    }
                  >
                    <option value="FULL_RULE_PLANNER">
                      Aturan + retrieval
                    </option>
                    <option value="FULL">Planner AI + fallback</option>
                    <option value="RULES_RETRIEVAL">Aturan + kebijakan</option>
                    <option value="RULES_ONLY">Aturan saja</option>
                  </select>
                </label>
              )}
              {!running && (
                <button
                  disabled={starting || !!runId}
                  className={`button ${completed ? "secondary" : ""}`}
                  onClick={() =>
                    start(
                      !!inv.data ||
                        c.progress_status === "INVESTIGATION_FAILED",
                    )
                  }
                >
                  {starting ? (
                    <IconRefresh size={18} className="spin" />
                  ) : completed ? (
                    <IconRefresh size={18} />
                  ) : (
                    <IconPlayerPlay size={18} />
                  )}{" "}
                  {starting
                    ? "Memulai…"
                    : completed
                      ? mode === "demo"
                        ? "Putar ulang demo"
                        : "Investigasi ulang"
                      : "Mulai investigasi"}
                </button>
              )}
              {running && <Badge value={inv.data?.run.run_status} />}
            </div>
          </div>
          {runs.data && runs.data.items.length > 0 && (
            <div className="run-history">
              <IconHistory size={17} />
              <label>
                Riwayat run
                <select
                  value={runId}
                  onChange={(e) => setRunId(e.target.value)}
                >
                  <option value="">Run terbaru</option>
                  {runs.data.items.map((r) => (
                    <option value={r.run_id} key={r.run_id}>
                      {date(r.started_at, true)} · {label(r.mode)} ·{" "}
                      {label(r.run_status)}
                    </option>
                  ))}
                </select>
              </label>
              {runId && (
                <span>
                  Menampilkan run yang dipilih. Pilih run terbaru untuk memulai
                  ulang.
                </span>
              )}
            </div>
          )}
          {inv.loading ? (
            <Loading label="Memuat state investigasi…" />
          ) : inv.error ? (
            <ErrorState error={inv.error} retry={refresh} />
          ) : inv.data ? (
            <>
              <RunProgress run={inv.data.run} />
              <Workspace
                investigation={inv.data}
                evidence={ev.data?.items || []}
              />
              {ev.error && <ErrorState error={ev.error} retry={ev.reload} />}
              <ActionTrail investigation={inv.data} />
              {completed && (
                <div className="section-action">
                  <span>
                    Investigasi berhenti: {label(inv.data.state.stop_reason)}.
                  </span>
                  <button className="button" onClick={() => navigate("brief")}>
                    Buka brief
                    <IconArrowRight size={18} />
                  </button>
                </div>
              )}
              {inv.data.run.run_status === "FAILED" && (
                <div className="inline-error" role="alert">
                  Run gagal atau terinterupsi. Hasil ini belum dapat dinilai.
                  Periksa jejak aksi dan jalankan ulang setelah layanan siap.
                </div>
              )}
            </>
          ) : (
            <Empty title="Investigasi belum dimulai">
              <p>
                Konteks episode sudah tersedia. Mulai pemeriksaan untuk menyusun
                evidence gap, jejak aksi, dan brief.
              </p>
            </Empty>
          )}
        </>
      ) : brief.loading ? (
        <Loading label="Memuat reviewer brief…" />
      ) : brief.error ? (
        <ErrorState error={brief.error} retry={brief.reload} />
      ) : brief.data ? (
        <Brief brief={brief.data} evidence={ev.data?.items || []} />
      ) : (
        <Empty
          title={running ? "Brief sedang disusun" : "Brief belum tersedia"}
        >
          <p>
            {running
              ? "Tunggu investigasi selesai. Anda dapat memantau langkah pemeriksaan di workspace."
              : "Mulai investigasi untuk mendapatkan ringkasan bukti dan ketidakpastian."}
          </p>
          <button className="button" onClick={() => navigate("workspace")}>
            Buka investigasi
            <IconArrowRight size={18} />
          </button>
        </Empty>
      )}
    </>
  );
}
function Overview({ c }: { c: CaseDetail }) {
  return (
    <section className="signal-overview">
      <div>
        <IconGitBranchLocal />
        <h2>Mengapa kasus ini ditandai?</h2>
        <p>{c.signal.description}</p>
        <div className="signal-criteria">
          <span>
            <IconCheck size={16} />
            Pasien yang sama
          </span>
          <span>
            <IconCheck size={16} />
            Fasilitas yang sama
          </span>
          <span>
            <IconCheck size={16} />
            Diagnosis utama sama persis
          </span>
          <span>
            <IconCheck size={16} />
            Interval ≤ {c.signal.params.threshold_days} hari
          </span>
        </div>
        <p className="signal-disclaimer">
          Sinyal risiko memulai investigasi, bukan menetapkan pelanggaran.
        </p>
      </div>
      <dl className="signal-summary">
        <div>
          <dt>Aturan</dt>
          <dd className="mono">{c.signal.rule_id}</dd>
        </div>
        <div>
          <dt>Versi aturan</dt>
          <dd>{c.signal.rule_version}</dd>
        </div>
        <div>
          <dt>Pasangan pemicu</dt>
          <dd>{c.signal.pairs.length} pasangan</dd>
        </div>
      </dl>
      {c.data_quality_issues.length > 0 && (
        <div className="inline-error">
          Kualitas data: {c.data_quality_issues.join("; ")}
        </div>
      )}
    </section>
  );
}
function IconGitBranchLocal() {
  return <IconTimeline size={25} className="section-icon" />;
}
function ModusContext({ c }: { c: CaseDetail }) {
  const guide = reviewGuide[c.signal_type];
  return (
    <section className="review-guide panel" aria-labelledby="modus-heading">
      <div className="panel-heading">
        <h2 id="modus-heading">Kaitan dengan modus yang ditinjau</h2>
        <span>Konteks panduan lomba</span>
      </div>
      <h3>{guide.title}</h3>
      <p>{guide.definition}</p>
      <p className="small-muted">Participant Guide Healthkathon 2026 · halaman 6 · kategori Fasilitas Kesehatan. Definisi ini tidak menggantikan kebijakan klaim yang berlaku.</p>
      <div className="review-question">
        <strong>Pertanyaan untuk reviewer</strong>
        <p>{guide.question}</p>
      </div>
      <h3>Pasangan episode pemicu</h3>
      {c.signal.pairs.length ? (
        <ul className="signal-pairs">
          {c.signal.pairs.map((pair) => (
            <li key={`${pair.from_episode_id}:${pair.to_episode_id}`}>
              <span className="mono">{pair.from_episode_id}</span>
              <IconArrowRight size={16} aria-hidden="true" />
              <span className="mono">{pair.to_episode_id}</span>
              <span>{pair.interval_days} hari</span>
            </li>
          ))}
        </ul>
      ) : <p>Pasangan pemicu belum tersedia.</p>}
      <p className="small-muted">Kesamaan diagnosis dan interval adalah pemicu screening. Tetap periksa keterkaitan episode, alasan medis, dan ketentuan paket sebelum menilai potensi pelanggaran.</p>
    </section>
  );
}
function Timeline({ timeline }: { timeline: EpisodeTimeline }) {
  const [expanded, setExpanded] = useState<string[]>([]);
  const toggle = (id: string) =>
    setExpanded((v) =>
      v.includes(id) ? v.filter((x) => x !== id) : [...v, id],
    );
  return (
    <section className="timeline-section">
      <div className="section-heading">
        <div>
          <h2>Timeline episode</h2>
          <p>
            Urutan kronologis, dengan peran episode dalam rekonstruksi kasus.
          </p>
        </div>
        <div className="timeline-legend">
          <Badge value="ANCHOR" />
          <Badge value="RELATED" />
          <Badge value="CONTEXT" />
        </div>
      </div>
      <ol className="episode-rail">
        {timeline.episodes.map((e, i) => (
          <li
            key={e.episode_id}
            className={e.role === "ANCHOR" ? "anchor-episode" : ""}
          >
            {i > 0 && e.interval_from_previous_days !== null && (
              <div className="episode-interval">
                {e.interval_from_previous_days} hari dari episode sebelumnya
              </div>
            )}
            <div className="episode-marker" />
            <div className="episode-card">
              <button
                className="episode-toggle"
                aria-expanded={expanded.includes(e.episode_id)}
                onClick={() => toggle(e.episode_id)}
              >
                <div>
                  <Badge value={e.role} />
                  <span className="mono">{e.episode_id}</span>
                  <h3>
                    {label(e.encounter_type)}
                    <span>
                      {date(e.start_at)}
                      {e.end_at &&
                      e.start_at?.slice(0, 10) !== e.end_at.slice(0, 10)
                        ? ` — ${date(e.end_at)}`
                        : ""}
                    </span>
                  </h3>
                  <p>
                    {e.provider.name} · diagnosis utama{" "}
                    <b>{e.primary_diagnosis.code}</b>
                    {e.primary_diagnosis.label &&
                      ` · ${e.primary_diagnosis.label}`}
                  </p>
                </div>
                <IconChevronDown
                  size={20}
                  className={expanded.includes(e.episode_id) ? "rotated" : ""}
                />
              </button>
              <div className="episode-facts">
                <span>
                  <IconBuildingHospital size={16} />
                  {label(e.admission_type || e.encounter_type)}
                </span>
                {e.length_of_stay_days !== null && (
                  <span>Lama rawat: {e.length_of_stay_days} hari</span>
                )}
                <span>{e.documents.length} dokumen</span>
                <span>{e.procedures.length} tindakan</span>
              </div>
              {expanded.includes(e.episode_id) && (
                <div className="episode-expanded">
                  <dl className="metadata">
                    <dt>Mulai</dt>
                    <dd>{date(e.start_at, true)}</dd>
                    <dt>Selesai</dt>
                    <dd>{date(e.end_at, true)}</dd>
                    <dt>Diagnosis sekunder</dt>
                    <dd>
                      {e.secondary_diagnoses.length
                        ? e.secondary_diagnoses
                            .map(
                              (d) =>
                                `${d.code}${d.label ? ` · ${d.label}` : ""}`,
                            )
                            .join(", ")
                        : "Tidak tercatat"}
                    </dd>
                    <dt>Prosedur ICD-9-CM</dt>
                    <dd>
                      {e.procedures.length
                        ? e.procedures
                            .map(
                              (p) =>
                                `${p.code}${p.label ? ` · ${p.label}` : ""}${p.performed_at ? ` (${date(p.performed_at)})` : ""}`,
                            )
                            .join(", ")
                        : "Tidak tercatat"}
                    </dd>
                    <dt>Referensi klaim</dt>
                    <dd>
                      {e.claim
                        ? `${e.claim.claim_id} · ${e.claim.inacbg_code || "Kode INA-CBG tidak tercatat"} · ${e.claim.claim_status || "Status tidak tercatat"}`
                        : "Tidak tersedia"}
                    </dd>
                    <dt>Kaitan episode</dt>
                    <dd>
                      {e.relation_reasons.map(label).join(" · ") ||
                        "Riwayat konteks"}
                    </dd>
                  </dl>
                  <h4>Dokumen klinis</h4>
                  {e.documents.length ? (
                    <ul className="document-list">
                      {e.documents.map((d) => (
                        <li key={d.note_id}>
                          <IconFileText size={17} />
                          <span>
                            {d.title || label(d.note_type)}
                            <small className="mono">{d.note_id}</small>
                          </span>
                          <Badge value={d.availability} />
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>Tidak ada dokumen klinis tercatat.</p>
                  )}
                  {e.evidence_ids.length > 0 && (
                    <EvidenceLinks ids={e.evidence_ids} />
                  )}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
function RunProgress({ run }: { run: RunSummary }) {
  return (
    <div className="run-progress">
      <div>
        <span className="mono">{run.run_id}</span>
        <Badge value={run.run_status} />
        <span>{label(run.mode)}</span>
      </div>
      <div>
        <strong>
          Langkah {run.step} / {run.max_steps}
        </strong>
        <span>Budget pemeriksaan, bukan persentase penyelesaian</span>
      </div>
    </div>
  );
}
function Workspace({
  investigation,
  evidence,
}: {
  investigation: InvestigationView;
  evidence: Evidence[];
}) {
  const st = investigation.state;
  return (
    <div className="workspace-grid">
      <div>
        <section className="panel">
          <div className="panel-heading">
            <h2>Pertanyaan & evidence gap</h2>
            <span>{st.requirements.length} pemeriksaan</span>
          </div>
          <div className="requirements">
            {st.requirements.map((r) => (
              <RequirementRow key={r.key} requirement={r} />
            ))}
          </div>
        </section>
        {st.next_action && (
          <section className="next-action">
            <IconArrowRight size={22} />
            <div>
              <h3>Pemeriksaan berikutnya</h3>
              <strong>{st.next_action.tool_label}</strong>
              <p>{st.next_action.reason}</p>
            </div>
          </section>
        )}
      </div>
      <div>
        <section className="panel">
          <div className="panel-heading">
            <h2>Bukti yang ditemukan</h2>
            <span>{evidence.length} sumber</span>
          </div>
          <EvidenceLedger evidence={evidence} />
        </section>
        {st.known_facts.length > 0 && (
          <section className="panel known-facts">
            <h3>Fakta yang diketahui</h3>
            {st.known_facts.map((f) => (
              <div key={f.fact_id}>
                <p>{f.text}</p>
                <EvidenceLinks ids={f.evidence_ids} />
              </div>
            ))}
          </section>
        )}
      </div>
    </div>
  );
}
function RequirementRow({ requirement: r }: { requirement: Requirement }) {
  return (
    <details className="requirement">
      <summary>
        <span className="requirement-main">
          <span className="requirement-direction">
            {r.direction === "CONTEXT"
              ? "Konteks penjelas"
              : label(r.direction)}
            {r.material ? " · material" : " · tambahan"}
          </span>
          <strong>{r.label}</strong>
        </span>
        <Badge value={r.state} />
        <IconChevronDown size={17} />
      </summary>
      <div className="requirement-body">
        <p>{r.state_explanation}</p>
        <div className="coverage">
          <span>
            {r.coverage.searched_sources} / {r.coverage.in_scope_sources} sumber
            diperiksa
          </span>
          <span>{r.coverage.unavailable_sources} tidak tersedia</span>
        </div>
        {r.state === "NOT_FOUND" && (
          <p className="small-muted">
            Pencarian sumber tersedia selesai; ini tidak membuktikan bahwa
            kondisi klinis tidak ada.
          </p>
        )}
        {r.state === "UNAVAILABLE" && (
          <p className="small-muted">
            Tidak dapat dinilai dari sumber yang tersedia; bukan temuan negatif.
          </p>
        )}
        {r.evidence_ids.length > 0 && <EvidenceLinks ids={r.evidence_ids} />}
        <p className="small-muted">
          Alat: {r.attempted_tools.join(", ") || "Belum diperiksa"}
        </p>
        {r.spawned_by && (
          <p className="small-muted">
            Pertanyaan lanjutan dari {label(r.spawned_by)}
          </p>
        )}
      </div>
    </details>
  );
}
function EvidenceLedger({ evidence }: { evidence: Evidence[] }) {
  const { openEvidence } = useApp();
  const [category, setCategory] = useState("ALL");
  const categories = useMemo(
    () => Array.from(new Set(evidence.map((e) => e.relevance_category))),
    [evidence],
  );
  const filtered = evidence.filter(
    (e) => category === "ALL" || e.relevance_category === category,
  );
  return (
    <>
      <div className="ledger-filter">
        <label>
          Kategori
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="ALL">Semua bukti</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {label(c)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {filtered.length ? (
        <div className="evidence-ledger">
          {filtered.map((e) => (
            <button
              className="evidence-item"
              key={e.evidence_id}
              onClick={() => openEvidence(e.evidence_id)}
            >
              <div>
                <span className="evidence-category">
                  {label(e.relevance_category)}
                </span>
                <IconArrowUpRight size={17} />
              </div>
              <strong>{e.source_title}</strong>
              <p>{e.source_excerpt}</p>
              <div>
                <span>
                  {label(e.source_type)} · langkah {e.investigation_step}
                </span>
                <Badge value={e.stance} />
              </div>
            </button>
          ))}
        </div>
      ) : (
        <Empty title="Belum ada bukti pada kategori ini">
          <p>Bukti akan muncul setelah pemeriksaan sumber.</p>
        </Empty>
      )}
    </>
  );
}
function ActionTrail({ investigation }: { investigation: InvestigationView }) {
  return (
    <section className="trail-section">
      <div className="section-heading">
        <div>
          <h2>Jejak investigasi</h2>
          <p>Aksi, perubahan state, dan bukti di setiap langkah.</p>
        </div>
        <span>{investigation.trail.length} aksi</span>
      </div>
      {investigation.trail.length ? (
        <ol className="action-trail">
          {investigation.trail.map((a) => (
            <li key={a.step}>
              <span className="step-number">{a.step}</span>
              <details>
                <summary>
                  <div>
                    <strong>{a.tool_label}</strong>
                    <span>{a.reason}</span>
                  </div>
                  <Badge value={a.tool_status} />
                  <IconChevronDown size={18} />
                </summary>
                <div className="trail-body">
                  <p className="mono small-muted">
                    {a.tool_name} · {a.duration_ms} ms ·{" "}
                    {date(a.started_at, true)}
                  </p>
                  {a.evidence_ids.length > 0 && (
                    <EvidenceLinks ids={a.evidence_ids} />
                  )}
                  <div className="state-updates">
                    {a.requirement_updates.map((u, i) => (
                      <div key={`${u.key}-${i}`}>
                        <span>{label(u.key)}</span>
                        <Badge value={u.from} />
                        <IconArrowRight size={14} />
                        <Badge value={u.to} />
                      </div>
                    ))}
                  </div>
                  <div className="planner-note">
                    <strong>{label(a.planner.source)}</strong>
                    {a.planner.note && <p>Catatan planner: {a.planner.note}</p>}
                    <small>
                      Catatan planner menjelaskan usulan aksi; bukan bukti.
                    </small>
                    {a.planner.validation_errors.length > 0 && (
                      <p>
                        Validasi usulan:{" "}
                        {a.planner.validation_errors.join("; ")}
                      </p>
                    )}
                    {a.planner.skipped_requirements.map((s) => (
                      <p key={s.key}>
                        Tidak diperiksa: {label(s.key)} — {s.reason}
                      </p>
                    ))}
                  </div>
                  {a.error && (
                    <div className="inline-error">
                      {a.error.code}: {a.error.message}
                    </div>
                  )}
                  <details className="input-details">
                    <summary>Scope pemeriksaan</summary>
                    <pre>{JSON.stringify(a.input_summary, null, 2)}</pre>
                  </details>
                </div>
              </details>
            </li>
          ))}
        </ol>
      ) : (
        <Empty title="Belum ada aksi tercatat" />
      )}
    </section>
  );
}
function Statements({
  items,
  empty,
}: {
  items: BriefStatement[];
  empty: string;
}) {
  return items.length ? (
    <div className="brief-statements">
      {items.map((s) => (
        <div key={s.statement_id}>
          <p>{s.text}</p>
          <EvidenceLinks ids={s.evidence_ids} />
        </div>
      ))}
    </div>
  ) : (
    <p className="muted">{empty}</p>
  );
}
function Brief({
  brief: b,
  evidence,
}: {
  brief: InvestigationBrief;
  evidence: Evidence[];
}) {
  const { openEvidence } = useApp();
  return (
    <article className="reviewer-brief">
      <div className="brief-heading">
        <div>
          <h2>Reviewer brief</h2>
          <p>
            {date(b.generated_at, true)} · generator {b.generator_version}
          </p>
          <span className="mono small-muted">
            {b.brief_id} · {b.run_id}
          </span>
        </div>
        <button
          className="button secondary compact"
          onClick={() => window.print()}
        >
          <IconPrinter size={18} />
          Cetak brief
        </button>
      </div>
      <div className="brief-outcome">
        <IconShieldCheck size={28} />
        <div>
          <Badge value={b.outcome} />
          <p>Investigasi berhenti: {label(b.stop_reason)}</p>
          <strong>Menunggu peninjauan manusia</strong>
        </div>
        <span>
          {b.traceability.with_evidence} / {b.traceability.material_statements}
          <small>pernyataan material memiliki sumber</small>
        </span>
      </div>
      <div className="brief-grid">
        <div>
          <section className="brief-section">
            <h3>Ringkasan kasus</h3>
            <Statements
              items={b.case_summary}
              empty="Ringkasan belum tersedia."
            />
          </section>
          <section className="brief-section">
            <h3>Sinyal risiko</h3>
            <p>{b.risk_signal.description}</p>
            <p className="muted">
              Sinyal memulai investigasi dan tetap terlihat ketika konteks
              penjelas ditemukan.
            </p>
          </section>
          <section className="brief-section">
            <h3>Bukti sinyal risiko</h3>
            <Statements
              items={b.supporting_risk_evidence}
              empty="Belum ada bukti sinyal risiko pada brief ini."
            />
          </section>
          <section className="brief-section">
            <h3>Konteks penjelas</h3>
            <Statements
              items={b.explaining_context_evidence}
              empty="Konteks penjelas belum ditemukan dari sumber yang diperiksa."
            />
          </section>
          <section className="brief-section">
            <h3>Referensi kebijakan</h3>
            {b.policy_references.length ? (
              b.policy_references.map((p) => (
                <div className="policy-reference" key={p.evidence_id}>
                  <strong>{p.document_title}</strong>
                  <span>
                    {p.section} · versi {p.version}
                  </span>
                  <blockquote>{p.excerpt}</blockquote>
                  <EvidenceLinks ids={[p.evidence_id]} />
                </div>
              ))
            ) : (
              <p className="muted">
                Tidak ada referensi kebijakan pada brief ini.
              </p>
            )}
          </section>
        </div>
        <div>
          <section className="brief-section uncertainty-section">
            <h3>Ketidakpastian & evidence gap</h3>
            <Statements
              items={b.uncertainty}
              empty="Tidak ada ketidakpastian tambahan yang tercatat."
            />
            {b.remaining_gaps.map((g) => (
              <div className="remaining-gap" key={g.key}>
                <Badge value={g.state} />
                <strong>{g.question}</strong>
                <p>{g.explanation}</p>
              </div>
            ))}
          </section>
          {b.conflicts.length > 0 && (
            <section className="brief-section conflict-section">
              <h3>
                <IconAlertTriangle size={20} />
                Sumber yang bertentangan
              </h3>
              {b.conflicts.map((c) => (
                <div key={c.key}>
                  <h4>{label(c.key)}</h4>
                  <div className="conflict-pair">
                    {[
                      {
                        title: "Mendukung pernyataan",
                        ids: c.affirming_evidence_ids,
                      },
                      {
                        title: "Menyangkal pernyataan",
                        ids: c.negating_evidence_ids,
                      },
                    ].map((side) => (
                      <div key={side.title}>
                        <strong>{side.title}</strong>
                        {side.ids.map((id) => {
                          const e = evidence.find((e) => e.evidence_id === id);
                          return (
                            <button key={id} onClick={() => openEvidence(id)}>
                              <span>{e?.source_title || id}</span>
                              <p>
                                {e?.source_excerpt ||
                                  "Buka sumber untuk membaca kutipan."}
                              </p>
                              <span className="text-link">
                                Telusuri sumber
                                <IconArrowUpRight size={15} />
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </section>
          )}
          <section className="brief-section">
            <h3>Pemeriksaan berikutnya untuk reviewer</h3>
            <Statements
              items={b.suggested_next_review}
              empty="Gunakan bukti dan konteks kasus untuk menetapkan pemeriksaan berikutnya."
            />
          </section>
          <section className="brief-section">
            <h3>Episode dalam brief</h3>
            <ul className="brief-episodes">
              {b.episode_timeline.map((e) => (
                <li key={e.episode_id}>
                  <strong>{e.label}</strong>
                  <span>
                    {date(e.start_at)}
                    {e.end_at ? ` — ${date(e.end_at)}` : ""}
                  </span>
                  <span className="mono">{e.episode_id}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
      <div className="brief-notice">
        <IconShieldCheck size={23} />
        <div>
          <p>{humanNotice}</p>
          <p lang="en">{b.human_decision_notice}</p>
        </div>
      </div>
      <details className="brief-provenance">
        <summary>
          Seluruh sumber pada brief ({b.provenance.evidence_ids.length})
        </summary>
        <EvidenceLinks ids={b.provenance.evidence_ids} />
      </details>
    </article>
  );
}
