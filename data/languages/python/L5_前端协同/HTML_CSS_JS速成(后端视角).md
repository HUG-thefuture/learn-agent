# L5 前端协同：HTML/CSS/JS 速成（后端视角）

> **本课运行方式说明**：浏览器真正运行的是 HTML/CSS/JS，而本页的练习框在 Python 沙箱里运行。因此本课用 Python 帮你“生成并打印前端源码”，同时用 Python 模拟后端返回值、检查 XSS、模拟 DOM 等。你可以把打印出来的 HTML/CSS/JS 复制到本地 `.html` 文件中，用浏览器打开看真实效果。

## 1. 本课目标

- 能看懂并写出最小 HTML 结构，知道 `id`、`class`、标签嵌套和必须做 HTML 转义的原因。
- 能用 CSS 类选择器给状态设置样式，理解“结构、样式、行为分离”。
- 能写出 `querySelector + addEventListener + fetch` 的最小 JS 交互，并知道检查 `response.ok`、用 `textContent` 防 XSS。

## 2. 概念讲解：从后端视角看前端三件套

把浏览器想成一家餐厅的“前厅”，你的 Flask/FastAPI 后端是“后厨”。

- **HTML** 像菜单和桌椅布局：决定页面上有哪些内容、层级关系是什么。
- **CSS** 像装修和摆盘：决定颜色、间距、大小、响应式布局。
- **JS** 像服务员：用户点击按钮、输入文字、向后端要数据时，由它来响应。

后端可能返回两种东西：

1. **整页 HTML**：例如 Flask 的 `render_template`，浏览器收到就能显示。这叫服务端渲染。
2. **JSON + 静态页面**：例如 FastAPI 返回 `{"id": 1, "title": "买牛奶"}`，浏览器里的 JS 用 `fetch` 拿到 JSON，再更新页面。这叫前后端分离。

### 2.1 HTML：页面的骨架

HTML 由标签组成，标签可以嵌套，例如 `html > body > ul > li`。浏览器会把 HTML 解析成一棵 DOM 树，JS 之后就能在这棵树上查找、修改节点。

两个非常重要的属性：

- `id`：像身份证号，**同一页里应唯一**。JS 常用 `document.querySelector("#todo-list")` 找它。
- `class`：像分类标签，**可以重复**。多个元素可以共享样式，例如 `class="badge active"`。

为什么后端视角必须关心转义？因为用户输入可能包含 `<script>`。如果你直接把用户输入拼进 HTML，就可能发生 **XSS 跨站脚本攻击**。所以文本进入 HTML 前要用 `html.escape`；前端渲染不可信文本时优先用 `textContent`，不要随便用 `innerHTML`。

### 2.2 CSS：选择器和状态样式

CSS 的基本形式是：

- 选择器：选中谁，例如 `.badge`、`#todo-list`、`.badge.active`。
- 声明：改什么，例如 `background: #d1fae5; color: #065f46;`。

优先用 `class` 表达状态，例如未完成是 `class="badge pending"`，完成是 `class="badge done"`。这样 HTML 只负责“它是什么状态”，CSS 负责“这个状态长什么样”，JS 只负责“切换类名”，职责清楚，容易维护。

### 2.3 JS：DOM、事件和异步请求

JS 在浏览器里主要做三件事：

- **查 DOM**：`document.querySelector("#todo-list")`。注意它可能返回 `null`，所以要先判断元素是否存在。
- **绑事件**：`button.addEventListener("click", save)`。这里传的是函数对象 `save`，不是 `save()`；写成 `save()` 会立刻执行。
- **发请求**：`fetch("/api/todos")` 返回一个 Promise。用 `await` 等它完成，再用 `response.ok` 判断 HTTP 状态是否 2xx，最后 `await response.json()` 解析 JSON。

为什么不能拿到响应就直接 `.json()`？因为服务器 500 时可能返回的是 HTML 错误页，强行解析 JSON 会抛异常。正确顺序是：先看 `response.ok`，成功再解析 JSON。

