# EPISIGHT

<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
Next.js and TypeScript, following the repository's documented Person 2 boundary. FastAPI and PostgreSQL supply the API. The user delegated completion of frontend stages 1–8 without further direction.

## Users
JKN/FKRTL claim reviewers investigating readmission and episode fragmentation.

## Product Purpose
Move from a screening signal to reconstructed episodes, traceable evidence and a brief for human review.

## Operating Context
Queue → overview/timeline → investigation workspace → reviewer brief → source provenance. Dataset v0.1.0 contains synthetic patients and providers only; corpus pc-0.1.1 contains policy references.

## Capabilities and Constraints
The API contract is authoritative. Screening, validation and stopping are deterministic. AI planning is optional and exposes rule fallback. Missing sources, negative search findings and conflicting sources remain distinct. The product does not determine fraud or approve, reject or pay claims. Review persistence is not implemented by the API.

## Brand Commitments
The supplied EPISIGHT PNG is the official logo. The supplied four-stage case slide is a landing-page illustration and visual reference. Its illustrative dates and evidence classifications do not replace runtime data.

## Evidence on Hand
Official synthetic data, generated API types, real engine fixtures and golden cases A–E. No real JKN feed or financial savings claims.

## Product Principles
Trace each material statement to a source. Keep human responsibility visible. Show evidence limitations. Preserve episode context. Render backend state directly.
