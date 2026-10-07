# -*- coding: utf-8 -*-
"""学习模块 v2：多语言、零基础分阶段学习路径、进度追踪、引导式学习、进阶实战。

课程结构：L0 零基础 -> L1 核心基础 -> L2 进阶特性 -> L3 工程能力
         -> L4 后端实战 -> L5 前端协同 -> L6 算法进阶（语言不同阶段略有差异）

"学习即训练"：每次 learn 产出的教程自动沉淀进知识库（TF-IDF 重建索引）。
"学以致用"：完成 L3 后可运行 capstone()，Agent 按已学内容自主完成进阶实战项目
（前后端开发/算法应用），走完整质量工作流。
"""
import json
import re
import time
from pathlib import Path

from core.config import data_dir, outputs_dir
from core.llm import router
from core.knowledge import kb
from core import websearch

PROGRESS_FILE = "progress.json"

# ---------------- 课程大纲（分阶段，从0开始） ----------------
CURRICULUM = {
    "python": {
        "name": "Python", "runner": "python",
        "goal": "能独立完成 Web 后端 API 开发、自动化脚本与力扣算法题",
        "stages": {
            "L0 零基础": ["环境搭建与第一个程序", "变量与数据类型", "输入输出与运算符", "条件语句与循环"],
            "L1 核心基础": ["列表/字典/集合/元组", "函数与参数传递", "字符串与格式化", "文件读写与编码"],
            "L2 进阶特性": ["类与面向对象", "装饰器与闭包", "迭代器与生成器", "异常处理与调试", "并发与异步编程"],
            "L3 工程能力": ["标准库常用模块", "单元测试与调试", "虚拟环境与包管理", "代码规范与重构"],
            "L4 后端实战": ["HTTP与REST API概念", "Flask/FastAPI Web开发", "SQLite与SQLAlchemy数据库", "认证部署与安全基础"],
            "L5 前端协同": ["HTML/CSS/JS速成(后端视角)", "模板渲染与前后端联调", "调用第三方API与CORS"],
            "L6 算法进阶": ["复杂度分析", "数组哈希与双指针", "链表与栈队列", "树与递归", "动态规划入门"],
        },
        "capstone": {"name": "个人博客系统（前后端）", "stack": "fastapi",
                     "desc": "FastAPI + SQLite 实现文章 CRUD 的 REST API（/api/posts），"
                             "附原生 HTML/JS 前端页面（列表+新建表单），提供 pytest 可跑的接口测试与健康检查。"
                             "数据层直接用 sqlite3 标准库，不要引入 SQLAlchemy 等 ORM"},
    },
    "javascript": {
        "name": "JavaScript", "runner": "node",
        "goal": "能独立完成前端页面交互开发与 Node.js 后端 API",
        "stages": {
            "L0 零基础": ["浏览器控制台与第一个脚本", "变量与类型(LET/CONST)", "运算符与条件循环", "函数入门"],
            "L1 核心基础": ["数组与高阶函数(map/filter/reduce)", "对象与解构", "字符串与模板字面量", "DOM查询与事件处理"],
            "L2 进阶特性": ["闭包与this", "原型与class", "Promise与async/await", "错误处理与调试", "ES6模块化"],
            "L3 工程能力": ["npm与工程配置", "Fetch与网络请求封装", "本地存储与状态管理思想", "代码规范与调试工具"],
            "L4 前端实战": ["表单校验与交互组件", "SPA路由思想与渲染优化", "组件化与简单框架概念(React/Vue)", "XSS防范与安全"],
            "L5 后端实战(Node)": ["Node.js基础与文件操作", "Express路由与中间件", "REST API设计与错误处理", "数据库接入与部署"],
            "L6 算法进阶": ["复杂度分析", "数组与哈希", "栈队列与链表", "递归与树"],
        },
        "capstone": {"name": "待办事项应用（全栈）", "stack": "express",
                     "desc": "Express 实现任务 CRUD REST API（/api/tasks），前端单页应用实现添加/完成/删除/筛选，"
                             "数据持久化到 JSON 文件，含健康检查接口"},
    },
    "java": {
        "name": "Java", "runner": "java",
        "goal": "能独立完成 Spring Boot 后端开发与常见业务系统",
        "stages": {
            "L0 零基础": ["JDK安装与第一个程序", "变量与基本类型", "运算符与流程控制", "数组与字符串"],
            "L1 核心基础": ["类与对象基础", "方法与封装", "继承与多态", "接口与抽象类"],
            "L2 进阶特性": ["集合框架 List/Map/Set", "泛型", "异常体系", "IO与try-with-resources", "多线程与线程安全", "Lambda与Stream"],
            "L3 工程能力": ["Maven/Gradle基础", "JUnit单元测试", "JVM内存与GC概念", "常见设计模式"],
            "L4 后端实战": ["HTTP与REST概念", "Spring Boot入门与MVC", "MyBatis/JPA数据库操作", "事务与参数校验"],
            "L5 前端协同": ["Thymeleaf模板", "REST接口设计与跨域", "前端页面联调"],
            "L6 算法进阶": ["复杂度分析", "数组与哈希", "链表与栈队列", "树与递归", "动态规划入门"],
        },
        "capstone": {"name": "学生成绩管理系统（后端）", "stack": "springboot",
                     "desc": "Spring Boot 实现 /api/students CRUD + 按成绩统计接口，Service 层单元测试，"
                             "内存存储即可（演示用），提供清晰的接口文档注释"},
    },
    "c++": {
        "name": "C++", "runner": None,
        "goal": "掌握系统级编程与高性能算法实现（本机无编译器，代码经 AI 审查验证）",
        "stages": {
            "L0 零基础": ["编译型语言概念与HelloWorld", "变量与基本类型", "输入输出与运算符", "条件与循环"],
            "L1 核心基础": ["数组与字符串", "函数与引用传参", "指针基础", "结构体与枚举"],
            "L2 进阶特性": ["类与RAII资源管理", "智能指针 unique/shared_ptr", "STL容器vector/map/set", "迭代器与算法库", "模板入门"],
            "L3 工程能力": ["头文件与多文件组织", "Makefile/CMake概念", "单元测试思路", "内存泄漏排查(Valgrind概念)"],
            "L4 实战方向": ["文件与流处理", "并发线程thread", "网络编程概念", "性能优化技巧"],
            "L5 算法进阶": ["复杂度分析", "STL在算法中的应用", "链表与栈队列", "树与图入门", "动态规划入门"],
        },
        "capstone": {"name": "高性能日志分析器（控制台）", "stack": "cpp",
                     "desc": "C++17 控制台程序：读取日志文件，用 unordered_map 统计各级别数量与 topN 关键字，"
                             "RAII 管理文件资源，附 Makefile 与单元测试思路说明"},
    },
    "go": {
        "name": "Go", "runner": None,
        "goal": "掌握云原生后端开发语言（本机无编译器，代码经 AI 审查验证）",
        "stages": {
            "L0 零基础": ["安装与第一个程序", "变量与类型", "控制流与循环", "函数与多返回值"],
            "L1 核心基础": ["数组/切片/映射", "结构体与方法", "接口", "错误处理惯例"],
            "L2 进阶特性": ["goroutine与channel", "sync包与并发安全", "defer/panic/recover", "包管理与模块"],
            "L3 工程能力": ["go test单元测试", "项目布局规范", "常用标准库", "代码格式化与静态检查"],
            "L4 后端实战": ["net/http与Handler", "JSON API开发", "中间件与路由", "数据库database/sql"],
            "L5 前端协同": ["静态文件服务", "REST接口设计与CORS", "前后端联调"],
            "L6 算法进阶": ["复杂度分析", "切片与哈希", "链表与栈队列", "递归与动态规划"],
        },
        "capstone": {"name": "短链接服务（后端）", "stack": "go",
                     "desc": "Go 标准库实现 POST /api/shorten 生成短码、GET /s/{code} 302 跳转，"
                             "内存存储+互斥锁保护，附 go test 单元测试"},
    },
    "sql": {
        "name": "SQL", "runner": "sqlite",
        "goal": "掌握数据库设计与查询，支撑后端开发数据层",
        "stages": {
            "L0 零基础": ["数据库概念与SQLite入门", "建表与数据类型", "INSERT/SELECT基础", "WHERE条件过滤"],
            "L1 核心基础": ["ORDER BY与LIMIT", "聚合函数COUNT/SUM/AVG", "GROUP BY与HAVING", "UPDATE与DELETE"],
            "L2 进阶特性": ["多表JOIN", "子查询", "索引与执行计划", "事务与ACID"],
            "L3 工程能力": ["范式化设计", "外键与约束", "Python中操作SQL(sqlite3)", "SQL注入防范"],
            "L4 实战应用": ["为Web应用设计库表", "分页查询", "常用报表SQL", "数据迁移思路"],
            "L5 进阶专题": ["窗口函数", "CTE递归查询", "性能调优案例"],
        },
        "capstone": {"name": "电商数据库设计与报表", "stack": "sql",
                     "desc": "用 sqlite3 设计 用户/商品/订单/订单明细 四表（含外键约束），"
                             "插入演示数据，编写 5 个报表查询（Top客户/月销售额/库存预警等），Python 脚本可一键运行验证"},
    },
    "html-css": {
        "name": "HTML/CSS 前端", "runner": None,
        "goal": "从零掌握网页结构与样式，能独立完成静态页面与响应式布局",
        "stages": {
            "L0 零基础": ["网页结构与第一个HTML", "常用标签文本/链接/图片", "列表与表格", "表单与输入控件"],
            "L1 核心基础": ["CSS语法与选择器", "盒子模型", "常用样式文本/颜色/背景", "显示与定位"],
            "L2 进阶布局": ["Flex弹性布局", "Grid网格布局", "响应式设计与媒体查询", "CSS变量与复用"],
            "L3 工程能力": ["语义化与可访问性", "BEM命名与组织", "浏览器调试工具", "性能与兼容性"],
            "L4 实战进阶": ["JS与DOM交互入门", "动画与过渡", "组件化样式思想", "与后端API联调的页面"],
        },
        "capstone": {"name": "个人主页网站", "stack": "html",
                     "desc": "响应式个人主页：头部导航+自我介绍+技能卡片(Flex/Grid)+作品集+联系表单(带JS校验)，"
                             "含暗色模式切换，纯 HTML/CSS/JS 无框架"},
    },
}

