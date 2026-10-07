# -*- coding: utf-8 -*-
"""前后端开发工具箱：

- 工具注册表 + LLM function-calling 循环（qwen3 原生支持 tools）
- 后端/前端/全栈项目脚手架生成
- 生成后自动做代码体检（语法 + 泄漏启发式）
"""
import json
from pathlib import Path

from core import codecheck, websearch
from core.config import outputs_dir
from core.knowledge import kb
from core.llm import router

# ---------------- 工具注册表（函数调用能力） ----------------
TOOLS = [
    {"type": "function", "function": {
        "name": "web_search", "description": "联网搜索编程资料/文档/题解，返回标题、链接与摘要",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "kb_search", "description": "在本地知识库中检索已学习的教程/速查表",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "run_python", "description": "运行一段 Python 代码并返回输出（带超时保护）",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "check_code", "description": "对 Python 代码做体检：语法、逻辑隐患、内存泄漏模式",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "list_problems", "description": "列出内置力扣题库",
        "parameters": {"type": "object", "properties": {
            "difficulty": {"type": "string", "enum": ["简单", "中等", "困难"]}}}}},
    {"type": "function", "function": {
        "name": "mysql_query", "description": "在本地 MySQL/MariaDB 上执行一条 SQL（SELECT/SHOW 返回数据，DML 返回受影响行数；禁止 DROP DATABASE）",
        "parameters": {"type": "object", "properties": {
            "sql": {"type": "string"}, "database": {"type": "string"}}, "required": ["sql"]}}},
    {"type": "function", "function": {
        "name": "mysql_schema", "description": "查看本地 MySQL 某数据库中所有表及其字段",
        "parameters": {"type": "object", "properties": {
            "database": {"type": "string"}}, "required": ["database"]}}},
]


def dispatch_tool(name: str, **kw):
    if name == "web_search":
        return websearch.search(kw["query"])
    if name == "kb_search":
        return kb().search(kw["query"], k=3)
    if name == "run_python":
        r = codecheck.run_python_code(kw["code"], timeout=10)
        return {"ok": r["ok"], "output": r["output"][:1500], "error": r["error"]}
    if name == "check_code":
        return codecheck.full_check(kw["code"], "python")
    if name == "list_problems":
        return [{"slug": p["slug"], "title": p["title"], "difficulty": p["difficulty"]}
                for p in __import__("modules.leetcode", fromlist=["PROBLEMS"]).PROBLEMS]
    if name == "mysql_query":
        from core.db import db
        return db().query(kw.get("sql", ""), kw.get("database"))
    if name == "mysql_schema":
        from core.db import db
        return db().schema(kw["database"])
    return {"error": f"未知工具 {name}"}


def tool_loop(user_prompt: str, max_iters: int = 4) -> str:
    """LLM function-calling 主循环：模型选择工具 -> 本地执行 -> 结果回填 -> 继续推理。"""
    r = router()
    lm = r.local
    messages = [
        {"role": "system", "content": "你是 learn-agent 编程助手，可调用工具检索资料、运行和检查代码。"
                                      "回答用中文，先给结论再给细节。"},
        {"role": "user", "content": user_prompt},
    ]
    import requests
    for i in range(max_iters):
        resp = requests.post(lm["base_url"] + "/api/chat", json={
            "model": lm["fast_model"], "messages": messages, "stream": False,
            "think": False, "tools": TOOLS,
            "options": {"temperature": 0.3, "num_ctx": lm.get("num_ctx", 8192)},
        }, timeout=180)
        resp.raise_for_status()
        msg = resp.json().get("message", {})
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content", "")
        messages.append({"role": "assistant", "content": msg.get("content", ""),
                         "tool_calls": calls})
        for c in calls:
            fn = c["function"]
            self_name = fn["name"]
            try:
                args = fn.get("arguments", {})
                args = args if isinstance(args, dict) else json.loads(args or "{}")
                result = dispatch_tool(self_name, **args)
            except Exception as e:
                result = {"error": str(e)}
            messages.append({"role": "tool", "content": json.dumps(
                result, ensure_ascii=False, default=str)[:4000]})
    return "（达到工具调用轮次上限）" + r.ask("请基于以上工具结果总结回答。")


