# TJWCCP

文创文旅产品训练。

本仓库当前交付 `lora_workshop/`：面向“天津地域文化文创产品智能生成应用系统”的 LoRA 训练、评估、人工优选与模型纳管工具链。

## 快速验证

```bash
python3 lora_workshop/runner.py --trials 3 --run-name smoke_niren_zhang
python3 lora_workshop/tools/build_review_site.py --run-dir lora_workshop/runs/smoke_niren_zhang
python3 -m http.server 8000 -d lora_workshop/review_site
```

打开 `http://127.0.0.1:8000/`，即可手动浏览训练 trial、选择优质 LoRA，并导出人工评审结果。

详见 [lora_workshop/README.md](lora_workshop/README.md)。
