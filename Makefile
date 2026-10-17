.PHONY: bootstrap run test lint format check seed-check data-download data-prepare data-all minilm-evaluate minilm-development minilm-cluster-bootstrap minilm-cluster-submit geo-prepare geo-check

bootstrap:
	uv sync --all-groups --locked

run:
	uv run uvicorn smart_recycling.api:app --reload

test:
	uv run --all-groups pytest

lint:
	uv run --all-groups ruff check .

format:
	uv run --all-groups ruff format .

check:
	uv lock --check
	uv run --all-groups ruff check .
	uv run --all-groups ruff format --check .
	uv run --all-groups pytest
	node --test tests/web_guidance.test.js tests/web_map.test.js

seed-check:
	uv run python scripts/validate_seed.py

data-download:
	uv run --group data python scripts/download_dataset_a.py
	uv run --group data python scripts/download_dataset_b.py

data-prepare:
	uv run --group data python scripts/run_data_pipeline.py --skip-download

data-all:
	uv run --group data python scripts/run_data_pipeline.py

minilm-evaluate:
	uv run --group data python scripts/evaluate_minilm.py

minilm-development:
	uv run --group data python scripts/evaluate_minilm_development.py

minilm-cluster-bootstrap:
	bash scripts/bootstrap_minilm_cluster.sh

minilm-cluster-submit:
	mkdir -p logs/slurm
	sbatch scripts/run_minilm_gpu.slurm

geo-prepare:
	uv run --group geo python scripts/prepare_geography.py

geo-check:
	uv run python scripts/validate_geography.py