STAGE_ORDER = list(next(iter(CURRICULUM.values()))["stages"].keys())  # 通用阶段顺序参考

# ---------------- 语言矩阵（规范要求的全量支持；未列出的语言同样可动态扩展） ----------------
CATALOG = {
    # 前端与脚本
    "html-css": "HTML/CSS 前端", "javascript": "JavaScript", "typescript": "TypeScript",
    "vue": "Vue 框架", "react": "React 框架", "nodejs": "Node.js",
    # 后端与通用
    "python": "Python", "java": "Java", "go": "Go", "c": "C",
    "csharp": "C#", "rust": "Rust", "php": "PHP", "ruby": "Ruby",
    "kotlin": "Kotlin", "swift": "Swift", "scala": "Scala", "lua": "Lua",
    "shell": "Shell/Bash",
    # 数据与查询
    "sql": "SQL", "mysql": "MySQL", "postgresql": "PostgreSQL",
    "mongodb": "MongoDB", "redis": "Redis",
    # 移动与跨端
    "dart": "Dart/Flutter", "kotlin-android": "Kotlin/Android", "swift-ios": "Swift/iOS",
    # 其他
    "r": "R", "matlab": "MATLAB", "asm": "汇编基础",
    "haskell": "Haskell", "elixir": "Elixir", "clojure": "Clojure",
}

