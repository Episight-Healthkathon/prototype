"""Builds the interim synthetic dataset used until Person 3's official dataset lands (BE-1.7).

Run from apps/api:  uv run python tests/fixtures/build_interim_dataset.py

Everything here is synthetic. No labels or expected outcomes are written into the dataset (Data Contract
v1 §1); the scenarios each patient represents are documented only in tests/fixtures/README.md.
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
DATASET_DIR = HERE / "dataset" / "v0-interim"
POLICY_DIR = HERE / "policies" / "pc-0-interim"
TZ = "+07:00"


def ts(day: str, time: str = "08:00") -> str:
    return f"{day}T{time}:00{TZ}"


providers = [
    {
        "provider_id": "PRV-0001",
        "name": "RS Sintetis Nusantara 01",
        "provider_type": "FKRTL",
        "hospital_class": "B",
        "region": "Wilayah Sintetis A",
    },
    {
        "provider_id": "PRV-0002",
        "name": "RS Sintetis Nusantara 02",
        "provider_type": "FKRTL",
        "hospital_class": "C",
        "region": "Wilayah Sintetis A",
    },
    {
        "provider_id": "PRV-0003",
        "name": "RS Sintetis Nusantara 03",
        "provider_type": "FKRTL",
        "hospital_class": "B",
        "region": "Wilayah Sintetis B",
    },
]

patients = [
    {"patient_id": "PAT-000001", "birth_year": 1962, "sex": "M", "chronic_conditions": ["I50.0", "I10"]},
    {"patient_id": "PAT-000002", "birth_year": 1988, "sex": "F", "chronic_conditions": []},
    {"patient_id": "PAT-000003", "birth_year": 1957, "sex": "M", "chronic_conditions": ["I25.1"]},
    {"patient_id": "PAT-000004", "birth_year": 1971, "sex": "F", "chronic_conditions": []},
    {"patient_id": "PAT-000005", "birth_year": 1979, "sex": "F", "chronic_conditions": []},
    {"patient_id": "PAT-000006", "birth_year": 1950, "sex": "M", "chronic_conditions": ["I50.0"]},
    {"patient_id": "PAT-000007", "birth_year": 1966, "sex": "F", "chronic_conditions": ["I50.0"]},
    {"patient_id": "PAT-000008", "birth_year": 1993, "sex": "M", "chronic_conditions": []},
    {"patient_id": "PAT-000009", "birth_year": 2001, "sex": "F", "chronic_conditions": []},
    {"patient_id": "PAT-000010", "birth_year": 1984, "sex": "M", "chronic_conditions": []},
]


def inpatient(eid, pid, prv, start, end, dx, *, sec=(), procs=(), adm=None, cls="3"):
    return {
        "episode_id": eid,
        "patient_id": pid,
        "provider_id": prv,
        "encounter_type": "INPATIENT",
        "start_at": start,
        "end_at": end,
        "admission_type": adm,
        "primary_diagnosis": dx,
        "secondary_diagnoses": list(sec),
        "procedures": [dict(p) for p in procs],
        "discharge_status": "HOME",
        "class_of_care": cls,
    }


def outpatient(eid, pid, prv, start, dx, *, sec=(), procs=()):
    return {
        "episode_id": eid,
        "patient_id": pid,
        "provider_id": prv,
        "encounter_type": "OUTPATIENT",
        "start_at": start,
        "end_at": None,
        "admission_type": None,
        "primary_diagnosis": dx,
        "secondary_diagnoses": list(sec),
        "procedures": [dict(p) for p in procs],
        "discharge_status": None,
        "class_of_care": None,
    }


episodes = [
    # PAT-000001: heart failure, readmitted through the emergency department (+ earlier outpatient visit)
    outpatient("EPI-000103", "PAT-000001", "PRV-0001", ts("2026-02-20", "09:30"), "I50.0", sec=["I10"]),
    inpatient(
        "EPI-000101",
        "PAT-000001",
        "PRV-0001",
        ts("2026-03-03", "09:10"),
        ts("2026-03-07", "11:00"),
        "I50.0",
        sec=["I10"],
        procs=[{"code": "89.52"}, {"code": "87.44"}],
    ),
    inpatient(
        "EPI-000102",
        "PAT-000001",
        "PRV-0001",
        ts("2026-03-12", "21:40"),
        ts("2026-03-16", "10:00"),
        "I50.0",
        sec=["I10"],
        procs=[{"code": "89.52"}],
    ),
    # PAT-000002: three outpatient gastritis visits in one week
    outpatient("EPI-000201", "PAT-000002", "PRV-0002", ts("2026-04-02", "08:30"), "K29.7"),
    outpatient("EPI-000202", "PAT-000002", "PRV-0002", ts("2026-04-06", "09:00"), "K29.7"),
    outpatient("EPI-000203", "PAT-000002", "PRV-0002", ts("2026-04-09", "10:15"), "K29.7"),
    # PAT-000003: staged coronary intervention
    inpatient(
        "EPI-000301",
        "PAT-000003",
        "PRV-0003",
        ts("2026-05-04", "08:00"),
        ts("2026-05-06", "12:00"),
        "I25.1",
        procs=[{"code": "88.56", "performed_at": ts("2026-05-04", "10:00")}],
        adm="ELECTIVE",
        cls="2",
    ),
    inpatient(
        "EPI-000302",
        "PAT-000003",
        "PRV-0003",
        ts("2026-05-20", "07:30"),
        ts("2026-05-22", "10:00"),
        "I25.1",
        procs=[{"code": "36.06", "performed_at": ts("2026-05-20", "09:30")}],
        adm="ELECTIVE",
        cls="2",
    ),
    # PAT-000004: pneumonia readmission; second-episode documents not accessible
    inpatient("EPI-000401", "PAT-000004", "PRV-0001", ts("2026-06-01", "14:00"), ts("2026-06-05", "10:00"), "J18.9"),
    inpatient("EPI-000402", "PAT-000004", "PRV-0001", ts("2026-06-15", "19:20"), ts("2026-06-19", "11:00"), "J18.9"),
    # PAT-000005: UTI readmission; documents disagree about how the patient was admitted
    inpatient("EPI-000501", "PAT-000005", "PRV-0002", ts("2026-07-01", "10:00"), ts("2026-07-04", "09:00"), "N39.0"),
    inpatient("EPI-000502", "PAT-000005", "PRV-0002", ts("2026-07-10", "23:15"), ts("2026-07-14", "10:00"), "N39.0"),
    # PAT-000006: same diagnosis and provider but 40 days apart; plus an exact duplicate row
    inpatient("EPI-000601", "PAT-000006", "PRV-0001", ts("2026-02-01", "10:00"), ts("2026-02-05", "10:00"), "I50.0"),
    inpatient("EPI-000602", "PAT-000006", "PRV-0001", ts("2026-03-17", "10:00"), ts("2026-03-20", "10:00"), "I50.0"),
    inpatient("EPI-000603", "PAT-000006", "PRV-0001", ts("2026-02-01", "10:00"), ts("2026-02-05", "10:00"), "I50.0"),
    # PAT-000007: second admission at a different provider
    inpatient("EPI-000701", "PAT-000007", "PRV-0001", ts("2026-04-10", "10:00"), ts("2026-04-14", "10:00"), "I50.0"),
    inpatient("EPI-000702", "PAT-000007", "PRV-0003", ts("2026-04-20", "10:00"), ts("2026-04-24", "10:00"), "I50.0"),
    # PAT-000008: outpatient visits exactly 7 days apart (inclusive boundary)
    outpatient("EPI-000801", "PAT-000008", "PRV-0003", ts("2026-05-10", "09:00"), "K29.7"),
    outpatient("EPI-000802", "PAT-000008", "PRV-0003", ts("2026-05-17", "09:00"), "K29.7"),
    # PAT-000009: different diagnoses 3 days apart; plus a record with a missing timestamp
    outpatient("EPI-000901", "PAT-000009", "PRV-0002", ts("2026-06-02", "10:00"), "J06.9"),
    outpatient("EPI-000902", "PAT-000009", "PRV-0002", ts("2026-06-05", "10:00"), "K29.7"),
    outpatient("EPI-000903", "PAT-000009", "PRV-0002", None, "K29.7"),
    # PAT-000010: inpatient followed by outpatient (encounter type mismatch)
    inpatient("EPI-001001", "PAT-000010", "PRV-0003", ts("2026-06-01", "10:00"), ts("2026-06-03", "10:00"), "A09"),
    outpatient("EPI-001002", "PAT-000010", "PRV-0003", ts("2026-06-05", "10:00"), "A09"),
]


def note(nid, eid, ntype, authored, text, title=None, availability="AVAILABLE"):
    return {
        "note_id": nid,
        "episode_id": eid,
        "note_type": ntype,
        "title": title,
        "authored_at": authored,
        "language": "id",
        "availability": availability,
        "text": text if availability == "AVAILABLE" else None,
    }


notes = [
    note(
        "NOTE-000100",
        "EPI-000103",
        "OUTPATIENT_VISIT",
        ts("2026-02-20", "10:00"),
        "Kontrol poli jantung. Pasien dengan gagal jantung kronik (CHF) dan hipertensi, keluhan sesak saat aktivitas "
        "sedang. Edema tungkai minimal. Terapi furosemide dan ramipril dilanjutkan. Kontrol 1 bulan.",
        title="Kunjungan poli jantung",
    ),
    note(
        "NOTE-000101",
        "EPI-000101",
        "DISCHARGE_SUMMARY",
        ts("2026-03-07", "10:30"),
        "Ringkasan pulang. Pasien laki-laki 64 tahun dirawat dengan gagal jantung kongestif (CHF NYHA III). Diberikan "
        "diuretik intravena, sesak membaik. Kondisi saat pulang stabil, edema berkurang. Rencana: kontrol poli jantung "
        "14 hari, lanjut furosemide oral dan pembatasan cairan.",
        title="Ringkasan pulang",
    ),
    note(
        "NOTE-000102",
        "EPI-000102",
        "TRIAGE",
        ts("2026-03-12", "21:45"),
        "Triase IGD. Pasien datang diantar keluarga dengan sesak napas memberat sejak 6 jam sebelum masuk rumah sakit, "
        "tidak bisa berbaring. SpO2 86% udara ruang, TD 170/100 mmHg, RR 32x/menit, ronki basah kedua lapang paru. "
        "Kategori triase: merah (gawat darurat). Dicurigai edema paru akut.",
        title="Catatan triase IGD",
    ),
    note(
        "NOTE-000103",
        "EPI-000102",
        "DISCHARGE_SUMMARY",
        ts("2026-03-16", "09:30"),
        "Ringkasan pulang. Dirawat ulang melalui IGD dengan acute decompensated heart failure dan edema paru akut. "
        "Pemicu: ketidakpatuhan pembatasan cairan dan infeksi saluran napas atas. Mendapat oksigen, furosemide IV, dan "
        "nitrat. Pulang dalam kondisi stabil.",
        title="Ringkasan pulang",
    ),
    note(
        "NOTE-000201",
        "EPI-000201",
        "OUTPATIENT_VISIT",
        ts("2026-04-02", "09:00"),
        "Kunjungan poli penyakit dalam. Keluhan nyeri ulu hati dan mual sejak 3 hari. Pemeriksaan fisik: nyeri tekan "
        "epigastrium ringan. Tidak ada tanda kegawatdaruratan. Diagnosis gastritis. Terapi omeprazole dan antasida. "
        "Pasien diminta kontrol kembali.",
        title="Kunjungan poli penyakit dalam",
    ),
    note(
        "NOTE-000202",
        "EPI-000202",
        "OUTPATIENT_VISIT",
        ts("2026-04-06", "09:30"),
        "Kontrol poli penyakit dalam. Keluhan nyeri ulu hati masih ada, mual berkurang. Pemeriksaan fisik dalam batas "
        "normal kecuali nyeri tekan epigastrium. Terapi dilanjutkan. Kontrol kembali.",
        title="Kontrol poli penyakit dalam",
    ),
    note(
        "NOTE-000203",
        "EPI-000203",
        "OUTPATIENT_VISIT",
        ts("2026-04-09", "10:45"),
        "Kontrol poli penyakit dalam. Keluhan serupa dengan kunjungan sebelumnya. Tidak ada pemeriksaan penunjang yang "
        "dijadwalkan. Terapi dilanjutkan, edukasi diet.",
        title="Kontrol poli penyakit dalam",
    ),
    note(
        "NOTE-000301",
        "EPI-000301",
        "PROCEDURE_REPORT",
        ts("2026-05-04", "11:30"),
        "Laporan kateterisasi jantung: angiografi koroner menunjukkan stenosis 80% LAD proksimal dan 70% RCA. Volume "
        "kontras sudah mendekati batas aman pada pasien dengan penurunan fungsi ginjal (eGFR 45).",
        title="Laporan angiografi koroner",
    ),
    note(
        "NOTE-000302",
        "EPI-000301",
        "PROCEDURE_PLAN",
        ts("2026-05-06", "09:00"),
        "Rencana tindakan: PCI bertahap. Tahap kedua pemasangan stent pada LAD (ICD-9-CM 36.06) dijadwalkan tanggal "
        "20 Mei 2026. Tindakan tidak dilakukan pada episode yang sama karena batas volume kontras dan perlindungan "
        "fungsi ginjal.",
        title="Rencana PCI bertahap",
    ),
    note(
        "NOTE-000303",
        "EPI-000301",
        "DISCHARGE_SUMMARY",
        ts("2026-05-06", "11:00"),
        "Ringkasan pulang. Pasien stabil pasca angiografi koroner, tanpa nyeri dada. Dijadwalkan masuk kembali untuk "
        "PCI tahap kedua sesuai rencana tindakan.",
        title="Ringkasan pulang",
    ),
    note(
        "NOTE-000304",
        "EPI-000302",
        "PROCEDURE_REPORT",
        ts("2026-05-20", "11:00"),
        "Laporan tindakan: PCI dengan pemasangan stent non-drug-eluting pada LAD proksimal sesuai rencana tahap kedua. "
        "Hasil aliran TIMI 3, tanpa komplikasi.",
        title="Laporan PCI",
    ),
    note(
        "NOTE-000305",
        "EPI-000302",
        "DISCHARGE_SUMMARY",
        ts("2026-05-22", "09:00"),
        "Ringkasan pulang. Pasca PCI tahap kedua, kondisi stabil. Lanjut dual antiplatelet. Kontrol poli jantung 2 "
        "minggu.",
        title="Ringkasan pulang",
    ),
    note(
        "NOTE-000401",
        "EPI-000401",
        "DISCHARGE_SUMMARY",
        ts("2026-06-05", "09:00"),
        "Ringkasan pulang. Pneumonia komunitas, mendapat antibiotik intravena 4 hari, demam turun, pulang dengan "
        "antibiotik oral 5 hari.",
        title="Ringkasan pulang",
    ),
    note(
        "NOTE-000402",
        "EPI-000402",
        "TRIAGE",
        ts("2026-06-15", "19:30"),
        None,
        title="Catatan triase IGD",
        availability="UNAVAILABLE",
    ),
    note(
        "NOTE-000403",
        "EPI-000402",
        "DISCHARGE_SUMMARY",
        ts("2026-06-19", "10:00"),
        None,
        title="Ringkasan pulang",
        availability="RESTRICTED",
    ),
    note(
        "NOTE-000501",
        "EPI-000501",
        "DISCHARGE_SUMMARY",
        ts("2026-07-04", "08:30"),
        "Ringkasan pulang. Infeksi saluran kemih, antibiotik intravena 3 hari, pulang dengan antibiotik oral.",
        title="Ringkasan pulang",
    ),
    note(
        "NOTE-000502",
        "EPI-000502",
        "TRIAGE",
        ts("2026-07-10", "23:20"),
        "Triase IGD. Pasien datang malam hari dengan demam 39,8 C, menggigil, nyeri pinggang kanan, tampak lemas. "
        "Kategori triase: kuning-merah. Dicurigai urosepsis.",
        title="Catatan triase IGD",
    ),
    note(
        "NOTE-000503",
        "EPI-000502",
        "DISCHARGE_SUMMARY",
        ts("2026-07-14", "09:00"),
        "Ringkasan pulang. Pasien masuk secara elektif sesuai jadwal untuk evaluasi lanjutan infeksi saluran kemih "
        "berulang dan pemberian antibiotik terencana. Tidak ada kondisi gawat darurat saat masuk.",
        title="Ringkasan pulang",
    ),
    note(
        "NOTE-000801",
        "EPI-000801",
        "OUTPATIENT_VISIT",
        ts("2026-05-10", "09:30"),
        "Kunjungan poli penyakit dalam. Nyeri ulu hati setelah makan pedas. Terapi antasida. Kontrol bila perlu.",
        title="Kunjungan poli penyakit dalam",
    ),
    note(
        "NOTE-000802",
        "EPI-000802",
        "OUTPATIENT_VISIT",
        ts("2026-05-17", "09:30"),
        "Kontrol poli penyakit dalam membawa hasil endoskopi saluran cerna atas yang dilakukan di luar: gastritis "
        "erosif ringan. Terapi disesuaikan berdasarkan hasil pemeriksaan penunjang.",
        title="Kontrol poli penyakit dalam",
    ),
]

INACBG = {
    "I50.0": "I-4-12-I",
    "I25.1": "I-4-10-I",
    "J18.9": "J-4-16-I",
    "N39.0": "N-4-10-I",
    "K29.7": "Q-5-44-0",
    "J06.9": "Q-5-18-0",
    "A09": "K-4-17-I",
}
claims = [
    {
        "claim_id": e["episode_id"].replace("EPI", "CLM"),
        "episode_id": e["episode_id"],
        "submitted_at": e["end_at"] or e["start_at"] or ts("2026-06-06"),
        "inacbg_code": INACBG[e["primary_diagnosis"]],
        "claimed_amount_idr": 4_850_000 if e["encounter_type"] == "INPATIENT" else 215_000,
        "claim_status": "SUBMITTED",
    }
    for e in episodes
]

policy_sections = [
    {
        "policy_id": "POL-INTERIM-READMISI-01",
        "document_title": "Permenkes No. 26 Tahun 2021 tentang Pedoman INA-CBG (ringkasan interim)",
        "section": "Readmisi: definisi dan pengecualian",
        "text": "Readmisi adalah kunjungan rawat inap berulang di FKRTL yang sama dengan diagnosis utama yang sama dalam "
        "waktu kurang dari atau sama dengan 30 hari. Pengecualian meliputi kasus kegawatdaruratan, penyakit "
        "kronis, prosedur terjadwal sesuai indikasi medis yang tidak dapat dilakukan dalam satu episode, atau "
        "kunjungan pada FKRTL berbeda atau kelas yang lebih tinggi.",
        "source_ref": "INTERIM PLACEHOLDER: parafrase dari proposal EPISIGHT bagian 3 (sumber: Permenkes 26/2021). "
        "Ganti dengan korpus kurasi Person 3.",
        "source_url": "https://jdih.kemkes.go.id/documents/peraturan-menteri-kesehatan-nomor-26-tahun-2021",
        "version": "interim-0",
        "effective_date": None,
        "topics": ["READMISSION", "EXCEPTION_EMERGENCY", "EXCEPTION_CHRONIC", "EXCEPTION_SCHEDULED"],
    },
    {
        "policy_id": "POL-INTERIM-FRAGMENTASI-01",
        "document_title": "Permenkes No. 26 Tahun 2021 tentang Pedoman INA-CBG (ringkasan interim)",
        "section": "Fragmentasi: definisi dan pengecualian",
        "text": "Fragmentasi adalah kunjungan rawat jalan berulang di FKRTL yang sama pada diagnosis yang sama dalam waktu "
        "kurang dari atau sama dengan 7 hari. Pengecualian meliputi kasus kegawatdaruratan, penyakit kronis, "
        "rangkaian prosedur terjadwal sesuai indikasi medis yang tidak dapat dilakukan dalam satu episode, atau "
        "konsultasi hasil pemeriksaan penunjang tertentu.",
        "source_ref": "INTERIM PLACEHOLDER: parafrase dari proposal EPISIGHT bagian 3 (sumber: Permenkes 26/2021). "
        "Ganti dengan korpus kurasi Person 3.",
        "source_url": "https://jdih.kemkes.go.id/documents/peraturan-menteri-kesehatan-nomor-26-tahun-2021",
        "version": "interim-0",
        "effective_date": None,
        "topics": [
            "FRAGMENTATION",
            "EXCEPTION_EMERGENCY",
            "EXCEPTION_CHRONIC",
            "EXCEPTION_SCHEDULED",
            "EXCEPTION_SUPPORTING_EXAM",
        ],
    },
]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")


def main() -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    POLICY_DIR.mkdir(parents=True, exist_ok=True)
    tables = {
        "patients": patients,
        "providers": providers,
        "episodes": episodes,
        "claims": claims,
        "clinical_notes": notes,
    }
    for name, rows in tables.items():
        write_jsonl(DATASET_DIR / f"{name}.jsonl", rows)
    manifest = {
        "dataset_version": "v0-interim",
        "generator_version": "interim-handwritten-1",
        "seed": 0,
        "generated_at": "2026-10-02T00:00:00+07:00",
        "contract_version": "data-contract/1",
        "counts": {k: len(v) for k, v in tables.items()},
    }
    (DATASET_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_jsonl(POLICY_DIR / "policy_sections.jsonl", policy_sections)
    (POLICY_DIR / "manifest.json").write_text(
        json.dumps({"corpus_version": "pc-0-interim", "contract_version": "data-contract/1"}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {DATASET_DIR} and {POLICY_DIR}")


if __name__ == "__main__":
    main()
