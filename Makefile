.PHONY: recsys test verify-docs marketplace

recsys:
	python3 recsys/src/run_all.py

test:
	python3 -m unittest discover -s recsys/tests -v

verify-docs:
	python3 scripts/validate_project_docs.py

marketplace:
	npm run dev

# Independent pretrained ABO benchmark; the historical RecSys targets above stay fixed.
MULTIMODAL_PYTHON ?= .venv-multimodal/bin/python
MM_ENV = OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1

.PHONY: multimodal-test multimodal-dev multimodal-benchmark multimodal-verify-docs

multimodal-test:
	$(MM_ENV) $(MULTIMODAL_PYTHON) -m unittest discover -s multimodal/tests -v

multimodal-dev:
	$(MM_ENV) $(MULTIMODAL_PYTHON) -m multimodal.src.benchmark --profile dev

multimodal-benchmark:
	$(MM_ENV) $(MULTIMODAL_PYTHON) -m multimodal.src.benchmark --profile mvp

multimodal-verify-docs:
	$(MULTIMODAL_PYTHON) -m multimodal.src.report --check

.PHONY: agent-test agent-benchmark agent-verify-docs agent-serve
AGENT_OUTPUT ?= multimodal/results/local-agent-$(shell date -u +%Y%m%dT%H%M%SZ)

agent-test:
	$(MM_ENV) $(MULTIMODAL_PYTHON) -m unittest discover -s multimodal/agent_tests -v

agent-benchmark:
	$(MM_ENV) $(MULTIMODAL_PYTHON) -m multimodal.src.agent_benchmark --output $(AGENT_OUTPUT)

agent-verify-docs:
	$(MM_ENV) $(MULTIMODAL_PYTHON) -m multimodal.src.agent_report --check

agent-serve:
	$(MM_ENV) $(MULTIMODAL_PYTHON) -m multimodal.src.agent_server
