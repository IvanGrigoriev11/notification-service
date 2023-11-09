SOURCE_DIRS = notification_service
TEST_DIRS = tests
SOURCE_AND_TEST_DIRS = $(SOURCE_DIRS) $(TEST_DIRS)

.PHONY: format lint-fix fix format-check lint pyright test

all: format-check lint pyright test

format:
	ruff -e --fix-only --select I001 $(SOURCE_AND_TEST_DIRS)
	black $(SOURCE_AND_TEST_DIRS)

lint-fix:
	ruff -e --fix-only $(SOURCE_AND_TEST_DIRS)

fix: lint-fix
	black $(SOURCE_AND_TEST_DIRS)

format-check:
	@(ruff --select I001 $(SOURCE_AND_TEST_DIRS)) && (black --check $(SOURCE_AND_TEST_DIRS)) || (echo "run \"make format\" to format the code"; exit 1)

lint:
	@(ruff $(SOURCE_AND_TEST_DIRS)) || (echo "run \"make lint-fix\" to fix some lint errors automatically"; exit 1)

pyright:
	pyright

test:
	python -m pytest $(TEST_DIRS)