# 九阶段通用框架（规范：每门语言从0到独立开发的完整闭环）
UNIVERSAL_STAGES = {
    "01 语言定位": ["语言定位与生态速览(用途/优劣/适用场景)", "与已学语言的差异对照"],
    "02 环境搭建": ["安装与版本管理", "编辑器与包管理", "第一个程序"],
    "03 基础语法": ["变量与类型", "运算符与控制流", "函数与作用域"],
    "04 核心数据结构": ["字符串", "数组/列表/映射/集合", "结构体与元组(视语言而定)"],
    "05 进阶特性": ["面向对象/接口/泛型(视语言而定)", "并发模型", "内存管理与错误处理"],
    "06 标准库与常用函数": ["标准库速查(函数/参数/返回值/易错点)", "文件/网络/时间等常用调用"],
    "07 工程化": ["模块与包管理", "测试框架与调试", "构建/格式化/静态检查"],
    "08 前后端实战": ["Web 服务入门(后端方向)", "页面与 API 联调(前端方向)", "实战小项目"],
    "09 算法训练": ["数组/哈希/双指针", "链表/栈/队列/树", "动态规划入门"],
}

FALLBACK_CAPSTONE = {"name": "实战入门项目", "stack": "",
                     "desc": "用该语言完成一个可运行的小型实战项目(如 CLI 工具/简单API/数据处理脚本)，"
                             "附测试与 README，走完整质量工作流"}


