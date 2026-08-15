.PHONY: recsys test verify-docs marketplace

recsys:
	python3 recsys/src/run_all.py

test:
	python3 -m unittest discover -s recsys/tests -v

verify-docs:
	python3 scripts/validate_project_docs.py

marketplace:
	npm run dev
