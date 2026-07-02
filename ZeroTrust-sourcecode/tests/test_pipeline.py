import json
import unittest

from agent_demo_app.claim_gateway import ClaimGateway
from agent_demo_app.consensus_engine import ConsensusEngine
from agent_demo_app.data_loader import DataLoader
from agent_demo_app.experiments import PipelineRunner
from agent_demo_app.verifier import ClaimPackageVerifier
from agent_demo_app.byzantine_detector import ByzantineDetector


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = DataLoader().load_all()
        if not cls.data.get("comm_events"):
            PipelineRunner().run_all(graph_task_limit=2)
            cls.data = DataLoader().load_all()

    def test_dataset_scale(self):
        self.assertGreaterEqual(len(self.data["agents"]), 50)
        self.assertGreaterEqual(len(self.data["comm_events"]), 1000)
        self.assertGreaterEqual(len(self.data["evidence"]), 400)

    def test_gateway_and_validation(self):
        packages = ClaimGateway(self.data).build_all(self.data["comm_events"][:60])
        validations = ClaimPackageVerifier(self.data).verify_all(packages)
        passed = sum(1 for v in validations if v["passed"])
        self.assertGreater(passed, 20)
        self.assertTrue(all("I_schema" in v["checks"] for v in validations))

    def test_bss_identifies_attack_families(self):
        packages = ClaimGateway(self.data).build_all(self.data["comm_events"][:240])
        validations = ClaimPackageVerifier(self.data).verify_all(packages)
        risk = ByzantineDetector(self.data).run(packages, validations)
        roots = {r["root_cause"] for r in risk if r["bss"] >= 0.25}
        self.assertIn("communication_tampering", roots)
        self.assertIn("evidence_poisoning", roots)
        self.assertIn("byzantine_agent", roots)

    def test_full_artifacts_exist(self):
        summary = PipelineRunner().run_all(graph_task_limit=1)
        self.assertGreaterEqual(summary["dataset"]["comm_events"], 1000)
        self.assertGreater(summary["validation_pass_rate"], 0.6)
        self.assertTrue(summary["files"]["neo4j_cypher"].endswith("neo4j_import.cypher"))


if __name__ == "__main__":
    unittest.main()
