from __future__ import annotations

import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

from agent_demo_app.config import DATASET_DIR, ROLE_PERMISSIONS, SCHEMA_VERSION, ensure_dirs
from agent_demo_app.utils import sha256_text, write_json

SEED = 20260628
HARD_SEED = 20260715
HARD_DATASET_DIR = DATASET_DIR.parent / "mabzt_comm_dataset_hard"

AGENT_PREFIX = {
    "none": "A_N",
    "byzantine_agent": "A_BYZ",
    "evidence_poisoning": "A_POISON",
    "communication_tampering": "A_COMM",
    "noisy_watch": "A_WATCH",
    "stealthy_collusion": "A_COL",
    "strategic_attack": "A_STRAT",
}


# ── Configuration profiles ────────────────────────────────────────────
def _easy_config() -> dict:
    return {
        "dataset_id": "MABZT-Comm-2026-synthetic-v1",
        "description": "Synthetic multi-agent communication dataset (EASY — naive attackers).",
        "normal_count": 32,
        "normal_trust": (86, 97),
        "byzantine_count": 8,
        "byzantine_trust": (42, 61),
        "byzantine_invalid_sig_every": 3,
        "byzantine_missing_subject_every": 17,
        "byzantine_forged_hash_every": 4,
        "byzantine_reuse_nonce_every": 19,
        "byzantine_no_evidence_every": 2,
        "byzantine_always_opposite": True,
        "poison_count": 6,
        "poison_trust": (62, 77),
        "poison_evidence_trust": (18, 48),
        "poison_source_category": "poisoned_rag",
        "comm_count": 4,
        "comm_trust": (82, 92),
        "comm_tamper_rate": 1.0,
        "watch_count": 4,
        "watch_trust": (68, 80),
        "collusion_count": 0,
        "collusion_trust": (78, 90),
        "strategic_count": 0,
        "strategic_trust": (80, 92),
        "false_evidence_trust": (72, 88),
        "collusion_wave_size": 0,
        "ambiguous_task_rate": 0.0,
    }


def _hard_config() -> dict:
    return {
        "dataset_id": "MABZT-Comm-2026-hard-v1",
        "description": "Synthetic multi-agent communication dataset (HARD — stealthy, validation-aware attackers at scale).",
        "normal_count": 30,
        "normal_trust": (86, 97),
        "byzantine_count": 12,
        "byzantine_trust": (72, 86),
        "byzantine_invalid_sig_every": 0,
        "byzantine_missing_subject_every": 0,
        "byzantine_forged_hash_every": 0,
        "byzantine_reuse_nonce_every": 0,
        "byzantine_no_evidence_every": 0,
        "byzantine_always_opposite": False,
        "byzantine_correct_rate": 0.25,
        "poison_count": 8,
        "poison_trust": (76, 88),
        "poison_evidence_trust": (65, 82),
        "poison_source_category": "rag_fragment",
        "comm_count": 4,
        "comm_trust": (82, 92),
        "comm_tamper_rate": 0.35,
        "watch_count": 6,
        "watch_trust": (74, 86),
        "collusion_count": 18,
        "collusion_trust": (82, 94),
        "strategic_count": 12,
        "strategic_trust": (82, 94),
        "false_evidence_trust": (85, 98),
        "collusion_wave_size": 8,
        # Ambiguous-evidence tasks: normal agents split, attackers exploit the confusion
        "ambiguous_task_rate": 0.30,
    }


# ── Helpers ───────────────────────────────────────────────────────────
def hmac_secret(agent_id: str) -> str:
    return f"demo_hmac_secret::{agent_id}::mabzt"


def build_agent(agent_id: str, role: str, attack_type: str, trust_prior: int, idx: int) -> dict:
    return {
        "agent_id": agent_id,
        "display_name": f"{role}-{idx:02d}",
        "role": role,
        "permissions": ROLE_PERMISSIONS[role],
        "public_key_id": f"pk_{agent_id}",
        "private_key_ref": f"demo-keyring/{agent_id}",
        "hmac_secret": hmac_secret(agent_id),
        "trust_prior": trust_prior,
        "attack_type": attack_type,
        "description": f"Synthetic {attack_type} agent for zero-trust multi-agent communication experiments.",
    }


