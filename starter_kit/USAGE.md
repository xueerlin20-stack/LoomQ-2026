# LoomQ 使用说明

以下命令均在仓库根目录 `/Users/bangbang/Documents/LoomQ-2026` 执行。

## 安装依赖

```bash
python3 -m pip install -r starter_kit/requirements.txt
```

## 运行单个线路

```bash
python3 starter_kit/adapter.py starter_kit/circuits/bell.qasm \
  --target braket \
  --shots 1024 \
  --output starter_kit/evidence/files
```

`--target` 可选：

- `spinq`
- `originq`
- `braket`

程序会打印 counts，并保存：

```text
starter_kit/evidence/files/braket-local-circuit.qasm
starter_kit/evidence/files/braket-local-result.json
```

## 批量运行 circuits 目录

把目录作为输入即可运行该目录中的全部 `.qasm` 文件：

```bash
python3 starter_kit/adapter.py starter_kit/circuits \
  --target braket \
  --shots 1024 \
  --output starter_kit/evidence/files
```

批量结果按线路名分目录保存：

```text
starter_kit/evidence/files/
├── bell/
│   ├── braket-local-circuit.qasm
│   └── braket-local-result.json
└── ghz3/
    ├── braket-local-circuit.qasm
    └── braket-local-result.json
```

## 在 Python 中运行并保存

```python
from pathlib import Path
from starter_kit.adapter import run_and_save

qasm = Path("starter_kit/circuits/bell.qasm").read_text(encoding="utf-8")
result = run_and_save(qasm, "braket", 1024, "starter_kit/evidence/files")

print(result["counts"])
print(result["meta"]["artifact_files"])
```

只运行、不保存时使用：

```python
from starter_kit.adapter import run

result = run(qasm, "braket", 1024)
```

## 真机运行

真机 CLI 增加 `--real`。SpinQ 私钥和 OriginQ Token 放在本地目录：

```text
starter_kit/qasm_L1/credentials/
├── spinq_private_key.pem.example
└── originq_token.txt.example
```

首次使用时复制模板，并把占位内容替换为真实凭据：

```bash
cp starter_kit/qasm_L1/credentials/spinq_private_key.pem.example \
  starter_kit/qasm_L1/credentials/spinq_private_key.pem
cp starter_kit/qasm_L1/credentials/originq_token.txt.example \
  starter_kit/qasm_L1/credentials/originq_token.txt
```

真实的 `spinq_private_key.pem` 和 `originq_token.txt` 已被该目录的
`.gitignore` 忽略，不会被 Git 收集。

### SpinQ Cloud

```bash
export SPINQ_USERNAME="your-user"
export SPINQ_PLATFORM="triangulum_vp"

python3 starter_kit/adapter.py starter_kit/circuits/bell.qasm \
  --target spinq --shots 100 --real \
  --output starter_kit/evidence/files
```

### AWS Braket QPU

AWS 凭证仍由 boto3 标准配置读取：

```bash
export BRAKET_DEVICE_ARN="arn:aws:braket:REGION::device/qpu/PROVIDER/DEVICE"

python3 starter_kit/adapter.py starter_kit/circuits/bell.qasm \
  --target braket --shots 100 --real \
  --output starter_kit/evidence/files
```

### OriginQ 悟空

```bash
python3 starter_kit/adapter.py starter_kit/circuits/bell.qasm \
  --target originq --shots 100 --real \
  --output starter_kit/evidence/files
```

目录批量模式同样支持 `--real`，但会为目录中的每个线路提交一个真机任务，可能消耗
多份额度或产生多笔费用。建议先用单个 Bell 线路和较低 shots 验证。

也可以在 Python 中使用 `run_real()`，并通过 `evidence_directory` 自动保存比赛证据：

```python
from pathlib import Path
from starter_kit.adapter import run_real

result = run_real(
    qasm,
    "originq",
    100,
    token=Path("starter_kit/qasm_L1/credentials/originq_token.txt")
        .read_text(encoding="utf-8").strip(),
    evidence_directory="starter_kit/evidence/files",
)
```

不要把真实 Token 或 SpinQ 私钥提交到 Git 仓库。
