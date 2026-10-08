"""Independent evaluation scenarios. Never imported by the backend or placed in source tables.

Expectations describe documented context, not whether a claim is legitimate. Gaps intentionally
avoid the current lexicon; their clinical expectations must not be weakened to match the engine.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Variant:
    id: str
    key: str
    text: str
    state: str = "FOUND"
    encounter: str = "INPATIENT"
    first_only: bool = False
    other_text: str | None = None
    availability: str = "AVAILABLE"
    performed: str = "36.06"
    known_gap: str | None = None


E = "EMERGENCY_CONTEXT"
C = "CHRONIC_CONDITION_CONTEXT"
S = "SCHEDULED_PROCEDURE_CONTEXT"
F = "SUPPORTING_EXAM_FOLLOWUP_CONTEXT"
J = "CLINICAL_JUSTIFICATION"

# Accepted limitations are precise, conservative outputs, never an exemption for unsafe closure.
KNOWN_GAP_STATES = {
    "P11": {E: {"expected": "FOUND", "actual": "NOT_FOUND"}},
    "P17": {C: {"expected": "FOUND", "actual": "NOT_FOUND"}},
    "P23": {"SCHEDULE_CONSISTENCY": {"expected": "FOUND", "actual": "NOT_FOUND"}},
    "P28": {F: {"expected": "FOUND", "actual": "NOT_FOUND"}},
}

VARIANTS = [
    Variant("P01", E, "Pasien diterima di UGD dan mendapat penanganan segera."),
    Variant("P02", E, "Terjadi penurunan kesadaran pada kedatangan kali ini."),
    Variant("P03", E, "Pasien distabilisasi langsung dalam ruangan resusitasi."),
    Variant("P04", E, "The patient was stabilized in the resuscitation area."),
    Variant("P05", E, "Tidak ada tanda kegawatdaruratan saat kunjungan ini.", "NOT_FOUND"),
    Variant("P06", E, "Pasien masuk secara elektif dengan keadaan stabil.", "NOT_FOUND"),
    Variant("P07", E, "Pasien diantar ambulans untuk kontrol rutin.", "NOT_FOUND"),
    Variant(
        "P08",
        E,
        "Jika memburuk, pasien akan ditangani di ruang resusitasi.",
        "NOT_FOUND",
    ),
    Variant("P09", E, "Riwayat syok dua tahun lalu. Saat ini kondisi stabil.", "NOT_FOUND"),
    Variant(
        "P10",
        E,
        "Jika terjadi syok, segera hubungi dokter. Saat ini kondisi stabil.",
        "NOT_FOUND",
    ),
    Variant(
        "P11",
        E,
        "Resusitasi dilakukan segera setelah pasien tiba dengan henti napas.",
        known_gap="Active resuscitation is worded outside the current phrase patterns.",
    ),
    Variant(
        "P12",
        E,
        "Pasien mengalami kegawatdaruratan pada perawatan pertama.",
        "NOT_FOUND",
        first_only=True,
    ),
    Variant("P13", C, "Pasien memiliki penyakit menahun yang memerlukan pemantauan."),
    Variant(
        "P14",
        C,
        "Penyakit kronis telah terdokumentasi pada kunjungan sebelumnya.",
        first_only=True,
    ),
    Variant("P15", C, "Chronic disease follow-up is documented."),
    Variant("P16", C, "Tidak ada penyakit kronis yang tercatat.", "NOT_FOUND"),
    Variant(
        "P17",
        C,
        "Diagnosis gagal ginjal telah berlangsung selama lima tahun.",
        known_gap="Duration implies chronic context but no chronic lexicon phrase is present.",
    ),
    Variant(
        "P18",
        S,
        "Tindakan ICD-9-CM 36.06 dijadwalkan pada perawatan berikutnya.",
        first_only=True,
    ),
    Variant(
        "P19",
        S,
        "PCI tahap II dengan kode 36.06 merupakan kelanjutan terapi.",
        first_only=True,
    ),
    Variant(
        "P20",
        S,
        "Scheduled procedure 36.06 will be performed at the next admission.",
        first_only=True,
    ),
    Variant(
        "P21",
        S,
        "Tidak ada tindakan 36.06 yang dijadwalkan.",
        "NOT_FOUND",
        first_only=True,
    ),
    Variant(
        "P22",
        S,
        "Rencana tindakan 36.06 dilakukan bertahap.",
        first_only=True,
        performed="36.07",
    ),
    Variant(
        "P23",
        S,
        "Tindakan dijadwalkan. Kode prosedur adalah 36.06.",
        first_only=True,
        known_gap="Plan and procedure code occur in separate sentences.",
    ),
    Variant(
        "P24",
        F,
        "Kunjungan untuk konsultasi hasil laboratorium.",
        encounter="OUTPATIENT",
    ),
    Variant(
        "P25",
        F,
        "Pasien membawa hasil endoskopi untuk dibahas bersama dokter.",
        encounter="OUTPATIENT",
    ),
    Variant("P26", F, "Hasil USG dibahas pada kunjungan ulang.", encounter="OUTPATIENT"),
    Variant(
        "P27",
        F,
        "Pasien tidak membawa hasil pemeriksaan penunjang.",
        "NOT_FOUND",
        encounter="OUTPATIENT",
    ),
    Variant(
        "P28",
        F,
        "Kunjungan ini untuk menelaah temuan pencitraan dari pemeriksaan kemarin.",
        encounter="OUTPATIENT",
        known_gap="Exam follow-up is expressed without the current phrase list.",
    ),
    Variant("P29", J, "Perawatan ulang atas indikasi medis yang terdokumentasi."),
    Variant("P30", J, "Keluhan memberat sehingga memerlukan evaluasi ulang."),
    Variant("P31", J, "Decompensated heart failure memerlukan penanganan ulang."),
    Variant("P32", J, "Tidak ada komplikasi. Kondisi stabil.", "NOT_FOUND"),
    Variant("P33", J, "Pasien tanpa perburukan. Kondisi stabil.", "NOT_FOUND"),
    Variant(
        "P34",
        E,
        "Pasien mengalami syok saat tiba.",
        "CONFLICTING",
        other_text="Tidak ada syok pada pemeriksaan saat tiba.",
    ),
    Variant(
        "P35",
        C,
        "Penyakit kronis terkonfirmasi.",
        "CONFLICTING",
        other_text="Tidak ada penyakit kronis dalam catatan ini.",
    ),
    Variant("P36", E, "", "UNAVAILABLE", availability="UNAVAILABLE"),
    Variant("P37", E, "", "UNAVAILABLE", availability="RESTRICTED"),
    Variant("P38", E, "Tanpa syok dan tanpa penurunan kesadaran.", "NOT_FOUND"),
    Variant(
        "P39",
        F,
        "Konsultasi hasil laboratorium dilakukan pada kunjungan pertama.",
        "NOT_FOUND",
        encounter="OUTPATIENT",
        first_only=True,
    ),
    Variant("P40", E, "UGD dicatat pada episode awal saja.", "NOT_FOUND", first_only=True),
]
