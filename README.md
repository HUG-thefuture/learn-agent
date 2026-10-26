# learn-agent — 编程学习与开发 Agent

[![CI](https://github.com/HUG-thefuture/learn-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/HUG-thefuture/learn-agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

基于**本地大模型**（Ollama / Qwen3）+ **网络数据检索** + 可选**外部大模型 API 增强**的编程学习助手。

核心能力：
- **七门语言、零基础到进阶**：Python / JavaScript / Java / C++ / Go / SQL / HTML-CSS 前端，
  每门按 **L0 零基础 → L1 核心 → L2 进阶 → L3 工程 → L4 后端(实战) → L5 前端协同 → L6 算法** 分阶段课程
- **引导式学习**：`start` 自动从第一课推进（学习即记录进度），`path` 随时查看路径与完成度，
  `review` 生成阶段复习（知识地图+综合练习），`quiz` 随堂测验
- **进阶实战（学以致用）**：`capstone` 让 Agent 用你已学的知识**自主完成**真实项目并走完整质量工作流——
  Python 个人博客系统(FastAPI+SQLite+前端)、JS 待办全栈应用(Express)、Java 成绩管理、C++ 日志分析器、
  Go 短链接服务、SQL 电商库表与报表、HTML/CSS 响应式个人主页
- **刷算法**：内置 20 道力扣经典题（带可运行测试），解题走完整质量工作流并自动判题、查内存泄漏
- **做开发**：FastAPI / Flask / Express + 前端脚手架一键生成，生成即体检
- **函数调用**：LLM function-calling 工具循环（联网搜索 / 运行代码 / 检索知识库 / 代码体检 / **MySQL 数据库操作**）
- **本地数据库**：直连本机 MySQL/MariaDB（凭据在 `config.yaml` 的 `database` 段，见下方[配置说明](#快速开始)），CLI `db` 命令、GUI 数据库页签、
  AI 工具 `mysql_query`/`mysql_schema` 三种方式操作真实库
- **质量工作流**：`思考 → 计划 → 审查 →（不过→回思考）→ 开发 → 代码审查 → 测试 →（不过→回思考）→ 完成`，最多 3 轮循环；连续失败自动升级模型（外部 API 或深度模型+思考模式）
- **训练体系**：数据蒸馏 → 知识库 TF-IDF 训练（带命中率指标）→ 定制本地模型 `learn-agent`（`ollama create`）→ 可选真·LoRA 微调脚本（RTX 4070 可跑）

## 目录结构

```
D:\learn-agent\
├── main.py                 # CLI 入口（chat/learn/quiz/solve/task/dev/ask/tools/kb/train/serve）
├── config.example.yaml     # 配置模板（入库）；复制为 config.yaml 填本机凭据（不入库）
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
├── gui/app.py              # 桌面图形应用（Tkinter 深色主题，六页签）
├── learn-agent-gui.bat     # 桌面应用双击启动器
├── tests/test_all.py       # 单元测试 + 集成测试
└── data/                   # knowledge(索引) datasets(蒸馏语料) outputs(任务产物)
```

## 快速开始

```bash
:: ① 安装依赖
pip install -r requirements.txt

:: ② 生成并填写本机配置（数据库密码等；不创建也能跑，程序自动用模板默认值）
copy config.example.yaml config.yaml
```


**桌面软件（推荐）**：双击桌面上的 **learn-agent** 图标（安装见下），或双击项目里的 `learn-agent.exe`。
单文件 exe，自带运行时，启动后自动预加载 `learn-agent` 模型（对话零冷启动）。

```bash
:: 重新打包桌面 exe（改完代码后）
pip install pyinstaller pillow
python assets\make_icon.py
python -m PyInstaller --noconfirm --onefile --windowed --icon D:\learn-agent\assets\learn-agent.ico ^
  --name learn-agent --distpath . --workpath build --specpath build ^
  --hidden-import modules.leetcode --hidden-import modules.devkit --hidden-import core.db --hidden-import modules.algo ^
  learn-agent.pyw
```

> 若桌面快捷方式丢失：项目根目录有 `learn-agent.exe`，右键发送到桌面快捷方式即可。

```bash
cd D:\learn-agent
:: 命令行/源码方式启动桌面应用（与 exe 等价）
python main.py gui

:: 训练（蒸馏数据 -> 知识库 -> 生成本地定制模型 learn-agent）
python main.py train --topics 5

:: 对话（默认用训练出的 learn-agent 模型）
python main.py chat

:: 学一个主题（教程 + 沉淀知识库 + 记录进度）
python main.py learn python 装饰器
python main.py learn javascript Promise

:: 零基础引导式学习（推荐入门方式）
python main.py path python       # 查看分阶段路径与进度
python main.py start python      # 自动学下一课（连跑即从0到进阶）
python main.py review python     # 阶段复习
python main.py quiz python 生成器 # 随堂测验

:: 进阶实战：Agent 用你已学的知识自主完成项目（前后端/算法）
python main.py capstone python   # 个人博客系统(FastAPI+SQLite+前端)
python main.py capstone sql      # 电商数据库设计与报表

:: 解力扣题（完整工作流 + 自动判题）
python main.py problems
python main.py solve two-sum

:: 通用开发任务
python main.py task "用Python实现一个线程安全的有界缓存并附测试"

:: 生成前后端项目（FastAPI + 原生前端，生成即体检）
python main.py dev my-app --stack fastapi

:: function-calling 工具循环
python main.py tools "搜一下 FastAPI 最新版本特性并总结"

:: 本地数据库（MySQL/MariaDB，凭据见 config.yaml）
python main.py db                          # 查看连接与数据库列表
python main.py db "SELECT VERSION()"       # 执行 SQL
python main.py db --schema xzs             # 查看某库表结构
:: 也可在 GUI「数据库」页签使用 SQL 控制台，或在对话中让 AI 通过 mysql_query 工具操作

:: Web 控制台
python main.py serve        # http://127.0.0.1:7860
```

## 启用外部大模型增强

编辑 `config.yaml`（本地文件，不会入库）：

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
| `python main.py gui`（或双击 `learn-agent-gui.bat`） | **桌面应用**（Tkinter，零额外依赖）：对话（流式输出）/ 语言学习 / 力扣刷题（选题解题+判题）/ 开发任务（实时工作流日志）/ 数据库（SQL 控制台）/ 训练（含报告展示） |
| `python main.py serve` → http://127.0.0.1:7860 | **浏览器控制台**（Flask）：同样的六大功能 |

两者均后台线程执行耗时操作，界面不卡顿；桌面版流式对话逐字显示。

## 工作流说明

```mermaid
flowchart LR
    A[思考 Think] --> B[计划 Plan]
    B --> C{计划审查}
    C -- "high 问题" --> A
    C -- 通过 --> D[开发 Develop]
    D --> E{代码审查<br/>静态+LLM 双保险}
    E -- "high 问题" --> A
    E -- 通过 --> F[测试<br/>子进程超时+内存泄漏检测]
    F -- 失败 --> A
    F -- 通过 --> G[完成<br/>全程落盘+复盘归档]
```

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
python -m unittest discover tests -v     # 单元测试 + 集成测试

:: 端到端集成测试（真跑 LLM 工作流，约数分钟）默认跳过以保证回归确定性；
:: 需 Ollama 在线并显式开启时运行：
set LEARN_AGENT_E2E=1 && python -m unittest tests.test_all.IntegrationLLM -v
```

单元测试不依赖任何外部服务（无 Ollama/MySQL 时相关用例自动跳过），CI 全绿即回归通过。
经验沉淀：`data/memory/error_patterns.json` 记录历次工作流踩过的真实缺陷模式——
例如"自动生成的测试脚手架期望值算错导致正确解法被误判"，已反哺到测试驱动修复的判定指引中。

## 环境要求

- Python 3.11+，`pip install -r requirements.txt`
- Ollama + `qwen3:8b` / `qwen3:14b`（NVIDIA GPU 建议 ≥12GB 显存）
- 可选：Node.js（JS 语法检查）、MySQL/MariaDB（数据库工具）、外部 LLM API Key（增强）

## 路线图

- [ ] **MCP Server 模式**：把质量工作流（判题/体检/知识库检索）以 [Model Context Protocol](https://modelcontextprotocol.io) 工具暴露给任意 MCP 客户端复用
- [ ] 多语言课程动态生成的质量评估基准（现有 7 门内置详纲 → 35 门动态生成）
- [ ] LoRA 微调模型与基座模型的 A/B 评测报告自动化
- [ ] Web 控制台流式输出与移动端适配

## 安全说明

本仓库不含任何真实凭据：`config.yaml`（数据库密码/API Key）已被 `.gitignore` 忽略，
仓库只保留脱敏模板 `config.example.yaml`；程序在 `config.yaml` 缺失时自动回退读取模板，开箱可运行。

