.PHONY: all validate prepare analyze

all: validate prepare analyze

validate:
	bash scripts/validate_header.sh
	bash scripts/validate.sh

prepare:
	python3 scripts/prepare_analysis.py

analyze:
	python3 scripts/analyze_results.py
