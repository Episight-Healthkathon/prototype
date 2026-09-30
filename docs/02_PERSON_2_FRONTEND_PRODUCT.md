# EPISIGHT — Person 2 Work Plan
## Frontend, Product & Reviewer Experience Owner

> Mission: turn the EPISIGHT investigation engine into a coherent reviewer-facing web product that makes episode context, evidence gaps, agent actions, uncertainty, and provenance understandable without exposing unsafe decision authority.

---

## 1. Ownership Boundary

- Own:
  - Next.js frontend.
  - design system.
  - application shell/navigation.
  - Case Queue.
  - Episode Timeline.
  - Investigation Workspace.
  - Reviewer Brief.
  - Evidence detail/provenance UI.
  - loading/error/uncertainty states.
  - product flow and frontend integration.
  - frontend testing and demo reliability.
- Co-own:
  - shared types with Person 1.
  - terminology/labels with Person 3.
  - end-to-end tests with the team.
- Do **not** own:
  - agent reasoning logic;
  - screening logic;
  - ground-truth generation;
  - benchmark metric validity.

---

## 2. Product Success Condition

A reviewer should be able to do this without needing technical explanation:

- [ ] Open Case Queue.
- [ ] Understand why a case was flagged.
- [ ] Open a case.
- [ ] Understand the episode timeline.
- [ ] See what EPISIGHT knows vs what is still missing.
- [ ] Start/open an investigation.
- [ ] Observe meaningful investigation actions.
- [ ] Understand when evidence is found, missing, or conflicting.
- [ ] Open the Reviewer Brief.
- [ ] Inspect evidence provenance.
- [ ] Understand that the final decision remains human.

---

# PHASE 0 — Product Contract Lock

## Tasks

- [ ] Read project context and Person 1 API contract.
- [ ] Agree core routes/pages:
  - `/cases`
  - `/cases/[id]`
  - `/cases/[id]/timeline`
  - `/cases/[id]/investigation`
  - `/cases/[id]/brief`
  - optional `/benchmark` or `/audit`.
- [ ] Agree shared enums with Person 1.
- [ ] Agree domain wording with Person 3.
- [ ] Agree which backend fields are mandatory for each screen.
- [ ] Create frontend mock data matching the exact API schemas.
- [ ] Define UI behavior for every investigation status.

## Exit checklist

- [ ] No page depends on undefined backend fields.
- [ ] Person 1 knows all required frontend response fields.
- [ ] Person 3 has reviewed major domain labels.

---

# PHASE 1 — Frontend Foundation

## Next.js setup

- [ ] Initialize Next.js application.
- [ ] Configure environment variables.
- [ ] Configure API base URL.
- [ ] Configure data-fetching strategy.
- [ ] Create reusable API client.
- [ ] Create typed models/shared types.
- [ ] Create global error boundary.
- [ ] Create loading skeleton components.

## Design system

- [ ] Define typography scale.
- [ ] Define color tokens.
- [ ] Define spacing tokens.
- [ ] Define card styles.
- [ ] Define table styles.
- [ ] Define status badges.
- [ ] Define evidence chips.
- [ ] Define buttons.
- [ ] Define drawer/modal patterns.
- [ ] Define icons.
- [ ] Define alert/warning patterns.

## Prototype environment cues

- [ ] Clearly label as prototype.
- [ ] Clearly label synthetic data environment.
- [ ] Avoid UI that implies real BPJS production integration.

---

# PHASE 2 — Application Shell

## Global structure

- [ ] Sidebar or top navigation.
- [ ] EPISIGHT identity/logo area.
- [ ] Current case context where relevant.
- [ ] Environment badge.
- [ ] Main content area.
- [ ] Consistent breadcrumb/back behavior.

## Recommended navigation

- [ ] Cases.
- [ ] Investigation context through selected case.
- [ ] Evidence/provenance access.
- [ ] Optional benchmark/audit page if time allows.

## Quality requirements

- [ ] Desktop/laptop first.
- [ ] No horizontal overflow on standard demo viewport.
- [ ] Readable contrast.
- [ ] Consistent status terminology.

