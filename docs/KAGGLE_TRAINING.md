# Kaggle 训练流程（详细版）

> 解决"本地没 GPU 怎么训 EfficientNetV2-M"的问题：  
> 利用 Kaggle 免费 GPU T4 x2 跑训练,产出 `best.pt` 后下载到本地后端。

---

## 为什么选 Kaggle

| 维度 | Kaggle 免费版 | 本地 (RTX 3060) | Colab 免费 |
|------|--------------|-----------------|-----------|
| GPU | T4 x2 (15GB) | 12GB | T4 (15GB) |
| 时长 | 9h/次 | 不限 | 12h 断线 |
| 数据 | `/kaggle/input` 直挂 | 本地 | Drive 慢 |
| 网络 | 需手动开启 | 全开 | 全开 |
| 推荐 | ✅ 主推 | 中等规模 | 小实验 |

EuroSAT 训练（10 类, 27000 图, 384×384）Kaggle 跑完两阶段约 1-2 小时。

---

## 0. 准备 Kaggle API Token

1. 打开 [kaggle.com/settings](https://www.kaggle.com/settings) → 「API」 → 「Create New Token」
2. 下载 `kaggle.json` (含 `username` + `key`)
3. 放到本地：
   ```
   Windows: C:\Users\<用户名>\.kaggle\kaggle.json
   Linux:   ~/.kaggle/kaggle.json
   ```
4. 验证：
   ```powershell
   $env:PY = "F:\anaconda\python.exe"
   & $env:PY -m pip install kaggle
   & $env:PY -c "import kaggle; print(kaggle.api.get_config_value('username'))"
   ```

---

## 1. 上传 EuroSAT 到 Kaggle Datasets

### 1.1 一次性打包（避免 1000 文件限制）

```powershell
$env:PY = "F:\anaconda\python.exe"
Compress-Archive -Path "e:\truth-视觉实践\data\eurosat\*" `
                 -DestinationPath "e:\truth-视觉实践\data\eurosat.zip" `
                 -CompressionLevel Optimal
```

> 产物 `eurosat.zip` 约 88 MB,远低于 Kaggle 单数据集 1GB 限制。

### 1.2 用 `upload_to_kaggle.py` 一键上传

```powershell
# 预览
& $env:PY e:\truth-视觉实践\scripts\upload_to_kaggle.py --dry-run

# 实际推送
& $env:PY e:\truth-视觉实践\scripts\upload_to_kaggle.py --yes
```

脚本完成：登录 → 创建 dataset `zhier1/eurosat-10-class-sentinel-2` → 上传 zip → 输出 dataset URL。

### 1.3 手动上传备选（若脚本失败）

`kaggle.com/datasets` → 「New Dataset」 → 拖入 `eurosat.zip` → 标题 `eurosat-10-class-sentinel-2` → Create。

---

## 2. 配置 Kaggle Notebook

### 2.1 创建 Notebook

1. `kaggle.com/code` → 「New Notebook」
2. 顶部 **Settings**：
   - **Accelerator** → 选 **GPU T4 x2**（需先在 [Account](https://www.kaggle.com/settings) 验证手机号才能选 GPU）
   - **Internet** → **ON**（要 `pip install` 与 `git clone`）
3. 右侧 **Add Data** → 搜 `eurosat-10-class-sentinel-2` → Add

### 2.2 克隆项目代码

```python
# Cell 1
!git clone https://github.com/zhier0707/Satellite-Imagery-Analysis.git
%cd Satellite-Imagery-Analysis
!pip install -q timm matplotlib opencv-python tensorboard
```

### 2.3 训练脚本

> 完整脚本见 `scripts/kaggle_train.py`，逻辑与本地 `src/train.py` 一致，  
> 仅修改：数据根目录 `/kaggle/input/eurosat-10-class-sentinel-2/...` 与产物目录 `/kaggle/working/`。

```python
# Cell 2: 训练
!python scripts/kaggle_train.py \
    --data-root /kaggle/input/eurosat-10-class-sentinel-2/eurosat \
    --stage 1 --epochs 3 --tag stage1_baseline
```

### 2.4 Stage 2（解冻更多层）

```python
# Cell 3
!python scripts/kaggle_train.py \
    --data-root /kaggle/input/eurosat-10-class-sentinel-2/eurosat \
    --resume-from /kaggle/working/stage1_baseline/last.pt \
    --stage 2 --epochs 10 --tag stage2_finetune
```

### 2.5 打包产物

```python
# Cell 4
!zip -r stage2_best.zip /kaggle/working/stage2_finetune/
```

---

## 3. 下载权重到本地

### 3.1 Notebook 内下载（限速 50KB/s，不推荐）

```python
from IPython.display import FileLink
FileLink(r'/kaggle/working/stage2_best.zip')
```

### 3.2 浏览器下载（推荐，10MB/s+）

1. 右侧 **Output** 面板 → 找到 `stage2_best.zip` → 三点菜单 → Download
2. 保存到 `C:\Users\<用户名>\Downloads\`

### 3.3 Kaggle CLI（中等速度）

```powershell
& $env:PY -m kaggle kernels output <username>/<notebook-slug> -p e:\truth-视觉实践\models\checkpoints
```

### 3.4 加速技巧

- 关掉 VPN / 代理
- 用 Cloudflare WARP：`warp-cli mode warp`
- 浏览器下载通常比 CLI 快 5-10x

---

## 4. 本地接入（关键步骤）

### 4.1 解压并放置

```powershell
$zip = "$env:USERPROFILE\Downloads\stage2_best.zip"
Expand-Archive -Path $zip -DestinationPath "e:\truth-视觉实践\models\checkpoints\_extracted" -Force
Move-Item "e:\truth-视觉实践\models\checkpoints\_extracted\best.pt" `
         "e:\truth-视觉实践\models\checkpoints\best.pt" -Force
```

### 4.2 验证完整性

```powershell
& $env:PY e:\truth-视觉实践\scripts\verify_model.py
```

预期输出：
```
[OK] state_dict 包含 1120 张量,共 53.2M 参数
[OK] num_classes = 10 (期望 10)
[SUCCESS] best.pt 验证通过!
```

### 4.3 跑回归测试

```powershell
& $env:PY e:\truth-视觉实践\tests\test_real_model_e2e.py
```

预期：5/5 PASS,所有 `mock=False`。

---

## 5. 常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| **选不了 GPU** | 手机号未验证 | kaggle.com/settings → Phone → 验证 |
| **NotFoundError removeChild** | 浏览器扩展冲突 | 关 AdBlock / 用无痕模式 |
| **Max files exceeded 27001/1000** | 直接上传散图 | 先 `Compress-Archive` 打包 |
| **下载 50KB/s 卡死** | CLI 限速 | 用浏览器 Output 面板下载 |
| **数据路径错误** | dataset slug 与代码不一致 | 改 `CONFIG["data_root"]` 为实际挂载路径 |
| **训练中断** | 9 小时限制 | 分 2 个 notebook 跑 stage1 / stage2 |

---

## 6. 完整命令速查

```powershell
# === 本地一次性准备 ===
$env:PY = "F:\anaconda\python.exe"
Compress-Archive -Path "e:\truth-视觉实践\data\eurosat\*" -DestinationPath "e:\truth-视觉实践\data\eurosat.zip"
& $env:PY e:\truth-视觉实践\scripts\upload_to_kaggle.py --yes

# === Kaggle Notebook 内 ===
!git clone https://github.com/zhier0707/Satellite-Imagery-Analysis.git
%cd Satellite-Imagery-Analysis && !pip install -q timm opencv-python
!python scripts/kaggle_train.py --data-root /kaggle/input/eurosat-10-class-sentinel-2/eurosat --stage 1 --epochs 3 --tag stage1_baseline
!python scripts/kaggle_train.py --resume-from /kaggle/working/stage1_baseline/last.pt --data-root /kaggle/input/eurosat-10-class-sentinel-2/eurosat --stage 2 --epochs 10 --tag stage2_finetune
!zip -r stage2_best.zip /kaggle/working/stage2_finetune/

# === 下载到本地后 ===
Expand-Archive "$env:USERPROFILE\Downloads\stage2_best.zip" -DestinationPath "e:\truth-视觉实践\models\checkpoints\_extracted" -Force
Move-Item "e:\truth-视觉实践\models\checkpoints\_extracted\best.pt" "e:\truth-视觉实践\models\checkpoints\best.pt" -Force
& $env:PY e:\truth-视觉实践\scripts\verify_model.py
& $env:PY e:\truth-视觉实践\tests\test_real_model_e2e.py
```

---

> **核心原则**：训练在云端,推理在本地。  
> 本地永远只放 `best.pt`（最终权重），中间 `last.pt` / `stage1_*.pt` 都留在 Kaggle Output 备份。
