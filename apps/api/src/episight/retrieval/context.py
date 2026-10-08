"""Deterministic context matcher: finds sentences that affirm or negate a context type in clinical notes.

Each lexicon entry is a phrase matched on word boundaries. A phrase preceded by a negation cue within a
short window ("tidak ada tanda kegawatdaruratan") counts as NEGATES. Explicit negating phrases
("masuk secara elektif" for emergency) also count as NEGATES. The excerpt is the whole sentence,
a literal substring of the note.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from episight.contracts.enums import Stance
from episight.retrieval.text import sentences


class ContextType(StrEnum):
    EMERGENCY = "EMERGENCY"
    CHRONIC = "CHRONIC"
    SCHEDULED_PROCEDURE = "SCHEDULED_PROCEDURE"
    SUPPORTING_EXAM_FOLLOWUP = "SUPPORTING_EXAM_FOLLOWUP"
    CLINICAL_JUSTIFICATION = "CLINICAL_JUSTIFICATION"
    RISK_INDICATOR = "RISK_INDICATOR"


@dataclass(frozen=True)
class Lexicon:
    affirm: tuple[str, ...]
    negate: tuple[str, ...] = ()
    # Words before a phrase searched for a negation cue. For descriptive lexicons (justification, risk
    # indicators) only a directly preceding cue applies, and a negated match is dropped instead of
    # becoming counter-evidence ("tanpa komplikasi" is not evidence against a justification).
    negation_window: int = 6
    negation_is_evidence: bool = True


LEXICONS: dict[ContextType, Lexicon] = {
    ContextType.EMERGENCY: Lexicon(
        affirm=(
            "igd",
            "ugd",
            "gawat darurat",
            "kegawatdaruratan",
            "triase merah",
            "triase: merah",
            "kuning-merah",
            "emergency",
            "cito",
            "penurunan kesadaran",
            "syok",
        ),
        negate=("masuk secara elektif", "admisi elektif", "elective admission"),
    ),
    ContextType.CHRONIC: Lexicon(
        affirm=("kronik", "kronis", "chronic", "menahun", "ppok", "copd", "ckd", "penyakit kronis"),
    ),
    ContextType.SCHEDULED_PROCEDURE: Lexicon(
        affirm=(
            "dijadwalkan",
            "terjadwal",
            "rencana tindakan",
            "bertahap",
            "tahap kedua",
            "tahap ii",
            "staged",
            "scheduled",
            "sesuai rencana",
            "sesuai jadwal",
            "planned",
        ),
    ),
    ContextType.SUPPORTING_EXAM_FOLLOWUP: Lexicon(
        affirm=(
            "hasil pemeriksaan penunjang",
            "pemeriksaan penunjang",
            "membawa hasil",
            "hasil laboratorium",
            "hasil lab",
            "hasil endoskopi",
            "hasil rontgen",
            "hasil radiologi",
            "hasil ekg",
            "hasil usg",
            "konsultasi hasil",
        ),
    ),
    ContextType.CLINICAL_JUSTIFICATION: Lexicon(
        affirm=(
            "pemicu",
            "atas indikasi",
            "indikasi medis",
            "dicurigai",
            "memberat",
            "perburukan",
            "edema paru akut",
            "komplikasi",
            "decompensated",
            "urosepsis",
            "sepsis",
            "tidak dapat dilakukan",
            "karena",
        ),
        negation_window=1,
        negation_is_evidence=False,
    ),
    ContextType.RISK_INDICATOR: Lexicon(
        affirm=(
            "keluhan serupa",
            "keluhan sama",
            "keluhan masih ada",
            "keluhan berulang",
            "belum membaik",
            "tidak membaik",
            "pulang atas permintaan sendiri",
            "pulang paksa",
            "tanpa indikasi",
        ),
        negation_window=1,
        negation_is_evidence=False,
    ),
}

NEGATION_CUES = ("tidak ada", "tidak", "tanpa", "bukan", "tak", "belum ada", "no", "without", "denies", "menyangkal")
_CUE = re.compile(r"(?<!\w)(" + "|".join(re.escape(c) for c in NEGATION_CUES) + r")(?!\w)")


@dataclass(frozen=True)
class ContextMatch:
    char_start: int
    char_end: int
    excerpt: str
    stance: Stance
    terms: tuple[str, ...]


def _phrase_regex(phrase: str) -> re.Pattern:
    return re.compile(r"(?<![\w-])" + re.escape(phrase) + r"(?![\w-])")


_PATTERNS = {
    ctx: (
        [(p, _phrase_regex(p)) for p in lex.affirm],
        [(p, _phrase_regex(p)) for p in lex.negate],
    )
    for ctx, lex in LEXICONS.items()
}

# Recognise documented active resuscitation care, rather than transport/location alone. These
# are lexical evidence candidates for human review, not clinical thresholds or a diagnosis.
_RESUSCITATION_CARE = re.compile(
    r"\b(?:ditangani|distabilisasi|dirawat|ditatalaksana)\s+(?:segera\s+|langsung\s+)?"
    r"(?:di|dalam)\s+(?:ruang|ruangan|unit)\s+resusitasi\b"
    r"|\b(?:treated|stabilized|resuscitated)\s+(?:immediately\s+)?in\s+(?:the\s+)?"
    r"resuscitation\s+(?:room|area)\b"
)
_NON_CURRENT_CARE = re.compile(
    r"\b(?:akan|bila|jika|apabila|rencana|edukasi|simulasi|latihan|riwayat|sebelumnya|"
    r"kemarin|pernah|history|previously|planned|would|will|if|training)\b"
)


def _negated(lower: str, start: int, phrase: str, window_words: int) -> bool:
    if any(phrase.startswith(c + " ") for c in NEGATION_CUES):
        return False  # the phrase itself carries the negation, e.g. "tidak membaik"
    prefix = lower[:start]
    # Measure distance from the END of a complete cue. A one-word window must still
    # recognise multiword cues such as "tidak ada komplikasi" / "belum ada perburukan".
    return any(len(prefix[m.end():].split()) < window_words for m in _CUE.finditer(prefix))


def match_context(text: str, context: ContextType) -> list[ContextMatch]:
    affirm_patterns, negate_patterns = _PATTERNS[context]
    lexicon = LEXICONS[context]
    out: list[ContextMatch] = []
    for sent in sentences(text):
        lower = sent.text.lower()
        # Historical/conditional emergency mentions do not document current care.
        # Apply the same conservative guard to ordinary phrases and active resuscitation.
        non_current_emergency = context == ContextType.EMERGENCY and bool(_NON_CURRENT_CARE.search(lower))
        affirmed: list[str] = []
        negated: list[str] = []
        for phrase, rx in affirm_patterns:
            for m in rx.finditer(lower):
                if not _negated(lower, m.start(), phrase, lexicon.negation_window):
                    if not non_current_emergency:
                        affirmed.append(phrase)
                elif lexicon.negation_is_evidence:
                    negated.append(phrase)
        for phrase, rx in negate_patterns:
            if rx.search(lower):
                negated.append(phrase)
        if context == ContextType.EMERGENCY and not _NON_CURRENT_CARE.search(lower):
            for m in _RESUSCITATION_CARE.finditer(lower):
                phrase = m.group()
                if not _negated(lower, m.start(), phrase, lexicon.negation_window):
                    affirmed.append(phrase)
        if affirmed and not any(p in dict(negate_patterns) for p in negated):
            stance, terms = Stance.AFFIRMS, affirmed
        elif negated:
            stance, terms = Stance.NEGATES, negated
        else:
            continue
        out.append(ContextMatch(sent.start, sent.end, sent.text, stance, tuple(dict.fromkeys(terms))))
    return out
