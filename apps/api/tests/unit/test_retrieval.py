import pytest

from episight.contracts.enums import Stance
from episight.ingest.loader import load_policies
from episight.retrieval.bm25 import BM25
from episight.retrieval.context import ContextType, match_context
from episight.retrieval.policy import PolicyIndex
from episight.retrieval.text import sentences, tokenize
from tests.conftest import POLICY_DIR

# --- text -------------------------------------------------------------------------------------------


def test_sentence_offsets_are_literal_and_keep_decimals_together():
    text = "Demam 39,8 C. Rencana PCI (ICD-9-CM 36.06) dijadwalkan. Kategori triase: merah (gawat darurat)."
    sents = sentences(text)
    assert [s.text for s in sents] == [
        "Demam 39,8 C.",
        "Rencana PCI (ICD-9-CM 36.06) dijadwalkan.",
        "Kategori triase: merah (gawat darurat).",
    ]
    assert all(text[s.start : s.end] == s.text for s in sents)


def test_tokenize_drops_stopwords_and_expands_abbreviations():
    tokens = tokenize("Pasien datang ke IGD dan diperiksa")
    assert "dan" not in tokens and "pasien" not in tokens
    assert {"igd", "gawat", "darurat"} <= set(tokens)


# --- BM25 -------------------------------------------------------------------------------------------


def test_bm25_ranks_matching_document_first_and_breaks_ties_by_order():
    docs = [tokenize(t) for t in ["nyeri ulu hati", "sesak napas memberat igd", "sesak napas ringan"]]
    hits = BM25(docs).search(tokenize("sesak igd"))
    assert [h.index for h in hits] == [1, 2]
    assert BM25(docs).search(tokenize("tidak relevan sama sekali")) == []


# --- context matcher --------------------------------------------------------------------------------


def _match(text, ctx):
    return [(m.stance, m.excerpt) for m in match_context(text, ctx)]


@pytest.mark.parametrize(
    "text,ctx,stance",
    [
        ("Kategori triase: merah (gawat darurat).", ContextType.EMERGENCY, Stance.AFFIRMS),
        ("Dirawat ulang melalui IGD dengan edema paru.", ContextType.EMERGENCY, Stance.AFFIRMS),
        ("Tidak ada tanda kegawatdaruratan.", ContextType.EMERGENCY, Stance.NEGATES),
        ("Pasien masuk secara elektif sesuai jadwal.", ContextType.EMERGENCY, Stance.NEGATES),
        ("Tahap kedua pemasangan stent dijadwalkan tanggal 20 Mei.", ContextType.SCHEDULED_PROCEDURE, Stance.AFFIRMS),
        ("Tidak ada pemeriksaan penunjang yang dijadwalkan.", ContextType.SCHEDULED_PROCEDURE, Stance.NEGATES),
        ("Pasien dengan gagal jantung kronik.", ContextType.CHRONIC, Stance.AFFIRMS),
        ("Kontrol membawa hasil endoskopi saluran cerna.", ContextType.SUPPORTING_EXAM_FOLLOWUP, Stance.AFFIRMS),
        ("Keluhan serupa dengan kunjungan sebelumnya.", ContextType.RISK_INDICATOR, Stance.AFFIRMS),
    ],
)
def test_context_stance(text, ctx, stance):
    assert _match(text, ctx) == [(stance, text)]


def test_negation_of_another_verb_does_not_negate_a_justification():
    text = "Tindakan tidak dilakukan pada episode yang sama karena batas volume kontras."
    assert _match(text, ContextType.CLINICAL_JUSTIFICATION) == [(Stance.AFFIRMS, text)]


def test_negated_descriptive_term_is_dropped_not_counter_evidence():
    assert _match("Hasil aliran TIMI 3, tanpa komplikasi.", ContextType.CLINICAL_JUSTIFICATION) == []


def test_unrelated_text_matches_nothing():
    assert _match("Terapi omeprazole dan antasida.", ContextType.EMERGENCY) == []


@pytest.mark.parametrize("text", [
    "Pasien ditangani segera di ruang resusitasi dengan dua jalur infus.",
    "Pasien distabilisasi dalam ruangan resusitasi setelah penilaian awal.",
    "Pasien dirawat langsung di unit resusitasi.",
    "The patient was treated immediately in the resuscitation room.",
])
def test_active_resuscitation_care_surfaces_literal_emergency_evidence(text):
    matches = match_context(text, ContextType.EMERGENCY)
    assert len(matches) == 1 and matches[0].stance == Stance.AFFIRMS
    assert text[matches[0].char_start:matches[0].char_end] == matches[0].excerpt == text


@pytest.mark.parametrize("text", [
    "Pasien diantar ambulans untuk kontrol rutin.",
    "Pasien menunggu keluarga di dekat ruang resusitasi.",
    "Pasien tidak ditangani di ruang resusitasi.",
    "Jika memburuk, pasien akan ditangani di ruang resusitasi.",
    "Riwayat pasien ditangani di ruang resusitasi pada perawatan sebelumnya.",
    "Simulasi: pasien ditangani di ruang resusitasi oleh peserta latihan.",
    "The patient will be treated in the resuscitation room if required.",
])
def test_transport_location_negation_and_non_current_care_are_not_emergency_evidence(text):
    assert _match(text, ContextType.EMERGENCY) == []


def test_matches_on_every_interim_note_are_literal_substrings(dataset):
    for note in dataset.notes:
        if note.text is None:
            continue
        for ctx in ContextType:
            for m in match_context(note.text, ctx):
                assert note.text[m.char_start : m.char_end] == m.excerpt


# --- policy -----------------------------------------------------------------------------------------


def test_policy_search_filters_by_topic_and_returns_stored_sections():
    corpus = load_policies(POLICY_DIR)
    index = PolicyIndex(corpus.sections, corpus.manifest.corpus_version)
    hits = index.search("readmisi rawat inap berulang pengecualian", topics=["READMISSION"])
    assert [h.section.policy_id for h in hits] == ["POL-INTERIM-READMISI-01"]
    frag = index.search("fragmentasi rawat jalan berulang", topics=["FRAGMENTATION"])
    assert [h.section.policy_id for h in frag] == ["POL-INTERIM-FRAGMENTASI-01"]
    assert index.get("POL-INTERIM-READMISI-01").text == corpus.sections[0].text


def test_empty_policy_index_returns_nothing():
    assert PolicyIndex([]).search("readmisi") == []