def make_agents(rng: random.Random, cfg: dict) -> List[dict]:
    agents = []
    normal_roles = ["rag_reader", "forensic", "planner", "verifier", "comm_monitor", "watcher"]
    lo, hi = cfg["normal_trust"]
    for i in range(1, cfg["normal_count"] + 1):
        role = normal_roles[(i - 1) % len(normal_roles)]
        agents.append(build_agent(f"A_N_{i:03d}", role, "none", rng.randint(lo, hi), i))

    byz_roles = ["rag_reader", "planner", "rag_reader", "planner", "forensic", "watcher", "rag_reader", "planner"]
    lo, hi = cfg["byzantine_trust"]
    for i in range(1, cfg["byzantine_count"] + 1):
        role = byz_roles[(i - 1) % len(byz_roles)]
        agents.append(build_agent(f"A_BYZ_{i:03d}", role, "byzantine_agent", rng.randint(lo, hi), i))

    poison_roles = ["rag_reader", "rag_reader", "forensic", "rag_reader", "watcher", "planner"]
    lo, hi = cfg["poison_trust"]
    pc = cfg["poison_count"]
    for i in range(1, pc + 1):
        role = poison_roles[(i - 1) % len(poison_roles)]
        agents.append(build_agent(f"A_POISON_{i:03d}", role, "evidence_poisoning", rng.randint(lo, hi), i))

    lo, hi = cfg["comm_trust"]
    for i in range(1, cfg["comm_count"] + 1):
        role = "comm_monitor" if i % 2 else "rag_reader"
        agents.append(build_agent(f"A_COMM_{i:03d}", role, "communication_tampering", rng.randint(lo, hi), i))

    lo, hi = cfg["watch_trust"]
    for i in range(1, cfg["watch_count"] + 1):
        role = "watcher" if i % 2 else "planner"
        agents.append(build_agent(f"A_WATCH_{i:03d}", role, "noisy_watch", rng.randint(lo, hi), i))

    # New families (hard mode only)
    lo, hi = cfg["collusion_trust"]
    col_roles = ["rag_reader", "rag_reader", "forensic", "rag_reader", "planner", "watcher",
                 "rag_reader", "forensic", "rag_reader", "planner", "forensic", "rag_reader"]
    for i in range(1, cfg["collusion_count"] + 1):
        role = col_roles[(i - 1) % len(col_roles)]
        agents.append(build_agent(f"A_COL_{i:03d}", role, "stealthy_collusion", rng.randint(lo, hi), i))

    lo, hi = cfg["strategic_trust"]
    strat_roles = ["planner", "planner", "rag_reader", "forensic", "planner", "rag_reader", "planner", "rag_reader"]
    for i in range(1, cfg["strategic_count"] + 1):
        role = strat_roles[(i - 1) % len(strat_roles)]
        agents.append(build_agent(f"A_STRAT_{i:03d}", role, "strategic_attack", rng.randint(lo, hi), i))

    return agents


def select_agent(agents: List[dict], attack_type: str, role: str | None, n: int) -> dict:
    pool = [a for a in agents if a["attack_type"] == attack_type and (role is None or a["role"] == role)]
    if not pool:
        pool = [a for a in agents if a["attack_type"] == attack_type]
    return pool[n % len(pool)]


def label_to_object(label: str) -> str:
    return "C2" if label == "malicious" else "benign_service"


def label_to_action(label: str) -> str:
    return "block_ip" if label == "malicious" else "do_not_block"


def make_message(subject: str, claim_type: str, label: str, confidence: float) -> str:
    if claim_type == "action_recommendation":
        return f"Action recommendation: {subject} should {label_to_action(label)}; confidence={confidence:.2f}."
    return f"Risk judgment: evidence indicates {subject} is {label_to_object(label)}; confidence={confidence:.2f}."


