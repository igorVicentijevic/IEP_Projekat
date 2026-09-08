import json
import os
from pathlib import Path

from solcx import compile_standard, install_solc, set_solc_version


ROOT_DIR = Path(__file__).resolve().parent
SOURCE_PATH = ROOT_DIR / "contract.sol"
ARTIFACT_PATH = ROOT_DIR / "VotingContract.json"
CONTRACT_NAME = "VotingContract"
SOLC_VERSION = os.environ.get("SOLC_VERSION", "0.8.20")


def compile_voting_contract():
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"Solidity source not found: {SOURCE_PATH}")

    try:
        install_solc(SOLC_VERSION)
        set_solc_version(SOLC_VERSION)
    except Exception as exc:
        raise RuntimeError(
            f"Unable to install/use solc {SOLC_VERSION}. "
            "Check network access or provide a preinstalled solc binary."
        ) from exc

    source_code = SOURCE_PATH.read_text(encoding="utf-8")

    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {SOURCE_PATH.name: {"content": source_code}},
            "settings": {
                "optimizer": {"enabled": False, "runs": 200},
                "outputSelection": {
                    "*": {
                        "*": ["abi", "evm.bytecode.object"]
                    }
                },
            },
        }
    )

    contract_data = compiled["contracts"][SOURCE_PATH.name][CONTRACT_NAME]
    abi = contract_data["abi"]
    bytecode = contract_data["evm"]["bytecode"]["object"]

    if not isinstance(abi, list) or not bytecode:
        raise ValueError("Compilation succeeded but ABI/bytecode output is invalid.")

    artifact = {
        "contractName": CONTRACT_NAME,
        "sourcePath": "contract/contract.sol",
        "compilerVersion": SOLC_VERSION,
        "abi": abi,
        "bytecode": bytecode,
    }

    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"Wrote artifact to {ARTIFACT_PATH}")


if __name__ == "__main__":
    compile_voting_contract()
