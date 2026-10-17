#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package_dir="$repo_dir/artifacts/cluster/python"

mkdir -p "$package_dir"
if [[ -d "$package_dir/sentence_transformers-5.7.0.dist-info" \
  && -d "$package_dir/scikit_learn-1.7.2.dist-info" \
  && -d "$package_dir/joblib-1.5.3.dist-info" \
  && -d "$package_dir/threadpoolctl-3.6.0.dist-info" ]]; then
  echo "Pinned host-Python package layer already exists at $package_dir"
  exit 0
fi

python3 -m pip install \
  --disable-pip-version-check \
  --no-deps \
  --upgrade \
  --target "$package_dir" \
  'sentence-transformers==5.7.0' \
  'scikit-learn==1.7.2' \
  'joblib==1.5.3' \
  'threadpoolctl==3.6.0'

echo "Prepared the host-Python MiniLM package layer at $package_dir"