### 2.4 后端协同与安全提醒

- API 返回 JSON 时，字段名、类型、状态码要稳定，例如 `title` 始终是字符串，成功用 200，创建成功可用 201，参数错误用 400，未登录用 401，无权限用 403。
- 前端验证只是体验优化，**后端必须再次验证**。
- 使用 Cookie 做认证时，要防 CSRF；跨域要正确配置 CORS；不要把数据库密码、密钥放进前端 JS。
- 前端显示用户内容时，默认不信任，优先 `textContent` 或后端 `html.escape`。

## 3. 由浅入深的 3 个完整示例

### 示例 1：后端安全地生成一张用户卡片 HTML

这个例子练习 HTML 结构、`id`/`class` 和 `html.escape`。

```python
from html import escape

def render_card(user: dict) -> str:
    # 后端视角：来自表单/数据库的文本默认不可信，进入 HTML 前要转义
    name = escape(str(user.get("name", "匿名用户")))
    bio = escape(str(user.get("bio", "")))
    # class 可复用；id 在本页应唯一
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>用户卡片</title>
</head>
<body>
  <article class="card" id="user-{int(user.get('id', 0))}">
    <h1>{name}</h1>
    <p class="bio">{bio}</p>
  </article>
</body>
</html>"""

user = {"id": 7, "name": "小明", "bio": "我喜欢 <Python> 和 \"Web\""}
html_doc = render_card(user)
print(html_doc)

# 额外自检：原始尖括号不应以标签形式进入 bio
assert "&lt;Python&gt;" in html_doc

# 预期输出（节选）：
# <!doctype html>
# <html lang="zh-CN">
# ...
# <article class="card" id="user-7">
#   <h1>小明</h1>
#   <p class="bio">我喜欢 &lt;Python&gt; 和 &quot;Web&quot;</p>
# </article>
```

### 示例 2：用 CSS 类表达待办状态

这个例子练习 CSS 选择器、类名组合和简单的响应式媒体查询。

```python
from html import escape

def render_page(items: list[dict]) -> str:
    rows = []
    for item in items:
        # done=True -> 添加 active 类；样式交给 CSS，而不是在 HTML 里写死颜色
        css_class = "badge active" if item["done"] else "badge"
        title = escape(item["title"])
        rows.append(
            f'<li class="todo"><span class="{css_class}">{title}</span></li>'
        )

    body = "\n    ".join(rows)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>待办</title>
  <style>
    .todo {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 8px 0;
    }}
    .badge {{
      padding: 2px 8px;
      border-radius: 999px;
      background: #eee;
      color: #333;
    }}
    .badge.active {{
      background: #d1fae5;
      color: #065f46;
    }}
    @media (max-width: 480px) {{
      .todo {{ font-size: 14px; }}
    }}
  </style>
</head>
<body>
  <h1>待办清单</h1>
  <ul>
    {body}
  </ul>
</body>
</html>"""

items = [
    {"title": "买牛奶", "done": False},
    {"title": "练习 <CSS>", "done": True},
]
html_doc = render_page(items)
print(html_doc)

print("\n--- 只看关键行 ---")
for line in html_doc.splitlines():
    if "badge" in line and "span" in line:
        print(line.strip())

# 预期输出（节选）：
# <!doctype html>
# <html lang="zh-CN">
# ...
# <li class="todo"><span class="badge">买牛奶</span></li>
# <li class="todo"><span class="badge active">练习 &lt;CSS&gt;</span></li>
# ...
# --- 只看关键行 ---
# <li class="todo"><span class="badge">买牛奶</span></li>
# <li class="todo"><span class="badge active">练习 &lt;CSS&gt;</span></li>
```

### 示例 3：生成一段带 `fetch` 的前端 JS

这个例子练习 DOM 查询、事件绑定、`fetch`、`response.ok` 和安全渲染。

