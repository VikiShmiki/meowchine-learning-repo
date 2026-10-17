#!/usr/bin/env bash
#SBATCH --job-name=recycling-translate-mk
#SBATCH --partition=cybermacs-queue
#SBATCH --gres=gpu:1
#SBATCH --nodelist=gpgpu01
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --output=logs/slurm/translate_mk_%j.out
#SBATCH --error=logs/slurm/translate_mk_%j.err

set -euo pipefail

repo_dir="${SLURM_SUBMIT_DIR:?Submit from the repository root}"
faculty_packages="/home/hpc/users/ml_models/rebeka.maneva/py_pkgs_cuda126"
export PYTHONNOUSERSITE=1
export PYTHONPATH="$repo_dir/src:$repo_dir/artifacts/cluster/python:$faculty_packages"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export TOKENIZERS_PARALLELISM=false
export HF_HOME="$repo_dir/runtime/huggingface"
export HF_HUB_DISABLE_PROGRESS_BARS=1

cd "$repo_dir"
python3 -u scripts/translate_datasets.py --device cuda --resume
