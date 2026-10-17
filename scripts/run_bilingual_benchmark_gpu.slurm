#!/usr/bin/env bash
#SBATCH --job-name=recycling-bilingual-s42
#SBATCH --partition=cybermacs-queue
#SBATCH --gres=gpu:1
#SBATCH --nodelist=gpgpu01
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=00:45:00
#SBATCH --output=logs/slurm/bilingual_seed42_%j.out
#SBATCH --error=logs/slurm/bilingual_seed42_%j.err

set -euo pipefail

repo_dir="${SLURM_SUBMIT_DIR:?Submit this job from the repository root}"
faculty_packages="/home/hpc/users/ml_models/rebeka.maneva/py_pkgs_cuda126"
package_dir="$repo_dir/artifacts/cluster/python"
dataset_version="${1:-v1}"
run_seed="${2:-${SLURM_ARRAY_TASK_ID:-42}}"
[[ "$run_seed" =~ ^[0-9]+$ ]] || { echo "Seed must be a nonnegative integer" >&2; exit 2; }
case "$dataset_version" in
  v1) run_name="bilingual_seed$run_seed" ;;
  v2) run_name="bilingual_v2_seed$run_seed" ;;
  *) echo "Expected dataset version v1 or v2" >&2; exit 2 ;;
esac
results_dir="$repo_dir/results/$run_name"
artifacts_dir="$repo_dir/artifacts/models/$run_name"
data_dir="$repo_dir/data/processed/bilingual_mk_$dataset_version"

for required in "$faculty_packages/torch" "$faculty_packages/transformers" \
  "$faculty_packages/peft" "$faculty_packages/accelerate" "$package_dir/sentence_transformers" \
  "$package_dir/sklearn"; do
  [[ -d "$required" ]] || { echo "Missing required package directory: $required" >&2; exit 2; }
done

export PYTHONNOUSERSITE=1
export PYTHONPATH="$repo_dir/src:$package_dir:$faculty_packages"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export TOKENIZERS_PARALLELISM=false
export HF_HOME="$repo_dir/runtime/huggingface"

cd "$repo_dir"
mkdir -p logs/slurm "$results_dir" "$artifacts_dir" "$HF_HOME"

python3 -u - <<'PY'
import importlib.metadata as metadata
import platform
import torch

expected = {
    "transformers": "5.13.0",
    "peft": "0.19.1",
    "accelerate": "1.14.0",
    "sentence-transformers": "5.7.0",
    "scikit-learn": "1.7.2",
}
actual = {name: metadata.version(name) for name in expected}
if actual != expected:
    raise RuntimeError(f"Unexpected package versions: {actual}; expected {expected}")
if torch.__version__ != "2.13.0+cu126":
    raise RuntimeError(f"Unexpected Torch runtime: {torch.__version__}")
if not torch.cuda.is_available() or torch.version.cuda != "12.6":
    raise RuntimeError(f"CUDA 12.6 GPU required, got available={torch.cuda.is_available()}, runtime={torch.version.cuda}")
print("Python:", platform.python_version(), flush=True)
print("Packages:", actual, flush=True)
print("GPU:", torch.cuda.get_device_name(0), flush=True)
print("CUDA:", torch.version.cuda, flush=True)
PY

python3 -u scripts/run_bilingual_benchmark.py \
  --results-dir "$results_dir" \
  --artifacts-dir "$artifacts_dir" \
  --data-dir "$data_dir" \
  --seed "$run_seed" \
  --device cuda \
  --batch-size 32 \
  --epochs 3 \
  --learning-rate 2e-4