```python
import json

def make_fetch_js(api_url: str, target_id: str) -> str:
    # 真实项目里，api_url 和 target_id 应由后端模板安全传入；
    # 这里示范前端最小交互：先检查元素，再 fetch，检查 response.ok，用 textContent 渲染。
    return f"""
async function loadTodos() {{
  const list = document.querySelector("#{target_id}");
  if (!list) return;

  try {{
    const response = await fetch("{api_url}", {{
      headers: {{ "Accept": "application/json" }},
      credentials: "same-origin"
    }});

    if (!response.ok) {{
      throw new Error(`HTTP ${{response.status}}`);
    }}

    const todos = await response.json();
    list.textContent = "";
    for (const todo of todos) {{
      const li = document.createElement("li");
      li.textContent = todo.title;  // 防 XSS：不要对不可信内容用 innerHTML
      li.dataset.id = todo.id;
      list.appendChild(li);
    }}
  }} catch (error) {{
    list.textContent = "加载失败：" + error.message;
  }}
}}

document.addEventListener("DOMContentLoaded", loadTodos);
""".strip()

# 模拟后端返回的 JSON（真实项目里由 FastAPI 的 JSONResponse 返回）
api_response = [
    {"id": 1, "title": "写 HTML", "done": False},
    {"id": 2, "title": "写 <JS>", "done": True},
]
print("后端 JSON：")
print(json.dumps(api_response, ensure_ascii=False))

print("\n前端 JS（会请求 /api/todos）：")
print(make_fetch_js("/api/todos", "todo-list"))

# 预期输出（节选）：
# 后端 JSON：
# [{"id": 1, "title": "写 HTML", "done": false}, {"id": 2, "title": "写 <JS>", "done": true}]
#
# 前端 JS（会请求 /api/todos）：
# async function loadTodos() {
#   const list = document.querySelector("#todo-list");
# ...
#     if (!response.ok) {
#       throw new Error(`HTTP ${response.status}`);
#     }
# ...
#       li.textContent = todo.title;  // 防 XSS：不要对不可信内容用 innerHTML
# ...
# }
# document.addEventListener("DOMContentLoaded", loadTodos);
```

## 4. 常用函数/调用速查表

| 函数/语法 | 签名/写法 | 用途 | 最小示例 |
|---|---|---|---|
| `html.escape` | `escape(s, quote=True)` | 把不可信文本转义后放入 HTML | `escape("<b>")` 得到 `&lt;b&gt;` |
| `id` / `class` | `<div id="x" class="a b">` | `id` 唯一，`class` 可重复复用 | `<ul id="todo-list" class="list">` |
| CSS 类选择器 | `.badge.active { ... }` | 选中同时含有两个类的元素 | `.done { color: green; }` |
| `document.querySelector` | `document.querySelector(selector)` | 找第一个匹配元素；可能为 `null` | `document.querySelector("#todo-list")` |
| `textContent` | `el.textContent = value` | 安全地写纯文本，降低 XSS 风险 | `li.textContent = todo.title` |
| `addEventListener` | `el.addEventListener(event, handler)` | 绑定事件；`handler` 传函数对象 | `btn.addEventListener("click", save)` |
| `fetch` | `await fetch(url, options)` | 异步请求后端 API，返回 Promise | `const r = await fetch("/api/todos")` |
| `response.ok` | `response.ok` / `response.status` | 判断 2xx 并处理错误 | `if (!response.ok) throw new Error(String(response.status))` |
| `response.json` | `await response.json()` | 把 JSON 响应体解析为对象/数组 | `const data = await response.json()` |
| `createElement` | `document.createElement(tag)` | 创建 DOM 节点 | `const li = document.createElement("li")` |
| `appendChild` | `parent.appendChild(child)` | 把节点挂到父节点 | `list.appendChild(li)` |
| `json.dumps` | `json.dumps(obj, ensure_ascii=False)` | 后端输出中文 JSON（调试/示例） | `json.dumps({"名": "小明"}, ensure_ascii=False)` |

