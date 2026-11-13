# learn-agent — 编程学习与开发 Agent

基于**本地大模型**（Ollama / Qwen3）+ **网络数据检索** + 可选**外部大模型 API 增强**的编程学习助手。

核心能力：
- **七门语言、零基础到进阶**：Python / JavaScript / Java / C++ / Go / SQL / HTML-CSS 前端，
  每门按 **L0 零基础 → L1 核心 → L2 进阶 → L3 工程 → L4 后端(实战) → L5 前端协同 → L6 算法** 分阶段课程
- **引导式学习**：`start` 自动从第一课推进（学习即记录进度），`path` 随时查看路径与完成度，
  `review` 生成阶段复习（知识地图+综合练习），`quiz` 随堂测验
- **进阶实战（学以致用）**：`capstone` 让 Agent 用你已学的知识**自主完成**真实项目并走完整质量工作流——
  Python 个人博客系统(FastAPI+SQLite+前端)、JS 待办全栈应用(Express)、Java 成绩管理、C++ 日志分析器、
  Go 短链接服务、SQL 电商库表与报表、HTML/CSS 响应式个人主页
- **刷算法**：内置 12 道力扣经典题（带可运行测试），解题走完整质量工作流并自动判题、查内存泄漏
- **做开发**：FastAPI / Flask / Express + 前端脚手架一键生成，生成即体检
- **函数调用**：LLM function-calling 工具循环（联网搜索 / 运行代码 / 检索知识库 / 代码体检 / **MySQL 数据库操作**）
- **本地数据库**：直连本机 MySQL/MariaDB（凭据在 `config.yaml` 的 `database` 段），CLI `db` 命令、GUI 数据库页签、
  AI 工具 `mysql_query`/`mysql_schema` 三种方式操作真实库
- **质量工作流**：`思考 → 计划 → 审查 →（不过→回思考）→ 开发 → 代码审查 → 测试 →（不过→回思考）→ 完成`，最多 3 轮循环；连续失败自动升级模型（外部 API 或深度模型+思考模式）
- **多模型池 + 智能路由**：`config.yaml` 云端模型 + DSH 通道网关（workbuddy-cn / qodercn / trae / buddy 等已登录账号）自动发现；
  每次调用按**可用性优先、兼顾性能**动态重排（成功率 + 新近成功主导，同分按实测耗时），失败自动冷却换通道，画像持久化免重启试错
- **训练体系**：数据蒸馏 → 知识库 TF-IDF 训练（带命中率指标）→ 定制本地模型 `learn-agent`（`ollama create`）→ 可选真·LoRA 微调脚本（RTX 4070 可跑）

## 目录结构

```
<项目目录>\
├── main.py                 # CLI 入口（chat/learn/quiz/solve/task/dev/ask/tools/kb/train/serve/modelpool）
├── launch.py               # 智能启动器：版本指纹比对 → 复用/自动重启到新版（双击图标走这里）
├── config.yaml             # 模型、工作流、测试参数；外部 API Key 填这里
├── core/
│   ├── llm.py              # LLM 路由：本地 qwen3 + 云端模型池 + DSH 通道网关；按可用性优先动态排序 + 自动降级
│   ├── version.py          # 代码版本指纹（内容 sha256，排除 data/tests/build）
│   ├── runtime.py          # 实例登记与探活（PID+创建时间双重校验，防误杀）
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
├── start-web.bat           # Web 控制台双击启动器（自动检测版本）
├── learn-agent-gui.bat     # 桌面应用双击启动器（自动检测版本）
├── stop-web.bat            # 停止 Web 实例
├── tests/test_all.py       # 单元测试 + 集成测试
└── data/                   # knowledge(索引) datasets(蒸馏语料) outputs(任务产物) runtime(实例登记)
```

## 快速开始

**改了代码怎么生效？** 直接双击图标即可 —— 启动器会自动检测代码版本，发现变了就重启到新版，
没变就复用正在跑的实例（不会重复开进程）。

