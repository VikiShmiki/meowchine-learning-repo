"""Environment-backed configuration."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(os.getenv("SRA_PROJECT_ROOT", Path.cwd())).resolve()


def _enabled(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


@dataclass(frozen=True)
class Settings:
    classifier_path: Path
    random_seed: int
    sites_data_path: Path
    infrastructure_path: Path
    policy_path: Path
    guidance_policy_path: Path = Path("data/policy/skopje_v2.json")
    coverage_path: Path = Path("data/coverage/skopje-v1")
    upgrades_path: Path = Path("data/upgrades/skopje-v1")
    ors_api_key: str = field(repr=False, default="")
    openai_api_key: str = field(repr=False, default="")
    openai_vision_model: str = "gpt-5.6-luna"
    minilm_suggestions_enabled: bool = True
    minilm_model_path: Path | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        if "SRA_CONFIDENCE_THRESHOLD" in os.environ:
            raise ValueError(
                "SRA_CONFIDENCE_THRESHOLD is retired; use the evaluated classifier artifact"
            )
        classifier = Path(os.getenv("SRA_CLASSIFIER_PATH", "data/classifier/rules-v3.json"))

        configured_path = Path(os.getenv("SRA_SITES_DATA_PATH", "data/seed/sites.json"))
        if not configured_path.is_absolute():
            configured_path = PROJECT_ROOT / configured_path

        infrastructure = Path(
            os.getenv(
                "SRA_INFRASTRUCTURE_PATH",
                "data/infrastructure/skopje-2026-09-19",
            )
        )
        policy = Path(os.getenv("SRA_POLICY_PATH", "data/policy/skopje_v1.json"))
        configured_model_path = os.getenv("SRA_MINILM_MODEL_PATH", "").strip()

        return cls(
            classifier_path=classifier if classifier.is_absolute() else PROJECT_ROOT / classifier,
            random_seed=int(os.getenv("SRA_RANDOM_SEED", "42")),
            sites_data_path=configured_path,
            infrastructure_path=(
                infrastructure if infrastructure.is_absolute() else PROJECT_ROOT / infrastructure
            ),
            policy_path=policy if policy.is_absolute() else PROJECT_ROOT / policy,
            guidance_policy_path=PROJECT_ROOT
            / os.getenv("SRA_GUIDANCE_POLICY_PATH", "data/policy/skopje_v2.json"),
            coverage_path=PROJECT_ROOT / os.getenv("SRA_COVERAGE_PATH", "data/coverage/skopje-v1"),
            upgrades_path=PROJECT_ROOT / os.getenv("SRA_UPGRADES_PATH", "data/upgrades/skopje-v1"),
            ors_api_key=os.getenv("SRA_ORS_API_KEY", "").strip(),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_vision_model=os.getenv("SRA_OPENAI_VISION_MODEL", "gpt-5.6-luna").strip(),
            minilm_suggestions_enabled=_enabled("SRA_MINILM_SUGGESTIONS", True),
            minilm_model_path=(
                (PROJECT_ROOT / configured_model_path).resolve() if configured_model_path else None
            ),
        )
