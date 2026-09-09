# 环境配置指南

> **何时读**：`scripts/check_environment.py` 返回 `needs_setup` 或 `partial` 时，按缺失项对照本指南补配。已通过的项目不用重复配置。

## 1. Python 运行时（python-runtime，必需）

- 用途：全部比对主流程、配置与知识库装载、Excel 人工核对产物、遗留文档格式转换、性能监控
- 支持版本：≥ 3.8（实测至 3.13）
- 官方主页：https://www.python.org/
- 官方文档：https://docs.python.org/3/
- 下载地址：https://www.python.org/downloads/
- 登录网址：不需要
- 配置步骤：
  1. 访问 python.org/downloads 下载对应系统安装包；
  2. 安装时勾选 Add to PATH（Windows）；
  3. 终端运行 `python3 --version` 确认 ≥ 3.8。
- 验证方式：`python3 --version` 输出 ≥ 3.8
- 缺失处理：主流程停止，无可靠降级
- 核验日期：2026-09-08（适用 3.8—3.14）

## 2. pip 依赖

一键安装（推荐）：

```bash
pip install pyyaml pandas openpyxl python-docx pdfplumber psutil
```

### pyyaml（必需）

- 用途：配置与知识库装载（config.yaml、knowledge_base/*.yaml）
- 官方主页：https://pyyaml.org/
- 官方文档：https://pyyaml.org/wiki/PyYAMLDocumentation
- 配置步骤：`pip install pyyaml`
- 验证方式：`python3 -c "import yaml; print(yaml.__version__)"`
- 缺失降级：主流程停止，无可靠降级；`pip install pyyaml` 恢复

### pandas（必需）

- 用途：Excel 人工核对产物生成、值域比对数据组织
- 官方主页：https://pandas.pydata.org/
- 官方文档：https://pandas.pydata.org/docs/
- 配置步骤：`pip install pandas`
- 验证方式：`python3 -c "import pandas; print(pandas.__version__)"`
- 缺失降级：跳过 Excel 生成，仅产出 HTML/MD 报告；人工核对由模型按报告输出映射清单。`pip install pandas openpyxl` 恢复。

### openpyxl（必需）

- 用途：可编辑 Excel 生成（模式四下拉框核对）
- 官方主页：https://openpyxl.readthedocs.io/
- 官方文档：https://openpyxl.readthedocs.io/en/stable/
- 配置步骤：`pip install openpyxl`
- 验证方式：`python3 -c "import openpyxl; print(openpyxl.__version__)"`
- 缺失降级：同 pandas

### python-docx（可选）

- 用途：遗留兼容路径——直接输入 .docx 时转 MD
- 官方主页：https://python-docx.readthedocs.io/
- 官方文档：https://python-docx.readthedocs.io/en/latest/
- 配置步骤：`pip install python-docx`
- 验证方式：`python3 -c "import docx"`
- 缺失降级：主路径（模型按 doc_parse_spec.md 产出规范化 MD）不依赖本包

### pdfplumber（可选）

- 用途：遗留兼容路径——直接输入 .pdf 时转 MD
- 官方主页：https://github.com/jsvine/pdfplumber
- 官方文档：https://github.com/jsvine/pdfplumber#readme
- 配置步骤：`pip install pdfplumber`
- 验证方式：`python3 -c "import pdfplumber"`
- 缺失降级：PDF 由模型直接阅读产出规范化 MD；扫描版需先 OCR

### psutil（可选）

- 用途：性能监控（utils/performance_monitor.py）
- 官方主页：https://github.com/giampaolo/psutil
- 官方文档：https://psutil.readthedocs.io/
- 配置步骤：`pip install psutil`
- 验证方式：`python3 -c "import psutil"`
- 缺失降级：静默跳过，不影响比对结果

## 3. 环境变量（全部可选；不设置时用 config.yaml 默认值）

| 变量 | 用途 | 示例值 | 验证方式 |
|---|---|---|---|
| `DATA_STD_OUTPUT` | 任务产物输出根目录 | `~/data-model-compare-docs` | 运行比对后检查该目录下是否生成 `<任务名>/reports/` |
| `DATA_STD_V5_PATHS` | 5.X 标准目录（冒号分隔），版本检测用 | `~/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/02 标准规范/库表接入规范` | 检测 v5 目录下文件路径应返回 v5 |
| `DATA_STD_V6_PATHS` | 6.0 标准目录（冒号分隔），版本检测用 | `~/winning/tfs2018/RDA-01-标准规范/03 V6.0/01 产品文档/01 标准规范` | 检测 v6 目录下文件路径应返回 v6 |
| `DATA_STD_E2E_TEST_DOCS` | e2e 测试文档（冒号分隔：前半源、后半目标） | `源1.docx:源2.xlsx:目标1.docx` | 未设置时 e2e_tests 自动跳过真实文档用例（正常） |

macOS/Linux 写入 shell 配置（`~/.zshrc`）示例：

```bash
export DATA_STD_OUTPUT="$HOME/data-model-compare-docs"
export DATA_STD_V5_PATHS="$HOME/winning/tfs2018/RDA-01-标准规范/02 V5.5/01 产品文档/02 标准规范/库表接入规范"
export DATA_STD_V6_PATHS="$HOME/winning/tfs2018/RDA-01-标准规范/03 V6.0/01 产品文档/01 标准规范"
```

> 注意：路径含空格/中文时整体加引号；多个目录用半角冒号 `:` 分隔。

## 4. 无登录/凭据/网络依赖

本 Skill 为纯本地工具：不联网、不需要账号、不存储凭据、无轮换/撤销项。知识库（`knowledge_base/`）随包携带、本地读写。所有 pip 依赖仅从 PyPI 官方源安装。

## 5. 验证

配置完成后重跑：

```bash
python3 <skill_root>/scripts/check_environment.py
```

期望输出 `ready`（或 `partial`，仅当有意不装可选项）。
