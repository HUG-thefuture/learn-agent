# -*- coding: utf-8 -*-
"""学习模块：编程语言学习路径、教程生成、测验、常用函数速查。

"学习即训练"：每次 learn 产出的教程自动沉淀进知识库（TF-IDF 重建索引）。
"""
import json
import time
from pathlib import Path

from core.config import outputs_dir
from core.llm import router
from core.knowledge import kb
from core import websearch

# 语言学习大纲（默认课程，可被 LLM 扩展）
CURRICULUM = {
    "python": {
        "name": "Python",
        "topics": ["基础语法与数据类型", "列表/字典/集合推导式", "函数与装饰器",
                   "类与面向对象", "迭代器与生成器", "异常处理与调试",
                   "文件IO与with语句", "标准库常用模块(collections/itertools/os)",
                   "并发 threading/multiprocessing", "异步 asyncio",
                   "单元测试 unittest/pytest", "性能优化与内存管理"],
        "backend": "后端方向：Flask/FastAPI 路由、请求校验、SQLAlchemy/SQLite、RESTful 设计、部署",
        "frontend": "辅助前端：Jinja2 模板、静态资源、CORS、与前端 API 联调",
    },
    "javascript": {
        "name": "JavaScript",
        "topics": ["基础语法与类型", "数组高阶函数(map/filter/reduce)", "函数/闭包/this",
                   "原型与 class", "Promise 与 async/await", "DOM 操作与事件",
                   "ES6+ 模块化 import/export", "Fetch 与网络请求",
                   "错误处理与调试", "前端框架入门(React/Vue 概念)",
                   "Node.js 基础与 npm", "Express 后端开发"],
        "backend": "后端方向：Node.js + Express/Koa、REST API、中间件、文件操作",
        "frontend": "前端方向：DOM/事件/渲染、Fetch、组件化思想、简单 SPA",
    },
    "java": {
        "name": "Java",
        "topics": ["基础语法与面向对象", "集合框架 List/Map/Set", "泛型",
                   "异常体系", "IO 与 try-with-resources", "多线程与线程安全",
                   "JVM 内存模型与 GC", "Lambda 与 Stream", "Spring Boot 入门",
                   "MySQL 与 JDBC", "单元测试 JUnit", "常见设计模式"],
        "backend": "后端方向：Spring Boot MVC、MyBatis、RESTful、事务",
        "frontend": "辅助前端：Thymeleaf、REST 接口设计、跨域配置",
    },
}


class LearningModule:
    def __init__(self):
        self.r = router()

    def curriculum(self, lang: str) -> dict:
        c = CURRICULUM.get(lang)
        if not c:
            raise ValueError(f"暂未内置 {lang} 大纲，可选: {list(CURRICULUM)}")
        return c

    def learn(self, lang: str, topic: str, use_web: bool = True) -> str:
        """学习一个主题：知识库检索 + 网络数据 + LLM 生成教程 -> 沉淀知识库。"""
        c = self.curriculum(lang)
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
        prompt = f"""你是编程教练。请为「{c['name']} - {topic}」编写一份高质量学习教程。

已有知识库参考：
{ctx_kb or '（无）'}

网络资料摘要（可选参考，注意甄别正确性）：
{web_ctx or '（无）'}

方向补充：{c['backend']}

要求输出 Markdown，包含：
1. 核心概念讲解（简洁准确，含内存/性能注意点）
2. 3个由浅入深的代码示例（完整可运行，注意资源释放）
3. 常用函数/调用速查表（表格：函数|签名|说明|示例）——这是重点，便于函数调用记忆
4. 5个易错点（含错误示例与正确写法）
5. 3道自测练习题（附答案）"""
        text = self.r.ask(prompt, deep=True)
        title = f"{lang}:{topic}"
        path = outputs_dir() / "learning" / f"{lang}_{topic.replace('/', '_').replace(' ', '_')}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", errors="replace")
        # 学习即训练：沉淀知识库并重建索引
        stats = kb().train([{"id": f"learn:{title}:{time.strftime('%Y%m%d')}",
                             "title": f"{c['name']} {topic}",
                             "lang": lang,
                             "tags": ["learn", lang, topic],
                             "text": text,
                             "source": str(path)}])
        return f"教程已生成: {path}\n知识库已更新: {stats}"

    def quiz(self, lang: str, topic: str, n: int = 3) -> dict:
        """生成测验（出题+参考答案+评分标准）。"""
        data = self.r.ask_json(f"""为「{CURRICULUM.get(lang, {}).get('name', lang)} - {topic}」出 {n} 道测验题
（2道概念选择题+1道编程题）。输出 JSON：
{{"questions": [{{"type": "choice|code", "question": "...", "options": ["A...","B..."],
"answer": "正确选项或参考代码", "explain": "解析"}}]}}""", deep=True)
        path = outputs_dir() / "learning" / f"quiz_{lang}_{topic.replace('/', '_')}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8", errors="replace")
        return data

    def cheatsheet(self, lang: str, topic: str = "常用函数") -> str:
        """生成函数调用速查表并沉淀知识库。"""
        text = self.r.ask(f"""生成 {CURRICULUM.get(lang, {}).get('name', lang)}「{topic}」速查表。
Markdown 表格（函数/方法 | 签名 | 用途 | 最小示例），至少 25 条，覆盖最常用的调用。
只输出表格与一句主题说明。""", deep=True)
        kb().train([{"id": f"cheat:{lang}:{topic}",
                     "title": f"{lang} {topic} 速查",
                     "lang": lang, "tags": ["cheatsheet"], "text": text,
                     "source": "cheatsheet"}])
        return text


def run_learn(lang: str, topic: str):
    return LearningModule().learn(lang, topic)
