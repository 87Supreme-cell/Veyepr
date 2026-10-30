# Veyepr Evidence Dossier

## Purpose and decision enabled

This dossier is a factual handoff for a product lead, technical partner, or
enterprise evaluator. It describes what this repository verifies locally,
what remains simulated, and the next decision required. It is not a claim of
production readiness, AI-output quality scoring, or enterprise security
certification.

**Recommended decision:** authorize a bounded technical-validation spike only
after an accountable deployment owner, privacy/legal reviewer, retention
owner, identity/access owner, and subject-access or appeal owner are named.
Do not approve live interception or enforcement from the current prototype.

## Verified local capabilities

| Area | Verified artifact | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Training telemetry | `contracts/training-event.schema.json`, Python tests, Rust verifier | A supplied training event has the published shape and core semantic constraints. | Model-output factuality, safety, or business suitability. |
| Operational exposition | Python pipeline tests and `/metrics` contract | Accepted training telemetry is routed to bounded Prometheus metrics. | A production monitoring deployment or operational SLO. |
| Static review | `scripts/verify-local.sh` | The dependency-free browser pages and declared JSON fixtures are assembled and served locally. | A running telemetry backend behind the static preview. |
| Mock deployment | `deployment/mock-deploy.json`, `scripts/mock-deploy-preflight.sh` | Contracts, policy, fixture input, and package integrity can be checked locally before a mock evidence package is written. | Cloud deployment, real agents, OAuth providers, or immutable storage. |
| Review-only sentinel | `contracts/agent-action.schema.json`, `policy/mock-sentinel-policy.json` | Sanitized tool-action metadata can be evaluated against transparent local rules. | Intent determination, misconduct determination, blocking, or discipline. |
| Failure and recovery drills | `fixtures/failure-drills.json`, `scripts/run-break-drills.sh` | Fixture failures have declared outcomes: rejected, review-required, or no-review-required recovery. | Live fault tolerance, attack resistance, or coverage of every failure mode. |

## Reproducible commands

Run these from the repository root. The first, mock deployment, and drills
need no Docker, cloud account, network endpoint, LLM, prompt, or real agent.

```bash
# Full Python reference test suite (after creating the documented .venv)
.venv/bin/python -m pytest

# Static preview and contract-fixture checks using standard Python tooling
./scripts/verify-local.sh

# Review-only mock deployment: output directory must be new
./scripts/mock-deploy-preflight.sh artifacts/review-demo

# Fixture-only failure and recovery drills: output directory must be new
./scripts/run-break-drills.sh artifacts/break-b4-buying

# Independent verifier with the committed Rust lockfile
(cd verifier && cargo test --locked)
```

Optional integration proof requires Docker Desktop:

```bash
./scripts/verify-compose.sh
```

The local scripts fail rather than overwrite existing evidence paths. The
mock-deployment and drill reports include SHA-256 payload digests. A digest is
only tamper-evident if its original value is retained independently; it is not
immutable storage or a digital signature.

## Current validation record

| Command | Current result |
| --- | --- |
| `.venv/bin/python -m pytest` | Passed: **25 tests**. |
| `./scripts/verify-local.sh` | Passed: all six static pages, assets, preview metrics fixture, and JSON fixtures served locally. |
| `./scripts/mock-deploy-preflight.sh <new-directory>` | Passed: generated a `review_required` package with two findings and no raw prompt/output content. |
| `./scripts/run-break-drills.sh <new-directory>` | Passed: five scenarios matched expectation—one rejected, three review-required, and one no-review-required recovery. |
| `(cd verifier && cargo test --locked)` | Not run in this environment because `cargo` is not installed. The command remains required when a Rust toolchain is available; do not treat it as current-run evidence. |

The per-test Pass 6 transcript is preserved in
[`PASS_6_TEST_LOG.md`](PASS_6_TEST_LOG.md).

## Current contracts and data boundary

1. `training-event.schema.json` accepts simulated training telemetry: `run_id`,
   `step`, `loss`, `gradient_norm`, `batch_size`, and an RFC 3339 timestamp.
2. `agent-action.schema.json` accepts only sanitized metadata: opaque session,
   action, actor, and target references; tool/action metadata; classification;
   requested scopes; estimated bytes; and SHA-256 hashes of prompt and output.
3. The agent-action contract rejects unknown fields, raw prompts, raw tool
   outputs, malformed timestamps, and unbounded identifiers.
4. The local policy supports exactly `review_only` and
   `metadata_and_hashes_only`.
5. Prompts, outputs, request IDs, timestamps, and step values are never
   Prometheus labels.

The supplied failure suite tests one unknown-field rejection, one duplicate-ID
sequence, one timestamp regression, one sensitive-export policy mismatch, and
one independent clean recovery. Its report preserves only record counts,
opaque identifiers, hashes, matched rules, and recovery guidance.

## Simulated elements and deliberate non-goals

- Browser telemetry is simulated for static preview.
- Agent and export scenarios are local JSON fixtures; no real user, customer,
  employee, SharePoint, OAuth, or SaaS data is used.
- No live network interception, endpoint sensor, proxy, OAuth/JWT collection,
  screen capture, session seizure, external alert, or SOC integration exists.
- No automatic block, suspension, discipline, employee scoring, or intent
  classification exists.
- A `review_required` result asks for human context. It is not evidence of
  malicious intent, misconduct, or a policy violation.
- The review package names both `security_reviewer` and `session_subject` as
  review parties, but it does not implement identity, access control,
  notification, appeals, or case management.

## Current gaps before a controlled trial

| Gap | Why it matters | Decision owner needed |
| --- | --- | --- |
| Data minimization and retention | Metadata can still be sensitive or linkable. | Privacy/legal and data governance |
| Identity and subject access | A package must be visible only to authorized reviewers and the subject through a defined process. | Identity/platform and HR/legal |
| Policy governance | Scope allowlists, export thresholds, and severities require accountable ownership and change control. | Security/risk and product |
| Evidence integrity | Local SHA-256 alone is not signing, independent retention, or chain of custody. | Security/platform |
| Deployment boundary | Any proxy, sidecar, or agent must be independently authorized and unable to be disabled by the model it observes. | Platform security |
| Evaluation validity | Output-quality grading needs a named rubric, reference data, evaluator, correction process, and review owner. | Product and domain owner |

## Next investment gate

The appropriate next step is **a technical-validation spike, not a deployment
pilot**. Its written charter should limit inputs to synthetic or explicitly
approved non-sensitive fixtures and should answer:

1. Which deployment boundary is accountable for collection?
2. Who owns policy authoring, review, correction, and subject access?
3. What minimum metadata is necessary for a review?
4. How are packages signed, retained, accessed, and deleted?
5. What proves that the observed system cannot control or disable its own
   observer?

Until those answers exist, keep Veyepr in its current local,
review-only, evidence-first mode.