---

# PHASE 3 — Screen 1: Case Queue

## Core content

- [ ] Case ID.
- [ ] pseudonymous patient ID.
- [ ] signal type.
- [ ] provider/FKRTL.
- [ ] relevant date.
- [ ] interval.
- [ ] investigation status.

## Filters

- [ ] All.
- [ ] Readmission.
- [ ] Fragmentation.
- [ ] Optional status filter:
  - flagged;
  - investigating;
  - human review required;
  - brief ready.

## Interaction

- [ ] Row/card opens case detail.
- [ ] Selected/hover state.
- [ ] Search by case ID or pseudonymous patient ID.
- [ ] Sorting where useful.

## Safety/product rules

- [ ] Do not display “Fraud Score” unless explicitly supported and safely defined.
- [ ] Do not label a flagged case as fraudulent.
- [ ] Make “risk signal” terminology clear.

## Exit checklist

- [ ] Works first with exact mock contract.
- [ ] Later works with Person 1 real API without restructuring page logic.

---

# PHASE 4 — Case Overview

## Core content

- [ ] Case summary.
- [ ] Risk signal and structured reasons.
- [ ] Current status.
- [ ] Related episode count.
- [ ] Navigation to timeline.
- [ ] Navigation to investigation.
- [ ] Navigation to brief if available.

## Actions

- [ ] Start Investigation when appropriate.
- [ ] Continue Investigation if in progress.
- [ ] Open Brief if ready.

## Constraints

- [ ] No claim approval/rejection actions.
- [ ] No autonomous judgement labels.

---

# PHASE 5 — Screen 2: Episode Timeline

## Required display

- [ ] Episode date/time.
- [ ] encounter type.
- [ ] provider/FKRTL.
- [ ] diagnosis.
- [ ] procedure(s).
- [ ] interval between related episodes.
- [ ] linked clinical-note indicator.
- [ ] relation reason when relevant.

## Interaction

- [ ] Click episode for more details.
- [ ] Click evidence indicator to open evidence drawer.
- [ ] Highlight episodes linked to the current risk signal.

## UX goals

- [ ] Reviewer understands chronology in under 10 seconds.
- [ ] Important interval is visually obvious.
- [ ] Related vs unrelated episode distinction is clear.
- [ ] Dense medical metadata does not overwhelm the main timeline.

## Edge states

- [ ] Missing diagnosis.
- [ ] Missing procedure.
- [ ] 3+ episodes.
- [ ] Long note title.
- [ ] No clinical note.

---

# PHASE 6 — Screen 3: Investigation Workspace

## Primary layout

- [ ] **Known Evidence / Known Facts** area.
- [ ] **Evidence Gaps / Unresolved Questions** area.
- [ ] **Next Action** area.
- [ ] **Investigation Trail** area.

## Known evidence

- [ ] Structured evidence chips/cards.
- [ ] Show source category.
- [ ] Allow evidence inspection.

## Evidence gaps

- [ ] Show missing questions explicitly.
- [ ] Example:
  - emergency context?;
  - scheduled procedure?;
  - chronic condition?;
  - clinical justification?.
- [ ] Differentiate unresolved from unavailable.

## Next action

- [ ] Show what EPISIGHT is checking next.
- [ ] Show tool/action name in reviewer-friendly wording.
- [ ] Show reason for the action when available.

## Investigation trail

- [ ] Screening completed.
- [ ] Episode history retrieved.
- [ ] diagnosis/procedure comparison.
- [ ] clinical evidence retrieved.
- [ ] policy checked.
- [ ] state updated.
- [ ] stopping state reached.

## Important transparency rule

- [ ] Show **action/state/evidence**, not raw model chain-of-thought.
- [ ] Do not expose internal hidden reasoning text.
- [ ] Do not make the UI look like a generic chatbot.

## Status presentation