## 5. 五个新手易错点

### 易错点1：把用户输入直接拼进 HTML，会给 XSS 留门

❌ **错误写法**

```python
def render_bio_unsafe(raw: str) -> str:
    return f"<p>{raw}</p>"

def must_not_contain_script(html_text: str) -> None:
    if "<script>" in html_text.lower():
        raise ValueError("XSS 风险：检测到未转义的 <script> 标签")

user_input = '<script>alert("xss")</script>'
html_text = render_bio_unsafe(user_input)
must_not_contain_script(html_text)
print(html_text)

# 运行报错：ValueError: XSS 风险：检测到未转义的 <script> 标签
```

✅ **正确写法**

```python
from html import escape

def render_bio_safe(raw: str) -> str:
    return f"<p>{escape(raw)}</p>"

def must_not_contain_script(html_text: str) -> None:
    if "<script>" in html_text.lower():
        raise ValueError("XSS 风险：检测到未转义的 <script> 标签")

user_input = '<script>alert("xss")</script>'
html_text = render_bio_safe(user_input)
must_not_contain_script(html_text)  # 通过：尖括号已转义
print(html_text)

# 预期输出：
# <p>&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;</p>
```

纠正要点：只要内容可能来自用户，就要把它当“文本”而不是“HTML 代码”处理，后端转义、前端优先 `textContent`。

### 易错点2：重复使用同一个 `id`，会让选择器和可维护性变差

❌ **错误写法**

```python
import re

html_doc = """
<div id="msg">第一条</div>
<div id="msg">第二条</div>
"""

ids = re.findall(r'id="([^"]+)"', html_doc)
if len(ids) != len(set(ids)):
    raise ValueError("HTML 中 id 重复：querySelector('#msg') 只会拿到第一个")
print("页面检查通过")

# 运行报错：ValueError: HTML 中 id 重复：querySelector('#msg') 只会拿到第一个
```

✅ **正确写法**

```python
import re

html_doc = """
<div id="msg-1" class="msg">第一条</div>
<div id="msg-2" class="msg">第二条</div>
"""

ids = re.findall(r'id="([^"]+)"', html_doc)
assert len(ids) == len(set(ids)), "id 必须唯一"
print("页面检查通过：", ids)
print("用 .msg 选择同类元素，用 #msg-1 选择唯一元素")

# 预期输出：
# 页面检查通过： ['msg-1', 'msg-2']
# 用 .msg 选择同类元素，用 #msg-1 选择唯一元素
```

纠正要点：`id` 用来唯一标识一个元素，`class` 用来给一组元素分类；不要用重复 `id` 当“批量选择器”。

### 易错点3：JS 查询到的元素可能不存在，直接访问属性会报错

❌ **错误写法**

```python
class FakeElement:
    def __init__(self, text_content: str):
        self.text_content = text_content

def query_selector(selector: str):
    # 模拟 document.querySelector("#not-found") 返回 null/None
    return None

el = query_selector("#not-found")
print(el.text_content)  # 直接访问

# 运行报错：AttributeError: 'NoneType' object has no attribute 'text_content'
# 真实浏览器里类似错误是：TypeError: Cannot read properties of null
```

✅ **正确写法**

```python
class FakeElement:
    def __init__(self, text_content: str):
        self.text_content = text_content

def query_selector(selector: str):
    if selector == "#found":
        return FakeElement("你好")
    return None

for selector in ["#found", "#missing"]:
    el = query_selector(selector)
    if el is not None:
        print(el.text_content)
    else:
        print(f"{selector} 不存在，已安全跳过")

# 预期输出：
# 你好
# #missing 不存在，已安全跳过
```

纠正要点：`querySelector` 找不到元素时返回 `null`，先判断元素存在，再操作它。

### 易错点4：`fetch` 收到 500 还直接 `.json()`，可能把页面搞崩

