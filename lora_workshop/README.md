# LoRA Workshop

这是面向“天津地域文化文创产品智能生成应用系统”的 LoRA 训练与纳管骨架。

它仿照 TAFA-SAIA 的思想，但按本项目书重写为：

- 核心方向：泥人张彩塑专属图像生成与文创产品转化。
- 模型体系：开源底座 + 核心微调模型 + 50 款定制 LoRA 矩阵。
- 数据要求：授权核心数据 + 中国传统文化扩充概念数据。
- 业务闭环：创意采集、提示词封装、生成调度、审核发布、运营分析、模型纳管。

运行 smoke：

```bash
python3 lora_workshop/runner.py --trials 3 --run-name smoke_niren_zhang
```

查看结果：

```text
lora_workshop/runs/smoke_niren_zhang/experiments.tsv
lora_workshop/runs/smoke_niren_zhang/best.json
```
