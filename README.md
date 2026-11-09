<div align="center">

# RSI-EdgeVision

### 基于 RDK X5 的遥感图像边缘智能识别终端

把双时相遥感变化检测，从云端 GPU 搬进一块 **4 GB 内存、无独立显卡** 的国产边缘板卡

[![F1](https://img.shields.io/badge/LEVIR--CD%20F1-0.8648-2ea043?style=flat-square)](#实验结果)
[![IoU](https://img.shields.io/badge/IoU-0.7617-2ea043?style=flat-square)](#实验结果)
[![Model](https://img.shields.io/badge/int8%20model-3.2%20MB-1f6feb?style=flat-square)](#模型与量化)
[![Latency](https://img.shields.io/badge/end--to--end-40.91%20ms-1f6feb?style=flat-square)](#实验结果)
[![Board](https://img.shields.io/badge/RDK%20X5-BPU-8957e5?style=flat-square)](https://developer.d-robotics.cc/)

</div>

---

## 项目简介

遥感变化检测是灾害评估、城市更新与国土监管的基础能力，但现有深度模型普遍依赖云端 GPU：单景影像百兆级，回传慢、排队不可控；灾区、山区、海上等现场断网即失效；遥感数据出域还存在合规风险。

本项目以自研轻量化网络 **REPB-Net** 为算法内核，打通 **PyTorch → ONNX → hb_mapper 量化 → RDK X5 BPU** 全链路，在板端实现「检测 → 指标评估 → 误差分析 → AI 语义解释 → 报告导出」的完整闭环，并针对板载 1024×600 触摸屏做了自适应交互。

**数据不出域，结果不过夜。**

---

## 核心亮点

| | 内容 |
|---|---|
| **算法** | REPB-Net：共享 MobileNetV2 编码器提取双时相特征；互易时相响应融合（RTRF）抑制光照阴影伪变化；多尺度侧监督细化桥（MSRB）与监督注意力解码（SAM）守住细长边界 |
| **量化** | 60 组真实样本校准替代随机校准，规避「量化后输出全 0」的塌陷；浮点 10.2 MB → int8 **3.2 MB**（约 −68%） |
| **板端** | `hbm_runtime` 一次加载常驻，双输入 NCHW int8，纯 BPU 推理 **8.65 ms**，端到端 **40.91 ms（24.4 FPS）** |
| **系统** | Flask Web 工作站，五模块（检测评估 / 误差分析 / 对话解析 / 时空孪生 / 风险预警），支持报告导出与设备温度·内存·CPU 实时监控 |
| **交互** | 1024×600 IPS 触摸屏自适应布局，暗色仪表盘，无需外接显示器 |

---

## 模型与量化

| 项目 | 数值 |
|---|---|
| 浮点权重 `best_model.pth` | 10.2 MB / 2,477,892 参数 |
| 量化模型 `repbnet_cd.bin` | **3,279,032 字节（约 3.2 MB）** |
| 输入 | 双输入 `x1`（后时相 B 的 RGB）、`x2`（前时相 A 的 RGB），各 1×3×256×256 |
| 输出 | 单通道 256×256 变化概率图 |
| 编译目标 | `march=bayes-e`，ONNX opset **11** |
| 量化配置 | `calibration_type: default`，`preprocess_on: False`，`cal_data_type: "float32; float32"` |

> **预处理必须四处一致**（训练 / ONNX 导出 / 量化校准 / 板端推理）：
> `cv2 读 BGR → 拼 6 通道 → /255 → 减均值 → 除标准差 → 通道反转(BGR→RGB) → HWC→CHW`
> 均值 `[0.406,0.456,0.485]`（重复两遍，BGR 顺序），标准差 `[0.225,0.224,0.229]`（重复两遍）。
> 有一处不一致，结果就会崩。

---

## 目录结构

```
.
├── deploy/                     # 板端系统（整体拷到 RDK X5 的 ~/deploy）
│   ├── webapp.py               # Flask Web 工作站（主入口）
│   ├── infer.py                # hbm_runtime 推理封装 + 预处理 + 统计
│   ├── app.py                  # Tkinter 桌面版（备用界面）
│   ├── explain.py              # 通义千问 qwen-vl-max 语义解释
│   ├── report.py               # 单文件 HTML 评估报告生成
│   ├── batch_eval.py           # 批量评估，输出逐样本 CSV
│   ├── bench.py                # 性能测试（延迟分解 / 长稳 / 量化权衡）
│   ├── rdx_infer.py            # 单对图片命令行推理
│   ├── repbnet_cd.bin          # int8 量化模型（3.2 MB）
│   ├── demo/                   # 演示样本 A/B/label
│   ├── test/                   # 测试图
│   ├── static/                 # 前端 JS / CSS
│   └── templates/              # 前端 HTML
│
├── scripts/                    # PC / 虚拟机侧：训练产物转换与量化
│   ├── LEVIR_caijian_256.py    # 数据集切分 256×256
│   ├── export_onnx.py          # PyTorch → ONNX（opset 11）
│   ├── make_cal_data.py        # 生成真实校准数据（60 组，每组 786432 字节）
│   ├── config_real.yaml        # hb_mapper 量化配置
│   ├── float_eval.py           # 浮点全量评估 + CPU 耗时对照
│   ├── rdx_infer.py            # 板端推理脚本副本
│   ├── test_qwen_vl.py         # API 连通性自检
│   └── qwen_api.example.json   # API 配置模板
│
├── 参赛资料/                    # 技术报告、图表、商业计划书
├── 报告源文件/                  # 报告的 HTML 源文件与构建脚本
└── 技术路线图/                  # 技术路线图 PPTX 与预览图
```

---

## 环境

**硬件**

- RDK X5（4 GB 内存，无独立 GPU，BPU 定点算力）
- 板载 1024×600 IPS 触摸屏（可选，不接也能跑）

**板端软件**

- Ubuntu 22.04 + D-Robotics 官方镜像（自带 `hbm_runtime`）
- Python 3.10
- `numpy`、`opencv-python`、`flask`、`pillow`、`requests`

**PC / 虚拟机侧（仅量化时需要）**

- Docker + `openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8-py310`
- Python 3.10 + `torch` / `onnx` / `onnxscript` / `opencv-python` / `numpy<2`

---

## 快速开始（板端）

```bash
# 1. 依赖（镜像一般已自带 numpy/opencv，缺什么装什么）
sudo apt install -y python3-tk python3-pil.imagetk
/usr/bin/python3 -m pip install --user flask requests pillow

# 2. 把 deploy/ 整个拷到板子的 ~/deploy，确认模型在
ls -lh ~/deploy/repbnet_cd.bin

# 3. 启动
cd ~/deploy
/usr/bin/python3 webapp.py

# 4. 浏览器打开
#    http://<板子IP>:5000
```

若未检测到 `hbm_runtime`，`infer.py` 会自动进入 **模拟推理** 模式（只会用像素差凑数，仅用于调界面，结果不可用），页面顶部会有红色告警条。

---

## 量化复现（PC / 虚拟机）

```bash
# 1. 切分数据集（输出 256×256，train/val/test 各含 A/B/label）
python3 scripts/LEVIR_caijian_256.py

# 2. 导出 ONNX（固定输入轴、双输入 x1/x2、opset 11）
python3 scripts/export_onnx.py

# 3. 生成真实校准数据（60 组，每组两个 .bin，各 786432 字节）
python3 scripts/make_cal_data.py

# 4. 量化（目录按自己的路径改）
docker run --rm \
  -v /path/to/project:/data \
  -v /path/to/quant:/quant \
  openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8-py310 \
  hb_mapper makertbin --model-type onnx --config /quant/config_real.yaml
```

看到 `Convert to runtime bin file successfully!` 即为成功，产物约 3.2 MB。

> **踩过的坑**
> - opset 用 17 会报 `No Adapter To Version 17 for Resize` → 改回 **11**
> - `calibration_type: skip` 用随机数据校准 → 板端输出全 0 → 必须用 **default + 真实数据**
> - 双输入模型的 `cal_data_type` 必须写两个值，分号分隔，少一个就报 `Wrong cal_data_type num given`

---

## 命令行工具

| 命令 | 作用 |
|---|---|
| `python3 deploy/batch_eval.py --data demo --limit 50` | 批量评估，输出逐样本 `eval_results.csv` |
| `python3 deploy/bench.py --quick` | 延迟分解（预处理 / BPU / 后处理） |
| `python3 deploy/bench.py --duration 300` | 300 秒长稳测试 |
| `python3 deploy/report.py --data demo --eval eval_results.csv` | 生成单文件 HTML 报告 |
| `python3 deploy/rdx_infer.py --bin repbnet_cd.bin --pre A.png --post B.png` | 单对图片推理，输出掩码 |
| `python3 scripts/float_eval.py --limit 20` | 浮点模型评估 + CPU 耗时（VP 侧） |

**AI 语义解释**：把 `scripts/qwen_api.example.json` 复制为 `qwen_api.json`，填入 `api_key` 即可。该文件已被 `.gitignore` 排除。

---

## 实验结果

**精度（LEVIR-CD，全量 2048 对，像素级累计）**

| 指标 | 数值 |
|---|---|
| Precision | 0.8782 |
| Recall | 0.8517 |
| **F1** | **0.8648** |
| IoU（变化类） | 0.7617 |

**UAV 数据集**：F1 0.7752 / IoU 0.6329

**板端性能（RDK X5，100 帧，预热 10 帧，取中位数）**

| 阶段 | 中位耗时 | 占比 |
|---|---|---|
| 预处理 | 27.15 ms | 66.4% |
| BPU 推理 | **8.65 ms** | 21.1% |
| 后处理 | 5.11 ms | 12.5% |
| **端到端** | **40.91 ms（24.4 FPS）** | 100% |

**300 秒连续运行**：吞吐 27.9 FPS 无衰减，温度 51.25 → 52.48 ℃，CPU 均值 12.4%，无降频。

> 口径说明：长稳测试只统计「预处理 + BPU 推理」两段（不含后处理），因此 27.9 FPS 与端到端的 24.4 FPS 不同口径。

---

## 已知限制

- **整机功耗尚未测量**，已列为后续标准测试项。
- 部署权重为**量化友好剪裁版**：共享编码器 + 相加融合 + 分层解码 + 四尺度深监督；RTRF 与 MSRB 属于算法设计方案，未进入本 `.bin`（其算子在 BPU 上支持度差、量化误差会被放大）。
- IoU 0.7617 为**变化类 IoU**，非二分类平均 mIoU。
- 长稳测试使用同一对图像循环，尚未覆盖真实摄像头取流场景。

---

## 致谢

- 数据集：[LEVIR-CD](https://justchenhao.github.io/LEVIR/)
- 硬件与工具链：[D-Robotics RDK X5](https://developer.d-robotics.cc/) / `hb_mapper`
- 语义解释：阿里云百炼 `qwen-vl-max`

---

<div align="center">

本项目为参赛作品，未声明开源许可。如需引用或复用，请联系作者。

</div>
