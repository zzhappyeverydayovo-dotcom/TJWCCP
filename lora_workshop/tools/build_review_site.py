import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_DIR = ROOT / "review_site"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_experiments(tsv_path):
    with Path(tsv_path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def maybe_copy_sample(trial_dir, assets_dir):
    sample_html = trial_dir / "sample_grid.html"
    if not sample_html.exists():
        return ""
    target = assets_dir / f"{trial_dir.name}_sample_grid.html"
    shutil.copy2(sample_html, target)
    return f"assets/{target.name}"


def build_review_data(run_dir, site_dir):
    run_dir = Path(run_dir)
    site_dir = Path(site_dir)
    assets_dir = site_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    rows = read_experiments(run_dir / "experiments.tsv")
    trials = []
    for row in rows:
        trial_dir = Path(row["artifact_dir"])
        if not trial_dir.is_absolute():
            trial_dir = run_dir / row["trial_id"]
        config = load_json(trial_dir / "config.json")
        evaluation = load_json(trial_dir / "evaluation.json")
        config_lock = load_json(trial_dir / "config.lock.json")
        sample_url = maybe_copy_sample(trial_dir, assets_dir)
        trials.append(
            {
                "trial_id": row["trial_id"],
                "lora_id": row["lora_id"],
                "lora_name": row["lora_name"],
                "theme": row["theme"],
                "status": row["status"],
                "score": float(row["score"]),
                "release_decision": row["release_decision"],
                "reject_reason": row["reject_reason"],
                "sample_url": sample_url,
                "config": {
                    "base_model": row["base_model"],
                    "dataset_ref": row["dataset_ref"],
                    "learning_rate": row["learning_rate"],
                    "rank": row["rank"],
                    "alpha": row["alpha"],
                    "steps": row["steps"],
                    "trigger_token": config["dataset"]["trigger_token"],
                    "default_weight": config["generation"]["lora_weight_default"],
                    "product_fit": config["lora_profile"].get("product_fit", []),
                },
                "evaluation": evaluation,
                "config_lock": {
                    "rendered_native_config_path": config_lock.get("rendered_native_config_path", ""),
                    "dry_run": config_lock.get("dry_run", False),
                },
            }
        )

    best_path = run_dir / "best.json"
    best = load_json(best_path) if best_path.exists() else {}
    return {
        "schema_version": "heritage-review-site-v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": run_dir.name,
        "project": "天津地域文化文创产品智能生成应用系统",
        "review_goal": "人工筛选 LoRA 训练结果，确认可进入模型纳管、复训或发布审核的候选版本。",
        "best_by_metric": best,
        "trials": sorted(trials, key=lambda item: item["score"], reverse=True),
        "review_rubric": [
            "泥人张彩塑造型语言、三分塑七分彩、手工泥塑质感是否稳定。",
            "天津地域文化、非遗符号和传统设色是否准确，是否存在文化误读。",
            "是否适合转化为礼盒、海报、包装、冰箱贴、文具、纪念品等文创产品。",
            "是否有商标、肖像、敏感内容、伪文字、水印、结构崩坏等风险。",
            "同等质量下优先选择训练成本更低、可控性更强、提示词遵循更好的版本。"
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--site-dir", default=str(DEFAULT_SITE_DIR))
    args = parser.parse_args()

    site_dir = Path(args.site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)
    data = build_review_data(args.run_dir, site_dir)
    write_json(site_dir / "review-data.json", data)
    print(f"review_site={site_dir}")
    print(f"trials={len(data['trials'])}")


if __name__ == "__main__":
    main()
