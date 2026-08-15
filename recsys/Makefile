PYTHON ?= python3

.PHONY: all pipeline test clean

all: pipeline test

pipeline:
	$(PYTHON) src/run_all.py

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	$(PYTHON) -c "import sys; sys.path.insert(0, 'src'); from run_all import clean_generated_files; clean_generated_files()"
