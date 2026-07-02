# MABZT-Comm-2026 synthetic dataset

This dataset is generated locally for the multi-agent zero-trust communication experiment.
It contains normal collaboration, poisoned RAG evidence dependency, Byzantine false claims, communication MITM/tampering, replay, invalid signature, invalid tool hash, and unsupported high-confidence claims.

## Scale
- agents: 54
- tasks: 120
- comm_events: 1200
- claims: 1200
- evidence: 480
- tool_calls: 1200
- consensus_groups: 480
- challenges: 120

## Files
- agents.json: registry with role, permissions, key reference, and ground-truth family.
- comm_events.json: raw/sent/received messages and transport metadata.
- claims.json: structured claim rows linked to communication events.
- evidence.json: evidence quality fields and RAG-related poison markers.
- tool_calls.json: tool hash material for zero-trust validation.
- consensus_groups.json: conflict groups used by the weighted consensus engine.
- challenges.json: active verifier challenge records.