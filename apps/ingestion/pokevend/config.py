"""Configuration loading and validation.

Both YAML files are read once and validated eagerly so a typo in a weight fails
the pipeline at startup rather than silently skewing every forecast.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_DIR = REPO_ROOT / "config"

_WEIGHT_SUM_TOLERANCE = 1e-6


class ConfigError(RuntimeError):
    """Raised when configuration is missing or internally inconsistent."""


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ConfigError(f"configuration file is not a mapping: {path}")
    return data


class ForecastConfig:
    """Typed accessor over forecast_config.yaml."""

    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw
        self.location = raw.get("location", {})
        self.forecast = raw.get("forecast", {})
        self.scoring_weights = raw.get("scoring_weights", {})
        self.confidence = raw.get("confidence", {})
        self.observation_weights = raw.get("observation_weights", {})
        self.matching = raw.get("matching", {})
        self.network_prior = raw.get("network_prior", {})
        self._validate()

    def _validate(self) -> None:
        if not self.scoring_weights:
            raise ConfigError("scoring_weights is empty")
        total = sum(float(v) for v in self.scoring_weights.values())
        if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise ConfigError(f"scoring_weights must sum to 1.0 (got {total:.6f})")
        for key, value in self.observation_weights.items():
            if not 0.0 <= float(value) <= 1.0:
                raise ConfigError(f"observation weight {key} out of range: {value}")
        if self.window_minutes <= 0:
            raise ConfigError("forecast.window_minutes must be positive")
        if self.minimum_observations < 1:
            raise ConfigError("forecast.minimum_observations must be >= 1")

    # -- location ---------------------------------------------------------
    @property
    def zip_code(self) -> str:
        return str(self.location.get("zip_code", "98092"))

    @property
    def radius_miles(self) -> float:
        return float(self.location.get("radius_miles", 10.0))

    @property
    def timezone_name(self) -> str:
        return str(self.location.get("timezone", "America/Los_Angeles"))

    @property
    def fallback_centroid(self):
        centroid = self.location.get("fallback_centroid", {})
        return float(centroid.get("latitude")), float(centroid.get("longitude"))

    # -- forecast ---------------------------------------------------------
    @property
    def window_minutes(self) -> int:
        return int(self.forecast.get("window_minutes", 5))

    @property
    def horizon_hours(self) -> int:
        return int(self.forecast.get("horizon_hours", 12))

    @property
    def horizon_decay_per_hour(self) -> float:
        return float(self.forecast.get("horizon_decay_per_hour", 0.08))

    @property
    def max_windows_per_machine(self) -> int:
        return int(self.forecast.get("max_windows_per_machine", 8))

    @property
    def minimum_observations(self) -> int:
        return int(self.forecast.get("minimum_observations", 8))

    @property
    def high_confidence_observations(self) -> int:
        return int(self.forecast.get("high_confidence_observations", 30))

    @property
    def minute_tolerance(self) -> int:
        return int(self.forecast.get("minute_tolerance", 3))

    @property
    def minute_pattern_min_samples(self) -> int:
        return int(self.forecast.get("minute_pattern_min_samples", 4))

    @property
    def interval_candidates(self):
        return [int(v) for v in self.forecast.get("interval_candidates_minutes", [30, 60, 90, 120])]

    @property
    def interval_tolerance_minutes(self) -> int:
        return int(self.forecast.get("interval_tolerance_minutes", 4))

    @property
    def interval_min_samples(self) -> int:
        return int(self.forecast.get("interval_min_samples", 4))

    @property
    def interval_min_support(self) -> float:
        return float(self.forecast.get("interval_min_support", 0.5))

    @property
    def recency_lambda_per_hour(self) -> float:
        return float(self.forecast.get("recency_lambda_per_hour", 0.0058))

    @property
    def recency_reference_hours(self) -> float:
        return float(self.forecast.get("recency_reference_hours", 72))

    @property
    def nearby_radii_miles(self):
        return [float(v) for v in self.forecast.get("nearby_radii_miles", [3, 5, 10])]

    @property
    def nearby_window_minutes(self) -> int:
        return int(self.forecast.get("nearby_window_minutes", 90))

    # -- confidence -------------------------------------------------------
    @property
    def full_confidence_observations(self) -> int:
        return int(self.confidence.get("full_confidence_observations", 30))

    @property
    def sample_scale_floor(self) -> float:
        return float(self.confidence.get("sample_scale_floor", 0.35))

    @property
    def confidence_bands(self):
        bands = self.confidence.get("bands", {})
        return float(bands.get("high", 0.7)), float(bands.get("medium", 0.4))

    def observation_weight(self, evidence_class: str) -> float:
        """Weight for an evidence class, defaulting to the weakest tier."""
        if evidence_class in self.observation_weights:
            return float(self.observation_weights[evidence_class])
        return float(self.observation_weights.get("THIRD_PARTY_INFERRED", 0.25))

    # -- network prior ----------------------------------------------------
    @property
    def network_prior_enabled(self) -> bool:
        return bool(self.network_prior.get("enabled", True))

    @property
    def network_regional_radius_miles(self) -> float:
        return float(self.network_prior.get("regional_radius_miles", 250))

    @property
    def network_min_regional_reports(self) -> int:
        return int(self.network_prior.get("min_regional_reports", 40))

    @property
    def network_min_reports(self) -> int:
        return int(self.network_prior.get("min_reports", 25))

    @property
    def network_min_hour_samples(self) -> int:
        return int(self.network_prior.get("min_hour_samples", 8))

    @property
    def network_max_probability(self) -> float:
        return float(self.network_prior.get("max_probability", 0.35))

    @property
    def network_hour_weight(self) -> float:
        return float(self.network_prior.get("hour_weight", 0.7))

    @property
    def network_weekday_weight(self) -> float:
        return float(self.network_prior.get("weekday_weight", 0.3))

    @property
    def min_machine_match_confidence(self) -> float:
        return float(self.matching.get("min_machine_match_confidence", 0.7))


class SourcesConfig:
    """Typed accessor over sources.yaml."""

    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw
        self.defaults = raw.get("defaults", {})
        self.sources = raw.get("sources", {})

    def source(self, name: str) -> Dict[str, Any]:
        """Per-source settings merged over the global defaults."""
        merged = dict(self.defaults)
        merged.update(self.sources.get(name, {}) or {})
        return merged

    def is_enabled(self, name: str) -> bool:
        return bool((self.sources.get(name) or {}).get("enabled", False))

    @property
    def names(self):
        return list(self.sources.keys())


class AppConfig:
    def __init__(self, forecast: ForecastConfig, sources: SourcesConfig, config_dir: Path):
        self.forecast = forecast
        self.sources = sources
        self.config_dir = config_dir


def load_config(config_dir: Optional[Path] = None) -> AppConfig:
    """Load and validate both configuration files.

    POKEVEND_CONFIG_DIR overrides the location, which is how the tests point at
    fixture configuration.
    """
    if config_dir is None:
        env_dir = os.environ.get("POKEVEND_CONFIG_DIR")
        config_dir = Path(env_dir) if env_dir else DEFAULT_CONFIG_DIR
    config_dir = Path(config_dir)
    forecast = ForecastConfig(_read_yaml(config_dir / "forecast_config.yaml"))
    sources = SourcesConfig(_read_yaml(config_dir / "sources.yaml"))
    return AppConfig(forecast=forecast, sources=sources, config_dir=config_dir)