- [ ] `INVESTIGATING`
- [ ] `EVIDENCE_SUFFICIENT`
- [ ] `EVIDENCE_CONFLICTING`
- [ ] `EVIDENCE_UNAVAILABLE`
- [ ] `HUMAN_REVIEW_REQUIRED`
- [ ] `BRIEF_READY`

## Exit checklist

- [ ] The user can visually see evidence-gap-driven behavior.
- [ ] The page is useful even if investigation stops early.
- [ ] Missing/conflicting evidence is not hidden.

---

# PHASE 7 — Investigation Runtime UX

## Start/run behavior

- [ ] `Run Investigation` action.
- [ ] Disable repeated accidental starts.
- [ ] Show progress state.
- [ ] Poll or stream updates from backend.
- [ ] Handle long-running investigation gracefully.

## Loading states

- [ ] “Reconstructing episodes…”
- [ ] “Checking clinical evidence…”
- [ ] “Checking policy context…”
- [ ] “Updating case state…”

## Failure states

- [ ] Backend unavailable.
- [ ] Investigation timeout.
- [ ] Evidence source unavailable.
- [ ] Policy source unavailable.
- [ ] Agent stopped at max steps.

## Rule

- [ ] Failure must not look like a successful conclusion.

---

# PHASE 8 — Screen 4: Reviewer Brief

## Required sections

- [ ] Case Summary.
- [ ] Risk Signal.
- [ ] Episode Timeline Summary.
- [ ] Evidence Supporting Risk.
- [ ] Evidence Explaining Context.
- [ ] Policy References.
- [ ] Remaining Gaps.
- [ ] Uncertainty / Stop Reason.
- [ ] Review Status.

## Evidence interaction

- [ ] Evidence items clickable.
- [ ] Open evidence detail drawer/modal.
- [ ] Preserve context when closing drawer.

## Allowed reviewer actions

- [ ] Open Evidence.
- [ ] Mark Reviewed.
- [ ] Request Additional Evidence if supported.
- [ ] Add Reviewer Note if supported.

## Explicitly disallowed UI actions

- [ ] No “Fraud Confirmed”.
- [ ] No “Reject Claim”.
- [ ] No “Approve Payment”.
- [ ] No “Auto Decision”.

## Exit checklist

- [ ] Brief is understandable without reading raw investigation logs.
- [ ] Uncertainty remains visible.
- [ ] Sources are inspectable.

---

# PHASE 9 — Evidence Detail / Provenance Drawer

## Required fields

- [ ] Evidence ID.
- [ ] Source type.
- [ ] Source title/ID.
- [ ] Excerpt or structured value.
- [ ] Related episode.
- [ ] Retrieved by tool.
- [ ] Retrieval reason.
- [ ] Retrieval timestamp.
- [ ] Policy version/section when applicable.
- [ ] Evidence category:
  - supporting risk;
  - explaining context;
  - neutral/background.

## UX behavior

- [ ] Source metadata readable.
- [ ] Long excerpts scroll safely.
- [ ] Missing source metadata is clearly marked.
- [ ] Reviewer can navigate back to the same place.

---

# PHASE 10 — Uncertainty & Conflict UX

## Evidence unavailable

- [ ] Show unavailable state.
- [ ] Show what source/evidence was attempted.
- [ ] Do not render as a negative finding.

## Evidence conflicting

- [ ] Show both evidence sides.
- [ ] Show `Human Review Required` status.
- [ ] Avoid visual bias toward one side unless justified by explicit source quality metadata.

## Missing context

- [ ] Keep unresolved question visible.
- [ ] Do not collapse missing data into a conclusion.

---

# PHASE 11 — Human Review State

## Optional prototype actions

- [ ] Mark as Reviewed.
- [ ] Add reviewer note.
- [ ] Request more evidence.

## Persist if implemented

- [ ] reviewer state;
- [ ] timestamp;
- [ ] note;
- [ ] action history.

## Boundary

- [ ] Do not turn the prototype into a claim adjudication system.

---

# PHASE 12 — Backend Integration

## Replace mocks progressively

