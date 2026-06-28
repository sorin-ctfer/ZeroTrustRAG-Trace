"""Schemas and configuration for RAG evaluation runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


MethodName = Literal["ras_only", "gis_only", "dualrisk", "dualrisk_cluster", "dualrisk_causal", "full_method"]


SUPPORTED_METHODS: tuple[MethodName, ...] = (
    "ras_only",
    "gis_only",
    "dualrisk",
    "dualrisk_cluster",
    "dualrisk_causal",
    "full_method",
)


@dataclass(frozen=True)
class EvaluationConfig:
    dataset: str = "all"
    mode: str = "sample"
    methods: tuple[MethodName, ...] = SUPPORTED_METHODS
    top_k: tuple[int, ...] = (3, 5, 10)
    poison_ratios: tuple[float, ...] = (0.01, 0.03, 0.05, 0.10)
    ras_threshold: float = 0.6
    gis_threshold: float = 0.45
    dualrisk_threshold: float = 0.25
    cluster_threshold: float = 0.35
    causal_threshold: float = 0.5
    cluster_causal_threshold: float = 0.5
    cluster_lambda: float = 0.5
    retrieval_mode: str = "faiss"
    subset_per_dataset: int = 100
    causal_weights: dict[str, float] = field(default_factory=lambda: {
        "remove_change": 0.35,
        "only_reproduce": 0.30,
        "replace_recovery": 0.25,
        "trust_improvement": 0.10,
    })
    safe_rerank_weights: dict[str, float] = field(default_factory=lambda: {
        "alpha": 0.40,
        "beta": 0.30,
        "gamma": 0.25,
        "delta": 0.25,
        "eta": 0.20,
        "mu": 0.10,
    })
    trust_threshold: float = 60.0

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None = None) -> "EvaluationConfig":
        data = data or {}
        methods = tuple(method for method in data.get("methods", SUPPORTED_METHODS) if method in SUPPORTED_METHODS)
        return cls(
            dataset=str(data.get("dataset", "all")),
            mode=str(data.get("mode", "sample")),
            methods=methods or SUPPORTED_METHODS,
            top_k=tuple(int(item) for item in data.get("top_k", (3, 5, 10))),
            poison_ratios=tuple(float(item) for item in data.get("poison_ratios", (0.01, 0.03, 0.05, 0.10))),
            ras_threshold=float(data.get("ras_threshold", 0.6)),
            gis_threshold=float(data.get("gis_threshold", 0.45)),
            dualrisk_threshold=float(data.get("dualrisk_threshold", 0.25)),
            cluster_threshold=float(data.get("cluster_threshold", 0.35)),
            causal_threshold=float(data.get("causal_threshold", 0.5)),
            cluster_causal_threshold=float(data.get("cluster_causal_threshold", 0.5)),
            cluster_lambda=float(data.get("cluster_lambda", 0.5)),
            retrieval_mode=str(data.get("retrieval_mode", "faiss")),
            subset_per_dataset=int(data.get("subset_per_dataset", 100)),
            causal_weights=dict(data.get("causal_weights") or {
                "remove_change": 0.35,
                "only_reproduce": 0.30,
                "replace_recovery": 0.25,
                "trust_improvement": 0.10,
            }),
            safe_rerank_weights=dict(data.get("safe_rerank_weights") or {
                "alpha": 0.40,
                "beta": 0.30,
                "gamma": 0.25,
                "delta": 0.25,
                "eta": 0.20,
                "mu": 0.10,
            }),
            trust_threshold=float(data.get("trust_threshold", 60.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "mode": self.mode,
            "methods": list(self.methods),
            "top_k": list(self.top_k),
            "poison_ratios": list(self.poison_ratios),
            "ras_threshold": self.ras_threshold,
            "gis_threshold": self.gis_threshold,
            "dualrisk_threshold": self.dualrisk_threshold,
            "cluster_threshold": self.cluster_threshold,
            "causal_threshold": self.causal_threshold,
            "cluster_causal_threshold": self.cluster_causal_threshold,
            "cluster_lambda": self.cluster_lambda,
            "retrieval_mode": self.retrieval_mode,
            "subset_per_dataset": self.subset_per_dataset,
            "causal_weights": self.causal_weights,
            "safe_rerank_weights": self.safe_rerank_weights,
            "trust_threshold": self.trust_threshold,
        }


@dataclass
class RunProgress:
    run_id: str = ""
    status: str = "idle"
    total: int = 0
    completed: int = 0
    failed: int = 0
    current_method: str = ""
    current_sample: str = ""
    error: str = ""
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "current_method": self.current_method,
            "current_sample": self.current_sample,
            "error": self.error,
            "config": self.config,
        }
