"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { IconHistory, IconX } from "@tabler/icons-react";
import type { RunSummary } from "@episight/shared-types";
import { Badge, Empty, ErrorState, Loading } from "./system";
import { date, label } from "@/lib/labels";
import { orderedRuns } from "@/lib/review-guide";

export function RunHistory({
  items,
  loading,
  error,
  retry,
  selectedId,
  onSelect,
}: {
  items: RunSummary[];
  loading: boolean;
  error: Error | null;
  retry: () => void;
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const runs = orderedRuns(items);
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button className="button secondary compact">
          <IconHistory size={18} />
          Riwayat pemeriksaan
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-overlay" />
        <Dialog.Content className="evidence-drawer history-drawer">
          <div className="drawer-heading">
            <div>
              <Dialog.Title>Riwayat pemeriksaan</Dialog.Title>
              <Dialog.Description>
                Hasil investigasi untuk kasus ini, dari yang terbaru.
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="icon-button"
              aria-label="Tutup riwayat pemeriksaan"
            >
              <IconX size={22} />
            </Dialog.Close>
          </div>
          <div className="history-drawer-body">
            {loading ? (
              <Loading label="Memuat riwayat pemeriksaan…" />
            ) : error ? (
              <ErrorState error={error} retry={retry} />
            ) : runs.length ? (
              <>
                <p className="small-muted">
                  Pilih hasil untuk meninjau bukti dan ringkasannya. Riwayat ini
                  bukan catatan keputusan reviewer.
                </p>
                <ol className="history-cards">
                  {runs.map((run, index) => {
                    const id = index === 0 ? "" : run.run_id;
                    const active = selectedId === id;
                    return (
                      <li
                        key={run.run_id}
                        className={active ? "selected-history" : ""}
                      >
                        <div className="history-card-heading">
                          <strong>{date(run.started_at, true)}</strong>
                          <span>{index === 0 ? "Terbaru" : "Sebelumnya"}</span>
                        </div>
                        <div className="history-card-badges">
                          <Badge value={run.run_status} />
                          {run.outcome && <Badge value={run.outcome} />}
                        </div>
                        <p>{label(run.mode)}</p>
                        <small className="mono">{run.run_id}</small>
                        <Dialog.Close asChild>
                          <button
                            className="button secondary compact"
                            onClick={() => onSelect(id)}
                          >
                            {active
                              ? "Buka hasil yang sedang dipilih"
                              : "Lihat hasil"}
                          </button>
                        </Dialog.Close>
                      </li>
                    );
                  })}
                </ol>
              </>
            ) : (
              <Empty title="Belum ada pemeriksaan">
                <p>Riwayat muncul setelah investigasi dimulai.</p>
              </Empty>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
