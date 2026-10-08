# Label amendment v0.1.0-labels-1

Evaluation-only labels for unchanged synthetic dataset `v0.1.0`; never ingest this directory.

This version changes exactly one field: GT-B06 `expected_exceptions` becomes
`["SCHEDULED_PROCEDURE_CONTEXT"]`. All episode IDs, evidence labels, expected requirement
states, outcomes and stop reasons remain identical to `v0.1.0`.

`evaluation/METRICS.md` defines exception identification as **surfaced FOUND context**. GT-B06
already expects `SCHEDULED_PROCEDURE_CONTEXT = FOUND`, while `SCHEDULE_CONSISTENCY = CONFLICTING`.
The scheduled plan exists even though the performed procedure differs. The previous empty
exception list conflated surfaced context with an accepted exception. The correct outcome remains
`EVIDENCE_CONFLICTING`, requiring human review; this amendment grants no clinical or payment decision.

Historical reports continue using the original labels and retain their 90.91% exception precision.
The offline acceptance records metrics under both versions separately. Any report using these
amended labels must identify this label version; improved label consistency is not improved engine
performance. The synthetic generator continues reproducing the original labels unchanged.