❌ **错误写法**

```python
import json

status_code = 500
body = "<h1>Internal Server Error</h1>"
# 模拟：没有检查 response.ok，直接 response.json()
data = json.loads(body)
print(data)

# 运行报错：json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

✅ **正确写法**

```python
import json

status_code = 500
body = "<h1>Internal Server Error</h1>"

if not (200 <= status_code < 300):
    print(f"请求失败：HTTP {status_code}，不解析 JSON，显示友好错误")
else:
    data = json.loads(body)
    print(data)

# 再模拟一次成功响应
status_code = 200
body = '{"items": [1, 2]}'
if 200 <= status_code < 300:
    data = json.loads(body)
    print("成功：", data["items"])

# 预期输出：
# 请求失败：HTTP 500，不解析 JSON，显示友好错误
# 成功： [1, 2]
```

纠正要点：先检查 `response.ok` 或状态码，再决定是否解析 JSON；错误分支要给用户可读提示。

### 易错点5：`addEventListener` 把函数写成 `fn()`，会立即执行而不是绑定

❌ **错误写法**

```python
def save():
    print("提交表单")
    return None

class Button:
    def add_event_listener(self, event: str, handler):
        if not callable(handler):
            raise TypeError("listener 必须是函数对象，不能是 undefined/None")
        self.handler = handler
        print(f"已绑定 {event}")

button = Button()
button.add_event_listener("click", save())  # 错：这里立刻执行了 save()
print("页面加载完成")

# 运行报错：TypeError: listener 必须是函数对象，不能是 undefined/None
```

✅ **正确写法**

```python
def save():
    print("提交表单")

class Button:
    def add_event_listener(self, event: str, handler):
        if not callable(handler):
            raise TypeError("listener 必须是函数对象，不能是 undefined/None")
        self.handler = handler
        print(f"已绑定 {event}")

button = Button()
button.add_event_listener("click", save)  # 对：传函数对象
button.handler()  # 模拟用户点击，此时才执行
print("页面加载完成")

# 预期输出：
# 已绑定 click
# 提交表单
# 页面加载完成
```

纠正要点：事件绑定要传“函数本身”，不要加括号调用；`save` 是函数对象，`save()` 是立刻执行后的返回值。

## 6. 本课小练习

### 练习1：安全地生成用户资料卡片

- **目标**：掌握 `html.escape`、`id` 唯一性和 `class` 复用。
- **引导步骤**：
  1. 对 `nickname` 和 `bio` 调用 `escape`，分别得到 `safe_nickname`、`safe_bio`。
  2. 把 `article` 的 `id` 改成 `profile-9` 这种形式，把 `class` 写成 `profile card`。
  3. 运行后检查输出里是否出现 `&lt;`、`&quot;`，而不是原始 `<`、`"`。
- **起步代码**

```python
from html import escape

def render_profile(uid: int, nickname: str, bio: str) -> str:
    # TODO 1：对 nickname 和 bio 做 HTML 转义
    safe_nickname = nickname
    safe_bio = bio
    # TODO 2：补全 id 和 class（id 要包含 uid，class 用 profile card）
    return f"""<article id="TODO" class="TODO">
  <h2>{safe_nickname}</h2>
  <p>{safe_bio}</p>
</article>"""

user = {
    "id": 9,
    "nickname": '小<研>',
    "bio": '喜欢 "API" & <JS>',
}
print(render_profile(user["id"], user["nickname"], user["bio"]))

# 预期输出（补全后）：
# <article id="profile-9" class="profile card">
#   <h2>小&lt;研&gt;</h2>
#   <p>喜欢 &quot;API&quot; &amp; &lt;JS&gt;</p>
# </article>
```

- **预期输出**：补全后运行，应看到 `id="profile-9"`、`class="profile card"`，并且昵称和简介中的特殊字符被转义。

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
from html import escape

