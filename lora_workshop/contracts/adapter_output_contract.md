# LoRA Adapter Output Contract

每个 trial 必须输出同一套结构，方便模型纳管、审核发布、运营分析和后续复训。

```text
trial_xxx/
  config.json
  config.lock.json
  trainer_config/
    ai_toolkit_config.yaml
    adapter_manifest.json
  metrics.json
  evaluation.json
  checkpoint_valid.json
  sample_grid.html
  summary.md
```

## 必填记录

- `base_model.id`：底座模型或内网模型路径。
- `dataset.core_ref` / `expanded_ref`：核心训练数据和扩充概念数据版本。
- `dataset.required_authorization`：授权状态必须为 `true` 才允许进入发布流程。
- `train`：实际生效的学习率、rank、alpha、steps、batch、caption dropout、seed。
- `lora_profile`：LoRA 矩阵中的编号、名称、主题、适用品类和默认权重。
- `evaluation`：风格还原、文化准确性、产品转化、提示词遵循、瑕疵控制和效率评分。
- `release_gate`：是否可进入平台模型纳管、公开展示或商业化应用。