def make_tool_call(tool_id: str, agent_id: str, task_id: str, tool_name: str, query: str, result_digest: str, integrity: str) -> dict:
    canonical = f"{tool_id}|{agent_id}|{task_id}|{tool_name}|{query}|{result_digest}"
    actual = sha256_text(canonical)
    declared = actual if integrity == "valid" else sha256_text("forged::" + canonical)
    return {
        "tool_call_id": tool_id,
        "agent_id": agent_id,
        "task_id": task_id,
        "tool_name": tool_name,
        "query": query,
        "result_digest": result_digest,
        "actual_tool_hash": actual,
        "declared_tool_hash": declared,
        "integrity": integrity,
    }


def build_dataset(task_count: int = 120, dataset_dir: Path | None = None, hard: bool = False) -> Dict[str, list | dict]:
    cfg = _hard_config() if hard else _easy_config()
    seed = HARD_SEED if hard else SEED
    rng = random.Random(seed)
    if dataset_dir is None:
        dataset_dir = HARD_DATASET_DIR if hard else DATASET_DIR
    ensure_dirs()
    agents = make_agents(rng, cfg)
    tasks, evidence, claims, events, tool_calls, challenges, groups = [], [], [], [], [], [], []
    base = datetime(2026, 6, 25, 9, 0, tzinfo=timezone(timedelta(hours=8)))
    event_no = 0
    claim_no = 0
    tool_no = 0
    seen_groups = set()
    last_nonce_by_agent: Dict[str, str] = {}

    def add_group(task_id: str, subject: str, label: str, group_kind: str):
        gid = f"G_{task_id}_{group_kind}_{label}"
        if gid not in seen_groups:
            seen_groups.add(gid)
            groups.append({
                "claim_group_id": gid,
                "task_id": task_id,
                "subject": subject,
                "group_kind": group_kind,
                "label": label,
                "high_risk_action": group_kind == "action" and label == "malicious",
                "conflicts_with": [],
            })
        return gid

    def add_evidence(task_id: str, subject: str, suffix: str, supports_label: str, source_category: str,
                     trust: int, dual: float, causal: float, indep: float, entail: float, contra: float):
        eid = f"E_{task_id}_{suffix}"
        evidence.append({
            "evidence_id": eid,
            "task_id": task_id,
            "subject": subject,
            "source_category": source_category,
            "supports_label": supports_label,
            "trust_score": trust,
            "dual_risk": round(dual, 3),
            "causal_score": round(causal, 3),
            "source_independence": round(indep, 3),
            "p_entail_if_aligned": round(entail, 3),
            "p_contra_if_opposed": round(contra, 3),
            "rag_returned": source_category in {"rag_fragment", "poisoned_rag"},
            "source_uri": f"zt://evidence/{task_id}/{suffix}",
            "summary": f"{source_category} evidence supports {supports_label} for {subject}.",
        })
        return eid

    def add_event(task: dict, agent: dict, receiver: dict, claim_type: str, label: str, evidence_ids: List[str],
                  confidence: float, scenario: str, attack_vector: str = "none", transport_integrity: bool = True,
                  signature_status: str = "valid", schema_status: str = "valid", tool_integrity: str = "valid",
                  nonce_mode: str = "unique", parent_claim_ids: List[str] | None = None,
                  timestamp_shift_days: int = 0):
        nonlocal event_no, claim_no, tool_no
        event_no += 1
        claim_no += 1
        tool_no += 1
        eid = f"M_{event_no:05d}"
        cid = f"C_{claim_no:05d}"
        tid = task["task_id"]
        subject = task["subject"]
        timestamp = base + timedelta(minutes=event_no * 2) + timedelta(days=timestamp_shift_days)
        group_kind = "action" if claim_type == "action_recommendation" else "risk"
        group_id = add_group(tid, subject, label, group_kind)
        sent_label = task["true_label"] if attack_vector == "comm_mitm" else label
        sent_msg = make_message(subject, claim_type, sent_label, confidence)
        received_msg = make_message(subject, claim_type, label, confidence)
        if transport_integrity:
            sent_msg = received_msg
        tool_name = "rag.retrieve" if claim_type != "action_recommendation" else "policy.plan_action"
        result_digest = sha256_text("|".join(evidence_ids) + label + subject)[:24]
        tool = make_tool_call(f"TOOL_{tool_no:05d}", agent["agent_id"], tid, tool_name, subject, result_digest, tool_integrity)
        tool_calls.append(tool)
        if nonce_mode == "reuse" and agent["agent_id"] in last_nonce_by_agent:
            nonce = last_nonce_by_agent[agent["agent_id"]]
        else:
            nonce = f"N_{agent['agent_id']}_{event_no:05d}"
            last_nonce_by_agent[agent["agent_id"]] = nonce
        predicate = "should" if claim_type == "action_recommendation" else "is"
        obj = label_to_action(label) if claim_type == "action_recommendation" else label_to_object(label)
        event = {
            "event_id": eid,
            "task_id": tid,
            "round": 1 + (event_no % 6),
            "sender": agent["agent_id"],
            "receiver": receiver["agent_id"],
            "sent_message": sent_msg,
            "received_message": received_msg,
            "message_hash_sent": sha256_text(sent_msg),
            "message_hash_received": sha256_text(received_msg),
            "transport_integrity": transport_integrity,
            "gateway_received": True,
            "claim_id": cid,
            "claim_group_id": group_id,
            "claim_type": claim_type,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "label": label,
            "confidence": round(confidence, 3),
            "evidence_ids": evidence_ids,
            "parent_claim_ids": parent_claim_ids or [],
            "tool_call_id": tool["tool_call_id"],
            "tool_hash_declared": tool["declared_tool_hash"],
            "nonce": nonce,
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "signature_status": signature_status,
            "schema_status": schema_status,
            "tool_integrity": tool_integrity,
            "scenario": scenario,
            "attack_vector": attack_vector,
            "ground_truth_label": task["true_label"],
        }
        claim = {
            "claim_id": cid,
            "event_id": eid,
            "task_id": tid,
            "agent_id": agent["agent_id"],
            "claim_group_id": group_id,
            "type": claim_type,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "label": label,
            "confidence": round(confidence, 3),
            "evidence_ids": evidence_ids,
            "parent_claim_ids": parent_claim_ids or [],
            "expected_correct": label == task["true_label"] if claim_type != "action_recommendation" else True,
            "scenario": scenario,
        }
        events.append(event)
        claims.append(claim)
        return cid

    for i in range(1, task_count + 1):
        tid = f"T_{i:04d}"
        subject = f"10.{(i * 3) % 250}.{(i * 7) % 250}.{(i * 13) % 240 + 10}"
        true_label = "malicious" if i % 5 in (0, 2) else "benign"
        false_label = "benign" if true_label == "malicious" else "malicious"
        task = {
            "task_id": tid,
            "subject": subject,
            "true_label": true_label,
            "scenario_family": "ip_risk_triage",
            "expected_safe_action": label_to_action(true_label),
        }
        tasks.append(task)

        # ── Evidence ──
        good_1 = add_evidence(tid, subject, "GOOD_NETFLOW", true_label, "network_log",
                              rng.randint(82, 98), rng.uniform(0.02, 0.15), rng.uniform(0.04, 0.18),
                              rng.uniform(0.78, 0.96), rng.uniform(0.82, 0.95), rng.uniform(0.72, 0.9))
        good_2 = add_evidence(tid, subject, "GOOD_FORENSIC", true_label, "sandbox_trace",
                              rng.randint(78, 96), rng.uniform(0.03, 0.18), rng.uniform(0.05, 0.22),
                              rng.uniform(0.76, 0.94), rng.uniform(0.8, 0.93), rng.uniform(0.68, 0.88))
        neutral = add_evidence(tid, subject, "NOISY_CONTEXT", true_label, "rag_fragment",
                               rng.randint(52, 70), rng.uniform(0.25, 0.45), rng.uniform(0.25, 0.5),
                               rng.uniform(0.45, 0.65), rng.uniform(0.45, 0.6), rng.uniform(0.35, 0.55))
        # Poison evidence: easy uses low-quality, hard uses medium-quality with rag_fragment label
        pcat = cfg["poison_source_category"]
        plo, phi = cfg["poison_evidence_trust"]
        poison = add_evidence(tid, subject, "POISON_PROMPT", false_label, pcat,
                              rng.randint(plo, phi), rng.uniform(0.52, 0.78), rng.uniform(0.48, 0.72),
                              rng.uniform(0.28, 0.52), rng.uniform(0.65, 0.85), rng.uniform(0.50, 0.72))
        # Hard-mode only: high-quality false evidence for stealthy attackers
        false_high_q = None
        false_high_q2 = None
        ambiguous_task = False
        amb_ev = None
        if hard:
            flo, fhi = cfg["false_evidence_trust"]
            false_high_q = add_evidence(tid, subject, "FAKE_INTEL", false_label, "sandbox_trace",
                                        rng.randint(flo, fhi), rng.uniform(0.05, 0.18), rng.uniform(0.04, 0.16),
                                        rng.uniform(0.74, 0.90), rng.uniform(0.80, 0.94), rng.uniform(0.68, 0.85))
            false_high_q2 = add_evidence(tid, subject, "FAKE_INTEL_2", false_label, "network_log",
                                         rng.randint(flo, fhi), rng.uniform(0.06, 0.20), rng.uniform(0.05, 0.18),
                                         rng.uniform(0.72, 0.88), rng.uniform(0.78, 0.92), rng.uniform(0.65, 0.83))
            # Ambiguous-evidence tasks: attackers exploit normal-agent confusion
            ambiguous_task = rng.random() < cfg["ambiguous_task_rate"]
            if ambiguous_task:
                amb_ev = add_evidence(tid, subject, "AMBIGUOUS_SIG", false_label, "sandbox_trace",
                                      rng.randint(78, 94), rng.uniform(0.08, 0.25), rng.uniform(0.08, 0.25),
                                      rng.uniform(0.60, 0.78), rng.uniform(0.70, 0.85), rng.uniform(0.60, 0.78))

        # ── Agent selection ──
        verifier = select_agent(agents, "none", "verifier", i)
        planner = select_agent(agents, "none", "planner", i)
        normal_1 = select_agent(agents, "none", "rag_reader", i)
        normal_2 = select_agent(agents, "none", "forensic", i)
        poison_1 = select_agent(agents, "evidence_poisoning", "rag_reader", i)
        poison_2 = select_agent(agents, "evidence_poisoning", None, i + 1)
        byz_1 = select_agent(agents, "byzantine_agent", "rag_reader", i)
        byz_2 = select_agent(agents, "byzantine_agent", "planner", i + 1)
        comm = select_agent(agents, "communication_tampering", None, i)
        watch = select_agent(agents, "noisy_watch", None, i)

        # ── Normal claims ──
        if hard:
            # Hard mode: fewer normal claims to test consensus under attack pressure
            # On ambiguous tasks, one normal agent gets confused — genuine disagreement
            if ambiguous_task and amb_ev:
                c1 = add_event(task, normal_1, verifier, "risk_judgment", true_label, [good_1],
                               rng.uniform(0.82, 0.95), "clean")
                # normal_2 misled by ambiguous evidence — reports wrong label
                c2 = add_event(task, normal_2, verifier, "risk_judgment", false_label, [amb_ev],
                               rng.uniform(0.75, 0.88), "clean")
            else:
                c1 = add_event(task, normal_1, verifier, "risk_judgment", true_label, [good_1],
                               rng.uniform(0.82, 0.95), "clean")
                c2 = add_event(task, normal_2, verifier, "risk_judgment", true_label, [good_2],
                               rng.uniform(0.80, 0.93), "clean")
            add_event(task, planner, verifier, "action_recommendation", true_label, [good_1, good_2],
                      rng.uniform(0.74, 0.88), "clean")
        else:
            c1 = add_event(task, normal_1, verifier, "risk_judgment", true_label, [good_1],
                           rng.uniform(0.82, 0.95), "clean")
            c2 = add_event(task, normal_2, verifier, "risk_judgment", true_label, [good_2],
                           rng.uniform(0.80, 0.93), "clean", parent_claim_ids=[c1])
            c3 = add_event(task, verifier, planner, "verification", true_label, [good_1, good_2],
                           rng.uniform(0.84, 0.96), "clean", parent_claim_ids=[c1, c2])
            add_event(task, planner, verifier, "action_recommendation", true_label, [good_1, good_2],
                      rng.uniform(0.74, 0.88), "clean", parent_claim_ids=[c3])

        # ── Evidence poisoning (both modes) ──
        add_event(task, poison_1, verifier, "risk_judgment", false_label, [poison],
                  rng.uniform(0.82, 0.94), "evidence_poisoning")
        add_event(task, poison_2, planner, "risk_judgment", false_label, [poison, neutral],
                  rng.uniform(0.78, 0.90), "evidence_poisoning")

        # ── Byzantine claims (mode-dependent) ──
        if hard:
            # HARD: stealthy byzantine — always valid sig/hash/schema, always has evidence, sometimes correct
            _build_hard_byzantine(task, byz_1, byz_2, verifier, planner, rng, cfg,
                                  add_event, good_1, good_2, neutral, poison, false_high_q, false_high_q2,
                                  true_label, false_label, i)
        else:
            # EASY: naive byzantine
            _build_easy_byzantine(task, byz_1, byz_2, verifier, planner, rng, cfg,
                                  add_event, poison, true_label, false_label, i)

        # ── Communication tampering ──
        tamper = rng.random() < cfg["comm_tamper_rate"]
        if tamper:
            add_event(task, comm, verifier, "risk_judgment", false_label, [good_1],
                      rng.uniform(0.74, 0.91), "communication_tampering", "comm_mitm",
                      transport_integrity=False,
                      signature_status="invalid" if not hard and i % 2 == 0 else "valid")
        else:
            add_event(task, comm, verifier, "risk_judgment", true_label, [good_1],
                      rng.uniform(0.78, 0.90), "clean")

        # ── Noisy watch ──
        shift = -10 if i % 23 == 0 else 0
        watch_ev = [neutral] if not hard else ([false_high_q, neutral] if i % 2 else [good_1, neutral])
        add_event(task, watch, verifier, "risk_judgment",
                  false_label if i % 2 else true_label, watch_ev,
                  rng.uniform(0.65, 0.82), "noisy_watch", "unsupported_high_conf" if not hard else "noisy_judgment",
                  nonce_mode="reuse" if not hard and i % 29 == 0 else "unique",
                  timestamp_shift_days=shift if not hard else 0)

        # ── Hard-only: collusion and strategic attacks ──
        if hard:
            _build_hard_extras(task, agents, verifier, planner, rng, cfg, add_event,
                               good_1, good_2, neutral, false_high_q, false_high_q2,
                               true_label, false_label, i, ambiguous_task)

    # Fill conflict links after all groups are known.
    group_by_task_kind: Dict[Tuple[str, str], List[dict]] = {}
    for g in groups:
        group_by_task_kind.setdefault((g["task_id"], g["group_kind"]), []).append(g)
    for gs in group_by_task_kind.values():
        ids = [g["claim_group_id"] for g in gs]
        for g in gs:
            g["conflicts_with"] = [x for x in ids if x != g["claim_group_id"]]

    for task in tasks:
        verifier = select_agent(agents, "none", "verifier", int(task["task_id"].split("_")[1]))
        challenges.append({
            "challenge_id": f"CH_{task['task_id']}",
            "task_id": task["task_id"],
            "verifier_agent": verifier["agent_id"],
            "subject": task["subject"],
            "approved_label": task["true_label"],
            "verifier_approve": 1,
            "challenge_type": "active_cross_evidence_check",
            "result": f"Verifier approves {task['true_label']} for {task['subject']}.",
        })

    attack_families = ["none", "evidence_poisoning", "byzantine_agent", "communication_tampering", "noisy_watch"]
    if hard:
        attack_families.extend(["stealthy_collusion", "strategic_attack"])

    manifest = {
        "dataset_id": cfg["dataset_id"],
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "description": cfg["description"],
        "scale": {
            "agents": len(agents),
            "tasks": len(tasks),
            "comm_events": len(events),
            "claims": len(claims),
            "evidence": len(evidence),
            "tool_calls": len(tool_calls),
            "consensus_groups": len(groups),
            "challenges": len(challenges),
        },
        "attack_families": attack_families,
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    }
    data = {
        "manifest": manifest,
        "agents": agents,
        "tasks": tasks,
        "evidence": evidence,
        "comm_events": events,
        "claims": claims,
        "tool_calls": tool_calls,
        "challenges": challenges,
        "consensus_groups": groups,
    }
    for name, obj in data.items():
        write_json(dataset_dir / f"{name}.json", obj)

    # README
    readme = [
        f"# {cfg['dataset_id']}",
        "",
        cfg["description"],
        "",
        "## Scale",
    ]
    for k, v in manifest["scale"].items():
        readme.append(f"- {k}: {v}")
    readme.extend([
        "",
        "## Attack families",
    ])
    for fam in attack_families:
        readme.append(f"- {fam}")
    readme.extend([
        "",
        "## Files",
        "- agents.json: registry with role, permissions, key reference, and ground-truth family.",
        "- comm_events.json: raw/sent/received messages and transport metadata.",
        "- claims.json: structured claim rows linked to communication events.",
        "- evidence.json: evidence quality fields and RAG-related poison markers.",
        "- tool_calls.json: tool hash material for zero-trust validation.",
        "- consensus_groups.json: conflict groups used by the weighted consensus engine.",
        "- challenges.json: active verifier challenge records.",
    ])
    (dataset_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")
    return data


# ── Attack builders ────────────────────────────────────────────────────
def _build_easy_byzantine(task, byz_1, byz_2, verifier, planner, rng, cfg, add_event,
                          poison, true_label, false_label, i):
    """Original naive byzantine: obvious validation-breaking patterns."""
    sig = "invalid" if i % cfg["byzantine_invalid_sig_every"] == 0 else "valid" if cfg["byzantine_invalid_sig_every"] else "valid"
    schema = "missing_subject" if cfg["byzantine_missing_subject_every"] and i % cfg["byzantine_missing_subject_every"] == 0 else "valid"
    tool_int = "forged" if cfg["byzantine_forged_hash_every"] and i % cfg["byzantine_forged_hash_every"] == 0 else "valid"
    nonce_mode = "reuse" if cfg["byzantine_reuse_nonce_every"] and i % cfg["byzantine_reuse_nonce_every"] == 0 else "unique"
    no_ev = cfg["byzantine_no_evidence_every"] and i % cfg["byzantine_no_evidence_every"] == 0
    add_event(task, byz_1, verifier, "risk_judgment", false_label,
              [poison] if not no_ev else [],
              rng.uniform(0.88, 0.98), "byzantine", "collusive_false_claim",
              signature_status=sig, schema_status=schema, tool_integrity=tool_int,
              nonce_mode=nonce_mode)
    add_event(task, byz_2, verifier, "action_recommendation", false_label,
              [] if no_ev else [poison],
              rng.uniform(0.84, 0.97), "byzantine", "unsafe_action",
              signature_status="invalid" if i % 7 == 0 else "valid",
              tool_integrity="forged" if i % 5 == 0 else "valid")


def _build_hard_byzantine(task, byz_1, byz_2, verifier, planner, rng, cfg, add_event,
                          good_1, good_2, neutral, poison, false_high_q, false_high_q2,
                          true_label, false_label, i):
    """Stealthy byzantine: always valid, always evidence, sometimes correct."""
    # Risk judgment: sometimes correct to blend in
    if rng.random() < cfg["byzantine_correct_rate"]:
        label_1 = true_label
        ev_1 = [good_1, neutral]
    else:
        label_1 = false_label
        ev_1 = [false_high_q, false_high_q2] if false_high_q else [poison, neutral]
    add_event(task, byz_1, verifier, "risk_judgment", label_1, ev_1,
              rng.uniform(0.82, 0.94), "byzantine", "stealthy_false_claim",
              signature_status="valid", schema_status="valid", tool_integrity="valid")

    # Action recommendation: stealthy attack
    if rng.random() < cfg["byzantine_correct_rate"]:
        label_2 = true_label
        ev_2 = [good_2, neutral]
    else:
        label_2 = false_label
        ev_2 = [false_high_q, false_high_q2] if false_high_q else [poison, good_2]
    add_event(task, byz_2, verifier, "action_recommendation", label_2, ev_2,
              rng.uniform(0.82, 0.95), "byzantine", "stealthy_action",
              signature_status="valid", schema_status="valid", tool_integrity="valid")


def _build_hard_extras(task, agents, verifier, planner, rng, cfg, add_event,
                       good_1, good_2, neutral, false_high_q, false_high_q2,
                       true_label, false_label, i, ambiguous_task=False):
    """Collusion and strategic attacks (hard mode only)."""

    # ── Stealthy collusion: N agents push the same wrong label using aligned false evidence (every 2nd task) ──
    wave = cfg.get("collusion_wave_size", 0)
    # On ambiguous tasks, use even more collusion agents
    actual_wave = wave + 4 if ambiguous_task else wave
    if wave and (i % 2 == 1 or ambiguous_task):
        col_agents_list = [select_agent(agents, "stealthy_collusion", None, i + k) for k in range(actual_wave)]
        col_agents_list = [select_agent(agents, "stealthy_collusion", None, i + k) for k in range(wave)]
        col_ev = [false_high_q, false_high_q2] if false_high_q else [good_1, neutral]
        for col_agent in col_agents_list:
            add_event(task, col_agent, verifier, "risk_judgment", false_label, col_ev,
                      rng.uniform(0.84, 0.95), "stealthy_collusion", "coordinated_false_consensus",
                      signature_status="valid", schema_status="valid", tool_integrity="valid")
        # Also push false actions from 2 agents
        if len(col_agents_list) >= 3:
            add_event(task, col_agents_list[2], verifier, "action_recommendation", false_label, col_ev,
                      rng.uniform(0.82, 0.94), "stealthy_collusion", "coordinated_false_action",
                      signature_status="valid", schema_status="valid", tool_integrity="valid")
        if len(col_agents_list) >= 6:
            add_event(task, col_agents_list[5], verifier, "action_recommendation", false_label, col_ev,
                      rng.uniform(0.80, 0.92), "stealthy_collusion", "coordinated_false_action",
                      signature_status="valid", schema_status="valid", tool_integrity="valid")

    # ── Strategic attack: correct risk, attack on action — every 3rd task ──
    if i % 3 == 0:
        strat_a = select_agent(agents, "strategic_attack", "planner", i)
        strat_b = select_agent(agents, "strategic_attack", "rag_reader", i + 1)
        # Risk judgment: correct (blend in)
        add_event(task, strat_a, verifier, "risk_judgment", true_label, [good_1, good_2],
                  rng.uniform(0.82, 0.93), "clean",
                  signature_status="valid", schema_status="valid", tool_integrity="valid")
        # Action recommendation: attack using aligned false evidence
        strat_ev = [false_high_q, false_high_q2] if false_high_q else [good_1, neutral]
        strat_action_label = false_label
        add_event(task, strat_a, verifier, "action_recommendation", strat_action_label, strat_ev,
                  rng.uniform(0.85, 0.96), "strategic_attack", "targeted_action_strike",
                  signature_status="valid", schema_status="valid", tool_integrity="valid")
        add_event(task, strat_b, verifier, "action_recommendation", strat_action_label, strat_ev,
                  rng.uniform(0.82, 0.94), "strategic_attack", "targeted_action_strike",
                  signature_status="valid", schema_status="valid", tool_integrity="valid")


# ── CLI ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    hard = "--hard" in sys.argv
    task_count = 120 if not hard else 300
    data = build_dataset(task_count=task_count, hard=hard)
    print(data["manifest"])
