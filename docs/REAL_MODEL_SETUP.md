# 真实模型部署与切换指南

> 把 Kaggle 训出来的 `best.pt` 接入本地后端,完成"mock → real"切换。

---

## 切换流程全景

```
[Kaggle]                          [本地]
                                  ┌─────────────────┐
kaggle_train.py ─┐                │ best.pt (203MB) │ ← 解压至此
                │                 └────────┬────────┘
                ▼                          │ verify_model.py
        /kaggle/working/                   │ (完整性校验)
        stage2_finetune/                   ▼
            best.pt                ┌─────────────────┐
                │                  │ uvicorn --reload │
                │                  │ MODEL_WEIGHTS=... │
                │                  └────────┬────────┘
                │                           │
                ▼                           ▼
        [Output 面板] ─下载─→ [models/checkpoints/]
                                  │
                                  ▼
                          /api/classify → mock=false
```

---

## 1. 文件摆放

| 路径 | 内容 | 作用 |
|------|------|------|
| `models/checkpoints/best.pt` | 最终权重 (~203MB) | 后端启动时加载 |
| `models/checkpoints/last.pt` | 最近一次 epoch | 恢复训练用,可不放 |
| `models/web_model/best.onnx` | ONNX 导出 | 前端 TF.js 转换源 |

> `best.pt` 唯一性约束:后端只看这一个路径,启动时若不存在自动 fallback 到 mock。

---

## 2. 验证脚本 (`scripts/verify_model.py`)

### 2.1 校验内容

1. **文件存在性** + 大小 (正常 200-220MB)
2. **state_dict 完整性**: 1120 张量 / 53.2M 参数
3. **类别数匹配**: 期望 10
4. **dummy 前向**: `(1, 3, 384, 384) → (1, 10)` shape 正确
5. **strict=False 容忍**: timm 版本升级时的 key 顺序小差异

### 2.2 用法

```powershell
$env:PY = "F:\anaconda\python.exe"
& $env:PY e:\truth-视觉实践\scripts\verify_model.py
```

环境变量 `MODEL_WEIGHTS` 可覆盖路径,默认 `models/checkpoints/best.pt`:

```powershell
$env:MODEL_WEIGHTS = "D:\backups\best_v2.pt"
& $env:PY e:\truth-视觉实践\scripts\verify_model.py
```

### 2.3 退出码

| Exit | 含义 |
|------|------|
| 0 | 验证通过,可重启后端 |
| 1 | 文件缺失 / 损坏 / 类别错 / 前向失败 |

---

## 3. 一键切换脚本 (`scripts/switch_to_real_model.ps1`)

> PowerShell 5.x 兼容,不依赖 bash 语法。

```powershell
$env:PY = "F:\anaconda\python.exe"
. e:\truth-视觉实践\scripts\switch_to_real_model.ps1
```

### 3.1 执行步骤