def render_profile(uid: int, nickname: str, bio: str) -> str:
    safe_nickname = escape(nickname)
    safe_bio = escape(bio)
    return f"""<article id="profile-{uid}" class="profile card">
  <h2>{safe_nickname}</h2>
  <p>{safe_bio}</p>
</article>"""

user = {
    "id": 9,
    "nickname": '小<研>',
    "bio": '喜欢 "API" & <JS>',
}
print(render_profile(user["id"], user["nickname"], user["bio"]))

# 预期输出：
# <article id="profile-9" class="profile card">
#   <h2>小&lt;研&gt;</h2>
#   <p>喜欢 &quot;API&quot; &amp; &lt;JS&gt;</p>
# </article>
```

</details>

### 练习2：用 CSS 类切换待办状态

- **目标**：理解“状态类 + CSS 规则”的配合方式。
- **引导步骤**：
  1. 补全 `status_class`：完成返回 `"badge done"`，未完成返回 `"badge pending"`。
  2. 在 `<style>` 中给 `.pending` 补上背景色和文字颜色。
  3. 运行后看两个 `<span>` 的 `class` 是否分别是 `badge pending` 和 `badge done`。
- **起步代码**

```python
from html import escape

def status_class(done: bool) -> str:
    # TODO：完成的返回 "badge done"，未完成返回 "badge pending"
    return "badge"

def render_tasks(tasks: list[dict]) -> str:
    rows = []
    for task in tasks:
        cls = status_class(bool(task["done"]))
        title = escape(task["title"])
        rows.append(f'<li><span class="{cls}">{title}</span></li>')
    body = "\n".join(rows)
    return f"""<ul>
{body}
</ul>
<style>
  .badge {{ padding: 2px 8px; border-radius: 999px; }}
  .done {{ background: #d1fae5; color: #065f46; }}
  /* TODO：补全 .pending 的 background 和 color */
  .pending {{ }}
</style>"""

tasks = [
    {"title": "写 HTML", "done": False},
    {"title": "检查 <CSS>", "done": True},
]
print(render_tasks(tasks))

# 预期输出（补全后，关键行）：
# <li><span class="badge pending">写 HTML</span></li>
# <li><span class="badge done">检查 &lt;CSS&gt;</span></li>
# 以及 .pending 规则中出现 background 和 color
```

- **预期输出**：未完成项使用 `badge pending`，完成项使用 `badge done`；`.pending` 规则中出现背景色和文字颜色。

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
from html import escape

def status_class(done: bool) -> str:
    return "badge done" if done else "badge pending"

def render_tasks(tasks: list[dict]) -> str:
    rows = []
    for task in tasks:
        cls = status_class(bool(task["done"]))
        title = escape(task["title"])
        rows.append(f'<li><span class="{cls}">{title}</span></li>')
    body = "\n".join(rows)
    return f"""<ul>
{body}
</ul>
<style>
  .badge {{ padding: 2px 8px; border-radius: 999px; }}
  .done {{ background: #d1fae5; color: #065f46; }}
  .pending {{ background: #fef3c7; color: #92400e; }}
</style>"""

tasks = [
    {"title": "写 HTML", "done": False},
    {"title": "检查 <CSS>", "done": True},
]
print(render_tasks(tasks))

# 预期输出（节选）：
# <ul>
# <li><span class="badge pending">写 HTML</span></li>
# <li><span class="badge done">检查 &lt;CSS&gt;</span></li>
# </ul>
# <style>
#   .badge { padding: 2px 8px; border-radius: 999px; }
#   .done { background: #d1fae5; color: #065f46; }
#   .pending { background: #fef3c7; color: #92400e; }
# </style>
```

</details>

### 练习3：补全一段安全的 `fetch` 前端 JS

- **目标**：掌握 `response.ok` 检查、JSON 解析和 `textContent` 渲染。
- **引导步骤**：
  1. 在解析 JSON 之前，补上 `if (!response.ok) throw new Error("HTTP " + response.status);`。
  2. 解析出 `items` 后，清空列表，并用 `for...of` 为每条数据创建 `li`。
  3. 用 `li.textContent = item.title` 写入文本，再 `list.appendChild(li)`。
