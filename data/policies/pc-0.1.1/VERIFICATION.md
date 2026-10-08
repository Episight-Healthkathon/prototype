# Policy corpus verification — pc-0.1.1

Verified on 2026-10-08 against the issuing ministry's original PDF:

- [JDIH Kemenkes document record](https://jdih.kemkes.go.id/documents/peraturan-menteri-kesehatan-nomor-26-tahun-2021)
- [Official PDF, page 55](https://jdih.kemkes.go.id/storage/documents/pdfs/2021permenkes026.pdf#page=55)
- [BPK independent metadata record](https://peraturan.bpk.go.id/Details/353186/permenkes-no-26-tahun-2021)

The PDF identifies itself as Permenkes 26/2021. Page 55 of its 56 pages contains Lampiran,
section E, subsections 1 (Readmisi) and 2 (Fragmentasi). The four corpus sections reproduce the
two definitions and two exception lists; whitespace and wrapped lines are normalized.
The document record and Article 5 establish the effective date as 2021-08-30.

## Corrections to the proposal-derived summaries

- Definitions now retain the reference to the previous inpatient/outpatient episode.
- Emergency exceptions retain the qualification about applicable regulation.
- Scheduled-care exceptions retain the doctor/facility scheduling and post-procedure wording.
- Readmission exception 1.d uses FKRTL class, not the summary's hospital-class wording.
- Fragmentation exception 2.d retains the limitation that the supporting examination could not
  be performed in one episode. The old phrase "penunjang tertentu" omitted this condition.
- Product commentary about signals/verdicts is kept in product documentation, outside legal quotes.

`manifest.json` records the source page, verification date, normalization and SHA-256 of the JSONL.
Policy IDs are stable for ground-truth joins; corpus version changes to preserve historical provenance.
The old `pc-0.1.0` corpus and its benchmark/recordings remain unchanged.

This verifies source fidelity for the prototype's selected sections. Context FOUND indicates
surfaced evidence for a reviewer; it does not certify that every legal exception condition is met.
