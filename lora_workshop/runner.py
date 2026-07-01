import argparse
import csv
import json
import random
import shutil
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
CONTRACTS_DIR = ROOT / "contracts"
RUNS_DIR = ROOT / "runs"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_nested(data, dotted_key):
    current = data
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return "__MISSING__"
        current = current[part]
    return current


def set_nested(data, dotted_key, value):
    current = data
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def flatten_leaf_paths(data, prefix=""):
    if isinstance(data, dict):
        paths = []
        for key, value in data.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            paths.extend(flatten_leaf_paths(value, next_prefix))
        return paths
    return [prefix]


def validate_agent_changes(base, proposal, policy):
    allowlist = set(policy["write_allowlist"])
    derived_prefixes = ("lora_profile.", "agent.")
    paths = sorted(set(flatten_leaf_paths(base)) | set(flatten_leaf_paths(proposal)))
    changed = {path for path in paths if get_nested(base, path) != get_nested(proposal, path)}
    blocked = {
        path
        for path in changed - allowlist
        if not path.startswith(derived_prefixes)
    }
    if blocked:
        raise ValueError(f"Agent proposal changed protected fields: {sorted(blocked)}")

    max_steps = int(policy["resource_limits"]["max_steps_per_trial"])
    if int(proposal["train"]["steps"]) > max_steps:
        raise ValueError(f"train.steps exceeds max_steps_per_trial={max_steps}")


def pick_lora_profile(matrix, index):
    profiles = matrix["profiles"]
    return profiles[index % len(profiles)]


def propose_config(base, search, policy, matrix, trial_index):
    config = deepcopy(base)
    if trial_index == 1:
        proposal = search["recommended_first_step"]
    else:
        rng = random.Random(20260701 + trial_index)
        proposal = {key: rng.choice(values) for key, values in search["space"].items()}

    for key, value in proposal.items():
        set_nested(config, f"train.{key}", value)

    profile = pick_lora_profile(matrix, trial_index - 1)
    config["lora_profile"] = profile
    config["generation"]["lora_weight_default"] = profile["default_weight"]
    validate_agent_changes(base, config, policy)
    config["agent"] = {
        "proposal_index": trial_index,
        "proposal_reason": "在授权数据、固定触发词和评估门槛不变的前提下，调整 LoRA 训练超参数与矩阵条目。",
        "editable_scope": policy["write_allowlist"],
    }
    return config


def run_trial(trial_id, config, run_dir):
    trial_dir = run_dir / trial_id
    trial_dir.mkdir(parents=True, exist_ok=True)
    config_path = trial_dir / "config.json"
    write_json(config_path, config)

    backend = config["train"]["backend"]
    if backend != "ai-toolkit-dry-run":
        raise RuntimeError(f"Unsupported backend in this local skeleton: {backend}")

    trainer_cmd = [
        sys.executable,
        str(ROOT / "adapters" / "ai_toolkit_adapter.py"),
        "--config",
        str(config_path),
        "--out",
        str(trial_dir),
        "--dry-run",
    ]
    subprocess.run(trainer_cmd, check=True)

    evaluator_cmd = [
        sys.executable,
        str(ROOT / "evaluator.py"),
        "--trial-dir",
        str(trial_dir),
        "--out",
        str(trial_dir / "evaluation.json"),
    ]
    subprocess.run(evaluator_cmd, check=True)
    return {
        "trial_dir": trial_dir,
        "metrics": load_json(trial_dir / "metrics.json"),
        "evaluation": load_json(trial_dir / "evaluation.json"),
        "config_lock": load_json(trial_dir / "config.lock.json"),
    }


def append_tsv(tsv_path, row):
    fields = [
        "run_id",
        "trial_id",
        "lora_id",
        "lora_name",
        "theme",
        "status",
        "base_model",
        "dataset_ref",
        "learning_rate",
        "rank",
        "alpha",
        "steps",
        "score",
        "release_decision",
        "reject_reason",
        "artifact_dir",
    ]
    exists = tsv_path.exists()
    with tsv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in fields})


def build_row(run_id, trial_id, config, result):
    evaluation = result["evaluation"]
    profile = config["lora_profile"]
    return {
        "run_id": run_id,
        "trial_id": trial_id,
        "lora_id": profile["id"],
        "lora_name": profile["name"],
        "theme": profile["theme"],
        "status": result["metrics"]["status"],
        "base_model": config["base_model"]["id"],
        "dataset_ref": config["dataset"]["core_ref"],
        "learning_rate": config["train"]["learning_rate"],
        "rank": config["train"]["rank"],
        "alpha": config["train"]["alpha"],
        "steps": config["train"]["steps"],
        "score": evaluation["score"],
        "release_decision": evaluation["release_gate"]["decision"],
        "reject_reason": evaluation["release_gate"]["reject_reason"],
        "artifact_dir": str(result["trial_dir"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=1, help="Number of LoRA matrix trials to render after baseline.")
    parser.add_argument("--run-name", default="")
    parser.add_argument("--base-config", default=str(CONFIG_DIR / "base_config.json"))
    args = parser.parse_args()

    base = load_json(args.base_config)
    search = load_json(CONFIG_DIR / "search_space.json")
    matrix = load_json(CONFIG_DIR / "lora_matrix.json")
    policy = load_json(CONTRACTS_DIR / "agent_policy.json")

    if args.trials > int(policy["resource_limits"]["max_trials_per_run"]):
        raise ValueError("Requested trials exceeds max_trials_per_run")

    run_id = args.run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    baseline = deepcopy(base)
    baseline["lora_profile"] = matrix["profiles"][0]
    baseline_id = "trial_000_baseline"
    baseline_result = run_trial(baseline_id, baseline, run_dir)
    append_tsv(run_dir / "experiments.tsv", build_row(run_id, baseline_id, baseline, baseline_result))

    best = {
        "trial_id": baseline_id,
        "score": baseline_result["evaluation"]["score"],
        "artifact_dir": str(baseline_result["trial_dir"]),
        "release_decision": baseline_result["evaluation"]["release_gate"]["decision"],
    }

    for index in range(1, args.trials + 1):
        trial_id = f"trial_{index:03d}_matrix_proposal"
        config = propose_config(base, search, policy, matrix, index)
        result = run_trial(trial_id, config, run_dir)
        append_tsv(run_dir / "experiments.tsv", build_row(run_id, trial_id, config, result))
        score = result["evaluation"]["score"]
        if score > best["score"]:
            best.update(
                {
                    "trial_id": trial_id,
                    "score": score,
                    "artifact_dir": str(result["trial_dir"]),
                    "release_decision": result["evaluation"]["release_gate"]["decision"],
                }
            )

    write_json(run_dir / "best.json", best)
    print(f"run_dir={run_dir}")
    print(f"best_trial={best['trial_id']}")
    print(f"best_score={best['score']}")


if __name__ == "__main__":
    main()