- **起步代码**

```python
def make_loader_js(target_id: str, api_url: str) -> str:
    return f"""
async function loadItems() {{
  const list = document.querySelector("#{target_id}");
  if (!list) {{
    console.warn("找不到列表容器");
    return;
  }}

  try {{
    const response = await fetch("{api_url}", {{
      headers: {{ "Accept": "application/json" }},
      credentials: "same-origin"
    }});

    // TODO 1：在解析 JSON 前，先检查 response.ok；失败时 throw new Error(...)

    const items = await response.json();

    // TODO 2：清空 list，用 for...of 创建 li，li.textContent = item.title，再 appendChild
    list.textContent = "TODO：补全渲染逻辑";
  }} catch (error) {{
    list.textContent = "加载失败：" + error.message;
  }}
}}

document.addEventListener("DOMContentLoaded", loadItems);
""".strip()

print(make_loader_js("item-list", "/api/items"))

# 预期输出（补全后，节选）：
# async function loadItems() {
#   const list = document.querySelector("#item-list");
# ...
#     if (!response.ok) throw new Error("HTTP " + response.status);
#     const items = await response.json();
#     list.textContent = "";
#     for (const item of items) {
#       const li = document.createElement("li");
#       li.textContent = item.title;
#       list.appendChild(li);
#     }
# ...
# }
# document.addEventListener("DOMContentLoaded", loadItems);
```

- **预期输出**：补全后运行，会打印出完整 JS 源码；其中应能看到 `response.ok` 检查、`await response.json()`、`textContent` 和 `appendChild`。

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
def make_loader_js(target_id: str, api_url: str) -> str:
    return f"""
async function loadItems() {{
  const list = document.querySelector("#{target_id}");
  if (!list) {{
    console.warn("找不到列表容器");
    return;
  }}

  try {{
    const response = await fetch("{api_url}", {{
      headers: {{ "Accept": "application/json" }},
      credentials: "same-origin"
    }});

    if (!response.ok) {{
      throw new Error("HTTP " + response.status);
    }}

    const items = await response.json();
    list.textContent = "";
    for (const item of items) {{
      const li = document.createElement("li");
      li.textContent = item.title;
      list.appendChild(li);
    }}
  }} catch (error) {{
    list.textContent = "加载失败：" + error.message;
  }}
}}

document.addEventListener("DOMContentLoaded", loadItems);
""".strip()

print(make_loader_js("item-list", "/api/items"))

# 预期输出（节选）：
# async function loadItems() {
#   const list = document.querySelector("#item-list");
# ...
#     if (!response.ok) {
#       throw new Error("HTTP " + response.status);
#     }
#     const items = await response.json();
#     list.textContent = "";
#     for (const item of items) {
#       const li = document.createElement("li");
#       li.textContent = item.title;
#       list.appendChild(li);
#     }
# ...
# }
# document.addEventListener("DOMContentLoaded", loadItems);
```

</details>

## 7. 本课小结

- HTML 负责结构和语义：`id` 唯一、`class` 可复用，不可信文本必须转义。
- CSS 用选择器表达样式，最好用 `class` 表达状态，例如 `.done`、`.pending`，避免到处写内联样式。
- JS 用 `querySelector` 查 DOM、`addEventListener` 绑事件、`fetch` 调 API；注意元素可能为 `null`。
- `fetch` 后先判断 `response.ok`，再 `response.json()`；渲染不可信文本优先 `textContent`。
- 后端视角要守住契约与安全：字段稳定、状态码清楚、后端二次校验、防 XSS/CSRF，不把密钥放前端。

下一课建议：把本课的静态页面接入 Flask/FastAPI 模板或真实 JSON API，并为登录后的写操作补上 CSRF 防护与更完整的错误提示。