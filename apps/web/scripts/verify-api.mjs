import assert from "node:assert/strict";
import { readFile, mkdir, writeFile } from "node:fs/promises";
const base = process.env.EPISIGHT_VERIFY_URL || "http://127.0.0.1:3001/api/v1";
const ids = [
  "CASE-RA-0bbfc334",
  "CASE-FR-83f41f66",
  "CASE-RA-d7840713",
  "CASE-RA-609280ef",
  "CASE-RA-608764ca",
];
async function request(path, options) {
  const res = await fetch(`${base}/${path}`, options);
  const body = await res.json();
  return { status: res.status, body, headers: res.headers };
}
const health = await request("health");
assert.equal(health.status, 200);
assert.equal(health.body.dataset_version, "v0.1.0");
assert.equal(health.body.corpus_version, "pc-0.1.1");
const queue = await request("cases?limit=10");
assert.equal(queue.body.total, 20);
assert.equal(queue.body.items.length, 10);
assert.equal((await request("cases?signal_type=FRAGMENTATION")).body.total, 7);
assert.equal(
  (await request("cases?q=PAT-000001")).body.items[0].case_id,
  ids[0],
);
assert.equal((await request("cases/CASE-NOT-FOUND")).status, 404);
const results = [];
for (const id of ids) {
  const detail = await request(`cases/${id}`);
  assert.equal(detail.status, 200);
  assert.ok(detail.headers.get("x-request-id"));
  const timeline = await request(`cases/${id}/episodes`);
  assert.equal(timeline.body.case_id, id);
  assert.ok(timeline.body.episodes.some((e) => e.role === "ANCHOR"));
  const accepted = await request(`cases/${id}/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: "FULL_RULE_PLANNER",
      rerun: !!detail.body.latest_run,
      max_steps: 12,
    }),
  });
  assert.equal(accepted.status, 202);
  const deadline = Date.now() + 60000;
  let run;
  do {
    run = await request(
      `cases/${id}/investigation?run_id=${accepted.body.run_id}`,
    );
    assert.equal(run.status, 200);
    if (!["QUEUED", "RUNNING"].includes(run.body.run.run_status)) break;
    await new Promise((r) => setTimeout(r, 200));
  } while (Date.now() < deadline);
  assert.equal(run.body.run.run_status, "COMPLETED");
  const brief = await request(`cases/${id}/brief`),
    evidence = await request(`cases/${id}/evidence`),
    history = await request(`cases/${id}/runs`);
  const expected = JSON.parse(
    await readFile(
      new URL(`../public/demo/cases/${id}.brief.json`, import.meta.url),
      "utf8",
    ),
  );
  assert.equal(brief.body.outcome, expected.outcome);
  assert.equal(brief.body.stop_reason, expected.stop_reason);
  assert.equal(
    brief.body.traceability.material_statements,
    brief.body.traceability.with_evidence,
  );
  assert.equal(
    (
      await request(`cases/${id}/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      })
    ).body.error.code,
    "INVESTIGATION_ALREADY_COMPLETED",
  );
  assert.ok(history.body.items.some((r) => r.run_id === accepted.body.run_id));
  const sources = await Promise.all(
    evidence.body.items.map(async (e) => {
      const source = await request(`evidence/${e.evidence_id}`);
      assert.equal(source.status, 200);
      assert.equal(source.body.evidence_id, e.evidence_id);
      return source.body;
    }),
  );
  if (brief.body.outcome === "EVIDENCE_CONFLICTING") {
    const c = brief.body.conflicts[0];
    assert.ok(
      c.affirming_evidence_ids.length && c.negating_evidence_ids.length,
    );
  }
  if (brief.body.outcome === "EVIDENCE_UNAVAILABLE")
    assert.ok(brief.body.remaining_gaps.some((g) => g.state === "UNAVAILABLE"));
  results.push({
    case_id: id,
    outcome: brief.body.outcome,
    stop_reason: brief.body.stop_reason,
    steps: run.body.run.step,
    evidence: sources.length,
    traceability: brief.body.traceability,
    run_id: accepted.body.run_id,
  });
  console.log(
    `${id}: ${brief.body.outcome}, ${sources.length} sources, all checks passed`,
  );
}
await mkdir(new URL("../test-results/", import.meta.url), { recursive: true });
await writeFile(
  new URL("../test-results/api-smoke.json", import.meta.url),
  JSON.stringify(
    {
      checked_at: new Date().toISOString(),
      base,
      mode: "FULL_RULE_PLANNER",
      results,
    },
    null,
    2,
  ) + "\n",
);
console.log("Live API + frontend proxy: 5/5 golden flows passed.");
