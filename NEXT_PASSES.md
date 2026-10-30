# Veyepr Continuation Plan: Passes 3–5

**Status:** Planning handoff only. No Pass 3, 4, or 5 implementation is
included in this document.  
**Last completed milestone:** Pass 2 — Harden and Verify (`bdbd7eb`).

This file preserves the product-lead observations and the structure for the
next three working sessions. It is intentionally specific enough to resume
without relying on chat history, while leaving consequential product and
security decisions for the product lead to make at the start of each pass.

## Product intent to preserve

Veyepr is intended to give enterprises an evidence-first way to observe AI
usage and the quality of the resulting output in real time. The system should
not invent a quality grade from weak telemetry. It must make clear:

1. What data was collected.
2. What validation was performed.
3. Which policy or rubric produced an assessment.
4. Who owns that policy and can review or correct a decision.
5. What evidence is retained for an audit.

The current implementation establishes only the first two items for simulated
training telemetry. It does **not** yet grade model output.

## Product observations carried forward

| # | Observation | Decision already made | Follow-through required |
|---|---|---|---|
| 1 | The public interface looked like a gimmicky site trying to sell something and included interview-coaching copy. | Reframed it as an evidence console and decision record; removed the mascot-led hero and interview coaching. | Keep every future interface factual, button-led, and explicit about simulation versus live data. |
| 2 | There was no way to validate data or prove an independent deployment. | Added a JSON Schema, fixtures, Python validation, a Rust verifier, local verification, and optional Compose verification. | Preserve these checks as release gates; add evidence artifacts rather than relying on verbal claims. |
| 3 | The reference runtime depended heavily on Python and mutable dependencies. | Pinned the Python runtime dependency and added a lockfile-backed Rust verifier. | Do not make a full runtime rewrite without comparing reliability, maintenance, data fidelity, and operating ownership. |
| 4 | Tests did not state what they used or whether they involved prompts, research, or coding agents. | README now lists test inputs and states no LLM prompts, deep research, coding agents, or one-shot evaluations are used. | Any future prompt or output-quality evaluation must document prompts, datasets, model version, rubric, evaluator, and retention. |
| 5 | Advanced UI functionality should be streamlined and gated by short multiple-choice questions. | Added a browser-only developer-mode intent check and documented that it is not authorization. | Any privileged capability must use server-side identity, roles, audit logging, and approvals. A quiz can never be the security control. |
| 6 | Docker should not be required for a completely local option. | Added a zero-package local static preview and verification path; Compose is optional. | Keep a local, non-daemon path for documentation, contract review, and basic verification. |

## Cross-pass rules

These rules apply to all remaining passes:

- Do not claim model-output quality assessment until a named rubric and
  accountable review process exist.
- Keep static-preview data visibly labeled as simulated.
- Treat prompts, outputs, and request identifiers as potentially sensitive and
  high-cardinality. They must not become Prometheus labels.
- Keep local, no-Docker verification working.
- Add a test or executable verification command for every new operational
  claim.
- Keep Docker/Compose optional. Its purpose is integration proof, not required
  product access.
- Do not expose privileged, harmful, or production-impacting capabilities from
  a client-side UI gate.
- Record decisions, rejected options, and evidence in the README or a linked
  decision record before presenting a feature as complete.

---

# Pass 3 — `mock_deploy`

## Objective

Model an enterprise-ready deployment path without needing cloud credentials,
production infrastructure, or an active AI model endpoint. The outcome is a
reviewable deployment package: an operator can see what would run, what data
would flow, what must be configured, and which claims are verified locally.

## In scope

1. **Deployment manifest**
   - Add a non-secret configuration template with required and optional
     settings.
   - Define environments such as `local`, `evaluation`, and `production`
     without embedding credentials or real endpoints.
   - Specify ports, health checks, retained data, and log destinations.

2. **Evidence pipeline model**
   - Define the boundary between telemetry validation and future output
     assessment.
   - Add a sample policy/rubric format that remains inactive by default.
   - Show how a policy version, evaluator version, and evidence ID would be
     attached to an assessment record.

3. **Deployment proof package**
   - Produce a dry-run or preflight command that validates configuration,
     contracts, and required files without deploying to a cloud.
   - Generate an evidence report containing command versions, contract
     versions, passed checks, and known limitations.
   - Keep the existing no-Docker path as the minimum proof.

4. **UI**
   - Add a compact deployment-readiness view, not a marketing dashboard.
   - Use buttons for: inspect configuration, run preflight, view generated
     evidence, and review limitations.
   - Clearly distinguish a mock deployment from a real deployment.

## Explicitly out of scope

- Cloud credential collection or storage.
- Automatic production deployment.
- Sending real customer prompts or outputs to any evaluator.
- Treating a mock deployment as a security certification.
- Adding a client-side control that claims to protect sensitive operations.

## Decision interview before implementation

Resolve these one at a time:

1. What deployment target should the mock model first: a private local server,
   a Kubernetes-style workload, or a managed container service?
2. Which evidence must be retained for a deployment approval: only preflight
   results, or configuration plus contract, test, and policy versions?
3. Who is the intended approving role in the workflow: product owner,
   platform owner, risk/compliance owner, or a named combination?
