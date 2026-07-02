# Agent module experiment report

## Dataset scale

| metric | value |
|---|---:|
| agents | 54 |
| tasks | 120 |
| comm_events | 1200 |
| claims | 1200 |
| evidence | 480 |
| tool_calls | 1200 |
| consensus_groups | 480 |
| challenges | 120 |

## Zero-trust validation

- total packages: 1200
- pass rate: 79.33%
- failed packages: 248

## Top BSS agents

| agent | role | BSS | status | root_cause | ground_truth |
|---|---|---:|---|---|---|
| A_COMM_003 | comm_monitor | 0.681 | restricted | communication_tampering | communication_tampering |
| A_COMM_001 | comm_monitor | 0.671 | restricted | communication_tampering | communication_tampering |
| A_BYZ_001 | rag_reader | 0.650 | restricted | byzantine_agent | byzantine_agent |
| A_POISON_002 | rag_reader | 0.524 | restricted | evidence_poisoning | evidence_poisoning |
| A_BYZ_003 | rag_reader | 0.521 | restricted | byzantine_agent | byzantine_agent |
| A_POISON_004 | rag_reader | 0.515 | restricted | evidence_poisoning | evidence_poisoning |
| A_BYZ_007 | rag_reader | 0.506 | restricted | byzantine_agent | byzantine_agent |
| A_POISON_001 | rag_reader | 0.498 | watch | evidence_poisoning | evidence_poisoning |
| A_BYZ_002 | planner | 0.479 | watch | byzantine_agent | byzantine_agent |
| A_BYZ_004 | planner | 0.477 | watch | byzantine_agent | byzantine_agent |

## Baseline comparison

| method | accuracy | false_block | missed_threat | attack_success |
|---|---:|---:|---:|---:|
| unprotected_direct_trust | 0.333 | 1.000 | 0.167 | 0.667 |
| majority_vote | 0.000 | 1.000 | 1.000 | 1.000 |
| single_verifier_agent | 1.000 | 0.000 | 0.000 | 0.000 |
| zero_trust_weighted_consensus | 1.000 | 0.000 | 0.000 | 0.000 |

## Consensus outcome

- accepted groups: 199
- challenged groups: 41
- rejected groups: 161

## Latency

| stage | total_ms | count | avg_ms |
|---|---:|---:|---:|
| claim_package_generation | 18.371 | 1200 | 0.015309 |
| zero_trust_validation | 24.974 | 1200 | 0.020811 |
| bss_risk_scoring | 5.185 | 54 | 0.09602 |
| weighted_consensus | 6.212 | 401 | 0.015493 |
| graph_build | 7.476 | 11095 | 0.000674 |

## Reproduction

```powershell
cd .\????
python generate_dataset.py
python run_experiments.py
python -m agent_demo_app.app
```
