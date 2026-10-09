import Link from "next/link";
import { AppShell, Notice } from "@/components/system";
import { humanNotice } from "@/lib/labels";
export default function Guide() {
  return (
    <AppShell>
      <div className="page-heading">
        <div>
          <h1>Panduan review</h1>
          <p>Mulai dari sinyal. Pahami konteks. Periksa sumber.</p>
        </div>
      </div>
      <Notice>{humanNotice}</Notice>
      <div className="guide-content">
        <section>
          <h2>Alur peninjauan</h2>
          <ol>
            <li>
              <strong>Pilih kasus dari antrean.</strong> Filter sinyal, progres
              atau kondisi bukti. Pencarian menggunakan ID kasus dan pasien.
            </li>
            <li>
              <strong>Rekonstruksi episode.</strong> Pemicu sinyal, episode
              terkait dan riwayat konteks memiliki peran berbeda. Buka setiap
              episode untuk melihat diagnosis, tindakan dan ketersediaan
              dokumen.
            </li>
            <li>
              <strong>Mulai investigasi.</strong> Pantau pertanyaan, cakupan
              pencarian dan jejak aksi. Angka langkah adalah budget pemeriksaan,
              bukan estimasi waktu.
            </li>
            <li>
              <strong>Review brief.</strong> Periksa bukti risiko, konteks
              penjelas, kebijakan, konflik dan ketidakpastian. Klik setiap
              sumber untuk melihat kutipan dan provenance.
            </li>
          </ol>
        </section>
        <section>
          <h2>Memahami kondisi bukti</h2>
          <dl className="guide-definitions">
            <dt>Bukti cukup untuk ditinjau</dt>
            <dd>
              Pemeriksaan mencapai kondisi bukti yang cukup. Sinyal tetap
              terlihat dan keputusan tetap pada reviewer.
            </dd>
            <dt>Bukti bertentangan</dt>
            <dd>
              Dua sumber memiliki keterangan berbeda. Baca kedua sisi dengan
              bobot tampilan yang sama.
            </dd>
            <dt>Bukti tidak tersedia</dt>
            <dd>
              Sumber material hilang atau dibatasi. Konteks belum dapat dinilai.
            </dd>
            <dt>Perlu tinjauan manusia</dt>
            <dd>
              Jalur pemeriksaan berakhir atau batas langkah tercapai. Periksa
              pertanyaan dan bukti yang belum terselesaikan.
            </dd>
            <dt>Tidak ditemukan setelah pencarian</dt>
            <dd>
              Pencarian semua sumber tersedia dalam scope selesai tanpa temuan;
              tidak membuktikan kondisi klinis tidak ada.
            </dd>
          </dl>
        </section>
        <section>
          <h2>API lokal dan demo offline</h2>
          <p>
            API lokal menjalankan backend dan menyimpan run investigasi. Demo
            offline memutar hasil engine deterministik dari dataset resmi v0.1.0
            dan corpus pc-0.1.1; progres pemutarannya disimpan pada tab browser.
            Mode demo selalu memakai aturan + retrieval.
          </p>
          <p>
            Mode planner AI pada API menggunakan konfigurasi server dan dapat
            beralih ke fallback aturan. Catatan planner adalah penjelasan usulan
            aksi, bukan bukti.
          </p>
        </section>
        <section>
          <h2>Data & batas prototype</h2>
          <p>
            Seluruh identitas pasien dan fasilitas bersifat sintetis. Tidak ada
            koneksi Mobile JKN atau data pasien BPJS asli. Prototype menyediakan
            investigasi, brief, riwayat run dan sumber bukti. Pencatatan catatan
            reviewer belum disediakan oleh API.
          </p>
        </section>
        <Link className="button" href="/cases">
          Buka antrean kasus
        </Link>
      </div>
    </AppShell>
  );
}