| 双击 | 作用 |
|---|---|
| `start-web.bat` | Web 控制台（自动开浏览器；代码变了自动重启） |
| `learn-agent-gui.bat` | 桌面 GUI（代码变了自动重启） |

```bash
python launch.py check          # 只看版本状态（有旧版在跑时退出码=1，适合 CI/脚本）
python launch.py web            # = start-web.bat；--force 强制重启，--no-browser 不开浏览器
python launch.py gui            # = learn-agent-gui.bat
python launch.py stop           # 停止当前实例（含占着端口的野进程）
python launch.py watch          # 常驻守护：代码一变就自动重启（开发时最爽）
```

启动器怎么判断"代码变了"（`core/version.py` + `core/runtime.py`）：

1. 对 `core/ modules/ gui/ webapp/ training/ evals/ prompts/ assets/` 与
   `main.py launch.py config.yaml README.md` 做**内容 sha256**，得到 12 位 build 指纹（~30ms）
2. 每个应用启动时把 `{pid, mode, build, 进程创建时间}` 写进 `data/runtime/instance.json`
3. 下次双击时比对：指纹相同 → 复用；不同 → 杀掉旧进程、等端口释放、启动新版

> 为什么用内容哈希而不是修改时间：`git checkout`、编辑器"另存"、复制粘贴都可能不改 mtime。
> 为什么记"进程创建时间"：Windows 会复用 PID，只凭 PID 可能误杀碰巧拿到同号的新进程。
> `data/`、`tests/`、`build/` 不参与指纹——知识库/日志每天在变，改测试也不该打断你正在用的界面。

```bash
cd <项目目录>
:: 命令行/源码方式启动桌面应用
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

编辑 `config.yaml`：

```yaml
external_model:
  enabled: true
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1   # 或 https://api.deepseek.com/v1
  api_key: "sk-你的KEY"
  model: qwen-plus
