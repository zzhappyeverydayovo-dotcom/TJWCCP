# 天津非遗文创 LoRA 训练运行手册

## 项目定位

本目录服务于“文化创意产品智能生成应用系统”的模型建设要求，采用“自研微调模型 + 自研工具 + 开源底座”的分层体系。

首批示范场景为泥人张彩塑，目标是支撑天津地域文化文创产品的智能生成，并可迁移到杨柳青年画、京剧脸谱、民族服饰、古代壁画等视觉非遗品类。

## 架构

```text
授权数据集
  -> 标准化结构化+美学化标注
  -> LoRA 矩阵配置
  -> runner 生成 trial
  -> AI Toolkit adapter 渲染训练 YAML
  -> 训练/采样/日志/权重产物
  -> evaluator 质量评估与发布门槛
  -> experiments.tsv + model registry
  -> 平台模型纳管与审核发布
```

## 本地 dry-run

先验证配置、矩阵和产物契约：

```bash
python3 lora_workshop/runner.py --trials 3 --run-name smoke_niren_zhang
```

输出目录：

```text
lora_workshop/runs/smoke_niren_zhang/
  experiments.tsv
  best.json
  trial_000_baseline/
  trial_001_matrix_proposal/
```

每个 trial 会包含：

```text
config.json
config.lock.json
trainer_config/ai_toolkit_config.yaml
metrics.json
evaluation.json
checkpoint_valid.json
sample_grid.html
summary.md
```

## 人工评审网站

构建静态评审网站数据：

```bash
python3 lora_workshop/tools/build_review_site.py --run-dir lora_workshop/runs/smoke_niren_zhang
```

本地打开：

```bash
python3 -m http.server 8000 -d lora_workshop/review_site
```

浏览器访问：

```text
http://127.0.0.1:8000/
```

评审台能力：

- 按 LoRA 名称、主题、trial id 搜索。
- 按发布状态筛选：内部预览、需要修订、可纳管、淘汰。
- 查看每个 trial 的训练参数、评估分轨、触发词、适用品类和样张。
- 手动设为 `Champion`、加入候选、保留观察或人工淘汰。
- 填写人工意见并导出 `human_review.json`，用于模型纳管和后续版本迭代。

## 真实训练接入点

当前默认 backend 是 `ai-toolkit-dry-run`，只渲染 AI Toolkit YAML，不启动训练。真实训练时应补充：

1. 将授权泥人张数据放入 `datasets/niren_zhang/v1`，图片和同名 `.txt` caption 对齐。
2. 每条 caption 保留触发词 `nrz_clay_heritage_style`，并包含结构化+美学化标签。
3. 安装并锁定 AI Toolkit commit。
4. 将 adapter 扩展为执行：

```bash
python run.py lora_workshop/runs/<run>/<trial>/trainer_config/ai_toolkit_config.yaml
```

5. 训练后复制 `.safetensors`、采样图、训练日志，并把 `checkpoint_valid.json` 改为真实加载验证结果。

## 质量门槛

LoRA 不以 loss 单独晋级。评估至少包含：

- 风格还原度：泥人张造型语言、手工泥塑质感、传统设色。
- 文化准确性：天津地域文化、非遗符号、服饰与文化语义。
- 产品转化适配性：礼盒、海报、包装、冰箱贴、文具、纪念品等场景。
- 提示词遵循：六大创作维度和结构化提示词。
- 瑕疵控制：文字伪影、商标、肖像、错误材质、结构变形。
- 效率指标：训练成本、生成时延、调用资源。

公开展示或商业应用前必须经过审核辅助智能体和人工复核。