4. What is the first non-sensitive output-assessment use case to model? For
   example: format adherence, required-field completeness, or policy
   classification. Do not select factual correctness until a trusted reference
   dataset is available.

## Acceptance evidence

- A new reader can run the preflight locally with no cloud account.
- The preflight fails clearly on missing or invalid configuration.
- A generated report identifies what was checked, the contract/policy
  versions, and what was not checked.
- The UI labels the flow as a mock deployment.
- Existing Python, Rust, and no-Docker checks still pass.

---

# Pass 4 — `Break_b4_Buying`

## Objective

Intentionally test the assumptions that would otherwise become hidden
operational risk. This is a failure-mode and recovery exercise, not a
penetration test or a path to privileged tooling.

## In scope

1. **Failure catalogue**
   - Invalid and unknown telemetry fields.
   - Schema-version mismatch.
   - Missing timestamp or malformed time zone.
   - Duplicate, delayed, out-of-order, and high-volume events.
   - Unavailable metrics destination.
   - Partial configuration and unavailable local dependencies.
   - Policy/rubric version not found, once Pass 3 has a policy format.

2. **Expected behavior**
   - Define whether each case is rejected, quarantined, retried, sampled, or
     surfaced to an operator.
   - Define the event and metric evidence left behind by each decision.
   - Define what the user sees, what the operator sees, and what is never
     silently ignored.

3. **Recovery drills**
   - Demonstrate a safe return to a healthy state.
   - Verify that a recovery does not erase the evidence of the failed input.
   - Document manual recovery steps before considering automation.

4. **UI**
   - Provide a controlled failure-scenario selector in developer mode.
   - Require server-side authorization before any future scenario could affect
     a live environment.
   - For the public/local preview, use fixtures only; do not expose live fault
     injection or harmful operations.

## Explicitly out of scope

- Exploit development, denial-of-service testing against public services, or
  bypassing access controls.
- Sending malformed traffic to systems not owned by the operator.
- Testing with customer data.
- Claiming comprehensive security coverage from a small failure catalogue.

## Decision interview before implementation

Resolve these one at a time:

1. Which failure class matters first to the intended enterprise buyer:
   incorrect data, unavailable destination, configuration drift, or
   governance/policy mismatch?
2. Should invalid records be dropped after counting, retained locally in a
   quarantine fixture, or routed to an operator review queue?
3. What recovery-time expectation is realistic for this reference system?
4. Which evidence can be retained safely, and what must be redacted before
   it is shown in a report or UI?

## Acceptance evidence

- Each exercised failure has a named input fixture, expected result, and
  observable evidence.
- The test suite proves both rejection and recovery behavior.
- No failure is silently converted into a success-shaped response.
- Local fixture-based drills run without Docker or external accounts.
- The README distinguishes tested failure modes from untested risks.

---

# Pass 5 — `Interlude`

## Objective

Consolidate the verified state into a decision-ready artifact for the product
lead, prospective technical partner, or enterprise evaluator. This is not a
sales presentation. It is a clear statement of what works, what is simulated,
what remains risky, and what decision is needed next.

## In scope

1. **Evidence dossier**
   - Current architecture and contract version.
   - Exact verification commands and latest expected outcomes.
   - Mock-deployment preflight evidence from Pass 3.
   - Failure and recovery evidence from Pass 4.
   - A concise list of unsupported claims and known limitations.

2. **Decision summary**
   - Product problem and target user.
   - Data handled and data intentionally excluded.
   - Current reliability posture.
   - Open security, privacy, and governance decisions.
   - Recommended next investment: prototype extension, technical validation,
     security review, or deployment pilot.

3. **Interface cleanup**
   - Ensure public routes show only verified capabilities.
   - Preserve a direct path to the decision record and local verification
     instructions.
   - Remove stale mock, interview, or demo language that no longer reflects
     the product boundary.

## Explicitly out of scope

- Making claims of enterprise readiness without a deployment owner and
  security review.
- Treating a static public preview as a production service.
- Introducing new core features. Interlude consolidates evidence; it does not
  expand scope.

## Decision interview before implementation

Resolve these one at a time:

1. Who is the primary reader of the dossier: enterprise buyer, technical
   cofounder, platform engineering team, or risk/compliance stakeholder?
2. What decision should the dossier enable: fund a pilot, approve a technical
   spike, select a deployment target, or pause pending risk reduction?
3. What proof would make the product lead comfortable saying “ready for the
   next controlled trial”?
4. Which limitations should remain visible in the public repository after it
   becomes private again?

## Acceptance evidence

- A reader can reproduce the verified claims from the documented commands.
- A reader can identify every simulation and every deliberate non-goal.
- The final recommendation names the next decision owner and decision needed.
- No new unverified product claim is introduced during consolidation.

---

## Restart checklist for the next session

1. Confirm the repository is private and that no credentials or real customer
   data have been added.
2. Read this file, the README decision record, and the latest commit history.
3. Run the existing baseline before making changes:

   ```bash
   ./scripts/verify-local.sh
   python3 -m pytest
   cd verifier && cargo test --locked
   ```

4. Start with the decision interview for the selected pass. Do not implement
   until the pass-specific choices are recorded.
5. Keep the scope boundary visible: validated telemetry is available today;
   output-quality assessment requires a declared rubric and accountable review.