def _curriculum_cache(lang: str) -> Path:
    return data_dir() / "memory" / f"curriculum_{lang}.json"


def _fallback_curriculum(lang: str) -> dict:
    name = CATALOG.get(lang, lang)
    return {"name": name, "runner": None, "generated": "fallback",
            "goal": f"从0掌握 {name}，达到能独立开发小型前后端项目并完成常见算法题",
            "stages": {k: list(v) for k, v in UNIVERSAL_STAGES.items()},
            "capstone": dict(FALLBACK_CAPSTONE, name=f"{name} 实战项目")}


def _generate_curriculum(lang: str) -> dict:
    """用 LLM 按九阶段框架生成语言课程；失败则退回确定性模板（绝不拒绝语言）。"""
    from core.llm import LLMError, router
    name = CATALOG.get(lang, lang)
    try:
        data = router().ask_json(f"""为编程语言「{name}」设计从零基础到独立开发的完整课程大纲。
严格使用以下九个阶段作为 stages 的键，每阶段 3~4 个主题（主题要具体到该语言）：
{json.dumps(list(UNIVERSAL_STAGES.keys()), ensure_ascii=False)}

输出 JSON：
{{"name": "{name}", "runner": "运行命令或null", "goal": "一句话目标",
 "stages": {{"01 语言定位": ["主题"...], ...}},
 "capstone": {{"name": "实战项目名", "stack": "技术栈", "desc": "项目要求(2-3句)"}}}}""",
                                 deep=True)
        stages = data.get("stages", {})
        if not stages or not any(str(k).startswith("0") for k in stages):
            raise LLMError("生成的大纲缺少九阶段结构")
        data.setdefault("name", name)
        data.setdefault("goal", f"从0掌握 {name}")
        data.setdefault("capstone", dict(FALLBACK_CAPSTONE, name=f"{name} 实战项目"))
        data["generated"] = "llm"
        return data
    except Exception:
        return _fallback_curriculum(lang)


def ensure_curriculum(lang: str) -> dict:
    """内置课程优先；其余语言动态生成并缓存（学习即建档）。"""
    if lang in CURRICULUM:
        return CURRICULUM[lang]
    cache = _curriculum_cache(lang)
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass
    cur = _generate_curriculum(lang)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    return cur


def _flatten(c: dict) -> list:
    """按阶段顺序展平 topics。"""
    out = []
    for stage, topics in c["stages"].items():
        out += list(topics)
    return out


