import json
import tempfile
import unittest
from pathlib import Path

DIRECTOR_SERVICE_DIR = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(DIRECTOR_SERVICE_DIR))

from contract_loader import load_voting_contract_artifact


class ContractLoaderTests(unittest.TestCase):
    def test_load_valid_artifact(self):
        artifact = {
            "abi": [{"type": "function", "name": "getStatus", "inputs": [], "outputs": []}],
            "bytecode": "60806040",
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_path = Path(tmp_dir) / "VotingContract.json"
            artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

            abi, bytecode = load_voting_contract_artifact(artifact_path)

        self.assertEqual(abi, artifact["abi"])
        self.assertEqual(bytecode, artifact["bytecode"])

    def test_missing_artifact_raises_clear_error(self):
        missing_path = Path(tempfile.gettempdir()) / "not-existing-voting-artifact.json"

        with self.assertRaises(RuntimeError) as raised:
            load_voting_contract_artifact(missing_path)

        self.assertIn("Voting contract artifact not found", str(raised.exception))

    def test_malformed_artifact_raises_clear_error(self):
        malformed_artifact = {"abi": "not-a-list", "bytecode": ""}

        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_path = Path(tmp_dir) / "VotingContract.json"
            artifact_path.write_text(json.dumps(malformed_artifact), encoding="utf-8")

            with self.assertRaises(RuntimeError) as raised:
                load_voting_contract_artifact(artifact_path)

        self.assertIn("must contain an 'abi' list", str(raised.exception))


class DirectorServiceIntegrationWiringTests(unittest.TestCase):
    def test_app_uses_loader_instead_of_embedded_constants(self):
        app_source = (DIRECTOR_SERVICE_DIR / "app.py").read_text(encoding="utf-8")

        self.assertNotIn("VOTING_CONTRACT_ABI = [", app_source)
        self.assertNotIn("VOTING_CONTRACT_BYTECODE = \"", app_source)
        self.assertIn("VOTING_CONTRACT_ABI, VOTING_CONTRACT_BYTECODE = load_voting_contract_artifact()", app_source)


if __name__ == "__main__":
    unittest.main()