- [ ] Case Queue → real API.
- [ ] Case Overview → real API.
- [ ] Episode Timeline → real API.
- [ ] Investigation Workspace → real API.
- [ ] Reviewer Brief → real API.
- [ ] Evidence Drawer → real API.

## Contract testing

- [ ] Missing optional fields do not crash UI.
- [ ] Unknown enum has safe fallback.
- [ ] API error is visible.
- [ ] Loading is not mistaken for empty result.

---

# PHASE 13 — Frontend Testing

## Functional

- [ ] Case filters.
- [ ] Case search.
- [ ] Case navigation.
- [ ] Timeline rendering.
- [ ] 2 episode case.
- [ ] 3+ episode case.
- [ ] Investigation start.
- [ ] Investigation polling/stream state.
- [ ] Brief rendering.
- [ ] Evidence drawer.

## Edge cases

- [ ] Empty Case Queue.
- [ ] No evidence found.
- [ ] Conflicting evidence.
- [ ] Long clinical note.
- [ ] Missing provider metadata.
- [ ] Missing policy reference.
- [ ] Backend error.
- [ ] Timeout.

## Accessibility / readability

- [ ] Sufficient contrast.
- [ ] Buttons have clear labels.
- [ ] Status is not conveyed only by color.
- [ ] Main workflow works on standard laptop viewport.

---

# PHASE 14 — Demo Reliability / Product QA

## Golden flow 1

- [ ] Legitimate Readmission.
- [ ] Open case.
- [ ] View timeline.
- [ ] Run/open investigation.
- [ ] See emergency/chronic context surfaced.
- [ ] Open brief.
- [ ] Open evidence source.

## Golden flow 2

- [ ] Missing Evidence.
- [ ] Open case.
- [ ] Run/open investigation.
- [ ] See unresolved evidence gap.
- [ ] See explicit uncertainty.
- [ ] See human review state.

## Stability

- [ ] No manual DB edits required mid-flow.
- [ ] No hidden route hacks.
- [ ] No random case mutation during demo.
- [ ] UI survives page refresh where reasonable.

---

# P0 / P1 / P2 Priorities

## P0 — Must finish

- [ ] Next.js app shell.
- [ ] Case Queue.
- [ ] Case Overview.
- [ ] Episode Timeline.
- [ ] Investigation Workspace.
- [ ] Reviewer Brief.
- [ ] Evidence Drawer.
- [ ] investigation statuses.
- [ ] loading/error/uncertainty states.
- [ ] real backend integration.
- [ ] reliable golden-case flow.

## P1 — Strongly recommended

- [ ] Investigation trail visualization.
- [ ] reviewer notes.
- [ ] richer policy citation display.
- [ ] internal benchmark/audit page.
- [ ] stronger responsive behavior.
- [ ] basic end-to-end browser tests.

## P2 — Stretch

- [ ] streaming progress animation.
- [ ] interactive episode graph.
- [ ] richer evidence relationship visualization.
- [ ] audit-event viewer.
- [ ] additional reviewer productivity features.

---

# Daily / PR Checklist

Before opening a PR:

- [ ] API contract still matches Person 1.
- [ ] New terminology reviewed against shared domain terms.
- [ ] No UI introduces fraud/payment decision authority.
- [ ] Missing/conflicting states remain explicit.
- [ ] Loading and error states tested.
- [ ] No hardcoded fake result conflicts with backend data.
- [ ] Golden flow still works.
- [ ] No secret/API key committed.

---

# Final Definition of Done — Person 2

- [ ] Frontend starts from documented commands.
- [ ] All four core screens are functional.
- [ ] Case Queue is connected to backend.
- [ ] Episode Timeline renders real reconstructed data.
- [ ] Investigation Workspace renders real state/actions/evidence.
- [ ] Reviewer Brief renders real backend output.
- [ ] Evidence provenance is inspectable.
- [ ] Missing/conflicting evidence is understandable.
- [ ] Human decision boundary is visually clear.
- [ ] Golden legitimate-context flow works.
- [ ] Golden uncertainty/escalation flow works.
- [ ] Application is stable enough for repeated end-to-end use.
