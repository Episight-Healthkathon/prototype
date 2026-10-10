import type {
  CaseDetail,
  CaseList,
  CaseSummary,
  EpisodeTimeline,
  EvidenceDetail,
  EvidenceList,
  Health,
  InvestigateAccepted,
  InvestigationBrief,
  InvestigationMode,
  InvestigationView,
  RunList,
} from "@episight/shared-types";
export type DataMode = "live" | "demo";
export type Query = {
  q?: string;
  signal_type?: string;
  progress_status?: string;
  outcome?: string;
  sort?: string;
  limit?: number;
  offset?: number;
};
export class ApiFailure extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
  ) {
    super(message);
  }
}
async function json<T>(url: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...options?.headers },
      cache: "no-store",
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok)
      throw new ApiFailure(
        res.status,
        body.error?.code || "HTTP_ERROR",
        body.error?.message ||
          (res.status >= 500
            ? "Layanan API belum tersedia. Jalankan backend lalu coba lagi."
            : "Permintaan belum dapat diproses."),
        body.error?.request_id || res.headers.get("X-Request-ID") || undefined,
      );
    return body as T;
  } catch (error) {
    if (error instanceof ApiFailure) throw error;
    throw new ApiFailure(
      0,
      "NETWORK_ERROR",
      "Koneksi terputus atau melewati batas waktu. Periksa layanan API lalu coba lagi.",
    );
  } finally {
    clearTimeout(timeout);
  }
}
const fixture = <T>(file: string) => json<T>(`/demo/${file}`);
const key = "episight-demo-runs-v1";
function playback(): Record<string, number> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(sessionStorage.getItem(key) || "{}");
  } catch {
    return {};
  }
}
const active = (id: string) => playback()[id];
const done = (id: string) => !!active(id) && Date.now() - active(id) > 2200;
const base = (id: string) => `cases/${encodeURIComponent(id)}`;
export function filterCases(items: CaseSummary[], query: Query) {
  const q = (query.q || "").toLowerCase();
  const filtered = items.filter(
    (c) =>
      (!q || `${c.case_id} ${c.patient_id}`.toLowerCase().includes(q)) &&
      (!query.signal_type || c.signal_type === query.signal_type) &&
      (!query.progress_status || c.progress_status === query.progress_status) &&
      (!query.outcome || c.outcome === query.outcome),
  );
  return filtered.sort((a, b) =>
    query.sort === "min_interval_days"
      ? a.min_interval_days - b.min_interval_days ||
        a.case_id.localeCompare(b.case_id)
      : query.sort === "case_id"
        ? a.case_id.localeCompare(b.case_id)
        : (query.sort === "index_date" ? 1 : -1) *
            a.index_date.localeCompare(b.index_date) ||
          a.case_id.localeCompare(b.case_id),
  );
}
export function createApi(mode: DataMode) {
  const live = mode === "live";
  const request = <T>(path: string, options?: RequestInit) =>
    json<T>(`/api/v1/${path}`, options);
  async function detail(id: string): Promise<CaseDetail> {
    if (live) return request<CaseDetail>(base(id));
    const c = await fixture<CaseDetail>(`${base(id)}.detail.json`);
    if (active(id)) {
      const view = await investigation(id);
      return {
        ...c,
        progress_status: done(id)
          ? view.state.progress_status
          : "INVESTIGATING",
        outcome: done(id) ? view.state.outcome : null,
        latest_run: view.run,
        brief_available: done(id),
        stop_reason: done(id) ? view.state.stop_reason : null,
      };
    }
    return c;
  }
  async function investigation(
    id: string,
    runId?: string,
  ): Promise<InvestigationView> {
    if (live)
      return request(
        `${base(id)}/investigation${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`,
      );
    if (!active(id))
      throw new ApiFailure(
        404,
        "RUN_NOT_FOUND",
        "Belum ada investigasi untuk kasus ini.",
      );
    return fixture(
      `${base(id)}.investigation.${done(id) ? "completed" : "running"}.json`,
    );
  }
  return {
    health: () =>
      live
        ? request<Health>("health")
        : Promise.resolve({
            status: "ok",
            db: "ok",
            policy_index: "ok",
            dataset_version: "v0.1.0",
            corpus_version: "pc-0.1.1",
          } as Health),
    cases: async (query: Query): Promise<CaseList> => {
      if (live)
        return request(
          `cases?${new URLSearchParams(
            Object.entries(query)
              .filter(([, v]) => v !== "" && v !== undefined)
              .map(([k, v]) => [k, String(v)]),
          )}`,
        );
      const list = await fixture<CaseList>("cases.list.json");
      const items = await Promise.all(
        list.items.map(async (c) =>
          active(c.case_id) ? { ...c, ...(await detail(c.case_id)) } : c,
        ),
      );
      const filtered = filterCases(items, query),
        offset = query.offset || 0,
        limit = query.limit || 10;
      return {
        items: filtered.slice(offset, offset + limit),
        total: filtered.length,
        limit,
        offset,
      };
    },
    detail,
    timeline: (id: string) =>
      live
        ? request<EpisodeTimeline>(`${base(id)}/episodes`)
        : fixture<EpisodeTimeline>(`${base(id)}.episodes.json`),
    start: async (
      id: string,
      investigationMode: InvestigationMode,
      rerun = false,
    ): Promise<InvestigateAccepted> => {
      if (live)
        return request(`${base(id)}/investigate`, {
          method: "POST",
          body: JSON.stringify({
            mode: investigationMode,
            rerun,
            max_steps: 12,
          }),
        });
      if (active(id) && !done(id))
        throw new ApiFailure(
          409,
          "INVESTIGATION_IN_PROGRESS",
          "Pemutaran investigasi sedang berjalan.",
        );
      if (done(id) && !rerun)
        throw new ApiFailure(
          409,
          "INVESTIGATION_ALREADY_COMPLETED",
          "Brief sudah tersedia.",
        );
      sessionStorage.setItem(
        key,
        JSON.stringify({ ...playback(), [id]: Date.now() }),
      );
      const view = await investigation(id);
      return {
        run_id: view.run.run_id,
        run_status: "QUEUED",
        poll_url: `/api/v1/${base(id)}/investigation`,
      };
    },
    investigation,
    evidence: async (id: string, runId?: string): Promise<EvidenceList> => {
      if (live) {
        const first = await request<EvidenceList>(
          `${base(id)}/evidence?limit=200${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`,
        );
        const items = [...first.items];
        const pinnedRun = runId || first.items[0]?.run_id;
        let offset = first.offset + first.items.length;
        while (offset < first.total) {
          if (!pinnedRun || !first.items.length)
            throw new ApiFailure(
              0,
              "PAGINATION_ERROR",
              "Daftar bukti belum lengkap. Coba muat ulang.",
            );
          const page = await request<EvidenceList>(
            `${base(id)}/evidence?limit=200&offset=${offset}&run_id=${encodeURIComponent(pinnedRun)}`,
          );
          const known = new Set(items.map((e) => e.evidence_id));
          const additional = page.items.filter(
            (e) => !known.has(e.evidence_id) && e.run_id === pinnedRun,
          );
          if (!additional.length)
            throw new ApiFailure(
              0,
              "PAGINATION_ERROR",
              "Daftar bukti belum lengkap. Coba muat ulang.",
            );
          items.push(...additional);
          offset += page.items.length;
        }
        return { ...first, items, limit: items.length };
      }
      if (!active(id)) return { items: [], total: 0, limit: 200, offset: 0 };
      const list = await fixture<EvidenceList>(`${base(id)}.evidence.json`);
      const view = await investigation(id);
      const items = list.items.filter(
        (e) => e.investigation_step <= view.run.step,
      );
      return { ...list, items, total: items.length };
    },
    source: (id: string) =>
      live
        ? request<EvidenceDetail>(`evidence/${encodeURIComponent(id)}`)
        : fixture<EvidenceDetail>(`evidence/${encodeURIComponent(id)}.json`),
    brief: (id: string, runId?: string) =>
      live
        ? request<InvestigationBrief>(
            `${base(id)}/brief${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`,
          )
        : done(id)
          ? fixture<InvestigationBrief>(`${base(id)}.brief.json`)
          : Promise.reject(
              new ApiFailure(
                409,
                "BRIEF_NOT_READY",
                "Brief tersedia setelah investigasi selesai.",
              ),
            ),
    runs: async (id: string): Promise<RunList> =>
      live
        ? request(`${base(id)}/runs`)
        : {
            items: active(id) ? [(await investigation(id)).run] : [],
            total: active(id) ? 1 : 0,
            limit: 50,
            offset: 0,
          },
  };
}
