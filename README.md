# learn-agent — 编程学习与开发 Agent

基于**本地大模型**（Ollama / Qwen3）+ **网络数据检索** + 可选**外部大模型 API 增强**的编程学习助手。

核心能力：
- **学语言**：Python / JavaScript / Java 课程化学习，教程自动沉淀进知识库（学习即训练）
- **刷算法**：内置 12 道力扣经典题（带可运行测试），解题走完整质量工作流并自动判题、查内存泄漏
- **做开发**：FastAPI / Flask / Express + 前端脚手架一键生成，生成即体检
- **函数调用**：LLM function-calling 工具循环（联网搜索 / 运行代码 / 检索知识库 / 代码体检）
- **质量工作流**：`思考 → 计划 → 审查 →（不过→回思考）→ 开发 → 代码审查 → 测试 →（不过→回思考）→ 完成`，最多 3 轮循环；连续失败自动升级模型（外部 API 或深度模型+思考模式）
- **训练体系**：数据蒸馏 → 知识库 TF-IDF 训练（带命中率指标）→ 定制本地模型 `learn-agent`（`ollama create`）→ 可选真·LoRA 微调脚本（RTX 4070 可跑）

## 目录结构

```
D:\learn-agent\
├── main.py                 # CLI 入口（chat/learn/quiz/solve/task/dev/ask/tools/kb/train/serve）
├── config.yaml             # 模型、工作流、测试参数；外部 API Key 填这里
├── core/
│   ├── llm.py              # LLM 路由：本地 qwen3:8b/14b + 外部 OpenAI 兼容接口 + 自动降级
│   ├── workflow.py         # 思考→计划→审查→开发→测试 状态机（全程落盘可追溯）
│   ├── knowledge.py        # 知识库：纯 Python TF-IDF 检索，train() 即训练
│   ├── codecheck.py        # 语法检查 / 泄漏启发式 / 子进程测试 / tracemalloc 泄漏检测
│   └── websearch.py        # DuckDuckGo + Bing 双通道网络检索
├── modules/
│   ├── learning.py         # 课程大纲 + 教程生成 + 测验 + 函数速查表
│   ├── leetcode.py         # 内置题库 + 判题器 + 解题工作流
│   └── devkit.py           # 工具注册表(function-calling) + 前后端脚手架
├── training/
│   ├── distill.py          # SFT 数据蒸馏（教学对/题解对/代码审查对）
│   ├── train_knowledge.py  # 知识库训练：种子知识 + 蒸馏语料 → 索引 → 命中率评估
│   ├── make_ollama_model.py# 生成 Modelfile 并 ollama create learn-agent
│   ├── finetune_lora.py    # 可选：QLoRA 真微调（需另装 torch/peft，见文件头注释）
│   └── run_training.py     # 一键训练
├── webapp/                 # Web 控制台（Flask + 原生前端）
├── gui/app.py              # 桌面图形应用（Tkinter 深色主题，五页签）
├── learn-agent-gui.bat     # 桌面应用双击启动器
├── tests/test_all.py       # 单元测试 + 集成测试
└── data/                   # knowledge(索引) datasets(蒸馏语料) outputs(任务产物)
```

## 快速开始

```bash
cd D:\learn-agent
:: 桌面图形应用（推荐，双击 learn-agent-gui.bat 亦可）
python main.py gui

:: 训练（蒸馏数据 -> 知识库 -> 生成本地定制模型 learn-agent）
python main.py train --topics 5

:: 对话（默认用训练出的 learn-agent 模型）
python main.py chat

:: 学一个主题（教程 + 沉淀知识库）
python main.py learn python 装饰器
python main.py learn javascript Promise
python main.py quiz python 生成器

:: 解力扣题（完整工作流 + 自动判题）
python main.py problems
python main.py solve two-sum

:: 通用开发任务
python main.py task "用Python实现一个线程安全的有界缓存并附测试"

:: 生成前后端项目（FastAPI + 原生前端，生成即体检）
python main.py dev my-app --stack fastapi

:: function-calling 工具循环
python main.py tools "搜一下 FastAPI 最新版本特性并总结"

:: Web 控制台
python main.py serve        # http://127.0.0.1:7860
```

## 启用外部大模型增强

编辑 `config.yaml`：

```yaml
external_model:
  enabled: true
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1   # 或 https://api.deepseek.com/v1
  api_key: "sk-你的KEY"
  model: qwen-plus
```

启用后：① 复杂审查与蒸馏自动走外部强模型；② 工作流连续失败 2 次自动升级到外部模型再审。

## 图形界面（两种）

| 入口 | 说明 |
|---|---|
| `python main.py gui`（或双击 `learn-agent-gui.bat`） | **桌面应用**（Tkinter，零额外依赖）：对话（流式输出）/ 语言学习 / 力扣刷题（选题解题+判题）/ 开发任务（实时工作流日志）/ 训练（含报告展示） |
| `python main.py serve` → http://127.0.0.1:7860 | **浏览器控制台**（Flask）：同样的五大功能 |

两者均后台线程执行耗时操作，界面不卡顿；桌面版流式对话逐字显示。

## 工作流说明

每个任务在 `data/outputs/<kind>/<task_id>/` 留下完整过程：
`roundN_1_think.md → roundN_2_plan.json → roundN_3_plan_review.json → code/ → roundN_5_code_review.json → roundN_6_test_report.json → summary.md`

质量门：
1. **计划审查**：LLM 严苛评审，high 严重度问题打回思考阶段重来
2. **代码审查**：静态检查（语法/泄漏模式/危险用法）+ LLM 评审双保险
3. **测试**：子进程带超时运行（死循环自动拦截）+ tracemalloc 重复调用堆增长检测（内存泄漏）+ 力扣内置用例判题

## 训练体系（三层）

| 层级 | 做法 | 产物 |
|---|---|---|
| 数据蒸馏 | 强模型生成 教学/题解/审查 SFT 语料 | `data/datasets/sft_distilled.jsonl` |
| 知识库训练 | 种子知识+蒸馏语料 → TF-IDF 索引重建 + 命中率评估 | `data/knowledge/index.json` |
| 本地模型定制 | 知识精华注入 SYSTEM → `ollama create learn-agent` | 本地命令 `ollama run learn-agent` |
| 真·微调(可选) | QLoRA 微调 Qwen3-1.7B/4B（依赖见 `finetune_lora.py` 头注释） | `models/lora-*/adapter` |

日常"学习"也在训练：`python main.py learn ...` 每学一个主题都会把教程沉淀进知识库并重建索引。

## 测试

```bash
python -m unittest discover tests -v     # 单元测试（无需大模型在线）
```

## 环境要求

- Python 3.11+，`pip install requests flask pyyaml`
- Ollama + `qwen3:8b` / `qwen3:14b`（NVIDIA GPU 建议 ≥12GB 显存）
- 可选：Node.js（JS 语法检查）、外部 LLM API Key（增强）
