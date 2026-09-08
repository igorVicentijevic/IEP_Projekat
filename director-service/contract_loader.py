import json
import os
from pathlib import Path

DIRECTOR_SERVICE_DIR = Path(__file__).resolve().parent
DEFAULT_CONTRACT_ARTIFACT_PATH = DIRECTOR_SERVICE_DIR.parent / "contract" / "VotingContract.json"
CONTRACT_ARTIFACT_PATH = Path(
    os.environ.get("VOTING_CONTRACT_ARTIFACT_PATH", str(DEFAULT_CONTRACT_ARTIFACT_PATH))
).resolve()


def load_voting_contract_artifact(path=CONTRACT_ARTIFACT_PATH):
    artifact_path = Path(path).resolve()

    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Voting contract artifact not found at {artifact_path}. "
            "Run `python contract/compile_contract.py` from the repository root."
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Voting contract artifact at {artifact_path} is unreadable or invalid JSON."
        ) from exc

    abi = artifact.get("abi")
    bytecode = artifact.get("bytecode")
    if not isinstance(abi, list) or not isinstance(bytecode, str) or not bytecode.strip():
        raise RuntimeError(
            f"Voting contract artifact at {artifact_path} must contain "
            "an 'abi' list and a non-empty 'bytecode' string."
        )

    return abi, bytecode
