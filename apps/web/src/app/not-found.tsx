import Link from "next/link";
export default function NotFound() {
  return (
    <main className="error-state">
      <h1>Halaman tidak ditemukan</h1>
      <p>Kembali ke antrean untuk memilih kasus yang tersedia.</p>
      <Link className="button" href="/cases">
        Buka antrean kasus
      </Link>
    </main>
  );
}
