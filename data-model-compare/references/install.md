# 依赖安装

> 本文件说明本 Skill 的 Python 依赖。**解析阶段由模型按
> [doc_parse_spec.md](doc_parse_spec.md) 产出规范化 MD，不依赖任何文档解析程序**；
> 下列依赖仅供比对主流程与遗留兼容路径使用。

## 安装依赖

```bash
# 主流程必需（配置装载 / Excel 生成 / 值域比对）
pip install pyyaml pandas openpyxl

# 遗留兼容路径（直接喂 docx/xlsx/pdf 原始文档时才需要，主路径不需要）
pip install python-docx pdfplumber

# 性能监控（utils/performance_monitor.py 使用）
pip install psutil
```

一键安装：

```bash
pip install pyyaml pandas openpyxl python-docx pdfplumber psutil
```

## 说明

- **主路径（规范化 MD）**：只需 `pyyaml`（config/知识库装载）、`pandas` + `openpyxl`（生成可编辑 Excel）、无文档解析依赖。
- **遗留兼容路径**：`parsers/converter.py` 直接转换 docx/xlsx/pdf 时才需要 `python-docx`（Word）、`pdfplumber`（PDF）。
- **PDF 已无专用解析器**：旧文档提到的 marker-pdf / pymupdf4llm 均未在代码中使用；PDF 建议由模型按解析说明直接阅读产出规范化 MD（见 SKILL.md FAQ Q1）。
- `.doc` 不可用：macOS 下转换必丢表格，须先另存为 `.docx`。
