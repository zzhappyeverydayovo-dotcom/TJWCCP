import argparse
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def proximity(value, target, scale):
    return math.exp(-abs(value - target) / scale)


def evaluate_dry_run(config):
    train = config["train"]
    profile = config["lora_profile"]
    lr = float(train["learning_rate"])
    rank = int(train["rank"])
    alpha = int(train["alpha"])
    steps = int(train["steps"])
    dropout = float(train["caption_dropout"])

    rank_score = 1.0 if rank == 16 else (0.92 if rank == 32 else 0.82)
    alpha_score = 1.0 if alpha == rank else 0.84
    lr_score = proximity(math.log10(lr), math.log10(0.0001), 0.34)
    step_score = proximity(steps, 1600, 900)
    dropout_score = proximity(dropout, 0.05, 0.06)
    product_bonus = 0.05 if "文创礼盒" in profile.get("product_fit", []) else 0.0

    style_fidelity = clamp(0.46 + 0.2 * rank_score + 0.16 * lr_score + 0.08 * alpha_score)
    cultural_accuracy = clamp(0.5 + 0.16 * dropout_score + 0.12 * step_score)
    product_transferability = clamp(0.48 + 0.18 * step_score + product_bonus)
    prompt_adherence = clamp(0.52 + 0.16 * dropout_score + 0.1 * lr_score)
    artifact_control = clamp(0.86 - max(0.0, lr - 0.00012) * 1000 - max(0, steps - 2600) / 8000)
    cost_efficiency = clamp(1.0 - steps / 5200 - rank / 160, 0.25, 1.0)

    return {
        "style_fidelity": round(style_fidelity, 4),
        "cultural_accuracy": round(cultural_accuracy, 4),
        "product_transferability": round(product_transferability, 4),
        "prompt_adherence": round(prompt_adherence, 4),
        "artifact_control": round(artifact_control, 4),
        "cost_efficiency": round(cost_efficiency, 4),
        "simulated": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    trial_dir = Path(args.trial_dir)
    config = load_json(trial_dir / "config.json")
    policy = load_json(ROOT / "contracts" / "evaluation_policy.json")
    checkpoint = load_json(trial_dir / "checkpoint_valid.json")
    dry_scores = evaluate_dry_run(config)

    weights = config["evaluation"]["weights"]
    score = round(
        sum(float(dry_scores[key]) * float(weight) for key, weight in weights.items()),
        4,
    )

    gates = policy["hard_gates"]
    release_blockers = []
    if gates["authorized_dataset_required"] and not config["dataset"].get("required_authorization"):
        release_blockers.append("dataset_not_authorized")
    if gates["checkpoint_must_exist"] and not checkpoint.get("valid"):
        release_blockers.append("checkpoint_missing")
    if dry_scores["cultural_accuracy"] < gates["cultural_accuracy_min"]:
        release_blockers.append("cultural_accuracy_below_gate")
    if dry_scores["artifact_control"] < gates["artifact_control_min"]:
        release_blockers.append("artifact_control_below_gate")
    if gates["requires_human_review_for_release"]:
        release_blockers.append("human_review_required")

    decision = "approved_for_platform"
    if "checkpoint_missing" in release_blockers:
        decision = "internal_preview"
    if any(item.endswith("_below_gate") for item in release_blockers):
        decision = "needs_revision"
    if "dataset_not_authorized" in release_blockers:
        decision = "reject"

    evaluation = {
        "schema_version": "heritage-evaluation-v1",
        "trial_id": trial_dir.name,
        "lora_profile": config["lora_profile"],
        "score": score,
        "tracks": dry_scores,
        "release_gate": {
            "decision": decision,
            "eligible_for_public_release": decision == "approved_for_platform" and not release_blockers,
            "reject_reason": ";".join(release_blockers),
            "notes": "Dry-run 分数用于配置筛选；真实模型发布必须替换为图像指标、人工盲评、版权肖像与文化表达复核。",
        },
    }
    write_json(args.out, evaluation)


if __name__ == "__main__":
    main()
