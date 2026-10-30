# Pass 6 Test Log

## Purpose and scope

This is the committed, verbose record of the Pass 6 local test run. It
transcribes each collected Python test case and its result, then records the
separate no-Docker operational checks that are not pytest cases.

The suite uses local fixtures and simulated telemetry only. It does not call
an LLM, send prompts, contact cloud services, access OAuth/JWT credentials,
or evaluate real employee or customer activity.

## Environment

| Item | Value |
| --- | --- |
| Test date | 2026-10-30 |
| Python | 3.14.7 |
| pytest | 8.4.2 |
| Test command | `.venv/bin/python -m pytest -vv` |
| Collected tests | 25 |
| Result | 25 passed in 0.67s |

## Verbose Python test transcript

```text
tests/test_app.py::test_console_and_triolingo_pages_are_served PASSED    [  4%]
tests/test_drills.py::test_failure_drills_match_declared_outcomes PASSED [  8%]
tests/test_drills.py::test_contract_rejection_preserves_no_raw_content PASSED [ 12%]
tests/test_drills.py::test_clean_recovery_remains_independent_after_prior_drills PASSED [ 16%]
tests/test_drills.py::test_failure_drills_reject_weakened_contract PASSED [ 20%]
tests/test_mock_deploy.py::test_mock_deploy_preflight_generates_review_only_evidence PASSED [ 24%]
tests/test_mock_deploy.py::test_mock_deploy_preflight_rejects_a_missing_artifact PASSED [ 28%]
tests/test_mock_deploy.py::test_write_json_does_not_overwrite_evidence PASSED [ 32%]
tests/test_mock_deploy.py::test_cli_rejects_existing_output_before_writing_any_artifact PASSED [ 36%]
tests/test_models.py::test_training_event_converts_scalar_tensor_like_values PASSED [ 40%]
tests/test_models.py::test_training_event_rejects_invalid_contract_values[batch_size-0] PASSED [ 44%]
tests/test_models.py::test_training_event_rejects_invalid_contract_values[batch_size-4.5] PASSED [ 48%]
tests/test_models.py::test_training_event_rejects_invalid_contract_values[batch_size-True] PASSED [ 52%]
tests/test_models.py::test_training_event_rejects_invalid_contract_values[step-1.5] PASSED [ 56%]
tests/test_models.py::test_training_event_rejects_invalid_contract_values[gradient_norm--0.1] PASSED [ 60%]
tests/test_router.py::test_pipeline_captures_transforms_routes_and_exposes_metrics PASSED [ 64%]
tests/test_router.py::test_pipeline_counts_unroutable_event_as_dropped PASSED [ 68%]
tests/test_sentinel.py::test_normal_action_needs_no_review PASSED        [ 72%]
tests/test_sentinel.py::test_sensitive_export_is_routed_to_human_review PASSED [ 76%]
tests/test_sentinel.py::test_audit_package_is_metadata_only_and_tamper_evident PASSED [ 80%]
tests/test_sentinel.py::test_action_rejects_raw_content_or_unknown_fields PASSED [ 84%]
tests/test_sentinel.py::test_contract_rejects_unknown_fields_and_missing_hash_pattern PASSED [ 88%]
tests/test_validation.py::test_contract_fixture_is_accepted_by_python_validator PASSED [ 92%]
tests/test_validation.py::test_invalid_contract_fixture_is_rejected PASSED [ 96%]
tests/test_validation.py::test_router_reports_contract_validation_outcomes PASSED [100%]

============================== 25 passed in 0.67s ==============================
```

## Operational verification transcript

These are executable repository checks. They are logged separately because
they validate a local workflow rather than appearing as individual pytest
items.

### Dependency-free static preview

**Command**

```bash
./scripts/verify-local.sh
```

**Output**

```text
Verification passed: dependency-free public pages and contract fixtures are available.
```

This serves and checks the six static pages, assets, preview metrics fixture,
and training-event JSON fixtures using standard local tooling.

### Review-only mock-deployment preflight

**Command**

```bash
./scripts/mock-deploy-preflight.sh /tmp/veyepr-pass6-mock-18490
```

**Output**

```text
Mock deployment preflight passed: review_required with 2 finding(s).
Evidence report: /tmp/veyepr-pass6-mock-18490/preflight-report.json
Review package: /tmp/veyepr-pass6-mock-18490/review-package.json
```

The JSON report and review package were then parsed successfully with
`python -m json.tool`. The fixture result is review-only; it performs no
blocking, alerting, or real-session inspection.

### Fixture-only failure and recovery drills

**Command**

```bash
./scripts/run-break-drills.sh /tmp/veyepr-pass6-drills-18489
```

**Output**

```text
Failure drills passed: 5 scenarios, 3 review-required, 1 rejected.
Drill report: /tmp/veyepr-pass6-drills-18489/drill-report.json
```

The report integrity digest was verified after generation. The five scenarios
produce one `rejected`, three `review_required`, and one
`no_review_required` outcome. Raw prompts and raw tool outputs are not
retained in the report.

## Unavailable check

The locked Rust verifier command remains:

```bash
(cd verifier && cargo test --locked)
```

It was **not run** in this environment because `cargo` is not installed. No
Rust result is represented as a Pass 6 success. Run the command on a host
with the declared Rust toolchain before using the Rust verifier as fresh
evidence.

## Interpretation boundary

Passing this test run proves only the local behavior named above. It does not
prove production readiness, live network interception, OAuth/JWT monitoring,
immutable evidence retention, output-quality grading, security certification,
or a basis for a personnel decision.
