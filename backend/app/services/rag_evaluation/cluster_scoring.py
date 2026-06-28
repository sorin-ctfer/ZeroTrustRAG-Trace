"""EvidenceCluster aggregation and ClusterDualRisk scoring."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .scoring import minmax


def cluster_key(chunk: dict[str, Any]) -> str | None:
    cluster_id = chunk.get("cluster_id")
    if not cluster_id:
        return None
    parts = [str(chunk.get("dataset", "")), str(chunk.get("sample_id", "")), str(chunk.get("case_id", ""))]
    if not any(parts):
        return str(cluster_id)
    return "|".join([*parts, str(cluster_id)])


def build_cluster_scores(
    retrieval_logs: list[dict[str, Any]],
    chunk_scores: dict[str, dict[str, float]],
    cluster_lambda: float = 0.5,
) -> dict[str, dict[str, Any]]:
    clusters: dict[str, dict[str, Any]] = {}
    cluster_freq: Counter[str] = Counter()
    total_retrievals = 0
    for log in retrieval_logs:
        seen_in_log: set[str] = set()
        for result in log.get("topk", []):
            total_retrievals += 1
            key = cluster_key(result)
            if not key:
                continue
            cluster = clusters.setdefault(key, {"cluster_id": key, "members": {}, "retrieved_member_ids": set()})
            cluster["members"][result["chunk_id"]] = result
            cluster["retrieved_member_ids"].add(result["chunk_id"])
            seen_in_log.add(key)
        for key in seen_in_log:
            cluster_freq[key] += 1

    raw_ras = {key: float(cluster_freq[key]) for key in clusters}
    normalized_ras = minmax(raw_ras)
    rows: dict[str, dict[str, Any]] = {}
    for key, cluster in clusters.items():
        members = list(cluster["members"].values())
        member_ids = [member["chunk_id"] for member in members]
        roots = [str(member.get("root_source_id") or member.get("source_id") or "") for member in members]
        unique_roots = {root for root in roots if root}
        member_count = max(1, len(members))
        copied = sum(1 for member in members if member.get("copied_from"))
        source_independence = len(unique_roots) / member_count
        copy_ratio = copied / member_count
        source_anomaly = max(0.0, min(1.0, (1.0 - source_independence + copy_ratio) / 2.0))
        gis_values = [chunk_scores.get(chunk_id, {}).get("gis", 0.0) for chunk_id in member_ids]
        cluster_gis = max(gis_values) if gis_values else 0.0
        cluster_ras = raw_ras.get(key, 0.0) / max(1.0, float(total_retrievals))
        normalized_cluster_ras = normalized_ras.get(key, 0.0)
        cluster_dualrisk = normalized_cluster_ras * cluster_gis * (1.0 + cluster_lambda * source_anomaly)
        rows[key] = {
            "cluster_id": key,
            "raw_cluster_id": members[0].get("cluster_id") if members else key,
            "member_chunk_ids": member_ids,
            "cluster_ras": cluster_ras,
            "normalized_cluster_ras": normalized_cluster_ras,
            "cluster_gis": cluster_gis,
            "source_independence": source_independence,
            "copy_ratio": copy_ratio,
            "source_anomaly": source_anomaly,
            "cluster_base_score": normalized_cluster_ras * cluster_gis,
            "cluster_dualrisk": cluster_dualrisk,
            "cluster_lambda": cluster_lambda,
        }
    return rows
