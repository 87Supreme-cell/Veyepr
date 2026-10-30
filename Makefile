.PHONY: test verify-local verify-compose verify-rust verify-contract verify-rust-container mock-deploy break-drills firm-demo

test:
	python3 -m pytest

verify-local:
	./scripts/verify-local.sh

verify-compose:
	./scripts/verify-compose.sh

verify-rust:
	cd verifier && cargo test --locked

verify-contract:
	cd verifier && cargo run --quiet --locked -- ../fixtures/valid-training-event.json

verify-rust-container:
	docker run --rm -v "$(CURDIR)/verifier:/workspace" -w /workspace rust:1.79 cargo test --locked

mock-deploy:
	./scripts/mock-deploy-preflight.sh

break-drills:
	./scripts/run-break-drills.sh

firm-demo:
	./scripts/run-firm-adapter.sh
