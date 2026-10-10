import Link from "next/link";
import { AppShell, Badge } from "@/components/system";
import {
  IconArrowRight,
  IconShieldCheck,
  IconTimeline,
  IconSearch,
  IconFileText,
  IconChecklist,
} from "@tabler/icons-react";
export default function Guide() {
  return (
    <AppShell>
      <div className="guide-page">
        <section className="guide-hero">
          <div>
            <span className="guide-eyebrow">PANDUAN PEMERIKSA</span>
            <h1>Dari sinyal ke review yang terarah.</h1>
            <p>
              Pahami alasan kasus ditandai, periksa buktinya, lalu tentukan
              tindak lanjut. Detail dibuka saat dibutuhkan.
            </p>
            <Link className="button" href="/cases">
              Pilih kasus dari antrean <IconArrowRight size={18} />
            </Link>
          </div>
          <aside className="guide-principle">
            <IconShieldCheck size={30} aria-hidden="true" />
            <strong>Sinyal adalah titik mulai.</strong>
            <p>
              Kunjungan berulang belum membuktikan pelanggaran. Alasan medis dan
              ketentuan episode tetap perlu diperiksa.
            </p>
            <span>Data sintetis · keputusan tetap pada reviewer</span>
          </aside>
        </section>
        <section aria-labelledby="guide-steps">
          <div className="section-heading">
            <div>
              <h2 id="guide-steps">Empat langkah dalam satu kasus</h2>
              <p>
                Ikuti urutan tab pada halaman kasus. Anda dapat kembali ke
                langkah sebelumnya.
              </p>
            </div>
          </div>
          <ol className="guide-steps">
            {[
              {
                title: "Pahami konteks kasus",
                icon: IconTimeline,
                question: "Mengapa kasus ini ditandai?",
                text: "Baca pemicu screening dan interval episode. Buka timeline untuk membandingkan diagnosis, tindakan, dan kunjungan.",
                result: "Kenali episode yang perlu dibandingkan.",
              },
              {
                title: "Baca ringkasan pemeriksaan",
                icon: IconSearch,
                question: "Apa yang sudah diketahui?",
                text: "Mulai investigasi, lalu lihat bukti pendukung, alasan medis, dan pemeriksaan yang perlu perhatian. Hasil diperbarui otomatis.",
                result: "Tentukan bagian yang perlu ditelusuri.",
              },
              {
                title: "Telusuri detail bukti",
                icon: IconFileText,
                question: "Apakah sumber mendukung penjelasannya?",
                text: "Buka sumber untuk membaca kutipan dan asal data. Bandingkan bukti risiko dengan konteks penjelas serta kebijakan.",
                result:
                  "Periksa sumber, termasuk keterangan yang bertentangan.",
              },
              {
                title: "Tinjau ringkasan akhir",
                icon: IconChecklist,
                question: "Apa tindak lanjut saya?",
                text: "Baca ketidakpastian dan saran pemeriksaan berikutnya. Ringkasan akhir tersedia setelah pemeriksaan mesin selesai.",
                result:
                  "Tetapkan tindak lanjut melalui proses review yang berlaku.",
              },
            ].map((step, i) => (
              <li key={step.title}>
                <div className="guide-step-top">
                  <span className="guide-step-number">{i + 1}</span>
                  <step.icon size={23} aria-hidden="true" />
                </div>
                <h3>{step.title}</h3>
                <strong className="guide-step-question">{step.question}</strong>
                <p>{step.text}</p>
                <div className="guide-step-result">{step.result}</div>
              </li>
            ))}
          </ol>
        </section>
        <section aria-labelledby="guide-status">
          <div className="section-heading">
            <div>
              <h2 id="guide-status">
                Lihat status, ketahui tindakan berikutnya
              </h2>
              <p>Status menggambarkan kondisi bukti, bukan keputusan klaim.</p>
            </div>
          </div>
          <div className="guide-outcomes">
            {[
              {
                status: "EVIDENCE_SUFFICIENT",
                meaning:
                  "Bukti siap untuk ditinjau. Ini bukan keputusan bahwa klaim sah atau terbukti fraud.",
                action: "Periksa sumber dan kebijakan sebelum menyimpulkan.",
              },
              {
                status: "EVIDENCE_CONFLICTING",
                meaning: "Ada keterangan sumber yang bertentangan.",
                action: "Baca kedua sisi dan klarifikasi perbedaannya.",
              },
              {
                status: "EVIDENCE_UNAVAILABLE",
                meaning:
                  "Sumber penting tidak tersedia atau aksesnya dibatasi.",
                action:
                  "Identifikasi dokumen yang perlu diminta melalui proses yang berlaku.",
              },
              {
                status: "HUMAN_REVIEW_REQUIRED",
                meaning:
                  "Pemeriksaan berhenti dengan pertanyaan yang masih perlu dinilai reviewer.",
                action:
                  "Tinjau bukti yang belum lengkap dan saran tindak lanjut.",
              },
            ].map((item) => (
              <article key={item.status}>
                <Badge value={item.status} />
                <p>{item.meaning}</p>
                <strong>Yang perlu Anda lakukan</strong>
                <p>{item.action}</p>
              </article>
            ))}
          </div>
          <div className="guide-reminder">
            <h3>“Tidak ditemukan” berbeda dengan “tidak tersedia”</h3>
            <p>
              Tidak ditemukan berarti pencarian sumber tersedia selesai tanpa
              temuan. Tidak tersedia berarti sumber belum bisa diperiksa.
              Keduanya tidak membuktikan kondisi klinis tidak ada.
            </p>
          </div>
        </section>
        <section aria-labelledby="guide-help">
          <h2 id="guide-help">Butuh penjelasan lebih lanjut?</h2>
          {[
            {
              title: "Di mana saya membuka sumber dan detail teknis?",
              text: "Pilih tab Detail bukti, lalu klik sumber untuk membaca kutipan dan asal data. Jejak aksi serta informasi planner ada di bagian Detail teknis dan jejak pemeriksaan. Catatan planner menjelaskan usulan aksi; bukan bukti.",
            },
            {
              title: "Bagaimana jika pemeriksaan gagal?",
              text: "Buka detail teknis dan jejak pemeriksaan untuk melihat kesalahan. Periksa kesiapan layanan, lalu jalankan ulang dari Ringkasan pemeriksaan. Hasil pemeriksaan gagal belum dapat dinilai.",
            },
            {
              title: "Apa bedanya API lokal dan demo offline?",
              text: "API lokal menjalankan backend dan menyimpan riwayat pemeriksaan. Demo offline memutar hasil yang sudah direkam pada data sintetis, tanpa eksekusi AI baru; progresnya disimpan pada tab browser. Metode pemeriksaan tersedia dalam Pengaturan lanjutan. Planner AI bergantung pada konfigurasi server dan dapat beralih ke aturan jika tidak tersedia.",
            },
            {
              title: "Apakah hasil review saya tersimpan?",
              text: "Prototype menyimpan hasil investigasi backend, tetapi belum menyediakan penyimpanan catatan atau keputusan reviewer. Gunakan ringkasan sebagai bahan peninjauan, dan catat keputusan melalui proses yang berlaku.",
            },
            {
              title: "Apakah ini memakai data peserta JKN nyata?",
              text: "Tidak. Identitas pasien dan fasilitas bersifat sintetis. Prototype tidak terhubung ke Mobile JKN atau data pasien BPJS asli, serta tidak menyetujui, menolak, atau menentukan pembayaran klaim.",
            },
          ].map((q) => (
            <details className="review-disclosure" key={q.title}>
              <summary>{q.title}</summary>
              <p>{q.text}</p>
            </details>
          ))}
        </section>
        <div className="section-action">
          <p>Siap mencoba? Pilih satu kasus dan mulai dari konteksnya.</p>
          <Link className="button" href="/cases">
            Buka antrean kasus <IconArrowRight size={18} />
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
