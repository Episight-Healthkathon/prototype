"""EPISIGHT official synthetic dataset generator (Person 3).

Writes, for one dataset version:
  data/synthetic/<version>/        manifest + 5 JSONL files (agent-readable, Data Contract v1 §2-§3.5)
  data/policies/<corpus_version>/  curated policy corpus (§3.6)
  data/ground-truth/<version>/     cases.jsonl (§3.7) + README.md. NEVER ingested by the backend.

Run from the repo root:
  python data/generator/generate_dataset.py                 # default seed, writes v0.1.0
  python data/generator/generate_dataset.py --seed 7 --noise-patients 30 --version v0.1.0-s7
  python data/generator/generate_dataset.py --reset         # delete the version's outputs first

Determinism: the same seed gives byte-identical files. Golden cases A-E never use the random
generator, so they are identical for every seed. Benchmark cases take their dates (small shift) and
wording variants from the seeded generator; IDs are allocated in a fixed order and do not depend on
the seed. Everything is synthetic: no real participants, no copied notes.

Writing rules that keep cases meaningful (see docs/03_PERSON_3_DATA_EVALUATION.md §0.4):
- context for EMERGENCY / CLINICAL_JUSTIFICATION / SUPPORTING_EXAM goes in the repeat episode's notes;
- every INPATIENT episode registers a DISCHARGE_SUMMARY unless the case is about it being missing;
- decimals in notes use a comma ("39,6 C") so they never look like ICD-9-CM codes; times use ":".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

GENERATOR_VERSION = "gen-0.1.0"
CONTRACT_VERSION = "data-contract/1"
DEFAULT_SEED = 20261004
DEFAULT_VERSION = "v0.1.0"
CORPUS_VERSION = "pc-0.1.1"
TZ = "+07:00"
REPO = Path(__file__).resolve().parents[2]

READMISSION, FRAGMENTATION = "READMISSION", "FRAGMENTATION"
CTX_NOTE, POLICY, EPISODE = "CLINICAL_NOTE", "POLICY_SECTION", "EPISODE_RECORD"
RISK, CONTEXT, NEUTRAL, IRRELEVANT = "SUPPORTING_RISK", "EXPLAINING_CONTEXT", "NEUTRAL", "IRRELEVANT"

POL_RA_DEF = "POL-PMK26-2021-READMISI-01"
POL_RA_EXC = "POL-PMK26-2021-READMISI-02"
POL_FR_DEF = "POL-PMK26-2021-FRAGMENTASI-01"
POL_FR_EXC = "POL-PMK26-2021-FRAGMENTASI-02"

PROVIDERS = [
    {"provider_id": "PRV-0001", "name": "RS Sintetis Nusantara 01", "provider_type": "FKRTL", "hospital_class": "B",
     "region": "Wilayah Sintetis A"},
    {"provider_id": "PRV-0002", "name": "RS Sintetis Nusantara 02", "provider_type": "FKRTL", "hospital_class": "C",
     "region": "Wilayah Sintetis A"},
    {"provider_id": "PRV-0003", "name": "RS Sintetis Nusantara 03", "provider_type": "FKRTL", "hospital_class": "B",
     "region": "Wilayah Sintetis B"},
    {"provider_id": "PRV-0004", "name": "RS Sintetis Nusantara 04", "provider_type": "FKRTL", "hospital_class": "A",
     "region": "Wilayah Sintetis B"},
    {"provider_id": "PRV-0005", "name": "RS Sintetis Nusantara 05", "provider_type": "FKRTL", "hospital_class": "C",
     "region": "Wilayah Sintetis C"},
    {"provider_id": "PRV-0006", "name": "RS Sintetis Nusantara 06", "provider_type": "FKRTL", "hospital_class": "D",
     "region": "Wilayah Sintetis C"},
]

INACBG = {
    "I50.0": "I-4-12-I", "I50.1": "I-4-12-I", "I25.1": "I-4-10-I", "I20.0": "I-4-13-I", "J18.9": "J-4-16-I",
    "N39.0": "N-4-10-I", "K30": "Q-5-44-0", "K29.7": "Q-5-44-0", "J44.1": "J-4-17-I", "D50.9": "Q-5-30-0",
    "J45.9": "Q-5-18-0", "A09": "K-4-17-I", "E11.3": "Q-5-42-0", "M54.5": "Q-5-35-0", "I63.9": "G-4-14-I",
    "K92.2": "K-4-13-I", "L03.1": "L-4-13-I", "A91": "A-4-14-I", "E87.1": "E-4-12-I", "N18.5": "N-3-15-0",
    "R51": "Q-5-18-0", "K35.8": "K-1-12-I", "E11.9": "Q-5-42-0", "H25.9": "Q-5-21-0", "J06.9": "Q-5-18-0",
    "M17.9": "Q-5-35-0", "B34.9": "Q-5-18-0", "K59.0": "Q-5-44-0",
}


def ts(day: date, time: str = "08:00") -> str:
    return f"{day.isoformat()}T{time}:00{TZ}"


@dataclass
class GroundTruth:
    gt_id: str
    golden_case: str | None
    scenario_class: str
    expected_signal_type: str | None
    anchor_episode_ids: list[str]
    expected_related_episode_ids: list[str]
    expected_evidence: list[dict] = field(default_factory=list)
    expected_exceptions: list[str] = field(default_factory=list)
    expected_requirement_states: dict[str, str] = field(default_factory=dict)
    expected_outcome: str | None = None
    expected_stop_reason: str | None = None
    notes_for_reviewers: str = ""
    # Evaluation-only extras (not part of §3.7's required set; ignored by anything but the harness)
    tags: list[str] = field(default_factory=list)

    def row(self) -> dict:
        return {
            "gt_id": self.gt_id,
            "golden_case": self.golden_case,
            "scenario_class": self.scenario_class,
            "expected_signal_type": self.expected_signal_type,
            "anchor_episode_ids": sorted(self.anchor_episode_ids),
            "expected_related_episode_ids": sorted(self.expected_related_episode_ids),
            "expected_evidence": self.expected_evidence,
            "expected_exceptions": self.expected_exceptions,
            "expected_requirement_states": self.expected_requirement_states,
            "expected_outcome": self.expected_outcome,
            "expected_stop_reason": self.expected_stop_reason,
            "notes_for_reviewers": self.notes_for_reviewers,
            "tags": self.tags,
        }


def ev(source_type: str, source_id: str, key: str, category: str, mandatory: bool = True) -> dict:
    return {"source_type": source_type, "source_id": source_id, "requirement_key": key, "category": category,
            "mandatory": mandatory}


def policy_labels(signal: str) -> list[dict]:
    """Readmission cases should cite the readmission sections; fragmentation sections are off-topic (and vice versa)."""
    own = [POL_RA_DEF, POL_RA_EXC] if signal == READMISSION else [POL_FR_DEF, POL_FR_EXC]
    other = [POL_FR_DEF, POL_FR_EXC] if signal == READMISSION else [POL_RA_DEF, POL_RA_EXC]
    return [ev(POLICY, p, "APPLICABLE_POLICY", NEUTRAL, mandatory=False) for p in own] + [
        ev(POLICY, p, "APPLICABLE_POLICY", IRRELEVANT, mandatory=False) for p in other
    ]


class Builder:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.patients: list[dict] = []
        self.episodes: list[dict] = []
        self.notes: list[dict] = []
        self.claims: list[dict] = []
        self.truth: list[GroundTruth] = []
        self._n_pat = self._n_epi = self._n_note = 0

    # ---- seeded helpers (benchmark cases only; golden cases never call these) -------------------------
    def shift(self, base: date, max_days: int = 20) -> date:
        return base + timedelta(days=self.rng.randint(0, max_days))

    def pick(self, options: list[str]) -> str:
        return options[self.rng.randrange(len(options))]

    # ---- entities -------------------------------------------------------------------------------------
    def patient(self, birth_year: int, sex: str, chronic: list[str] | None = None) -> str:
        self._n_pat += 1
        pid = f"PAT-{self._n_pat:06d}"
        self.patients.append({"patient_id": pid, "birth_year": birth_year, "sex": sex,
                              "chronic_conditions": chronic or []})
        return pid

    def _episode(self, pid: str, prv: str, enc: str, start: str | None, end: str | None, dx: str, *, sec=(),
                 procs=(), adm=None, discharge=None, cls=None, episode_id: str | None = None) -> str:
        if episode_id is None:
            self._n_epi += 1
            episode_id = f"EPI-{self._n_epi:06d}"
        self.episodes.append({
            "episode_id": episode_id, "patient_id": pid, "provider_id": prv, "encounter_type": enc,
            "start_at": start, "end_at": end, "admission_type": adm, "primary_diagnosis": dx,
            "secondary_diagnoses": list(sec), "procedures": [dict(p) for p in procs],
            "discharge_status": discharge, "class_of_care": cls,
        })
        self.claims.append({
            "claim_id": episode_id.replace("EPI", "CLM"), "episode_id": episode_id,
            "submitted_at": end or start or ts(date(2026, 9, 1)), "inacbg_code": INACBG.get(dx),
            "claimed_amount_idr": 4_850_000 if enc == "INPATIENT" else 215_000, "claim_status": "SUBMITTED",
        })
        return episode_id

    def inpatient(self, pid, prv, admit: date, admit_time: str, days: int, dx, *, sec=(), procs=(), adm=None,
                  discharge="HOME", cls="3") -> str:
        return self._episode(pid, prv, "INPATIENT", ts(admit, admit_time), ts(admit + timedelta(days=days), "10:00"),
                             dx, sec=sec, procs=procs, adm=adm, discharge=discharge, cls=cls)

    def outpatient(self, pid, prv, day: date | None, time: str, dx, *, sec=(), procs=()) -> str:
        return self._episode(pid, prv, "OUTPATIENT", ts(day, time) if day else None, None, dx, sec=sec, procs=procs)

    def duplicate_row(self, episode_id: str) -> str:
        """An exact content duplicate of an episode under a new ID (data-quality fixture)."""
        src = next(e for e in self.episodes if e["episode_id"] == episode_id)
        return self._episode(src["patient_id"], src["provider_id"], src["encounter_type"], src["start_at"],
                             src["end_at"], src["primary_diagnosis"], sec=src["secondary_diagnoses"],
                             procs=src["procedures"], adm=src["admission_type"], discharge=src["discharge_status"],
                             cls=src["class_of_care"])

    def note(self, eid: str, ntype: str, authored: str, text: str | None, title: str,
             availability: str = "AVAILABLE") -> str:
        self._n_note += 1
        nid = f"NOTE-{self._n_note:06d}"
        self.notes.append({
            "note_id": nid, "episode_id": eid, "note_type": ntype, "title": title, "authored_at": authored,
            "language": "id", "availability": availability,
            "text": text if availability == "AVAILABLE" else None,
        })
        return nid

    def discharge(self, eid: str, text: str | None, availability: str = "AVAILABLE") -> str:
        ep = next(e for e in self.episodes if e["episode_id"] == eid)
        authored = ep["end_at"].replace("T10:00", "T09:30")
        return self.note(eid, "DISCHARGE_SUMMARY", authored, text, "Ringkasan pulang", availability)

    def add(self, gt: GroundTruth) -> None:
        self.truth.append(gt)


# =====================================================================================================
# Golden cases A-E (fixed; no randomness)
# =====================================================================================================

def golden_a(b: Builder) -> None:
    pid = b.patient(1961, "M", ["I50.0", "I10"])
    prv = "PRV-0001"
    op = b.outpatient(pid, prv, date(2026, 2, 16), "09:30", "I50.0", sec=["I10"])
    n_op = b.note(op, "OUTPATIENT_VISIT", ts(date(2026, 2, 16), "10:00"),
                  "Kontrol rutin poli jantung. Riwayat gagal jantung menahun sejak 2021 disertai hipertensi. "
                  "Sesak bila berjalan sekitar 100 meter, edema tungkai minimal. Terapi bisoprolol, furosemide "
                  "dan spironolakton dilanjutkan.", "Kunjungan poli jantung")
    e1 = b.inpatient(pid, prv, date(2026, 3, 2), "09:00", 4, "I50.0", sec=["I10"],
                     procs=[{"code": "89.52"}, {"code": "87.44"}])
    b.discharge(e1, "Ringkasan pulang. Dirawat dengan gagal jantung kongestif NYHA III. Mendapat diuretik "
                    "intravena, sesak berkurang dan berat badan turun 3 kg. Pulang dalam kondisi stabil dengan edukasi "
                    "pembatasan cairan dan garam. Kontrol poli jantung dalam 2 minggu.")
    e2 = b.inpatient(pid, prv, date(2026, 3, 12), "22:10", 5, "I50.0", sec=["I10"], procs=[{"code": "89.52"}])
    n_tri = b.note(e2, "TRIAGE", ts(date(2026, 3, 12), "22:15"),
                   "Pasien diantar keluarga ke Instalasi Gawat Darurat pada malam hari dengan sesak napas hebat sejak "
                   "sore, harus duduk untuk bernapas. Saturasi oksigen 84% dengan udara ruang, TD 180/105 mmHg, "
                   "frekuensi napas 34x/menit, ronki basah di kedua basal paru. Kategori triase merah, langsung "
                   "ditangani di ruang resusitasi.", "Catatan triase IGD")
    n_prog = b.note(e2, "PROGRESS", ts(date(2026, 3, 14), "08:00"),
                    "Catatan perkembangan hari ke-2. Sesak berkurang dengan oksigen dan furosemide intravena. Keluhan "
                    "serupa dengan perawatan bulan lalu, pencetus kali ini infeksi saluran napas dan asupan cairan "
                    "berlebih.", "Catatan perkembangan")
    n_ds2 = b.discharge(e2, "Ringkasan pulang. Masuk melalui IGD dengan gagal jantung dekompensasi akut disertai "
                            "edema paru akut. Perburukan dipicu infeksi saluran napas atas dan ketidakpatuhan "
                            "pembatasan cairan. Pulang dalam kondisi stabil.")
    b.add(GroundTruth(
        "GT-A", "A", "LEGIT_READMISSION_EMERGENCY", READMISSION, [e1, e2], [op, e1, e2],
        expected_evidence=[
            ev(CTX_NOTE, n_tri, "EMERGENCY_CONTEXT", CONTEXT),
            ev(CTX_NOTE, n_ds2, "EMERGENCY_CONTEXT", CONTEXT, mandatory=False),
            ev(CTX_NOTE, n_op, "CHRONIC_CONDITION_CONTEXT", CONTEXT),
            ev(CTX_NOTE, n_ds2, "CLINICAL_JUSTIFICATION", CONTEXT),
            ev(CTX_NOTE, n_tri, "CLINICAL_JUSTIFICATION", CONTEXT, mandatory=False),
            ev(CTX_NOTE, n_prog, "RISK_INDICATORS_IN_NOTES", RISK),
            ev(CTX_NOTE, n_prog, "CLINICAL_JUSTIFICATION", CONTEXT, mandatory=False),
            *policy_labels(READMISSION),
        ],
        expected_exceptions=["EMERGENCY_CONTEXT", "CHRONIC_CONDITION_CONTEXT"],
        expected_requirement_states={"EMERGENCY_CONTEXT": "FOUND", "CHRONIC_CONDITION_CONTEXT": "FOUND",
                                     "CLINICAL_JUSTIFICATION": "FOUND", "RISK_INDICATORS_IN_NOTES": "FOUND"},
        expected_outcome="EVIDENCE_SUFFICIENT", expected_stop_reason="SUFFICIENT_EVIDENCE",
        notes_for_reviewers="Heart-failure readmission 6 days after discharge. Emergency presentation is documented "
                            "only in the repeat episode's triage note and discharge summary (admission_type null). "
                            "Chronic context sits in a prior related outpatient visit. A risk indicator (similar "
                            "complaint) is still present, so the brief must show both sides.",
        tags=["golden", "hard-negative"],
    ))


def golden_b(b: Builder) -> None:
    pid = b.patient(1987, "F")
    prv = "PRV-0002"
    v1 = b.outpatient(pid, prv, date(2026, 4, 6), "08:30", "K30")
    b.note(v1, "OUTPATIENT_VISIT", ts(date(2026, 4, 6), "09:00"),
           "Kunjungan poli penyakit dalam. Keluhan perut kembung, nyeri ulu hati dan cepat kenyang sejak 1 minggu. "
           "Nyeri tekan epigastrium ringan, tanda vital stabil. Diagnosis dispepsia fungsional. Diberikan lansoprazole "
           "dan domperidone. Disarankan kembali bila keluhan menetap.", "Kunjungan poli penyakit dalam")
    v2 = b.outpatient(pid, prv, date(2026, 4, 9), "09:15", "K30")
    n2 = b.note(v2, "OUTPATIENT_VISIT", ts(date(2026, 4, 9), "09:40"),
                "Kunjungan ulang poli penyakit dalam. Keluhan kembung dan nyeri ulu hati belum membaik. Pemeriksaan "
                "fisik sama dengan kunjungan sebelumnya. Obat dilanjutkan dengan penambahan antasida.",
                "Kunjungan ulang poli penyakit dalam")
    v3 = b.outpatient(pid, prv, date(2026, 4, 13), "10:00", "K30")
    n3 = b.note(v3, "OUTPATIENT_VISIT", ts(date(2026, 4, 13), "10:20"),
                "Kunjungan poli penyakit dalam. Keluhan masih ada, pasien meminta resep ulang. Tanda vital dalam "
                "batas normal. Edukasi pola makan, obat diteruskan.", "Kunjungan poli penyakit dalam")
    b.add(GroundTruth(
        "GT-B", "B", "POTENTIAL_FRAGMENTATION", FRAGMENTATION, [v1, v2, v3], [v1, v2, v3],
        expected_evidence=[
            ev(CTX_NOTE, n2, "RISK_INDICATORS_IN_NOTES", RISK),
            ev(CTX_NOTE, n3, "RISK_INDICATORS_IN_NOTES", RISK),
            *policy_labels(FRAGMENTATION),
        ],
        expected_exceptions=[],
        expected_requirement_states={"EMERGENCY_CONTEXT": "NOT_FOUND", "CHRONIC_CONDITION_CONTEXT": "NOT_FOUND",
                                     "SCHEDULED_PROCEDURE_CONTEXT": "NOT_FOUND",
                                     "SUPPORTING_EXAM_FOLLOWUP_CONTEXT": "NOT_FOUND",
                                     "CLINICAL_JUSTIFICATION": "NOT_FOUND", "RISK_INDICATORS_IN_NOTES": "FOUND"},
        expected_outcome="HUMAN_REVIEW_REQUIRED", expected_stop_reason="EVIDENCE_PATHS_EXHAUSTED",
        notes_for_reviewers="Three dyspepsia outpatient visits within 7 days (3 d, 4 d) chain into one case. Notes "
                            "are readable and contain no emergency, chronic, scheduled or supporting-exam context; "
                            "complaints persist. The concern must stay unresolved (D-05), not be closed.",
        tags=["golden", "hard-positive"],
    ))


def golden_c(b: Builder) -> None:
    pid = b.patient(1956, "M", ["I25.1"])
    prv = "PRV-0003"
    e1 = b.inpatient(pid, prv, date(2026, 5, 4), "08:00", 2, "I25.1",
                     procs=[{"code": "88.56", "performed_at": ts(date(2026, 5, 4), "10:00")}], adm="ELECTIVE", cls="2")
    b.note(e1, "PROCEDURE_REPORT", ts(date(2026, 5, 4), "11:30"),
           "Laporan angiografi koroner: stenosis signifikan 85% di LAD proksimal dan 75% di RCA tengah. Total kontras "
           "180 ml, fungsi ginjal pasien menurun (eGFR 42).", "Laporan angiografi koroner")
    n_plan = b.note(e1, "PROCEDURE_PLAN", ts(date(2026, 5, 6), "08:30"),
                    "Rencana tindakan: intervensi koroner perkutan bertahap, pemasangan stent LAD (ICD-9-CM 36.06) "
                    "pada perawatan berikutnya sekitar dua minggu lagi untuk membatasi beban kontras pada ginjal.",
                    "Rencana PCI bertahap")
    n_ds1 = b.discharge(e1, "Ringkasan pulang. Pasca angiografi koroner, tanpa nyeri dada, kreatinin stabil. Pasien "
                            "akan masuk kembali untuk PCI tahap II.")
    e2 = b.inpatient(pid, prv, date(2026, 5, 20), "07:30", 2, "I25.1",
                     procs=[{"code": "36.06", "performed_at": ts(date(2026, 5, 20), "09:30")}], adm="ELECTIVE", cls="2")
    b.note(e2, "PROCEDURE_REPORT", ts(date(2026, 5, 20), "11:00"),
           "Laporan PCI: satu stent di LAD proksimal, aliran akhir TIMI 3, tanpa komplikasi.", "Laporan PCI")
    b.discharge(e2, "Ringkasan pulang. Pasca PCI kondisi stabil. Lanjut dual antiplatelet dan kontrol poli jantung.")
    b.add(GroundTruth(
        "GT-C", "C", "LEGIT_STAGED_PROCEDURE", READMISSION, [e1, e2], [e1, e2],
        expected_evidence=[
            ev(CTX_NOTE, n_plan, "SCHEDULED_PROCEDURE_CONTEXT", CONTEXT),
            ev(CTX_NOTE, n_ds1, "SCHEDULED_PROCEDURE_CONTEXT", CONTEXT, mandatory=False),
            ev(CTX_NOTE, n_plan, "SCHEDULE_CONSISTENCY", CONTEXT),
            ev(EPISODE, e2, "SCHEDULE_CONSISTENCY", CONTEXT),
            ev(CTX_NOTE, n_plan, "CLINICAL_JUSTIFICATION", CONTEXT, mandatory=False),
            *policy_labels(READMISSION),
        ],
        expected_exceptions=["SCHEDULED_PROCEDURE_CONTEXT"],
        expected_requirement_states={"SCHEDULED_PROCEDURE_CONTEXT": "FOUND", "SCHEDULE_CONSISTENCY": "FOUND"},
        expected_outcome="EVIDENCE_SUFFICIENT", expected_stop_reason="SUFFICIENT_EVIDENCE",
        notes_for_reviewers="Staged PCI: the plan in episode 1 names ICD-9-CM 36.06 and episode 2 records 36.06 as "
                            "performed 14 days after discharge. Wording avoids 'dijadwalkan'; the plan uses "
                            "'rencana tindakan' and 'bertahap', the discharge summary 'tahap II'.",
        tags=["golden", "hard-negative"],
    ))


def golden_d(b: Builder) -> None:
    pid = b.patient(1970, "F")
    prv = "PRV-0001"
    e1 = b.inpatient(pid, prv, date(2026, 6, 1), "14:00", 4, "J18.9")
    b.discharge(e1, "Ringkasan pulang. Pneumonia komunitas lobus kanan bawah, antibiotik intravena 4 hari, demam "
                    "turun. Pulang dengan antibiotik oral 5 hari.")
    e2 = b.inpatient(pid, prv, date(2026, 6, 16), "19:20", 4, "J18.9")
    n_tri = b.note(e2, "TRIAGE", ts(date(2026, 6, 16), "19:30"), None, "Catatan triase IGD", "UNAVAILABLE")
    n_prog = b.note(e2, "PROGRESS", ts(date(2026, 6, 17), "08:00"), None, "Catatan perkembangan", "UNAVAILABLE")
    n_ds2 = b.discharge(e2, None, "RESTRICTED")
    b.add(GroundTruth(
        "GT-D", "D", "MISSING_EVIDENCE", READMISSION, [e1, e2], [e1, e2],
        expected_evidence=[*policy_labels(READMISSION)],
        expected_exceptions=[],
        expected_requirement_states={"CLINICAL_DOCUMENT_AVAILABILITY": "UNAVAILABLE",
                                     "EMERGENCY_CONTEXT": "UNAVAILABLE", "CLINICAL_JUSTIFICATION": "UNAVAILABLE"},
        expected_outcome="EVIDENCE_UNAVAILABLE", expected_stop_reason="REQUIRED_EVIDENCE_UNAVAILABLE",
        notes_for_reviewers=f"Pneumonia readmission 11 days after discharge. All repeat-episode documents are "
                            f"registered but unreadable ({n_tri}, {n_prog} UNAVAILABLE; {n_ds2} RESTRICTED). The "
                            f"agent must not infer context; uncertainty must stay explicit.",
        tags=["golden", "missing"],
    ))


def golden_e(b: Builder) -> None:
    pid = b.patient(1978, "F")
    prv = "PRV-0002"
    e1 = b.inpatient(pid, prv, date(2026, 7, 1), "10:00", 3, "N39.0")
    b.discharge(e1, "Ringkasan pulang. Infeksi saluran kemih, antibiotik intravena 3 hari, pulang dengan antibiotik "
                    "oral.")
    e2 = b.inpatient(pid, prv, date(2026, 7, 10), "23:30", 4, "N39.0")
    n_tri = b.note(e2, "TRIAGE", ts(date(2026, 7, 10), "23:35"),
                   "Pasien datang ke IGD tengah malam dengan demam 39,6 C, menggigil dan nyeri pinggang kiri. Tampak "
                   "lemah, TD 90/60 mmHg. Kategori triase kuning-merah.", "Catatan triase IGD")
    n_ds2 = b.discharge(e2, "Ringkasan pulang. Pasien menjalani admisi elektif untuk evaluasi infeksi saluran kemih "
                            "berulang dan pemberian antibiotik intravena. Saat masuk tidak dalam kondisi gawat "
                            "darurat.")
    b.add(GroundTruth(
        "GT-E", "E", "CONFLICTING_EVIDENCE", READMISSION, [e1, e2], [e1, e2],
        expected_evidence=[
            ev(CTX_NOTE, n_tri, "EMERGENCY_CONTEXT", CONTEXT),
            ev(CTX_NOTE, n_ds2, "EMERGENCY_CONTEXT", RISK),
            *policy_labels(READMISSION),
        ],
        expected_exceptions=[],
        expected_requirement_states={"EMERGENCY_CONTEXT": "CONFLICTING"},
        expected_outcome="EVIDENCE_CONFLICTING", expected_stop_reason="CONFLICTING_EVIDENCE",
        notes_for_reviewers="UTI readmission 6 days after discharge. The triage note documents an emergency "
                            "presentation; the discharge summary of the same episode states an elective admission "
                            "and no emergency. Both sides must remain visible; no forced conclusion.",
        tags=["golden", "conflict"],
    ))


# =====================================================================================================
# Benchmark cases (seeded dates/wording; expected behaviour fixed)
# =====================================================================================================

def bm_chronic_readmission(b: Builder) -> None:
    pid = b.patient(1955, "M", ["J44.1"])
    prv = "PRV-0004"
    d1 = b.shift(date(2026, 1, 12))
    e1 = b.inpatient(pid, prv, d1, "11:00", 5, "J44.1")
    n_ds1 = b.discharge(e1, "Ringkasan pulang. Eksaserbasi PPOK dengan sesak dan dahak bertambah. Nebulisasi, steroid "
                    "sistemik dan antibiotik oral. Pulang dengan inhaler rutin.")
    e2 = b.inpatient(pid, prv, d1 + timedelta(days=5 + 18), "13:00", 5, "J44.1")
    adm_txt = b.pick([
        ("Pasien PPOK lama dengan sesak bertambah dan dahak purulen sejak 3 hari. Riwayat merokok 30 tahun, memakai "
        "inhaler tiotropium."),
        ("Pasien dengan penyakit paru obstruktif kronik datang dengan sesak bertambah dan dahak kehijauan. Riwayat "
        "merokok lama, memakai inhaler tiotropium."),
    ])
    n_adm = b.note(e2, "ADMISSION", ts(d1 + timedelta(days=23), "13:30"), adm_txt, "Catatan masuk")
    b.discharge(e2, "Ringkasan pulang. Eksaserbasi akut teratasi dengan nebulisasi dan steroid sistemik. Pulang "
                    "dengan inhaler rutin dan rujukan rehabilitasi paru.")
    b.add(GroundTruth(
        "GT-B01", None, "LEGIT_CHRONIC", READMISSION, [e1, e2], [e1, e2],
        expected_evidence=[ev(CTX_NOTE, n_adm, "CHRONIC_CONDITION_CONTEXT", CONTEXT),
                           ev(CTX_NOTE, n_ds1, "CHRONIC_CONDITION_CONTEXT", CONTEXT, mandatory=False),
                           *policy_labels(READMISSION)],
        expected_exceptions=["CHRONIC_CONDITION_CONTEXT"],
        expected_requirement_states={"CHRONIC_CONDITION_CONTEXT": "FOUND"},
        expected_outcome="EVIDENCE_SUFFICIENT", expected_stop_reason="SUFFICIENT_EVIDENCE",
        notes_for_reviewers="COPD readmission 18 days after discharge; chronic disease documented in the repeat "
                            "admission note. No emergency wording.",
        tags=["hard-negative", "chronic"],
    ))


def bm_supporting_exam_boundary(b: Builder) -> None:
    pid = b.patient(1990, "F")
    prv = "PRV-0005"
    d1 = b.shift(date(2026, 2, 2))
    v1 = b.outpatient(pid, prv, d1, "09:00", "D50.9")
    b.note(v1, "OUTPATIENT_VISIT", ts(d1, "09:30"),
           "Kunjungan poli penyakit dalam. Pasien lemas dan tampak pucat sejak 1 bulan, Hb kapiler 8,9 g/dL. Diminta "
           "periksa darah lengkap, feritin dan saturasi transferin.", "Kunjungan poli penyakit dalam")
    v2 = b.outpatient(pid, prv, d1 + timedelta(days=7), "09:00", "D50.9")
    txt = b.pick([
        ("Kunjungan untuk konsultasi hasil laboratorium: Hb 8,7 g/dL, feritin rendah, sesuai anemia defisiensi besi. "
        "Terapi besi oral dimulai."),
        ("Pasien kembali membawa hasil laboratorium yang diminta: feritin dan saturasi transferin rendah. Diagnosis "
        "anemia defisiensi besi, terapi besi oral dimulai."),
    ])
    n2 = b.note(v2, "OUTPATIENT_VISIT", ts(d1 + timedelta(days=7), "09:30"), txt, "Kontrol poli penyakit dalam")
    b.add(GroundTruth(
        "GT-B02", None, "LEGIT_SUPPORTING_EXAM_FOLLOWUP", FRAGMENTATION, [v1, v2], [v1, v2],
        expected_evidence=[ev(CTX_NOTE, n2, "SUPPORTING_EXAM_FOLLOWUP_CONTEXT", CONTEXT),
                           *policy_labels(FRAGMENTATION)],
        expected_exceptions=["SUPPORTING_EXAM_FOLLOWUP_CONTEXT"],
        expected_requirement_states={"SUPPORTING_EXAM_FOLLOWUP_CONTEXT": "FOUND"},
        expected_outcome="EVIDENCE_SUFFICIENT", expected_stop_reason="SUFFICIENT_EVIDENCE",
        notes_for_reviewers="Second visit exactly 7 days later (inclusive threshold) to review requested lab "
                            "results.",
        tags=["hard-negative", "boundary"],
    ))


def bm_emergency_fragmentation(b: Builder) -> None:
    pid = b.patient(1999, "M")
    prv = "PRV-0006"
    d1 = b.shift(date(2026, 3, 2))
    v1 = b.outpatient(pid, prv, d1, "10:00", "J45.9")
    b.note(v1, "OUTPATIENT_VISIT", ts(d1, "10:30"),
           "Kontrol poli paru. Asma terkontrol sebagian, memakai inhaler budesonide-formoterol. Edukasi teknik "
           "inhalasi.", "Kunjungan poli paru")
    v2 = b.outpatient(pid, prv, d1 + timedelta(days=4), "02:40", "J45.9")
    txt = b.pick([
        ("Pasien datang ke UGD dini hari dengan serangan sesak berat, bicara terputus-putus, saturasi 88%. Diberikan "
        "nebulisasi berulang dan steroid intravena, pulang setelah sesak mereda."),
        ("Kunjungan IGD dini hari: serangan asma berat, mengi difus, saturasi 87%. Nebulisasi tiga kali dan steroid "
        "intravena, pasien dipulangkan setelah stabil."),
    ])
    n2 = b.note(v2, "TRIAGE", ts(d1 + timedelta(days=4), "02:45"), txt, "Catatan IGD")
    b.add(GroundTruth(
        "GT-B03", None, "LEGIT_EMERGENCY_RETURN", FRAGMENTATION, [v1, v2], [v1, v2],
        expected_evidence=[ev(CTX_NOTE, n2, "EMERGENCY_CONTEXT", CONTEXT), *policy_labels(FRAGMENTATION)],
        expected_exceptions=["EMERGENCY_CONTEXT"],
        expected_requirement_states={"EMERGENCY_CONTEXT": "FOUND"},
        expected_outcome="EVIDENCE_SUFFICIENT", expected_stop_reason="SUFFICIENT_EVIDENCE",
        notes_for_reviewers="Asthma outpatient follow-up, then an emergency-department visit 4 days later.",
        tags=["hard-negative", "emergency"],
    ))


def bm_unresolved_readmission(b: Builder) -> None:
    pid = b.patient(1983, "M")
    prv = "PRV-0003"
    d1 = b.shift(date(2026, 3, 9))
    e1 = b.inpatient(pid, prv, d1, "15:00", 2, "A09", discharge="AGAINST_ADVICE")
    n_ds1 = b.discharge(e1, "Ringkasan pulang. Gastroenteritis akut dengan dehidrasi ringan. Pasien pulang atas "
                            "permintaan sendiri pada hari kedua sebelum terapi cairan selesai.")
    e2 = b.inpatient(pid, prv, d1 + timedelta(days=2 + 9), "16:00", 3, "A09")
    n_adm = b.note(e2, "ADMISSION", ts(d1 + timedelta(days=11), "16:30"),
                   "Pasien kembali dirawat dengan diare dan muntah, keluhan sama dengan perawatan sebelumnya. Tanda "
                   "vital stabil.", "Catatan masuk")
    b.discharge(e2, "Ringkasan pulang. Diare membaik dengan rehidrasi intravena. Pulang dalam kondisi baik.")
    b.add(GroundTruth(
        "GT-B04", None, "POTENTIAL_READMISSION", READMISSION, [e1, e2], [e1, e2],
        expected_evidence=[ev(CTX_NOTE, n_ds1, "RISK_INDICATORS_IN_NOTES", RISK),
                           ev(CTX_NOTE, n_adm, "RISK_INDICATORS_IN_NOTES", RISK),
                           ev(EPISODE, e1, "RISK_INDICATORS_IN_NOTES", RISK, mandatory=False),
                           *policy_labels(READMISSION)],
        expected_exceptions=[],
        expected_requirement_states={"EMERGENCY_CONTEXT": "NOT_FOUND", "RISK_INDICATORS_IN_NOTES": "FOUND"},
        expected_outcome="HUMAN_REVIEW_REQUIRED", expected_stop_reason="EVIDENCE_PATHS_EXHAUSTED",
        notes_for_reviewers="Discharged against advice, readmitted 9 days later with the same complaint; no "
                            "legitimate context documented.",
        tags=["hard-positive"],
    ))


def bm_staged_outpatient(b: Builder) -> None:
    pid = b.patient(1964, "F", ["E11.9"])
    prv = "PRV-0004"
    d1 = b.shift(date(2026, 3, 23))
    v1 = b.outpatient(pid, prv, d1, "08:30", "E11.3", procs=[{"code": "14.34", "performed_at": ts(d1, "09:30")}])
    plan_txt = b.pick([
        ("Panretinal photocoagulation dibagi menjadi tiga sesi. Sesi kedua (ICD-9-CM 14.34) dijadwalkan 5 hari lagi "
        "untuk area nasal mata kanan."),
        ("Laser fotokoagulasi retina dilakukan bertahap dalam tiga sesi; sesi kedua (ICD-9-CM 14.34) untuk area "
        "nasal mata kanan 5 hari lagi."),
    ])
    n_plan = b.note(v1, "PROCEDURE_PLAN", ts(d1, "10:00"), plan_txt, "Rencana laser retina")
    v2 = b.outpatient(pid, prv, d1 + timedelta(days=5), "08:30", "E11.3",
                      procs=[{"code": "14.34", "performed_at": ts(d1 + timedelta(days=5), "09:15")}])
    n2 = b.note(v2, "PROCEDURE_REPORT", ts(d1 + timedelta(days=5), "10:00"),
                "Sesi kedua laser fotokoagulasi retina mata kanan sesuai rencana, tanpa komplikasi.",
                "Laporan laser retina")
    b.add(GroundTruth(
        "GT-B05", None, "LEGIT_STAGED_PROCEDURE", FRAGMENTATION, [v1, v2], [v1, v2],
        expected_evidence=[ev(CTX_NOTE, n_plan, "SCHEDULED_PROCEDURE_CONTEXT", CONTEXT),
                           ev(CTX_NOTE, n2, "SCHEDULED_PROCEDURE_CONTEXT", CONTEXT, mandatory=False),
                           ev(CTX_NOTE, n_plan, "SCHEDULE_CONSISTENCY", CONTEXT),
                           ev(EPISODE, v2, "SCHEDULE_CONSISTENCY", CONTEXT),
                           *policy_labels(FRAGMENTATION)],
        expected_exceptions=["SCHEDULED_PROCEDURE_CONTEXT"],
        expected_requirement_states={"SCHEDULED_PROCEDURE_CONTEXT": "FOUND", "SCHEDULE_CONSISTENCY": "FOUND"},
        expected_outcome="EVIDENCE_SUFFICIENT", expected_stop_reason="SUFFICIENT_EVIDENCE",
        notes_for_reviewers="Diabetic retinopathy laser in planned sessions 5 days apart; plan names 14.34 and the "
                            "second visit records 14.34.",
        tags=["hard-negative", "scheduled"],
    ))


def bm_schedule_mismatch(b: Builder) -> None:
    pid = b.patient(1959, "M", ["I25.1"])
    prv = "PRV-0004"
    d1 = b.shift(date(2026, 4, 6))
    e1 = b.inpatient(pid, prv, d1, "08:00", 2, "I25.1",
                     procs=[{"code": "88.56", "performed_at": ts(d1, "10:00")}], adm="ELECTIVE", cls="2")
    n_plan = b.note(e1, "PROCEDURE_PLAN", ts(d1 + timedelta(days=2), "08:30"),
                    "Rencana tindakan: PCI tahap kedua pada RCA dengan stent non-drug-eluting (ICD-9-CM 36.06) "
                    "sekitar dua minggu lagi.", "Rencana PCI")
    b.discharge(e1, "Ringkasan pulang. Pasca angiografi koroner kondisi stabil, tanpa nyeri dada.")
    e2 = b.inpatient(pid, prv, d1 + timedelta(days=2 + 13), "07:30", 2, "I25.1",
                     procs=[{"code": "36.07", "performed_at": ts(d1 + timedelta(days=15), "09:30")}], adm="ELECTIVE",
                     cls="2")
    b.note(e2, "PROCEDURE_REPORT", ts(d1 + timedelta(days=15), "11:00"),
           "Laporan PCI: pemasangan dua stent drug-eluting di LAD dan RCA, aliran akhir TIMI 3.", "Laporan PCI")
    b.discharge(e2, "Ringkasan pulang. Pasca PCI kondisi stabil, lanjut dual antiplatelet.")
    b.add(GroundTruth(
        "GT-B06", None, "CONFLICTING_EVIDENCE", READMISSION, [e1, e2], [e1, e2],
        expected_evidence=[ev(CTX_NOTE, n_plan, "SCHEDULED_PROCEDURE_CONTEXT", CONTEXT),
                           ev(CTX_NOTE, n_plan, "SCHEDULE_CONSISTENCY", CONTEXT),
                           ev(EPISODE, e2, "SCHEDULE_CONSISTENCY", RISK),
                           *policy_labels(READMISSION)],
        expected_exceptions=[],
        expected_requirement_states={"SCHEDULED_PROCEDURE_CONTEXT": "FOUND", "SCHEDULE_CONSISTENCY": "CONFLICTING"},
        expected_outcome="EVIDENCE_CONFLICTING", expected_stop_reason="CONFLICTING_EVIDENCE",
        notes_for_reviewers="A staged plan exists (36.06, single vessel) but episode 2 records a different procedure "
                            "(36.07, two vessels). Plan-vs-performed mismatch must surface as a conflict.",
        tags=["conflict", "hard-positive"],
    ))


def bm_missing_fragmentation(b: Builder) -> None:
    pid = b.patient(1975, "M")
    prv = "PRV-0005"
    d1 = b.shift(date(2026, 4, 13))
    v1 = b.outpatient(pid, prv, d1, "09:00", "M54.5")
    b.note(v1, "OUTPATIENT_VISIT", ts(d1, "09:20"),
           "Kunjungan poli saraf. Nyeri punggung bawah setelah mengangkat beban, tanpa defisit neurologis. Diberikan "
           "analgesik dan fisioterapi.", "Kunjungan poli saraf")
    v2 = b.outpatient(pid, prv, d1 + timedelta(days=5), "09:00", "M54.5")
    n2 = b.note(v2, "OUTPATIENT_VISIT", ts(d1 + timedelta(days=5), "09:20"), None, "Kunjungan poli saraf",
                "UNAVAILABLE")
    b.add(GroundTruth(
        "GT-B07", None, "MISSING_EVIDENCE", FRAGMENTATION, [v1, v2], [v1, v2],
        expected_evidence=[*policy_labels(FRAGMENTATION)],
        expected_exceptions=[],
        expected_requirement_states={"EMERGENCY_CONTEXT": "UNAVAILABLE"},
        expected_outcome="EVIDENCE_UNAVAILABLE", expected_stop_reason="REQUIRED_EVIDENCE_UNAVAILABLE",
        notes_for_reviewers=f"Low back pain revisit 5 days later; the repeat visit note {n2} is registered but "
                            f"unavailable.",
        tags=["missing"],
    ))


def bm_missing_discharge_summary(b: Builder) -> None:
    pid = b.patient(1952, "F", ["I10"])
    prv = "PRV-0006"
    d1 = b.shift(date(2026, 4, 27))
    e1 = b.inpatient(pid, prv, d1, "13:00", 6, "I63.9", sec=["I10"])
    b.discharge(e1, "Ringkasan pulang. Stroke iskemik dengan hemiparesis kanan ringan. Pulang dengan antiplatelet "
                    "dan fisioterapi rawat jalan.")
    e2 = b.inpatient(pid, prv, d1 + timedelta(days=6 + 16), "10:00", 5, "I63.9", sec=["I10"])
    b.note(e2, "PROGRESS", ts(d1 + timedelta(days=24), "08:00"),
           "Hari ke-3 perawatan. Kondisi umum stabil, mobilisasi di tempat tidur, makan lewat mulut baik.",
           "Catatan perkembangan")
    # Deliberately NO discharge summary registered for e2 (D-12 expected-document rule).
    b.add(GroundTruth(
        "GT-B08", None, "MISSING_EVIDENCE", READMISSION, [e1, e2], [e1, e2],
        expected_evidence=[*policy_labels(READMISSION)],
        expected_exceptions=[],
        expected_requirement_states={"CLINICAL_DOCUMENT_AVAILABILITY": "UNAVAILABLE"},
        expected_outcome="EVIDENCE_UNAVAILABLE", expected_stop_reason="REQUIRED_EVIDENCE_UNAVAILABLE",
        notes_for_reviewers="Stroke readmission 16 days later. The repeat inpatient episode has no discharge "
                            "summary registered (expected document missing); the only readable note is neutral.",
        tags=["missing"],
    ))


def bm_paraphrased_emergency(b: Builder) -> None:
    pid = b.patient(1968, "M")
    prv = "PRV-0001"
    d1 = b.shift(date(2026, 5, 11))
    e1 = b.inpatient(pid, prv, d1, "09:00", 4, "K92.2")
    b.discharge(e1, "Ringkasan pulang. Melena akibat ulkus duodenum, mendapat transfusi dan penghambat pompa proton "
                    "intravena. Pulang stabil dengan terapi oral.")
    e2 = b.inpatient(pid, prv, d1 + timedelta(days=4 + 8), "03:15", 4, "K92.2")
    n_tri = b.note(e2, "TRIAGE", ts(d1 + timedelta(days=12), "03:20"),
                   "Pasien dibawa dengan ambulans setelah muntah darah dua kali di rumah, tampak pucat dan gelisah, "
                   "nadi 128x/menit, TD 80/50 mmHg. Ditangani segera di ruang resusitasi dengan dua jalur infus.",
                   "Catatan penerimaan malam")
    b.discharge(e2, "Ringkasan pulang. Perdarahan saluran cerna atas berulang akibat ulkus duodenum, mendapat "
                    "transfusi 2 kantong dan hemostasis endoskopik. Pulang stabil.")
    b.add(GroundTruth(
        "GT-B09", None, "LEGIT_READMISSION_EMERGENCY", READMISSION, [e1, e2], [e1, e2],
        expected_evidence=[ev(CTX_NOTE, n_tri, "EMERGENCY_CONTEXT", CONTEXT), *policy_labels(READMISSION)],
        expected_exceptions=["EMERGENCY_CONTEXT"],
        expected_requirement_states={"EMERGENCY_CONTEXT": "FOUND"},
        expected_outcome="EVIDENCE_SUFFICIENT", expected_stop_reason="SUFFICIENT_EVIDENCE",
        notes_for_reviewers="Emergency is described clinically (ambulance, haematemesis, hypotension, resuscitation "
                            "room) without any of the usual keywords (IGD, gawat darurat, triase, syok). A reviewer "
                            "recognises it; a keyword matcher may not. Lexical-robustness probe.",
        tags=["hard-negative", "paraphrase"],
    ))


def bm_negated_emergency(b: Builder) -> None:
    pid = b.patient(1980, "F")
    prv = "PRV-0002"
    d1 = b.shift(date(2026, 5, 18))
    e1 = b.inpatient(pid, prv, d1, "10:00", 4, "L03.1")
    b.discharge(e1, "Ringkasan pulang. Selulitis tungkai kanan, antibiotik intravena 4 hari, kemerahan berkurang. "
                    "Pulang dengan antibiotik oral.")
    e2 = b.inpatient(pid, prv, d1 + timedelta(days=4 + 7), "11:00", 3, "L03.1")
    n_adm = b.note(e2, "ADMISSION", ts(d1 + timedelta(days=11), "11:20"),
                   "Pasien datang sendiri dari poli bedah dan tidak dalam kondisi gawat darurat. Kemerahan dan bengkak "
                   "tungkai kanan dengan keluhan serupa seperti perawatan sebelumnya, pasien meminta dirawat kembali.",
                   "Catatan masuk")
    b.discharge(e2, "Ringkasan pulang. Selulitis tungkai kanan, antibiotik intravena dilanjutkan 3 hari. Pulang "
                    "dengan antibiotik oral.")
    b.add(GroundTruth(
        "GT-B10", None, "POTENTIAL_READMISSION", READMISSION, [e1, e2], [e1, e2],
        expected_evidence=[ev(CTX_NOTE, n_adm, "EMERGENCY_CONTEXT", RISK),
                           ev(CTX_NOTE, n_adm, "RISK_INDICATORS_IN_NOTES", RISK),
                           *policy_labels(READMISSION)],
        expected_exceptions=[],
        expected_requirement_states={"EMERGENCY_CONTEXT": "NOT_FOUND", "RISK_INDICATORS_IN_NOTES": "FOUND"},
        expected_outcome="HUMAN_REVIEW_REQUIRED", expected_stop_reason="EVIDENCE_PATHS_EXHAUSTED",
        notes_for_reviewers="The emergency keyword appears only negated ('tidak dalam kondisi gawat darurat'). It "
                            "must not be read as emergency context.",
        tags=["hard-positive", "negation"],
    ))


def bm_metadata_only_emergency(b: Builder) -> None:
    pid = b.patient(2002, "M")
    prv = "PRV-0003"
    d1 = b.shift(date(2026, 6, 1))
    e1 = b.inpatient(pid, prv, d1, "12:00", 4, "A91")
    b.discharge(e1, "Ringkasan pulang. Demam berdarah dengue, trombosit naik ke 110 ribu/uL, pulang tanpa "
                    "perdarahan.")
    e2 = b.inpatient(pid, prv, d1 + timedelta(days=4 + 10), "14:00", 3, "A91", adm="EMERGENCY")
    b.note(e2, "ADMISSION", ts(d1 + timedelta(days=14), "14:30"),
           "Pasien dirawat dengan demam hari ke-3, trombosit 95 ribu/uL, nyeri sendi dan mual.", "Catatan masuk")
    b.discharge(e2, "Ringkasan pulang. Demam membaik, trombosit stabil. Pulang dengan edukasi minum cukup.")
    b.add(GroundTruth(
        "GT-B11", None, "POTENTIAL_READMISSION", READMISSION, [e1, e2], [e1, e2],
        expected_evidence=[*policy_labels(READMISSION)],
        expected_exceptions=[],
        expected_requirement_states={"EMERGENCY_CONTEXT": "NOT_FOUND"},
        expected_outcome="HUMAN_REVIEW_REQUIRED", expected_stop_reason="EVIDENCE_PATHS_EXHAUSTED",
        notes_for_reviewers="admission_type = EMERGENCY on the repeat episode, but no note documents an emergency. "
                            "D-11: metadata alone never resolves emergency context.",
        tags=["hard-positive", "metadata"],
    ))


def bm_chain_of_three(b: Builder) -> None:
    pid = b.patient(1949, "F")
    prv = "PRV-0003"
    d1 = b.shift(date(2026, 6, 8))
    e1 = b.inpatient(pid, prv, d1, "09:00", 3, "E87.1")
    b.discharge(e1, "Ringkasan pulang. Hiponatremia dengan lemas dan mual, koreksi natrium intravena. Pulang dengan "
                    "pembatasan cairan.")
    d2 = d1 + timedelta(days=3 + 12)
    e2 = b.inpatient(pid, prv, d2, "10:00", 3, "E87.1")
    n2 = b.note(e2, "ADMISSION", ts(d2, "10:30"),
                "Pasien dirawat kembali dengan lemas, natrium serum rendah. Keluhan berulang seperti perawatan lalu.",
                "Catatan masuk")
    b.discharge(e2, "Ringkasan pulang. Natrium terkoreksi, pulang dengan pembatasan cairan.")
    d3 = d2 + timedelta(days=3 + 10)
    e3 = b.inpatient(pid, prv, d3, "11:00", 3, "E87.1")
    n3 = b.note(e3, "ADMISSION", ts(d3, "11:30"),
                "Masuk lagi dengan lemas dan mual, natrium serum rendah, belum membaik sejak pulang.", "Catatan masuk")
    b.discharge(e3, "Ringkasan pulang. Natrium terkoreksi, rencana evaluasi penyebab hiponatremia di poli.")
    b.add(GroundTruth(
        "GT-B12", None, "POTENTIAL_READMISSION", READMISSION, [e1, e2, e3], [e1, e2, e3],
        expected_evidence=[ev(CTX_NOTE, n2, "RISK_INDICATORS_IN_NOTES", RISK),
                           ev(CTX_NOTE, n3, "RISK_INDICATORS_IN_NOTES", RISK),
                           *policy_labels(READMISSION)],
        expected_exceptions=[],
        expected_requirement_states={"RISK_INDICATORS_IN_NOTES": "FOUND"},
        expected_outcome="HUMAN_REVIEW_REQUIRED", expected_stop_reason="EVIDENCE_PATHS_EXHAUSTED",
        notes_for_reviewers="Three hyponatraemia admissions chained (12 d, 10 d intervals) into one case; no "
                            "legitimate context documented.",
        tags=["hard-positive", "chain"],
    ))


def bm_boundary_30d_emergency(b: Builder) -> None:
    pid = b.patient(1958, "M", ["I25.1"])
    prv = "PRV-0005"
    d1 = b.shift(date(2026, 6, 15))
    e1 = b.inpatient(pid, prv, d1, "09:00", 4, "I20.0")
    b.discharge(e1, "Ringkasan pulang. Angina tidak stabil, terapi antiplatelet ganda dan antikoagulan. Pulang "
                    "stabil, rencana kontrol poli jantung.")
    e2 = b.inpatient(pid, prv, d1 + timedelta(days=4 + 30), "05:50", 4, "I20.0")
    txt = b.pick([
        ("Pasien dikirim ke UGD subuh dengan nyeri dada hebat menjalar ke lengan kiri sejak 1 jam, keringat dingin. "
        "EKG cito menunjukkan depresi segmen ST."),
        ("Datang ke IGD menjelang subuh dengan nyeri dada berat saat istirahat, berkeringat dingin. EKG segera "
        "menunjukkan depresi segmen ST."),
    ])
    n_tri = b.note(e2, "TRIAGE", ts(d1 + timedelta(days=34), "06:00"), txt, "Catatan triase IGD")
    b.discharge(e2, "Ringkasan pulang. Angina tidak stabil berulang, terapi dioptimalkan. Pulang stabil.")
    b.add(GroundTruth(
        "GT-B13", None, "LEGIT_READMISSION_EMERGENCY", READMISSION, [e1, e2], [e1, e2],
        expected_evidence=[ev(CTX_NOTE, n_tri, "EMERGENCY_CONTEXT", CONTEXT), *policy_labels(READMISSION)],
        expected_exceptions=["EMERGENCY_CONTEXT"],
        expected_requirement_states={"EMERGENCY_CONTEXT": "FOUND"},
        expected_outcome="EVIDENCE_SUFFICIENT", expected_stop_reason="SUFFICIENT_EVIDENCE",
        notes_for_reviewers="Readmission exactly 30 days after discharge (inclusive threshold) through the emergency "
                            "department.",
        tags=["hard-negative", "boundary", "emergency"],
    ))


def bm_chronic_fragmentation(b: Builder) -> None:
    pid = b.patient(1966, "M", ["N18.5"])
    prv = "PRV-0006"
    d1 = b.shift(date(2026, 7, 6))
    v1 = b.outpatient(pid, prv, d1, "07:00", "N18.5", procs=[{"code": "39.95"}])
    b.note(v1, "OUTPATIENT_VISIT", ts(d1, "11:30"),
           "Hemodialisis rutin 4 jam, ultrafiltrasi 2,5 liter. Tekanan darah stabil selama tindakan.",
           "Catatan hemodialisis")
    v2 = b.outpatient(pid, prv, d1 + timedelta(days=3), "07:00", "N18.5", procs=[{"code": "39.95"}])
    txt = b.pick([
        ("Pasien penyakit ginjal kronik stadium 5 menjalani hemodialisis rutin dua kali seminggu. Ultrafiltrasi 2 "
        "liter, tanpa keluhan intradialitik."),
        "Hemodialisis rutin pada pasien CKD stadium 5, jadwal dua kali per minggu. Ultrafiltrasi 2 liter, stabil.",
    ])
    n2 = b.note(v2, "OUTPATIENT_VISIT", ts(d1 + timedelta(days=3), "11:30"), txt, "Catatan hemodialisis")
    b.add(GroundTruth(
        "GT-B14", None, "LEGIT_CHRONIC", FRAGMENTATION, [v1, v2], [v1, v2],
        expected_evidence=[ev(CTX_NOTE, n2, "CHRONIC_CONDITION_CONTEXT", CONTEXT), *policy_labels(FRAGMENTATION)],
        expected_exceptions=["CHRONIC_CONDITION_CONTEXT"],
        expected_requirement_states={"CHRONIC_CONDITION_CONTEXT": "FOUND"},
        expected_outcome="EVIDENCE_SUFFICIENT", expected_stop_reason="SUFFICIENT_EVIDENCE",
        notes_for_reviewers="Routine haemodialysis twice a week for end-stage kidney disease; repeated outpatient "
                            "visits are expected care.",
        tags=["hard-negative", "chronic"],
    ))


def bm_ambiguous_fragmentation(b: Builder) -> None:
    pid = b.patient(1995, "F")
    prv = "PRV-0006"
    d1 = b.shift(date(2026, 7, 20))
    v1 = b.outpatient(pid, prv, d1, "13:00", "R51")
    b.note(v1, "OUTPATIENT_VISIT", ts(d1, "13:20"),
           "Kunjungan poli saraf. Nyeri kepala tegang 2 minggu, pemeriksaan neurologis normal. Diberikan analgesik. "
           "Pasien juga mengeluh batuk ringan, diberikan obat simtomatik.", "Kunjungan poli saraf")
    v2 = b.outpatient(pid, prv, d1 + timedelta(days=6), "13:00", "R51")
    n2 = b.note(v2, "OUTPATIENT_VISIT", ts(d1 + timedelta(days=6), "13:20"),
                "Pasien kembali dengan nyeri kepala yang menurut pasien sedikit berkurang. Mungkin perlu evaluasi "
                "lanjutan, namun rencana pemeriksaan belum ditentukan. Analgesik diganti.", "Kunjungan poli saraf")
    b.add(GroundTruth(
        "GT-B15", None, "POTENTIAL_FRAGMENTATION", FRAGMENTATION, [v1, v2], [v1, v2],
        expected_evidence=[*policy_labels(FRAGMENTATION)],
        expected_exceptions=[],
        expected_requirement_states={"SUPPORTING_EXAM_FOLLOWUP_CONTEXT": "NOT_FOUND",
                                     "SCHEDULED_PROCEDURE_CONTEXT": "NOT_FOUND"},
        expected_outcome="HUMAN_REVIEW_REQUIRED", expected_stop_reason="EVIDENCE_PATHS_EXHAUSTED",
        notes_for_reviewers=f"Ambiguous: the repeat note ({n2}) hints at further evaluation but documents no plan, "
                            f"exam result or emergency. Includes irrelevant noise (cough) in visit 1.",
        tags=["hard-positive", "ambiguous", "noise"],
    ))


# =====================================================================================================
# Screening fixtures that must NOT be flagged (expected_signal_type = null)
# =====================================================================================================

def _not_flagged(b: Builder, gt_id: str, cls: str, anchors: list[str], why: str, tags: list[str]) -> None:
    b.add(GroundTruth(gt_id, None, cls, None, anchors, anchors, notes_for_reviewers=why, tags=["screening", *tags]))


def nf_fixtures(b: Builder) -> None:
    neutral_ds = "Ringkasan pulang. Kondisi membaik dengan terapi standar. Pulang dengan obat oral dan kontrol poli."

    pid = b.patient(1960, "M", ["I50.0"])
    e1 = b.inpatient(pid, "PRV-0001", date(2026, 1, 5), "10:00", 4, "I50.0")
    b.discharge(e1, neutral_ds)
    e2 = b.inpatient(pid, "PRV-0001", date(2026, 1, 9) + timedelta(days=31), "10:00", 4, "I50.0")
    b.discharge(e2, neutral_ds)
    _not_flagged(b, "GT-N01", "NOT_FLAGGABLE", [e1, e2], "Same patient/provider/diagnosis, readmitted 31 days after "
                 "discharge: just outside the inclusive 30-day threshold.", ["boundary", "outside-threshold"])

    pid = b.patient(1963, "F", ["I50.0"])
    e1 = b.inpatient(pid, "PRV-0001", date(2026, 2, 9), "10:00", 4, "I50.0")
    b.discharge(e1, neutral_ds)
    e2 = b.inpatient(pid, "PRV-0003", date(2026, 2, 20), "10:00", 4, "I50.0")
    b.discharge(e2, neutral_ds)
    _not_flagged(b, "GT-N02", "NOT_FLAGGABLE", [e1, e2], "Second admission at a different provider.",
                 ["different-provider"])

    pid = b.patient(1972, "M")
    e1 = b.inpatient(pid, "PRV-0002", date(2026, 3, 2), "10:00", 4, "J18.9")
    b.discharge(e1, neutral_ds)
    e2 = b.inpatient(pid, "PRV-0002", date(2026, 3, 11), "10:00", 3, "K35.8")
    b.discharge(e2, "Ringkasan pulang. Apendisitis akut, dilakukan apendektomi, pulang stabil.")
    _not_flagged(b, "GT-N03", "UNRELATED_LOOKALIKE", [e1, e2], "Same provider, 5 days apart, unrelated diagnoses "
                 "(pneumonia then appendicitis).", ["different-diagnosis"])

    pid = b.patient(1985, "F")
    e1 = b.inpatient(pid, "PRV-0003", date(2026, 3, 16), "10:00", 2, "A09")
    b.discharge(e1, neutral_ds)
    e2 = b.outpatient(pid, "PRV-0003", date(2026, 3, 21), "10:00", "A09")
    b.note(e2, "OUTPATIENT_VISIT", ts(date(2026, 3, 21), "10:30"), "Kontrol pasca rawat inap, diare sudah berhenti.",
           "Kontrol pasca rawat")
    _not_flagged(b, "GT-N04", "NOT_FLAGGABLE", [e1, e2], "Inpatient followed by outpatient with the same diagnosis: "
                 "encounter-type mismatch, neither rule applies.", ["encounter-mismatch"])

    pid = b.patient(1951, "M", ["I50.0"])
    e1 = b.inpatient(pid, "PRV-0004", date(2026, 4, 6), "10:00", 4, "I50.0")
    b.discharge(e1, neutral_ds)
    dup = b.duplicate_row(e1)
    e3 = b.inpatient(pid, "PRV-0004", date(2026, 5, 25), "10:00", 4, "I50.0")
    b.discharge(e3, neutral_ds)
    _not_flagged(b, "GT-N05", "NOT_FLAGGABLE", [e1, dup], "Exact duplicate episode row (data-quality "
                 "DUPLICATE_EPISODE_ROW) must not create a readmission; the real second admission is 45 days later.",
                 ["duplicate"])

    pid = b.patient(2000, "F")
    e1 = b.outpatient(pid, "PRV-0005", date(2026, 5, 4), "10:00", "K29.7")
    b.note(e1, "OUTPATIENT_VISIT", ts(date(2026, 5, 4), "10:30"), "Nyeri ulu hati, diberikan antasida.",
           "Kunjungan poli penyakit dalam")
    e2 = b.outpatient(pid, "PRV-0005", None, "10:00", "K29.7")
    _not_flagged(b, "GT-N06", "NOT_FLAGGABLE", [e1, e2], "Second visit has no timestamp (data-quality "
                 "MISSING_TIMESTAMP); it must be reported, not flagged.", ["missing-date"])

    pid = b.patient(1992, "M")
    e1 = b.outpatient(pid, "PRV-0006", date(2026, 5, 11), "10:00", "K29.7")
    b.note(e1, "OUTPATIENT_VISIT", ts(date(2026, 5, 11), "10:30"), "Nyeri ulu hati, diberikan antasida.",
           "Kunjungan poli penyakit dalam")
    e2 = b.outpatient(pid, "PRV-0006", date(2026, 5, 19), "10:00", "K29.7")
    b.note(e2, "OUTPATIENT_VISIT", ts(date(2026, 5, 19), "10:30"), "Kontrol, nyeri ulu hati berkurang.",
           "Kunjungan poli penyakit dalam")
    _not_flagged(b, "GT-N07", "NOT_FLAGGABLE", [e1, e2], "Outpatient visits 8 days apart: just outside the inclusive "
                 "7-day threshold.", ["boundary", "outside-threshold"])

    pid = b.patient(1957, "F", ["I50.0"])
    e1 = b.inpatient(pid, "PRV-0002", date(2026, 6, 8), "10:00", 4, "I50.0")
    b.discharge(e1, neutral_ds)
    e2 = b.inpatient(pid, "PRV-0002", date(2026, 6, 22), "10:00", 4, "I50.1")
    b.discharge(e2, neutral_ds)
    _not_flagged(b, "GT-N08", "UNRELATED_LOOKALIKE", [e1, e2], "Same ICD-10 category (I50) but different primary "
                 "codes (I50.0 vs I50.1): screening requires the exact code.", ["same-category"])


# =====================================================================================================
# Background noise: unflaggable patients that make the dataset less trivial
# =====================================================================================================

NOISE_OUTPATIENT = [
    ("E11.9", "Kontrol diabetes melitus tipe 2, gula darah puasa 142 mg/dL. Metformin dilanjutkan, edukasi diet."),
    ("H25.9", "Pemeriksaan mata, katarak senilis mata kiri, visus 6/18. Edukasi dan evaluasi berkala."),
    ("J06.9", "Batuk pilek 3 hari, tanpa sesak. Terapi simtomatik dan istirahat."),
    ("M17.9", "Nyeri lutut kanan saat berjalan lama, krepitasi ringan. Analgesik dan latihan penguatan otot."),
    ("K59.0", "Sulit buang air besar 1 minggu, pola makan rendah serat. Edukasi serat dan cairan."),
]
NOISE_INPATIENT = [
    ("K35.8", "Ringkasan pulang. Apendisitis akut, apendektomi laparoskopi tanpa penyulit. Pulang hari ketiga."),
    ("B34.9", "Ringkasan pulang. Infeksi virus dengan demam tinggi, terapi cairan dan antipiretik. Pulang membaik."),
    ("J18.9", "Ringkasan pulang. Pneumonia ringan, antibiotik intravena 3 hari. Pulang dengan antibiotik oral."),
]


def noise(b: Builder, count: int) -> None:
    providers = [p["provider_id"] for p in PROVIDERS]
    for _ in range(count):
        pid = b.patient(b.rng.randint(1945, 2005), b.pick(["M", "F"]))
        prv = b.pick(providers)
        start = date(2026, 1, 5) + timedelta(days=b.rng.randint(0, 120))
        visits = b.rng.randint(1, 2)
        dxs = b.rng.sample(range(len(NOISE_OUTPATIENT)), visits)  # different diagnoses -> never flaggable
        for i, k in enumerate(dxs):
            day = start + timedelta(days=i * b.rng.randint(95, 140))
            if b.rng.random() < 0.3:
                dx, text = NOISE_INPATIENT[b.rng.randrange(len(NOISE_INPATIENT))]
                eid = b.inpatient(pid, prv, day, "10:00", b.rng.randint(2, 5), dx)
                b.discharge(eid, text)
            else:
                dx, text = NOISE_OUTPATIENT[k]
                eid = b.outpatient(pid, prv, day, "09:00", dx)
                b.note(eid, "OUTPATIENT_VISIT", ts(day, "09:30"), text, "Kunjungan poliklinik")


# =====================================================================================================
# Policy corpus
# =====================================================================================================

PMK26_TITLE = ("Peraturan Menteri Kesehatan Nomor 26 Tahun 2021 tentang Pedoman Indonesian Case Base Groups "
               "(INA-CBG) dalam Pelaksanaan Jaminan Kesehatan")
PMK26_URL = "https://jdih.kemkes.go.id/storage/documents/pdfs/2021permenkes026.pdf#page=55"
PMK26_REF = ("Permenkes No. 26 Tahun 2021, Lampiran, halaman 55, bagian E. Readmisi dan Fragmentasi. "
             "Transkripsi diverifikasi terhadap PDF resmi JDIH Kemenkes pada 2026-10-08; "
             "hanya spasi dan pemenggalan baris dinormalisasi.")

POLICY_SECTIONS = [
    {"policy_id": POL_RA_DEF, "section": "Readmisi: definisi",
     "text": "Readmisi adalah kunjungan rawat inap berulang di FKRTL yang sama dengan diagnosis utama yang sama "
             "dari episode rawat inap sebelumnya dalam waktu kurang atau sama dengan 30 hari.",
     "topics": ["READMISSION"]},
    {"policy_id": POL_RA_EXC, "section": "Readmisi: pengecualian",
     "text": "Kondisi yang dikecualikan dari readmisi yaitu sebagai berikut: "
             "a. dalam kondisi kegawatdaruratan sesuai regulasi yang berlaku; "
             "b. penyakit kronis; "
             "c. tindakan/prosedur/post prosedur yang terjadwal oleh dokter/fasilitas kesehatan sesuai indikasi "
             "medis dan tidak dapat dilakukan dalam satu episode; atau "
             "d. kunjungan pada FKRTL yang berbeda atau kelas FKRTL yang lebih tinggi.",
     "topics": ["READMISSION", "EXCEPTION_EMERGENCY", "EXCEPTION_CHRONIC", "EXCEPTION_SCHEDULED"]},
    {"policy_id": POL_FR_DEF, "section": "Fragmentasi: definisi",
     "text": "Fragmentasi adalah kunjungan rawat jalan berulang di FKRTL yang sama pada kasus dengan diagnosis "
             "yang sama dari episode rawat jalan sebelumnya dalam waktu kurang atau sama dengan 7 hari.",
     "topics": ["FRAGMENTATION"]},
    {"policy_id": POL_FR_EXC, "section": "Fragmentasi: pengecualian",
     "text": "Kondisi yang dikecualikan dari fragmentasi adalah sebagai berikut: "
             "a. dalam kondisi kegawatdaruratan sesuai regulasi yang berlaku; "
             "b. penyakit kronis; "
             "c. rangkaian tindakan/prosedur/post prosedur yang terjadwal oleh dokter/fasilitas kesehatan sesuai "
             "indikasi medis dan tidak dapat dilakukan dalam satu episode; atau "
             "d. konsultasi hasil pemeriksaan penunjang yang tidak dapat dilakukan dalam satu episode.",
     "topics": ["FRAGMENTATION", "EXCEPTION_EMERGENCY", "EXCEPTION_CHRONIC", "EXCEPTION_SCHEDULED",
                "EXCEPTION_SUPPORTING_EXAM"]},
]


def policy_rows() -> list[dict]:
    return [{"policy_id": s["policy_id"], "document_title": PMK26_TITLE, "section": s["section"], "text": s["text"],
             "source_ref": PMK26_REF, "source_url": PMK26_URL, "version": "Permenkes 26/2021",
             "effective_date": "2021-08-30", "topics": s["topics"]} for s in POLICY_SECTIONS]


# =====================================================================================================
# Output
# =====================================================================================================

SCENARIOS = [golden_a, golden_b, golden_c, golden_d, golden_e,
             bm_chronic_readmission, bm_supporting_exam_boundary, bm_emergency_fragmentation,
             bm_unresolved_readmission, bm_staged_outpatient, bm_schedule_mismatch, bm_missing_fragmentation,
             bm_missing_discharge_summary, bm_paraphrased_emergency, bm_negated_emergency,
             bm_metadata_only_emergency, bm_chain_of_three, bm_boundary_30d_emergency, bm_chronic_fragmentation,
             bm_ambiguous_fragmentation, nf_fixtures]


def build(seed: int, noise_patients: int) -> Builder:
    b = Builder(seed)
    for scenario in SCENARIOS:
        scenario(b)
    noise(b, noise_patients)
    return b


def _jsonl(rows: list[dict]) -> bytes:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def ground_truth_readme(b: Builder, version: str, seed: int) -> str:
    lines = [
        f"# Ground truth — dataset `{version}` (seed {seed})",
        "",
        "Evaluation-only. Never place these files where the backend ingests data (the ingest refuses any",
        "`ground-truth` path). Generated by `data/generator/generate_dataset.py`; do not edit by hand.",
        "",
        "| gt_id | Golden | Scenario | Signal | Anchors | Expected outcome | Tags |",
        "|---|---|---|---|---|---|---|",
    ]
    for t in b.truth:
        lines.append(f"| {t.gt_id} | {t.golden_case or ''} | {t.scenario_class} | {t.expected_signal_type or '—'} | "
                     f"{', '.join(sorted(t.anchor_episode_ids))} | {t.expected_outcome or 'not flagged'} | "
                     f"{', '.join(t.tags)} |")
    lines += ["", "Rationale per case is in `notes_for_reviewers` inside `cases.jsonl`.", ""]
    return "\n".join(lines)


def write_all(root: Path, version: str, seed: int, noise_patients: int, reset: bool = False) -> dict[str, Path]:
    b = build(seed, noise_patients)
    out = {
        "dataset": root / "synthetic" / version,
        "policies": root / "policies" / CORPUS_VERSION,
        "ground_truth": root / "ground-truth" / version,
    }
    if reset:
        for key in ("dataset", "ground_truth"):
            shutil.rmtree(out[key], ignore_errors=True)
    tables = {"patients": b.patients, "providers": PROVIDERS, "episodes": b.episodes, "claims": b.claims,
              "clinical_notes": b.notes}
    hashes = {}
    for name, rows in tables.items():
        data = _jsonl(rows)
        _write(out["dataset"] / f"{name}.jsonl", data)
        hashes[f"{name}.jsonl"] = "sha256:" + hashlib.sha256(data).hexdigest()
    manifest = {
        "dataset_version": version,
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "generated_at": "2026-10-04T00:00:00+07:00",
        "contract_version": CONTRACT_VERSION,
        "counts": {k: len(v) for k, v in tables.items()},
        "files": hashes,
    }
    _write(out["dataset"] / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))

    sections = policy_rows()
    _write(out["policies"] / "policy_sections.jsonl", _jsonl(sections))
    _write(out["policies"] / "manifest.json", (json.dumps(
        {"corpus_version": CORPUS_VERSION, "contract_version": CONTRACT_VERSION, "sections": len(sections),
         "status": "verified-transcription", "verified_at": "2026-10-08", "source_page": 55,
         "source_url": PMK26_URL, "text_normalization": "whitespace-and-line-wraps-only",
         "files": {"policy_sections.jsonl": "sha256:" + hashlib.sha256(_jsonl(sections)).hexdigest()}},
        indent=2) + "\n").encode("utf-8"))

    _write(out["ground_truth"] / "cases.jsonl", _jsonl([t.row() for t in b.truth]))
    _write(out["ground_truth"] / "README.md", ground_truth_readme(b, version, seed).encode("utf-8"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--noise-patients", type=int, default=12, help="Background patients that must never be flagged.")
    ap.add_argument("--root", type=Path, default=REPO / "data", help="Output root (default: <repo>/data).")
    ap.add_argument("--reset", action="store_true", help="Delete this version's dataset and ground truth first.")
    args = ap.parse_args()
    out = write_all(args.root, args.version, args.seed, args.noise_patients, args.reset)
    for k, p in out.items():
        print(f"wrote {k}: {p}")


if __name__ == "__main__":
    main()
