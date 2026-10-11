# Reviewer frontend audit

Scope: queue, case context, examination summary, evidence detail, source drawer,
run history, final brief, guide, and shared loading/error/navigation behavior.
Reviewed against current source, synthetic fixtures and supplied screenshots.
This is not a production security certification or a usability study.

## Findings addressed

- Live evidence stopped at 200 entries: load subsequent pages and pin them to
  the same run; explicitly fail rather than silently present incomplete pages.
- Switching live/demo could retain historical selection and queue pagination:
  remount case/queue state for each data source.
- Evidence entries were called sources: distinguish entries from unique sources.
- Evidence browsing required connecting two dense columns: prioritize source
  cards, category filters and a clear source-opening action. Keep policy and
  neutral evidence discoverable, not only signal/medical-context categories.
- English requirement questions dominated the interface: use localized labels
  keyed to the backend requirement. Preserve original excerpts and explanations.
- Technical metadata dominated source reading: make provenance expandable while
  keeping the excerpt and full content accessible.
- Historical overview timelines can contain latest-run evidence links because
  the timeline endpoint is case-scoped: hide these links for historical selection;
  inspect historical evidence in the run-scoped evidence view instead.
- Mobile sidebar rules hid the guide label: keep its text visible.

## Existing safeguards retained

- Screening is not a fraud verdict; sufficient evidence is not claim approval.
- NOT_FOUND and UNAVAILABLE remain distinct; both sides of conflicts are retained.
- Loading, empty and retryable error states are provided.
- Source links use the original evidence ID; excerpts are not rewritten as facts.
- Historical results are marked and have a return-to-latest action.
- Radix dialogs provide modal focus/close behavior; filters expose aria-pressed.
- Queue filters reset pagination; search is debounced; browser back supports tabs.
- Demo data is synthetic and recorded playback is explained in the guide.

## Remaining limitations / follow-up

- Browser visual, keyboard and mobile interaction verification is outstanding:
  browser tooling failed to initialize in this environment. Responsive CSS and
  production compilation are not a substitute for rendered interaction testing.
- Validate with actual reviewers whether category terminology, source excerpts
  and the four-stage workflow match their working process.
- Backend-authored statements/excerpts may remain in English. Do not silently
  paraphrase clinical evidence in the frontend; localization needs an agreed
  contract or clearly labeled translations.
- Authentication, access controls, durable reviewer notes/decisions and audit
  attribution are not implemented. This remains a synthetic prototype.
- The case timeline is not a historical snapshot. Run-scoped investigation,
  evidence and brief provide the historical results.
- Run history exposes the first backend page (up to 50 results); pagination is
  a future requirement if usage grows beyond the prototype.

## Verification

Passed: TypeScript, ESLint, all 16 unit tests, Next.js production build, and
git diff whitespace checks. Browser-rendered interaction QA remains outstanding.

Run frontend TypeScript/ESLint, unit tests (including golden-case traceability,
source highlighting, playback boundaries, evidence pagination, category coverage
and history ordering), production build, and git diff whitespace checks.