```

启用后：① 复杂审查与蒸馏自动走外部强模型；② 工作流连续失败 2 次自动升级到外部模型再审。

## 模型池与调用顺序（可用性优先 + 兼顾性能）

模型来源有两类，统一进 `strong`（难题/规划/审查）与 `fast`（聊天/短答/教程）两档：

1. `config.yaml` 的 `cloud.models` —— 显式配置的 OpenAI 兼容端点（AMD / 商汤 / Nvidia 等）
2. **DSH 通道网关**（`127.0.0.1:8326`）—— 自动枚举 DeepSeek Harness 里已登录账号的模型。
   凭据取自 `~/.dsh/openai-gateway/api-key`，本项目不存任何第三方 Key。
   **新增/下线模型无需改代码**，网关更新后自动生效（可用 `modelpool` 查看）。

当前接入的通道（2026-10-30 实测）：

| 通道 | 状态 | 代表模型 |
|---|---|---|
| `workbuddy-cn` | ✓ | kimi-k3.1-pro / deepseek-v4-pro / glm-5.3-flash |
| `qodercn` | ✓ | qmodel_38max / qmodel_latest / qfmodel |
| `qoder` | ✓ | ultimate / performance / qmodel_38max |
| `trae` | ✓ | kimi-k3.1-pro / DeepSeek-V4-Pro |
| `buddy` | ✓ | kimi-k3.1-pro / deepseek-v4-pro |
| `cline` | ✓ 部分 | **claude-opus-5.5 / gpt-6.1-sol / claude-sonnet-5.5** |
| `workbuddy` | ✓ | kimi-k3 / kimi-k3.1-pro |
| `our-free-model` | ✓ | nemotron-3-ultra-550b / big-pickle |
| `zcode` | 额度制 | GLM-5.3（按自然日恢复） |
| `pi-github-copilot` / `deepseek-official` / `st-daily-use` | ✗ | 无授权 / 502，不接入 |

> 每个通道限额 3 强 + 4 快，总量按**通道轮转**分配——上限收紧时是"
> 每家少给一点"，而不是"排在后面的通道全丢"。同名旗舰（如 kimi-k3.1-pro）
> 在多家都有，其中一家挂了自动切下一家。

**调用顺序不是写死的配置序，而是每次调用前按历史表现动态重排：**

| 优先级 | 规则 |
|---|---|
| 1 | **可用性优先**：有成功记录的通道按「成功率 + 新近成功」排前，刚成功过的更靠前 |
| 2 | **兼顾性能**：可用性同分时，按实测耗时（EMA）快的优先 |
| 3 | 从未调用过的通道保持配置/服务商原序，夹在中间（不盲目提前） |
| 4 | 只失败过、从未成功过的通道沉到队尾 |

画像持久化在 `data/memory/llm_channels.json`（7 天过期），**重启后不必从零试错**；
推理/JSON 校验失败的通道会被判为失败并换下一条，不会把垃圾内容抛给上层。

```bash
python main.py modelpool           # 查看两档的实际调用顺序 + 可用率/耗时/冷却
python main.py modelpool --probe   # 对每条通道发最小请求做真实探测（慢，消耗额度）
python main.py modelpool --clear   # 清空画像，恢复配置原始顺序
python scripts/probe_gateway.py --all --update   # 网关全量体检 + 打印接入建议
```

### 更新模型池（网关有新模型时）

网关的模型会变（新增旗舰、下线旧版）。检测与更新流程：

```bash
python scripts/probe_gateway.py --all --update
```

脚本会逐条实测并分类，最后打印建议的 `GATEWAY_PREFIXES`：

| 分类 | 含义 | 处理 |
|---|---|---|
| `ok` | HTTP 2xx 且有正文 | 接入 |
| `quota` | 429 / "额度已用尽" | 接入（会按日/按窗口恢复，不是坏） |
| `noauth` | 401/402/403 / "not subscribed" | 不接入（需订阅或未登录） |
| `gone` | 404/410 | 不接入（模型已下线） |
| `broken` | 5xx | 不接入（通道未打通） |

两个容易误判的坑（脚本已处理）：

- **推理模型会先烧思考链**：`max_tokens` 太小会导致 `content` 为空、`reasoning_content`
  有内容，看起来像"不可用"。脚本遇到空正文会自动加大 `max_tokens` 重试一次。
- **不能只看 HTTP 状态码**：网关会把上游的"额度用尽"包成 5xx 或 200，
  必须连响应体一起判断，否则会把"明天还能用"误判成"通道坏了"。

Web 控制台顶部的「云端 N 模型」提示会显示**当前会先被调用的强档/快档模型**，
`GET /api/cloud` 返回的 `models[].order` 就是实际优先级。

## 图形界面（两种）

| 入口 | 说明 |
|---|---|
| `python main.py gui`（或双击 `learn-agent-gui.bat`） | **桌面应用**（Tkinter，零额外依赖）：对话（流式输出）/ 语言学习 / 力扣刷题（选题解题+判题）/ 开发任务（实时工作流日志）/ 训练（含报告展示） |
| `python main.py serve` → http://127.0.0.1:7860 | **浏览器控制台**（Flask）：同样的五大功能 |

两者均后台线程执行耗时操作，界面不卡顿；桌面版流式对话逐字显示。

### 教程实操（Web 控制台）

Web 控制台的学习/实战教程与「回顾」里打开的已学教程，Markdown 中的 ``` 代码块会渲染成**可编辑 + 可运行**的练习框（`webapp/static/labs.js`）：

- Python 围栏：显示「▶ 运行」按钮，点击后代码经 `POST /api/run` 在沙箱子进程（带超时）中执行，stdout/报错就地显示；
- 非 Python 围栏（如 bash）：只读展示；
- 任务区已完成的教程卡片可直接展开练习，「回顾」中点「查看」同样可编辑运行。

### 侧边栏目录与回看（Web 控制台）

三个页面都配了**侧边栏目录**，解决"生成了却找不到"的问题：

| 页面 | 侧边栏 | 说明 |
|---|---|---|
| 语言学习 | 📑 课程目录 | 按 L0→L6 阶段折叠，✓已学/○未学，顶部进度条与「下一课」；点一下右侧直接渲染该课教程；主题后有 🎯N 表示有几套练习 |
| 力扣刷题 | 📖 讲解目录 | 按难度分组，●有讲解/○无；点一下直接显示本地讲解（秒开，不重新生成） |
| 语言学习 | 📋 历史练习 | 按主题分组列出 `data/practice/` 下所有练习，点「开始做题」可改代码 ▶ 运行判题 |

