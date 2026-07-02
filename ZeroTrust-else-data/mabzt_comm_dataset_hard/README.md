# MABZT-Comm-2026-hard-v1

Synthetic multi-agent communication dataset (HARD — stealthy, validation-aware attackers at scale).

## Scale
- agents: 90
- tasks: 300
- comm_events: 4890
- claims: 4890
- evidence: 1881
- tool_calls: 4890
- consensus_groups: 1180
- challenges: 300

## Attack families
- none
- evidence_poisoning
- byzantine_agent
- communication_tampering
- noisy_watch
- stealthy_collusion
- strategic_attack

## Files
- agents.json: registry with role, permissions, key reference, and ground-truth family.
- comm_events.json: raw/sent/received messages and transport metadata.
- claims.json: structured claim rows linked to communication events.
- evidence.json: evidence quality fields and RAG-related poison markers.
- tool_calls.json: tool hash material for zero-trust validation.
- consensus_groups.json: conflict groups used by the weighted consensus engine.
- challenges.json: active verifier challenge records.