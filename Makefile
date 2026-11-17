PYTHON ?= python3

.PHONY: build artwork preview test verify

build:
	$(PYTHON) lumi.py build

artwork:
	$(PYTHON) lumi.py artwork

preview:
	$(PYTHON) lumi.py preview

test:
	$(PYTHON) -m unittest discover -s tests -v

verify:
	$(PYTHON) lumi.py verify