**关于"练习无法查看"**：练习生成后原本只存在 Web 进程的内存 `JOBS` 里，
服务一重启（改代码后双击图标就会重启）就查不到了——而磁盘上的
`data/practice/*.json` 却一直在。现在加了 `GET /api/practices`（列目录）与
`?file=`（取单套）直接从**磁盘**读，配合「📋 历史练习」入口和课程目录里的
🎯N 标记，重启后照样能回看、能改代码重做、能判题。

**关于"讲解未显示"**：`loadExplain` 原来用 `<pre>${esc(content)}</pre>` 输出，
用户看到的是满屏 `#`、`**`、```` ``` ```` 原文，误以为讲解没出来。现在走
`tutorialHtml` 渲染——标题/列表/加粗正常显示，代码围栏变成可运行的练习框。

**关于"点讲解要等 30~90 秒"**：`explainBySlug` 原来无条件重新生成并覆盖。
现在先查本地文件，有就直接显示；要覆盖得点「重新生成」。

桌面版（Tkinter）同步：力扣页选中题目即显示本地讲解（列表带 ✓ 标记），
「重新生成」才覆盖；语言学习页新增「练习」「历史练习」按钮。

### 多开与「边学边练」

Windows 上有两个显示器、或者只是想把教程和练习摆在一起对照？Web 控制台支持：

| 功能 | 用法 |
|---|---|
| **多开模式** | 顶部勾选「⊞ 多开模式」。此后点击顶部导航是**切换该栏显示/隐藏**，而不是独占切换——可以同时开着「语言学习」和「力扣刷题」。只点亮一栏时它会自动铺满全宽；三栏以上第一栏跨行。 |
| **边学边练** | 语言学习页点「⇔ 边学边练」（或课程目录里某课的 `⇔` 小按钮）。左侧显示教程（含可运行代码框），右侧粘性显示练习区，**独立滚动、可拖动分隔条调宽**，边看边改代码。 |

细节：

- 单栏时 wrapper 用 `display:contents`，布局与之前完全一致（不影响原有使用习惯）。
- 开启状态记在 `localStorage`，刷新后自动恢复。
- 支持 URL 深链，方便收藏/分享特定视图：
  - `?multi=1&panels=learn,lc` — 多开并显示这两栏
  - `?split=1` — 学习页开启边学边练
  - `?lang=python&topic=装饰器与闭包` — 直接打开该课的边学边练
- 双栏模式下，练习相关操作不会再清空左栏教程（这是最初的 bug：点 🎯 后左半屏空白）。

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

### 知识库怎么用：常驻精华 + 运行时检索（两段式）

看到报告里写「知识注入 22/244 篇」不要误会成"知识库没用"——**这是上下文预算的
物理限制，不是缺陷**。分工如下：

| 机制 | 装什么 | 容量 | 覆盖 |
|---|---|---|---|
| **SYSTEM 常驻** | 最通用的速查/要点（按优先级填充到 6000 字） | 固定 22 篇 | 每条对话都在 |
| **运行时检索** | 按当前问题从全库 244 篇里取最相关的 2~3 篇 | 每次动态 | 检索自评 **88% 排第 1 / 97.5% 进前 3** |

为什么不能全塞进去：`num_ctx=8192` 里 system prompt 已经占了 6000 字（70%+），
知识库全量 26.8 万字，是预算的 45 倍。塞满就没地方放用户问题和模型回答了。

注入点（`ask`/`ask_json` 的 `kb_query` 参数）：

```python
# 自动检索「Python 装饰器」，把命中的知识片段拼进提示词
router().ask("为学员出 3 道题", kb_query="Python 装饰器")
router().ask_json(prompt, kb_query=f"{lang} {topic}")   # 测验/练习/实战都接了
```

已接入的调用点：教程生成、测验、阶段复习、速查表、实操练习、智能复习、进阶实战。
默认**不注入**（`kb_query=None`），避免给每次调用平白增加 token。

几个容易踩的坑（已修）：

- **TF-IDF 缺长度归一化**：查询「背包问题 动态规划」时，真正讲背包的
  《动态规划入门要点》(205字, 命中全部 4 个词) 只得 88.75 分，而只沾了
  "动态规划" 3 个词的题解《爬楼梯》(456字) 却拿 100.85 分——长文档靠词频刷分。
  更隐蔽的是 `hit_rate` 仍显示 0.97（还在前 3 名），完全掩盖了排序错误。
  改为 **L2 归一化**（余弦相似度）后，正确文档回到第 1。
- **中文二元组的假阳性**：`"完全不相关"` 里含「相关」、`"查询"` 是常见词，
  无意义查询也能凑出 22~33% 覆盖率骗过分数阈值。加了 **覆盖率阈值 0.4**
  （实测真实查询 50~100%、噪声 22~33%），噪声查询现在稳定返回空。
- **`source` 字段含义不统一**：种子知识是 `"seed"`，学习教程存的是**文件绝对路径**
  （`C:\...\某课.md`）。早期用 `src == "seed"` 判断优先级，结果 16 万字的大部头
  教程全挤进了 6000 字预算，真正该常驻的精华反而被挤掉。改为按内容形态+长度判断。

### 训练报告（四段，完整不截断）

`data/train_report.json` 与 GUI/Web 训练页展示同样四段：

```
① 蒸馏     pairs / llm_calls / avg_per_call / seconds
② 知识库   docs / vocab / hit_rate / retrieval{top1_rate,top3_rate,avg_rank} / distilled_docs
③ 定制模型 model / base / system_chars / knowledge{injected,skipped,budget,total_docs,kb,note} / seconds
④ 验证回答 verify（完整正文）+ verify_meta{content_chars, thinking_chars, ...}
```

其中 `knowledge.note` 会明确写出"为什么只注入 N 篇"以及其余文档的检索去向，
`retrieval` 给出检索质量自评（比 `hit_rate` 严格：还看平均排名）。

几个容易踩的坑（已修）：

- **验证回答曾用 `ollama run` 的 stdout 再 `[:300]` 硬切** —— CLI 会把思考链和终端控制符
  一起写进 stdout，结果第 300 字切出来的全是 `<think>` 内容，既不是回答也读不通。
  现在改走 HTTP API `/api/chat`：`message.content` 是纯回答、`message.thinking` 单独给，
  `verify` 存**完整正文**，思考链长度记在 `verify_meta.thinking_chars`。
- **SYSTEM 提示词预算**：知识库 100+ 篇不可能全塞进去（要占对话上下文）。改为
  固定骨架（角色/纪律/守则，永不裁） + 按优先级填充预算（默认 6000 字），
  每条按**段落边界**收尾而不是硬切前 N 字。注入了多少、为什么跳过，都写进报告
  （`knowledge.injected / skipped / budget`）。运行时长期记忆由 `kb.search` 的
  TF-IDF 检索承担，不依赖把整个知识库塞进 prompt。
- **Web 训练结果曾把 `distill` 段整体过滤掉**（`{k:v for k,v in rep.items() if k != "distill"}`），
  导致蒸馏统计永远看不到。现在 Web 直接复用 `training.run_training.run`，任务结果里
  `result.report` 带**完整报告**，训练卡片按四段折叠展示，另有「查看完整报告 JSON」。

## 测试

```bash
python -m unittest discover tests -v     # 单元测试（无需大模型在线）
node tests/lab_check.js                  # 教程围栏切分/练习框渲染回归（无需浏览器）
python tests/llm_overlap_check.py        # LLM 长文续写去重回归（mock，不发真实请求）
```

## 环境要求

- Python 3.11+，`pip install requests flask pyyaml`
- Ollama + `qwen3:8b` / `qwen3:14b`（NVIDIA GPU 建议 ≥12GB 显存）
- 可选：Node.js（JS 语法检查）、外部 LLM API Key（增强）