def _stage_of(c: dict, topic: str) -> str:
    for stage, topics in c["stages"].items():
        if topic in topics:
            return stage
    return ""


class LearningModule:
    def __init__(self):
        self.r = router()

    # ---------- 进度持久化 ----------
    def _progress_path(self) -> Path:
        return data_dir() / PROGRESS_FILE

    def _load_progress(self) -> dict:
        p = self._progress_path()
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_progress(self, prog: dict):
        self._progress_path().write_text(json.dumps(prog, ensure_ascii=False, indent=2),
                                         encoding="utf-8")

    def _mark_learned(self, lang: str, topic: str):
        prog = self._load_progress()
        entry = prog.setdefault(lang, {"learned": [], "quiz": {}, "updated": ""})
        if topic not in entry["learned"]:
            entry["learned"].append(topic)
        entry["updated"] = time.strftime("%Y-%m-%d %H:%M")
        self._save_progress(prog)

    def _mark_quiz(self, lang: str, topic: str):
        prog = self._load_progress()
        entry = prog.setdefault(lang, {"learned": [], "quiz": {}, "updated": ""})
        entry["quiz"][topic] = time.strftime("%Y-%m-%d %H:%M")
        self._save_progress(prog)

    # ---------- 课程与路径 ----------
    def curriculum(self, lang: str) -> dict:
        """内置课程优先，其余语言按九阶段框架动态生成（绝不拒绝）。"""
        return ensure_curriculum(lang)

    def languages(self) -> dict:
        """语言矩阵：内置详纲 + 目录中其余语言。"""
        return {**{k: c["name"] for k, c in CURRICULUM.items()}, **CATALOG}

    def matrix(self) -> dict:
        """语言对照矩阵（规范要求）：各语言进度与阶段分布。
        未学过的语言不触发生成（避免批量 LLM 调用）。"""
        prog = self._load_progress()
        out = {}
        for lang, name in self.languages().items():
            cached = lang in CURRICULUM or _curriculum_cache(lang).exists()
            learned = prog.get(lang, {}).get("learned", [])
            if cached:
                total = len(self.flat_topics(lang))
                pct = round(len(learned) / total * 100) if total else 0
            elif learned:
                total = max(len(learned), 1)
                pct = min(99, len(learned) * 10)
            else:
                total = 0
                pct = 0
            out[lang] = {"name": name, "learned": len(learned), "total": total,
                         "pct": pct, "updated": prog.get(lang, {}).get("updated", "")}
        return out

    def radar(self) -> str:
        """能力雷达：各语言掌握度条形图。"""
        m = self.matrix()
        lines = ["【语言能力雷达】"]
        for lang, v in sorted(m.items(), key=lambda kv: -kv[1]["pct"]):
            if v["total"] == 0:
                lines.append(f"{v['name']:<14} ─ 未开始")
                continue
            bar = "█" * (v["pct"] // 5) + "░" * (20 - v["pct"] // 5)
            lines.append(f"{v['name']:<14} {bar} {v['pct']:>3}%  ({v['learned']}/{v['total']})")
        return "\n".join(lines)

    def flat_topics(self, lang: str) -> list:
        return _flatten(self.curriculum(lang))

    def next_topic(self, lang: str):
        """引导式学习：返回第一个未学的主题(可能为None=全学完)。"""
        learned = set(self._load_progress().get(lang, {}).get("learned", []))
        for t in self.flat_topics(lang):
            if t not in learned:
                return t
        return None

    def path(self, lang: str) -> str:
        """渲染学习路径（含进度标记）。"""
        c = self.curriculum(lang)
        learned = set(self._load_progress().get(lang, {}).get("learned", []))
        lines = [f"【{c['name']} 学习路径】目标: {c['goal']}",
                 f"运行环境: {c['runner'] or '教程+AI审查(本机无编译器)'}", ""]
        done_n = 0
        total = 0
        for stage, topics in c["stages"].items():
            marks = []
            for t in topics:
                total += 1
                if t in learned:
                    done_n += 1
                    marks.append(f"✓{t}")
                else:
                    marks.append(f"○{t}")
            stage_done = sum(1 for t in topics if t in learned)
            lines.append(f"■ {stage}  [{stage_done}/{len(topics)}]")
            lines.append("   " + "  ".join(marks))
        pct = done_n / total * 100 if total else 0
        lines.append("")
        lines.append(f"总进度: {done_n}/{total} ({pct:.0f}%)")
        nxt = self.next_topic(lang)
        lines.append("下一课: " + (nxt if nxt else "全部完成！试试 `capstone` 进阶实战项目 →"))
        return "\n".join(lines)

    # ---------- 学习 ----------
    def learn(self, lang: str, topic: str = None, use_web: bool = True) -> str:
        """学习一个主题（topic 为空时进入引导式：自动学下一课）。
        含前置知识回顾、网络资料参考、教程生成、知识库沉淀、进度记录。
        """
        c = self.curriculum(lang)
        if topic is None:
            topic = self.next_topic(lang)
            if topic is None:
                return "全部课程已学完！运行 capstone(lang) 开始进阶实战项目。"
        stage = _stage_of(c, topic)
        learned = self._load_progress().get(lang, {}).get("learned", [])
        prereq = "、".join(learned[-4:]) if learned else "（无，这是第一课）"
        ctx_kb = kb().context_for(f"{lang} {topic}", k=3)
        web_ctx = ""
        if use_web:
            try:
                hits = websearch.search(f"{lang} {topic} 教程 要点 易错点")
                pages = []
                for h in hits[:2]:
                    try:
                        pages.append(h["title"] + ": " + websearch.fetch_text(h["url"], 2500))
                    except Exception:
                        continue
                web_ctx = "\n".join(pages)[:3500]
            except Exception:
                web_ctx = ""
        prompt = f"""你是零基础编程教练。学员正在按阶段路径学习「{c['name']}」，当前课程：

【阶段】{stage or '自定义'}
【本课主题】{topic}
【已学前置课程】{prereq}

已有知识库参考：
{ctx_kb or '（无）'}

网络资料摘要（参考，注意甄别）：
{web_ctx or '（无）'}

请编写零基础友好的课程（Markdown），假设学员刚学完前置课程：
1. 本课目标（3条以内，学完能做什么）
2. 概念讲解（循序渐进、多打比方、解释"为什么"）
3. 3个由浅入深的完整示例（{c['runner'] or '目标语言'}代码，可运行、注释清楚、注意资源释放）
4. 常用函数/调用速查表（表格：函数|签名|用途|最小示例）
5. 5个新手易错点（错误写法 vs 正确写法）
6. 本课小练习（2题，附答案）"""
        text = self.r.ask(prompt, deep=True)
        safe = topic.replace("/", "_").replace(" ", "_")
        # 规范目录: languages/{lang}/{阶段}/{主题}.md
        stage_dir = re.sub(r"[^\w\u4e00-\u9fff]+", "_", stage or "custom")[:40]
        out_dir = data_dir() / "languages" / lang / stage_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{safe}.md"
        path.write_text(text, encoding="utf-8", errors="replace")
        # 学习即训练：沉淀知识库并重建索引
        stats = kb().train([{"id": f"learn:{lang}:{topic}:{time.strftime('%Y%m%d')}",
                             "title": f"{c['name']} {topic}",
                             "lang": lang, "tags": ["learn", stage or "custom", topic],
                             "text": text, "source": str(path)}])
        self._mark_learned(lang, topic)
        nxt = self.next_topic(lang)
        tail = f"\n\n---\n✅ 已完成并记录进度。教程: {path}\n知识库: {stats}\n下一课: {nxt or '全部完成，进阶实战见 capstone'}"
        return text + tail

    def quiz(self, lang: str, topic: str, n: int = 3) -> dict:
        """生成测验（出题+参考答案+评分标准），并记录进度。"""
        c = self.curriculum(lang)
        data = self.r.ask_json(f"""为「{c['name']} - {topic}」出 {n} 道测验题
（2道概念选择题+1道编程题，难度贴合零基础到进阶学员）。输出 JSON：
{{"questions": [{{"type": "choice|code", "question": "...", "options": ["A...","B..."],
"answer": "正确选项或参考代码", "explain": "解析"}}]}}""", deep=True)
        out_dir = outputs_dir() / "learning"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = topic.replace("/", "_")
        (out_dir / f"quiz_{lang}_{safe}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", errors="replace")
        self._mark_quiz(lang, topic)
        return data

    def review(self, lang: str) -> str:
        """阶段复习：串讲已学主题 + 出综合练习。"""
        c = self.curriculum(lang)
        learned = self._load_progress().get(lang, {}).get("learned", [])
        if not learned:
            return "还没有学习记录，先用 `start` 从第一课开始。"
        text = self.r.ask(f"""学员已学习「{c['name']}」以下课程：
{json.dumps(learned, ensure_ascii=False)}

请生成阶段复习资料（Markdown）：
1. 知识串讲：把已学主题组织成知识地图（哪些概念互相关联）
2. 高频混淆点对比（表格）
3. 综合练习 3 题（跨主题结合，附答案与解析）
4. 检验清单：认为自己掌握的标准""", deep=True)
        out = outputs_dir() / "learning" / f"review_{lang}_{time.strftime('%Y%m%d_%H%M')}.md"
        out.write_text(text, encoding="utf-8", errors="replace")
        return text + f"\n\n---\n复习资料已保存: {out}"

    def cheatsheet(self, lang: str, topic: str = "常用函数") -> str:
        """生成函数调用速查表并沉淀知识库。"""
        c = self.curriculum(lang)
        text = self.r.ask(f"""生成 {c['name']}「{topic}」速查表。
Markdown 表格（函数/方法 | 签名 | 用途 | 最小示例），至少 25 条，覆盖最常用的调用。
只输出表格与一句主题说明。""", deep=True)
        kb().train([{"id": f"cheat:{lang}:{topic}",
                     "title": f"{lang} {topic} 速查",
                     "lang": lang, "tags": ["cheatsheet"], "text": text,
                     "source": "cheatsheet"}])
        return text

    # ---------- 进阶实战：学以致用 ----------
    def capstone(self, lang: str, log_fn=None) -> dict:
        """进阶实战项目：Agent 依据已学内容自主完成前后端/算法项目开发。
        走完整质量工作流（思考→计划→审查→开发→测试），产物落盘 data/outputs/projects/。
        """
        c = self.curriculum(lang)
        cap = c["capstone"]
        learned = self._load_progress().get(lang, {}).get("learned", [])
        learned_str = "、".join(learned[-12:]) if learned else "（尚无学习记录，按零基础标准交付）"
        from core.workflow import Workflow
        task = f"完成「{c['name']}」进阶实战项目：{cap['name']}"
        context = f"""【项目要求】{cap['desc']}
【学员已学课程】{learned_str}
【交付标准】
1. 项目完整可运行，文件结构清晰（后端/前端或单程序均可）
2. 使用已学知识即可理解，不引入超纲复杂框架
3. 必须附自测代码或测试脚本，运行能证明功能正确
4. 资源管理规范：文件 with、并发有保护、网络请求有 timeout
5. 附 README 说明启动方式
【范围控制（重要）】
- 只实现上述要求的最小可用版本，严禁超出范围自行加需求
- 认证/JWT/权限/分页/连接池等企业级特性一律不做（如涉及用户，用固定演示用户即可）
- 宁可功能少但每个功能都正确可运行、可测试"""
        wf = Workflow(task, kind="project", context=context, log_fn=log_fn)
        res = wf.run()
        res["capstone"] = cap["name"]
        return res


def run_learn(lang: str, topic: str = None):
    return LearningModule().learn(lang, topic)
