# This Makefile has some convenience targets for use durint development. In
# particular, running "make check" before committing identifies any style
# issues. "make sort" can fix these issues that relate to import sorting.

all:
	@echo "  clean        Removes all temporary files"
	@echo "  check        Run all relevant pre-commit checks"
	@echo "  sort         Apply proper import sorting"
	@echo "  coverage     Runs the tests and shows code coverage"
	@echo "  flake8       Runs flake8 to check for PEP8 compliance"
	@echo "  test         Runs the tests"


# performs the tests and measures code coverage
coverage: ensure_virtual_env test
	$(PYTHON_BIN)/coverage html
	$(PYTHON_BIN)/coverage report


# deletes all temporary files created by Django
clean:
	@find . -iname "*.pyc" -delete
	@find . -iname "__pycache__" -delete
	@rm -rf .coverage coverage_html


# Run all pre-commit checks
check: flake8 test

# Fix import sorting
sort:
	./setup.py isort -y

# runs flake8 to check for PEP8 compliance
flake8:
	./setup.py flake8

# runs the tests
test:
	# TODO: run tests

.PHONY: all clean coverage flake8 check test
