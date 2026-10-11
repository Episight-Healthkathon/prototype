"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  IconArrowRight,
  IconChevronLeft,
  IconChevronRight,
  IconFilterOff,
  IconSearch,
  IconRefresh,
} from "@tabler/icons-react";
import {
  useApp,
  useResource,
  Badge,
  Loading,
  ErrorState,
  Empty,
  Notice,
} from "@/components/system";
import { date, humanNotice } from "@/lib/labels";
import type { Query } from "@/lib/api";
export default function Queue() {
  const { mode } = useApp();
  return <QueueSession key={mode} />;
}
function QueueSession() {
  const { api, mode } = useApp();
  const [search, setSearch] = useState(""),
    [q, setQ] = useState(""),
    [signal, setSignal] = useState(""),
    [progress, setProgress] = useState(""),
    [outcome, setOutcome] = useState(""),
    [sort, setSort] = useState("-index_date"),
    [offset, setOffset] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(search);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  const query: Query = {
    q,
    signal_type: signal,
    progress_status: progress,
    outcome,
    sort,
    limit: 10,
    offset,
  };
  const list = useResource(
    () => api.cases(query),
    `queue:${mode}:${JSON.stringify(query)}`,
  );
  const reset = () => {
    setSearch("");
    setQ("");
    setSignal("");
    setProgress("");
    setOutcome("");
    setOffset(0);
  };
  const change = (set: (v: string) => void, v: string) => {
    set(v);
    setOffset(0);
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Antrean kasus</h1>
          <p>Pilih sinyal untuk memahami episode dan menelusuri buktinya.</p>
        </div>
        <button className="button secondary compact" onClick={list.reload}>
          <IconRefresh size={17} />
          Perbarui
        </button>
      </div>
      <Notice>{humanNotice}</Notice>
      <div className="queue-toolbar">
        <label className="search-field">
          <IconSearch size={19} />
          <span className="sr-only">Cari ID kasus atau pasien</span>
          <input
            placeholder="Cari ID kasus atau pasien…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label>
          Sinyal
          <select
            value={signal}
            onChange={(e) => change(setSignal, e.target.value)}
          >
            <option value="">Semua sinyal</option>
            <option value="READMISSION">Readmission</option>
            <option value="FRAGMENTATION">Fragmentasi episode</option>
          </select>
        </label>
        <label>
          Progres
          <select
            value={progress}
            onChange={(e) => change(setProgress, e.target.value)}
          >
            <option value="">Semua progres</option>
            <option value="FLAGGED">Belum diinvestigasi</option>
            <option value="INVESTIGATING">Investigasi berjalan</option>
            <option value="BRIEF_READY">Brief tersedia</option>
            <option value="INVESTIGATION_FAILED">Investigasi gagal</option>
          </select>
        </label>
        <label>
          Kondisi bukti
          <select
            value={outcome}
            onChange={(e) => change(setOutcome, e.target.value)}
          >
            <option value="">Semua kondisi</option>
            <option value="EVIDENCE_SUFFICIENT">
              Bukti cukup untuk ditinjau
            </option>
            <option value="EVIDENCE_CONFLICTING">Bukti bertentangan</option>
            <option value="EVIDENCE_UNAVAILABLE">Bukti tidak tersedia</option>
            <option value="HUMAN_REVIEW_REQUIRED">
              Perlu tinjauan manusia
            </option>
          </select>
        </label>
      </div>
      <div className="queue-meta">
        <span>
          {list.data
            ? `${list.data.total} kasus sesuai filter`
            : "Antrean kasus"}
        </span>
        <div>
          {(search || signal || progress || outcome) && (
            <button className="text-link" onClick={reset}>
              <IconFilterOff size={16} />
              Reset filter
            </button>
          )}
          <label>
            Urutkan
            <select
              value={sort}
              onChange={(e) => change(setSort, e.target.value)}
            >
              <option value="-index_date">Tanggal terbaru</option>
              <option value="index_date">Tanggal terlama</option>
              <option value="min_interval_days">Interval terpendek</option>
              <option value="case_id">ID kasus</option>
            </select>
          </label>
        </div>
      </div>
      {list.loading ? (
        <div className="panel">
          <Loading label="Memuat antrean kasus…" />
        </div>
      ) : list.error ? (
        <ErrorState error={list.error} retry={list.reload} />
      ) : (
        list.data && (
          <>
            {!list.data.items.length ? (
              <Empty title="Tidak ada kasus yang sesuai">
                <p>Coba kata pencarian atau filter yang berbeda.</p>
                <button className="button secondary" onClick={reset}>
                  Reset filter
                </button>
              </Empty>
            ) : (
              <div className="table-container">
                <table className="case-table">
                  <thead>
                    <tr>
                      <th>Kasus & pasien</th>
                      <th>Sinyal</th>
                      <th>Fasilitas</th>
                      <th>Tanggal indeks</th>
                      <th>Interval</th>
                      <th>Progres & bukti</th>
                      <th>
                        <span className="sr-only">Buka</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.data.items.map((c) => (
                      <tr key={c.case_id}>
                        <td>
                          <Link
                            className="case-link"
                            href={`/cases/${c.case_id}`}
                          >
                            {c.case_id}
                          </Link>
                          <span className="table-sub">
                            {c.patient_id} · {c.episode_count} episode pemicu
                          </span>
                        </td>
                        <td>
                          <Badge value={c.signal_type} />
                        </td>
                        <td>
                          {c.provider.name}
                          <span className="table-sub mono">
                            {c.provider.provider_id}
                          </span>
                        </td>
                        <td className="nowrap">{date(c.index_date)}</td>
                        <td className="interval-cell">
                          <strong>{c.min_interval_days}</strong> hari
                        </td>
                        <td>
                          <Badge value={c.progress_status} />
                          {c.outcome && (
                            <span className="table-sub">
                              <Badge value={c.outcome} />
                            </span>
                          )}
                        </td>
                        <td>
                          <Link
                            href={`/cases/${c.case_id}`}
                            className="icon-button"
                            aria-label={`Buka ${c.case_id}`}
                          >
                            <IconArrowRight size={20} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="pagination">
              <span>
                {list.data.total
                  ? `${offset + 1}–${Math.min(offset + 10, list.data.total)} dari ${list.data.total} kasus`
                  : "0 kasus"}
              </span>
              <div>
                <button
                  className="button secondary compact"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - 10))}
                >
                  <IconChevronLeft size={17} />
                  Sebelumnya
                </button>
                <button
                  className="button secondary compact"
                  disabled={offset + 10 >= list.data.total}
                  onClick={() => setOffset(offset + 10)}
                >
                  Berikutnya
                  <IconChevronRight size={17} />
                </button>
              </div>
            </div>
          </>
        )
      )}
    </>
  );
}