1. 定位 `$env:USERPROFILE\Downloads\*stage2*.zip`
2. 解压到 `models\checkpoints\_extracted\`
3. `Move-Item` 把 `best.pt` 移到目标位置（不覆盖,失败回滚)
4. 调 `verify_model.py`,失败立即退出
5. `Get-Process uvicorn | Stop-Process` 停掉旧进程
6. 启动新 `uvicorn` 带 `MODEL_WEIGHTS` 环境变量

### 3.2 失败诊断

| 现象 | 排查 |
|------|------|
| Move-Item operation not permitted | Trae AI 环境对 `E:\` 盘移动受限,改用手动复制 |
| verify_model.py 报 0 张量 | 权重文件不是 `timm` checkpoint,需要 `state["model"]` 提取 |
| uvicorn 启动后立即 500 | 查看 logs/app.log 确认 `model loaded from` 行 |

---

## 4. 回归测试 (`tests/test_real_model_e2e.py`)

### 4.1 测试用例

5 张 EuroSAT 训练集图,每张都来自其真实类别子目录:

| 路径 | 期望 | 最低置信度 |
|------|------|-----------|
| `AnnualCrop/AnnualCrop_1.jpg` | AnnualCrop | 0.50 |
| `Forest/Forest_1.jpg` | Forest | 0.50 |
| `Highway/Highway_1.jpg` | Highway | 0.50 |
| `River/River_1.jpg` | River | 0.50 |
| `SeaLake/SeaLake_1.jpg` | SeaLake | 0.50 |

### 4.2 关键检查

- `response["mock"] == false`: 后端必须返回真实模型
- `response["top1"]["label"] == expected`: 类别命中
- `response["top1"]["score"] >= 0.5`: 置信度阈值

> 为什么 0.5: 真实模型对训练集图一般 0.8+,mock 模式伪随机几乎不可能 5/5 全部 >= 0.5。  
> 这个阈值是"反降级"保险,而非"测精度"。

### 4.3 用法

```powershell
& $env:PY e:\truth-视觉实践\tests\test_real_model_e2e.py
```

### 4.4 失败含义

| 失败模式 | 含义 |
|---------|------|
| 某行 `mock=True` 或 `MOCK!` | 模型没加载,被 fallback |
| 5 张全错乱分类 | 权重与训练时类别映射不一致 |
| 1-2 张置信度低 | 单图异常,可接受;若全低则权重有问题 |

---

## 5. 后端加载机制

### 5.1 启动流程

```
uvicorn 启动
    └─→ @app.on_event("startup")
            ├─→ Base.metadata.create_all(bind=engine)  # 建表
            └─→ load_model()                            # 加载权重
                    ├─→ 检查 MODEL_WEIGHTS 路径
                    ├─→ timm.create_model("tf_efficientnetv2_m", num_classes=10)
                    ├─→ torch.load(...) 提取 state
                    └─→ model.load_state_dict(state, strict=False)
```

### 5.2 Fallback 策略

```python
# backend/api/classify.py
def load_model(weights_path=None):
    try:
        ...
    except Exception as e:
        log.warning("failed to load model: %s, fallback to mock", e)
        return  # _MODEL_LOADED 仍为 False
```

后续分类请求会走 mock 分支,响应里 `mock: true` 标识。

### 5.3 检查后端是否走真实模型

```bash
curl http://127.0.0.1:8000/api/classify -F "image=@test.jpg" -H "Authorization: Bearer ..."
# 看返回 JSON 中 "mock": true / false
```

或在浏览器 F12 Network 面板看响应体。

---

## 6. 常见切换失败

| 现象 | 原因 | 解决 |
|------|------|------|
| `FileNotFoundError: best.pt` | 路径不对 | 检查 `MODEL_WEIGHTS` 绝对路径 |
| `RuntimeError: Error(s) in loading state_dict` | 模型结构不匹配 | 确认 `timm.create_model("tf_efficientnetv2_m", num_classes=10)` |
| `KeyError: 'model'` | checkpoint 没有 `model` 子字典 | `state = state.get("model", state)` |
| 启动后 `mock: true` | 静默 fallback | 看 logs/app.log 找 warning |
| 推理返回 shape (1, 1000) | 用了 ImageNet 预训练 | 必须传 `num_classes=10` |

---

## 7. CI / 自动化建议

把 `tests/test_real_model_e2e.py` 接入 `scripts/quickstart.ps1` 的 `-SkipE2E $false` 流程:

```powershell
# quickstart.ps1 末尾追加
if (-not $SkipE2E) {
    & $env:PY tests/test_real_model_e2e.py
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "真实模型回归未通过,请检查 best.pt"
    }
}
```

---

> **核心原则**: 训练是离线的,推理是在线的。  
> 切换到真实模型,只是把"权重文件从 Kaggle 搬到本地",业务代码完全不变。  
> 任何"改 classify.py 才能用真实模型"的 hack,都是反模式。
