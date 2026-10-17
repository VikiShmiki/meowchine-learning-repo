#!/usr/bin/env bash
#SBATCH --job-name=recycling-minilm
#SBATCH --partition=cybermacs-queue
#SBATCH --gres=gpu:1
#SBATCH --nodelist=gpgpu01
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=logs/slurm/minilm_gpu_%j.out
#SBATCH --error=logs/slurm/minilm_gpu_%j.err

set -euo pipefail

repo_dir="${SLURM_SUBMIT_DIR:?Submit this job from the repository root}"
package_dir="$repo_dir/artifacts/cluster/python"
faculty_packages="/home/hpc/users/ml_models/rebeka.maneva/py_pkgs_cuda126"

if [[ ! -d "$package_dir/sentence_transformers" ]]; then
  echo "Missing $package_dir/sentence_transformers; run make minilm-cluster-bootstrap first" >&2
  exit 2
fi
if [[ ! -d "$faculty_packages/torch" ]]; then
  echo "Missing faculty CUDA package cache: $faculty_packages" >&2
  exit 2
fi
if [[ ! -d "$package_dir/sklearn" ]]; then
  echo "Missing $package_dir/sklearn; run make minilm-cluster-bootstrap first" >&2
  exit 2
fi

export PYTHONNOUSERSITE=1
export PYTHONPATH="$repo_dir/src:$package_dir:$faculty_packages"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export TOKENIZERS_PARALLELISM=false

cd "$repo_dir"

python3 -u - <<'PY'
import platform

import joblib
import numpy
import pandas
import sentence_transformers
import sklearn
import scipy
import torch
import transformers

expected = {
    "torch": "2.13.0+cu126",
    "transformers": "5.13.0",
    "sentence-transformers": "5.7.0",
    "scikit-learn": "1.7.2",
    "joblib": "1.5.3",
    "numpy": "2.2.6",
    "pandas": "2.3.3",
    "scipy": "1.15.3",
}
actual = {
    "torch": torch.__version__,
    "transformers": transformers.__version__,
    "sentence-transformers": sentence_transformers.__version__,
    "scikit-learn": sklearn.__version__,
    "joblib": joblib.__version__,
    "numpy": numpy.__version__,
    "pandas": pandas.__version__,
    "scipy": scipy.__version__,
}
if actual != expected:
    raise RuntimeError(f"Unexpected mutable host package versions: {actual}; expected {expected}")
print("Python:", platform.python_version(), flush=True)
for name, version in actual.items():
    print(f"{name}: {version}", flush=True)
print("CUDA runtime:", torch.version.cuda, flush=True)
if torch.version.cuda != "12.6":
    raise RuntimeError(f"Expected CUDA runtime 12.6, found {torch.version.cuda}")
print("CUDA available:", torch.cuda.is_available(), flush=True)
if not torch.cuda.is_available():
    raise RuntimeError("Slurm allocated a GPU but CUDA is unavailable to torch")
print("GPU:", torch.cuda.get_device_name(0), flush=True)
PY

python3 -u scripts/evaluate_minilm_development.py \
  --device cuda \
  --batch-size 256 \
  --no-progress \
  --results-dir results/gpu \
  --artifacts-dir artifacts/models/gpu
