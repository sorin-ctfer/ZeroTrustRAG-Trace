# Agent module experiment report

## Dataset scale

| metric | value |
|---|---:|
| agents | 90 |
| tasks | 300 |
| comm_events | 4890 |
| claims | 4890 |
| evidence | 1881 |
| tool_calls | 4890 |
| consensus_groups | 1180 |
| challenges | 300 |

## Zero-trust validation

- total packages: 4890
- pass rate: 91.51%
- failed packages: 415

## Top BSS agents

| agent | role | BSS | status | root_cause | ground_truth |
|---|---|---:|---|---|---|
| A_COMM_002 | rag_reader | 0.128 | normal | communication_tampering | communication_tampering |
| A_POISON_001 | rag_reader | 0.119 | normal | evidence_poisoning | evidence_poisoning |
| A_POISON_002 | rag_reader | 0.117 | normal | evidence_poisoning | evidence_poisoning |
| A_COMM_001 | comm_monitor | 0.114 | normal | none | communication_tampering |
| A_COMM_003 | comm_monitor | 0.110 | normal | none | communication_tampering |
| A_COMM_004 | rag_reader | 0.105 | normal | none | communication_tampering |
| A_POISON_003 | forensic | 0.101 | normal | evidence_poisoning | evidence_poisoning |
| A_POISON_006 | planner | 0.101 | normal | evidence_poisoning | evidence_poisoning |
| A_POISON_007 | rag_reader | 0.100 | normal | evidence_poisoning | evidence_poisoning |
| A_POISON_008 | rag_reader | 0.096 | normal | evidence_poisoning | evidence_poisoning |

## Baseline comparison

| method | accuracy | false_block | missed_threat | attack_success |
|---|---:|---:|---:|---:|
| unprotected_direct_trust | 0.343 | 0.956 | 0.208 | 0.657 |
| majority_vote | 0.307 | 0.689 | 0.700 | 0.693 |
| single_verifier_agent | 0.600 | 0.000 | 1.000 | 0.400 |
| zero_trust_weighted_consensus | 0.983 | 0.011 | 0.025 | 0.017 |

## Consensus outcome

- accepted groups: 342
- challenged groups: 508
- rejected groups: 317

## Latency

| stage | total_ms | count | avg_ms |
|---|---:|---:|---:|
| claim_package_generation | 77.897 | 4890 | 0.01593 |
| zero_trust_validation | 106.819 | 4890 | 0.021844 |
| bss_risk_scoring | 35.496 | 90 | 0.394394 |
| weighted_consensus | 34.806 | 1167 | 0.029826 |
| graph_build | 62.533 | 47656 | 0.001312 |

## Reproduction

```powershell
cd .\????
python generate_dataset.py
python run_experiments.py
python -m agent_demo_app.app
```