# ---------------- 项目脚手架 ----------------
_BACKEND_TPL = {
    "fastapi": {
        "main.py": '''# -*- coding: utf-8 -*-
"""FastAPI 服务骨架（learn-agent 生成）"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="{name}")


class Item(BaseModel):
    name: str
    value: int


DB = {}  # 演示用内存存储；生产请换 SQLite/SQLAlchemy


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/items")
def list_items():
    return [{"id": k, **v} for k, v in DB.items()]


@app.post("/api/items")
def create_item(item: Item):
    item_id = str(len(DB) + 1)
    DB[item_id] = item.model_dump()
    return {"id": item_id}


@app.put("/api/items/{item_id}")
def update_item(item_id: str, item: Item):
    if item_id not in DB:
        raise HTTPException(404, "not found")
    DB[item_id] = item.model_dump()
    return {"ok": True}


@app.delete("/api/items/{item_id}")
def delete_item(item_id: str):
    return {"deleted": DB.pop(item_id, None) is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
''',
        "requirements.txt": "fastapi\nuvicorn\npydantic\n",
        "README.md": "# {name}\n\n启动: `uvicorn main:app --reload`\n\n接口: /api/health /api/items CRUD\n",
    },
    "flask": {
        "app.py": '''# -*- coding: utf-8 -*-
"""Flask 服务骨架（learn-agent 生成）"""
from flask import Flask, jsonify, request

app = Flask(__name__)
DB = {}


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/items")
def list_items():
    return jsonify([{"id": k, **v} for k, v in DB.items()])


@app.post("/api/items")
def create_item():
    data = request.get_json(force=True)
    if not data.get("name"):
        return jsonify(error="name required"), 400
    item_id = str(len(DB) + 1)
    DB[item_id] = {"name": data["name"], "value": data.get("value", 0)}
    return jsonify(id=item_id), 201


if __name__ == "__main__":
    app.run(port=5000, debug=True)
''',
        "requirements.txt": "flask\n",
    },
    "express": {
        "server.js": '''// Express 服务骨架（learn-agent 生成）
const express = require('express');
const app = express();
app.use(express.json());

const DB = new Map();

app.get('/api/health', (_req, res) => res.json({ status: 'ok' }));

app.get('/api/items', (_req, res) => {
  res.json([...DB.entries()].map(([id, v]) => ({ id, ...v })));
});

app.post('/api/items', (req, res) => {
  const { name } = req.body || {};
  if (!name) return res.status(400).json({ error: 'name required' });
  const id = String(DB.size + 1);
  DB.set(id, { name, value: req.body.value || 0 });
  res.status(201).json({ id });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`listening on ${PORT}`));
''',
        "package.json": '{\n  "name": "{name}",\n  "main": "server.js",\n  "scripts": {"start": "node server.js"},\n  "dependencies": {"express": "^4.19.0"}\n}\n',
    },
}

_FRONTEND_TPL = {
    "index.html": '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; }}
  #list li {{ margin: 6px 0; }}
  .err {{ color: #c00; }}
</style>
</head>
<body>
<h1>{name}</h1>
<form id="f">
  <input id="name" placeholder="名称" required>
  <input id="value" type="number" placeholder="数值">
  <button type="submit">添加</button>
</form>
<p id="msg" class="err"></p>
<ul id="list"></ul>
<script src="app.js"></script>
</body>
</html>
''',
    "app.js": '''// learn-agent 生成的前端逻辑：Fetch + 渲染
const API = location.origin.includes(':8000') ? 'http://127.0.0.1:8000' : '';

async function load() {
  try {
    const res = await fetch(API + '/api/items');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const items = await res.json();
    document.getElementById('list').innerHTML =
      items.map(i => `<li>#${i.id} ${i.name} = ${i.value}</li>`).join('') || '<li>暂无数据</li>';
    document.getElementById('msg').textContent = '';
  } catch (e) {
    document.getElementById('msg').textContent = '加载失败: ' + e.message;
  }
}

document.getElementById('f').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('name').value.trim();
  const value = Number(document.getElementById('value').value || 0);
  try {
    const res = await fetch(API + '/api/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, value }),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    document.getElementById('f').reset();
    load();
  } catch (err) {
    document.getElementById('msg').textContent = '提交失败: ' + err.message;
  }
});

load();
''',
}


class DevToolkit:
    def scaffold(self, name: str, stack: str = "fastapi", frontend: bool = True) -> Path:
        stack = stack.lower()
        if stack not in _BACKEND_TPL:
            raise ValueError(f"支持的后端栈: {list(_BACKEND_TPL)}")
        proj = outputs_dir() / "projects" / name
        (proj / "backend").mkdir(parents=True, exist_ok=True)
        for fn, tpl in _BACKEND_TPL[stack].items():
            (proj / "backend" / fn).write_text(tpl.replace("{name}", name),
                                               encoding="utf-8")
        if frontend:
            (proj / "frontend").mkdir(exist_ok=True)
            for fn, tpl in _FRONTEND_TPL.items():
                (proj / "frontend" / fn).write_text(tpl.replace("{name}", name),
                                                    encoding="utf-8")
        # 生成后立即体检
        report = []
        for py in (proj / "backend").glob("*.py"):
            report += [f"[{py.name}] {i}" for i in
                       codecheck.full_check(py.read_text(encoding="utf-8"), "python")]
        for js in (proj / "frontend").glob("*.js"):
            report += [f"[{js.name}] {i}" for i in
                       codecheck.full_check(js.read_text(encoding="utf-8"), "javascript")]
        (proj / "check_report.txt").write_text(
            "\n".join(report) or "全部通过语法与启发式检查", encoding="utf-8")
        return proj

    def fullstack_demo(self, name: str = "demo-app") -> Path:
        """FastAPI + 原生前端 全栈示例，并自测 /api/health。"""
        proj = self.scaffold(name, "fastapi", frontend=True)
        import subprocess, time, requests, sys
        main = proj / "backend" / "main.py"
        proc = subprocess.Popen([sys.executable, str(main)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            ok = False
            for _ in range(20):
                time.sleep(0.5)
                try:
                    r = requests.get("http://127.0.0.1:8000/api/health", timeout=2)
                    ok = r.json().get("status") == "ok"
                    break
                except Exception:
                    continue
            (proj / "smoke_test.txt").write_text(
                "健康检查通过 http://127.0.0.1:8000/api/health" if ok
                else "健康检查失败，请查看进程输出", encoding="utf-8")
        finally:
            proc.terminate()
        return proj
