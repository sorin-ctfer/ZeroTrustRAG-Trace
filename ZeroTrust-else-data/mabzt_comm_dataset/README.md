# MABZT-Comm-2026-synthetic-v1

Synthetic multi-agent communication dataset (EASY — naive attackers).

## Scale
- agents: 54
- tasks: 120
- comm_events: 1200
- claims: 1200
- evidence: 480
- tool_calls: 1200
- consensus_groups: 480
- challenges: 120

## Attack families
- none
- evidence_poisoning
- byzantine_agent
- communication_tampering
- noisy_watch

## Files
- agents.json: registry with role, permissions, key reference, and ground-truth family.
- comm_events.json: raw/sent/received messages and transport metadata.
- claims.json: structured claim rows linked to communication events.
- evidence.json: evidence quality fields and RAG-related poison markers.
- tool_calls.json: tool hash material for zero-trust validation.
- consensus_groups.json: conflict groups used by the weighted consensus engine.
- challenges.json: active verifier challenge records.