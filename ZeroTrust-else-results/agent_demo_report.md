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
- pass rate: 80.58%
- failed packages: 233

## Top BSS agents

| agent | role | BSS | status | root_cause | ground_truth |
|---|---|---:|---|---|---|
| A_COMM_003 | comm_monitor | 0.662 | restricted | communication_tampering | communication_tampering |
| A_COMM_001 | comm_monitor | 0.645 | restricted | communication_tampering | communication_tampering |
| A_BYZ_001 | rag_reader | 0.637 | restricted | byzantine_agent | byzantine_agent |
| A_BYZ_004 | planner | 0.479 | watch | byzantine_agent | byzantine_agent |
| A_BYZ_008 | planner | 0.479 | watch | byzantine_agent | byzantine_agent |
| A_BYZ_002 | planner | 0.476 | watch | byzantine_agent | byzantine_agent |
| A_POISON_004 | rag_reader | 0.471 | watch | evidence_poisoning | evidence_poisoning |
| A_POISON_002 | rag_reader | 0.466 | watch | evidence_poisoning | evidence_poisoning |
| A_BYZ_003 | rag_reader | 0.462 | watch | byzantine_agent | byzantine_agent |
| A_BYZ_007 | rag_reader | 0.455 | watch | byzantine_agent | byzantine_agent |

## Baseline comparison

| method | accuracy | false_block | missed_threat | attack_success |
|---|---:|---:|---:|---:|
| unprotected_direct_trust | 0.292 | 1.000 | 0.271 | 0.708 |
| majority_vote | 0.000 | 1.000 | 1.000 | 1.000 |
| single_verifier_agent | 1.000 | 0.000 | 0.000 | 0.000 |
| zero_trust_weighted_consensus | 1.000 | 0.000 | 0.000 | 0.000 |

## Consensus outcome

- accepted groups: 184
- challenged groups: 55
- rejected groups: 162

## Latency

| stage | total_ms | count | avg_ms |
|---|---:|---:|---:|
| claim_package_generation | 20.009 | 1200 | 0.016674 |
| zero_trust_validation | 28.381 | 1200 | 0.023651 |
| bss_risk_scoring | 9.312 | 54 | 0.172446 |
| weighted_consensus | 7.923 | 401 | 0.019758 |
| graph_build | 11.115 | 11255 | 0.000988 |

## Reproduction

```powershell
cd .\????
python generate_dataset.py
python run_experiments.py
python -m agent_demo_app.app
```
