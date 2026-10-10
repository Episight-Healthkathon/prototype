"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import {
  IconArrowLeft,
  IconArrowRight,
  IconCircleCheck,
  IconDatabase,
  IconExternalLink,
  IconFileText,
  IconLayoutList,
  IconLoader2,
  IconRefresh,
  IconSearch,
  IconShieldCheck,
  IconX,
  IconAlertCircle,
  IconChevronRight,
} from "@tabler/icons-react";
import type { EvidenceDetail, Health } from "@episight/shared-types";
import { ApiFailure, createApi, type DataMode } from "@/lib/api";
import { date, label, tone } from "@/lib/labels";
import { sourceSegments } from "@/lib/source";

type ContextValue = {
  mode: DataMode;
  setMode: (mode: DataMode) => void;
  api: ReturnType<typeof createApi>;
  openEvidence: (id: string) => void;
  health: Health | null;
  healthError: Error | null;
  refreshHealth: () => void;
};
const Context = createContext<ContextValue | null>(null);
export const useApp = () => {
  const ctx = useContext(Context);
  if (!ctx) throw new Error("AppProvider is required");
  return ctx;
};
export function useResource<T>(loader: () => Promise<T>, key: string) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState<Error | null>(null),
    [loading, setLoading] = useState(true),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    setData(null);
    loader()
      .then((v) => {
        if (alive) setData(v);
      })
      .catch((e) => {
        if (alive) setError(e);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
    // Callers supply a key covering every argument to the loader.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, revision]);
  return {
    data,
    error,
    loading,
    reload: useCallback(() => setRevision((v) => v + 1), []),
  };
}
export function AppProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<DataMode>("live"),
    [ready, setReady] = useState(false),
    [evidenceId, setEvidenceId] = useState<string | null>(null);
  useEffect(() => {
    const param = new URLSearchParams(window.location.search).get("mode");
    const saved = localStorage.getItem("episight-mode");
    if (param === "demo" || param === "live")
      localStorage.setItem("episight-mode", param);
    setModeState(
      param === "demo" || param === "live"
        ? param
        : saved === "demo"
          ? "demo"
          : "live",
    );
    setReady(true);
  }, []);
  const setMode = (m: DataMode) => {
    localStorage.setItem("episight-mode", m);
    setModeState(m);
    setEvidenceId(null);
  };
  const api = useMemo(() => createApi(mode), [mode]);
  const health = useResource(() => api.health(), `health:${mode}:${ready}`);
  const value = {
    mode,
    setMode,
    api,
    openEvidence: setEvidenceId,
    health: health.data,
    healthError: health.error,
    refreshHealth: health.reload,
  };
  return (
    <Context.Provider value={value}>
      {ready ? (
        children
      ) : (
        <div className="boot">
          <Logo />
          <Loading label="Menyiapkan ruang review…" />
        </div>
      )}
      <EvidenceDrawer id={evidenceId} close={() => setEvidenceId(null)} />
    </Context.Provider>
  );
}
export function Logo({ small = false }: { small?: boolean }) {
  return (
    <Link
      href="/"
      aria-label="EPISIGHT beranda"
      className={`logo ${small ? "small" : ""}`}
    >
      <Image
        src="/brand/episight-logo.png"
        width={2169}
        height={725}
        alt="EPISIGHT"
        priority
      />
    </Link>
  );
}
export function Badge({
  value,
  children,
}: {
  value?: string | null;
  children?: React.ReactNode;
}) {
  return (
    <span className={`badge ${tone(value)}`}>
      <span className="status-dot" aria-hidden="true" />
      {children || label(value)}
    </span>
  );
}
export function Loading({
  label: message = "Memuat data…",
}: {
  label?: string;
}) {
  return (
    <div className="loading" role="status">
      <IconLoader2 className="spin" size={22} />
      <span>{message}</span>
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry: () => void;
}) {
  const failure = error instanceof ApiFailure ? error : null;
  return (
    <div className="error-state" role="alert">
      <IconAlertCircle size={30} />
      <h2>
        {failure?.status === 404
          ? "Data tidak ditemukan"
          : "Data belum dapat dimuat"}
      </h2>
      <p>{error.message}</p>
      {failure?.requestId && (
        <p className="mono muted">Request ID: {failure.requestId}</p>
      )}
      <button className="button secondary" onClick={retry}>
        <IconRefresh size={18} />
        Coba lagi
      </button>
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <IconSearch size={30} />
      <h3>{title}</h3>
      {children}
    </div>
  );
}
export function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="notice">
      <IconShieldCheck size={20} />
      <span>{children}</span>
    </div>
  );
}
export function EvidenceLinks({ ids }: { ids: string[] }) {
  const { openEvidence } = useApp();
  return (
    <span className="evidence-links">
      {ids.map((id, i) => (
        <button key={id} title={id} onClick={() => openEvidence(id)}>
          <IconFileText size={14} />
          Sumber {i + 1}
        </button>
      ))}
    </span>
  );
}
export function ModeControl() {
  const { mode, setMode, health, healthError, refreshHealth } = useApp();
  return (
    <div className="mode-control">
      <span
        className={`connection ${healthError ? "offline" : ""}`}
        title={healthError?.message}
      >
        <span />
        {mode === "demo"
          ? "Demo fixture"
          : healthError
            ? "API tidak tersedia"
            : health
              ? "API terhubung"
              : "Memeriksa API"}
      </span>
      <label>
        <span className="sr-only">Sumber data</span>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as DataMode)}
        >
          <option value="live">API lokal</option>
          <option value="demo">Demo offline</option>
        </select>
      </label>
      {healthError && (
        <button
          className="icon-button"
          aria-label="Periksa ulang API"
          onClick={refreshHealth}
        >
          <IconRefresh size={18} />
        </button>
      )}
    </div>
  );
}
export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname(),
    { mode, health, healthError } = useApp();
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Lewati ke konten
      </a>
      <aside className="sidebar">
        <Logo />
        <div className="sidebar-caption">Ruang reviewer</div>
        <nav aria-label="Navigasi utama">
          <Link
            className={path.startsWith("/cases") ? "active" : ""}
            href="/cases"
          >
            <IconLayoutList size={20} />
            Antrean kasus
            <IconChevronRight size={16} />
          </Link>
          <Link href="/guide" className={path === "/guide" ? "active" : ""}>
            <IconFileText size={20} />
            Panduan review
          </Link>
        </nav>
        <div className="sidebar-bottom">
          <IconDatabase size={22} />
          <strong>Lingkungan prototype</strong>
          <p>
            Data sintetis
            <br />
            {health?.dataset_version || "v0.1.0"} ·{" "}
            {health?.corpus_version || "pc-0.1.1"}
          </p>
          <span>Keputusan tetap pada manusia.</span>
        </div>
      </aside>
      <div className="app-body">
        <header className="app-header">
          <div className="header-product">
            Episode Integrity <span>/</span> Reviewer workspace
          </div>
          <ModeControl />
        </header>
        {healthError && mode === "live" && (
          <div className="api-banner" role="alert">
            API belum siap. Jalankan backend, lalu periksa ulang koneksi. Mode
            demo offline tersedia di pilihan sumber data.
          </div>
        )}
        <main id="main" className="app-main">
          {children}
        </main>
      </div>
    </div>
  );
}
function EvidenceDrawer({
  id,
  close,
}: {
  id: string | null;
  close: () => void;
}) {
  const { api, mode } = useApp();
  const source = useResource<EvidenceDetail>(
    () => (id ? api.source(id) : Promise.reject(new Error("Pilih bukti"))),
    `source:${mode}:${id}`,
  );
  const ev = source.data;
  const segments = sourceSegments(ev?.source.text || "", ev?.source.highlight);
  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={(open) => {
        if (!open) close();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-overlay" />
        <Dialog.Content className="evidence-drawer">
          <div className="drawer-heading">
            <div>
              <Dialog.Title>Telusuri sumber bukti</Dialog.Title>
              <Dialog.Description>
                Dokumen asli, kutipan, dan asal setiap temuan.
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="icon-button"
              aria-label="Tutup sumber bukti"
            >
              <IconX size={22} />
            </Dialog.Close>
          </div>
          {source.loading ? (
            <Loading />
          ) : source.error ? (
            <ErrorState error={source.error} retry={source.reload} />
          ) : (
            ev && (
              <>
                <div className="source-top">
                  <Badge value={ev.source_type} />
                  <Badge value={ev.stance} />
                  <h2>{ev.source_title}</h2>
                </div>
                <section className="source-section">
                  <h3>Kutipan yang digunakan</h3>
                  <blockquote>{ev.source_excerpt}</blockquote>
                  <p>
                    {label(ev.relevance_category)} · {label(ev.requirement_key)}
                  </p>
                </section>
                <section className="source-section">
                  <h3>Isi sumber</h3>
                  {ev.source.availability && (
                    <Badge value={ev.source.availability} />
                  )}{" "}
                  {ev.source.text ? (
                    <pre className="source-text">
                      {segments.before}
                      {segments.marked && <mark>{segments.marked}</mark>}
                      {segments.after}
                    </pre>
                  ) : (
                    <>
                      <p>
                        Teks lengkap tidak disediakan untuk sumber ini. Periksa
                        nilai atau kutipan yang dikembalikan API.
                      </p>
                      {ev.source.value !== undefined && (
                        <pre className="source-text">
                          {JSON.stringify(ev.source.value, null, 2)}
                        </pre>
                      )}
                    </>
                  )}
                  {ev.source.source_url && (
                    <a
                      className="text-link"
                      href={ev.source.source_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Buka dokumen kebijakan
                      <IconExternalLink size={16} />
                    </a>
                  )}
                </section>
                <details className="source-section source-provenance">
                  <summary>Detail sumber dan asal data</summary>
                  <dl className="metadata">
                    <dt>Evidence ID</dt>
                    <dd className="mono">{ev.evidence_id}</dd>
                    <dt>Episode</dt>
                    <dd>{ev.episode_id || "Lintas episode"}</dd>
                    <dt>Run</dt>
                    <dd className="mono">{ev.run_id}</dd>
                    <dt>Metode ekstraksi</dt>
                    <dd>{label(ev.extraction_method)}</dd>
                    <dt>Alat</dt>
                    <dd>{ev.retrieved_by_tool}</dd>
                    <dt>Langkah</dt>
                    <dd>{ev.investigation_step}</dd>
                    <dt>Diambil</dt>
                    <dd>{date(ev.retrieved_at, true)}</dd>
                    {ev.field_path && (
                      <>
                        <dt>Field</dt>
                        <dd className="mono">{ev.field_path}</dd>
                      </>
                    )}
                    {ev.policy_version && (
                      <>
                        <dt>Versi kebijakan</dt>
                        <dd>{ev.policy_version}</dd>
                      </>
                    )}
                    {ev.source.section && (
                      <>
                        <dt>Bagian</dt>
                        <dd>{ev.source.section}</dd>
                      </>
                    )}
                  </dl>
                  <h4>Alasan pencarian</h4>
                  <p>{ev.retrieval_reason}</p>
                </details>
              </>
            )
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export { IconArrowLeft, IconArrowRight, IconCircleCheck, IconFileText };
