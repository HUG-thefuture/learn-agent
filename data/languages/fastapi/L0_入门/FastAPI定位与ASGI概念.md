# L0 入门 · 第1课：FastAPI 定位与 ASGI 概念

---

## 一、本课目标

学完本课，你将能够：

1. **说清楚 FastAPI 是什么、为什么用它**（定位、特点、对比其他框架）
2. **理解 ASGI 是什么**，能用自己的话讲出它和 WSGI 的区别（为什么 FastAPI 能"快"）
3. **跑通第一个 FastAPI 应用**，理解"请求 → 路由函数 → 响应"的完整链路

---

## 二、概念讲解

### 1. 先搞清楚：什么是"Web 框架"？

当你在浏览器输入 `https://example.com/users/5` 时，背后发生的事是：

```
浏览器（客户端）
   │  发送 HTTP 请求：GET /users/5
   ▼
服务器（一台运行在某处的电脑）
   │  收到请求字符串，解析出方法(GET)、路径(/users/5)
   ▼
你的 Python 代码：根据路径决定调哪个函数，处理业务，返回数据
   │  把返回数据按 HTTP 格式打包成响应
   ▼
浏览器：显示页面或渲染 JSON
```

如果每次写网站都从"解析 HTTP 请求字符串"开始，太痛苦了。**Web 框架**就是把这些脏活累活封装好，让你只需要写"**当用户访问 X 时，返回 Y**"。

> 比喻：Web 框架像一家餐厅的"前厅经理"——客人进门、点单、上菜、买单都由它安排，厨师（你的代码）只需要专注于做菜。

### 2. FastAPI 是什么？

**FastAPI 是一个用于构建 API 的现代 Python Web 框架**，主要特点：

| 特点 | 一句话解释 |
|---|---|
| **快（Fast）** | 基于 ASGI 异步架构，性能接近 Node.js / Go |
| **少 Bug** | 利用 Python 类型提示自动做参数校验 |
| **自动文档** | 启动后访问 `/docs` 就有交互式 API 文档 |
| **现代** | 原生支持 `async/await`，适合 I/O 密集场景 |
| **易学** | 写法简单，类似 Flask |

**对比一下主流 Python Web 框架**：

- **Flask**：经典、轻量，但同步模型（WSGI），高并发弱
- **Django**：大而全（带 ORM/Admin/模板），重，传统同步
- **FastAPI**：聚焦 API、异步、自带校验和文档，适合现代前后端分离项目

### 3. 什么是 ASGI？为什么 FastAPI 能"快"？

这是本课最核心的概念。**先看一个餐厅比喻**：

#### 🍽️ WSGI（老式同步模型，如 Flask/Django 默认）

> 餐厅只有 1 个服务员。他给 A 桌点完单，**必须站在厨房门口等菜做好**端给 A 桌，才能去服务 B 桌。结果：餐厅里坐了 50 桌客人，服务员忙死，客人等死。

技术上：**WSGI**（Web Server Gateway Interface）规定服务器**一个请求占用一个线程/进程**直到响应完成。如果代码里要查数据库 2 秒，这 2 秒线程就"卡死"在等待，CPU 闲着也没用。

#### 🍽️ ASGI（新式异步模型，FastAPI 用这个）

> 餐厅还是 1 个服务员，但他用对讲机：给 A 桌点完单 → 对讲机告诉厨房 → **不等，转身去 B 桌**。厨房做好菜通过对讲机叫他，他再来端菜。

技术上：**ASGI**（**A**synchronous Server Gateway Interface，异步服务器网关接口）允许服务器在等待 I/O（数据库、网络、文件）时**让出 CPU 去处理别的请求**。一个线程能同时"挂着"成百上千个请求。

#### 🔄 联系你已学过的知识：生成器

你学过 Python **生成器**——`yield` 会让函数暂停、保存状态、下次从原位置继续。这就是"协程"思想的雏形。

```
生成器（yield）        协程（async/await）
─────────────         ──────────────
暂停执行              暂停执行
保存状态              保存状态
主动 next() 唤醒      事件循环自动唤醒
单线程内"看起来并行"   单线程内真正并行 I/O
```

**FastAPI 的"快"本质上来自**：
1. ASGI 让单线程高并发处理 I/O（不用为每个请求开线程）
2. 类型提示让参数校验通过 Pydantic 在 C 扩展层面快速完成
3. Starlette 提供轻量路由层

### 4. FastAPI ≠ 自己能跑

一个关键概念：**FastAPI 是框架，但它自己不会"监听端口"**。它需要外挂一个 **ASGI 服务器**（最常用的是 **Uvicorn**）来真正接收网络请求、转交给 FastAPI 处理。

```
浏览器请求
   │
   ▼
[Uvicorn] ← ASGI 服务器，监听端口，接收 HTTP
   │  按 ASGI 协议调用
   ▼
[FastAPI] ← 框架，路由分发、参数校验
   │  调用
   ▼
你写的路由函数（def / async def）
```

> 比喻：FastAPI 是"厨艺高超的厨师"，Uvicorn 是"前厅接待"。光有厨师没人接客不行，光有接待没厨师也不行。

---

## 三、3 个由浅入深的完整示例

### 示例 1：Hello World —— 最小可运行应用

**目标**：跑通第一个 FastAPI 程序，看到返回。

```python
# 文件名：hello.py
from fastapi import FastAPI

# 1. 创建应用实例（相当于"开一家餐厅"）
app = FastAPI()

# 2. 注册一个路由：当有人 GET 访问 "/" 时，执行下面的函数
@app.get("/")
def say_hello():
    # FastAPI 会自动把字典转成 JSON 返回给浏览器
    return {"message": "Hello, FastAPI!"}

# 3. 启动服务器：要么在终端用 `uvicorn hello:app --reload`，
#    要么直接运行本文件
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

**运行方式**（任选其一）：

```bash
# 方式 A：直接运行（推荐新手）
python hello.py

# 方式 B：用 uvicorn 命令（开发常用，--reload 改代码自动重启）
uvicorn hello:app --reload
```

**测试**：浏览器打开 `http://127.0.0.1:8000/` → 看到 `{"message":"Hello, FastAPI!"}`
**惊喜**：打开 `http://127.0.0.1:8000/docs` → 自动生成的交互式文档！

---

### 示例 2：同步 vs 异步 —— 亲眼看见 ASGI 的威力

**目标**：通过对比，体会 WSGI（同步阻塞）和 ASGI（异步非阻塞）的差异。

```python
# 文件名：sync_vs_async.py
import time
import asyncio
from fastapi import FastAPI

app = FastAPI()

# 路由 A：同步函数，用 time.sleep（阻塞整个线程）
@app.get("/sync")
def slow_sync():
    time.sleep(3)  # 模拟"卡 3 秒"的数据库查询
    return {"type": "sync", "msg": "我卡了 3 秒，期间谁也别想被服务"}

# 路由 B：异步函数，用 await asyncio.sleep（让出 CPU）
@app.get("/async")
async def fast_async():
    await asyncio.sleep(3)  # 模拟"等 3 秒"的异步 I/O
    return {"type": "async", "msg": "我等了 3 秒，但期间别人能被服务"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

**亲手做实验**：

1. 浏览器开两个标签页，同时访问 `/sync` → **两个都要等 3 秒多**（一个一个排队）
2. 同样两个标签页，同时访问 `/async` → **几乎同时返回**（事件循环并发处理）

> 💡 关键：**异步函数里绝对不能用 `time.sleep`**，否则会阻塞整个事件循环！这就是 ASGI 模型的核心约束。

---

### 示例 3：路径参数 + 查询参数 + 生命周期管理（资源释放）

**目标**：综合演示类型提示校验、参数类型、应用启停时的资源管理。

```python
# 文件名：demo.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

# 模拟一个"外部资源"（数据库连接池、Redis 客户端等）
_db_pool: list[str] = []

# lifespan：管理应用启动/关闭时的资源
# 类比：餐厅开业前布置桌椅、打烊后关门关灯
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ───── 启动时执行 ─────
    print("🚀 [启动] 初始化数据库连接池...")
    _db_pool.append("connection-1")
    _db_pool.append("connection-2")
    
    yield  # ⚠️ 这里是关键：yield 之前是启动代码，之后是关闭代码
           #     应用运行期间，所有请求都在这个 yield 暂停状态中处理
    
    # ───── 关闭时执行（Ctrl+C 或收到终止信号） ─────
    print("👋 [关闭] 释放数据库连接池...")
    _db_pool.clear()  # 释放资源，避免泄漏

# 把 lifespan 传给 FastAPI
app = FastAPI(lifespan=lifespan)


# 路由 1：根路径，查看资源状态
@app.get("/")
def root():
    return {"db_pool_size": len(_db_pool)}


# 路由 2：路径参数 {user_id}，类型提示为 int
# FastAPI 自动校验：如果传 /users/abc 会返回 422 错误，告诉客户端"必须是整数"
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id, "name": f"用户_{user_id}"}


# 路由 3：查询参数（?q=关键词&limit=数量）
# limit: int = 10 表示"默认 10"，客户端不传就用 10
@app.get("/search")
def search(q: str, limit: int = 10):
    return {
        "你搜索的关键词": q,
        "返回条数上限": limit,
        "示例结果": [f"{q}-结果{i}" for i in range(min(limit, 5))]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

**测试用例**：

| 访问 URL | 返回 |
|---|---|
| `http://127.0.0.1:8000/` | `{"db_pool_size": 2}` |
| `http://127.0.0.1:8000/users/5` | `{"user_id": 5, "name": "用户_5"}` |
| `http://127.0.0.1:8000/users/abc` | **422 错误**（自动校验失败） |
| `http://127.0.0.1:8000/search?q=apple&limit=3` | 返回包含 apple 的搜索结果 |

**按 Ctrl+C 关闭服务时**，你会看到 `[关闭] 释放数据库连接池...` 被打印——这就是**资源释放**的体现。

---

## 四、常用函数 / 调用速查表

| 函数/对象 | 签名 | 用途 | 最小示例 |
|---|---|---|---|
| `FastAPI()` | `FastAPI(**kwargs)` | 创建应用实例 | `app = FastAPI()` |
| `@app.get` | `app.get(path)` | 注册 GET 路由 | `@app.get("/")` |
| `@app.post` | `app.post(path)` | 注册 POST 路由（创建资源） | `@app.post("/users")` |
| `@app.put` | `app.put(path)` | 注册 PUT 路由（整体更新） | `@app.put("/users/{id}")` |
| `@app.delete` | `app.delete(path)` | 注册 DELETE 路由（删除） | `@app.delete("/users/{id}")` |
| `@app.patch` | `app.patch(path)` | 注册 PATCH 路由（部分更新） | `@app.patch("/users/{id}")` |
| `uvicorn.run` | `uvicorn.run(app, host, port, **kw)` | 启动 ASGI 服务器 | `uvicorn.run(app, host="127.0.0.1", port=8000)` |
| `asynccontextmanager` | `asynccontextmanager(func)` | 把 async 生成器变成 lifespan 管理器 | 见示例 3 |
| `app.lifespan` | `FastAPI(lifespan=...)` | 注册生命周期钩子 | `FastAPI(lifespan=lifespan)` |

**常用启动参数**：

| 参数 | 说明 | 示例 |
|---|---|---|
| `host` | 监听地址 | `"127.0.0.1"`（本机）/ `"0.0.0.0"`（外网可访问） |
| `port` | 监听端口 | `8000` |
| `reload` | 改代码自动重启（仅开发用） | `uvicorn.run("demo:app", reload=True)` |

---

## 五、5 个新手易错点

### ❌ 易错 1：在 `async` 函数里用 `time.sleep`

```python
# ❌ 错误：阻塞整个事件循环，所有其他请求都被卡住
@app.get("/bad")
async def bad():
    time.sleep(3)
    return {"msg": "我卡死了所有人"}

# ✅ 正确：用 await asyncio.sleep，让出 CPU
@app.get("/good")
async def good():
    await asyncio.sleep(3)
    return {"msg": "我等待时别人能继续工作"}
```

> 规则：**async 函数里所有"等待"都必须用 await，被等待的对象必须是协程/异步库**。

### ❌ 易错 2：直接运行却忘记写 `if __name__ == "__main__"` 启动块

```python
# ❌ 错误：只有 app 定义，python hello.py 没反应（没启动服务器）
from fastapi import FastAPI
app = FastAPI()
@app.get("/")
def root(): return {"hi": 1}

# ✅ 正确：补上启动代码
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

或者用命令行启动：`uvicorn hello:app --reload`（注意是**文件名:app变量名**，不带 .py）

### ❌ 易错 3：路径不以 `/` 开头

```python
# ❌ 错误：FastAPI 会抛 RuntimeError
@app.get("users")
def users(): ...

# ✅ 正确：路径必须以 / 开头
@app.get("/users")
def users(): ...
```

### ❌ 易错 4：路径参数和查询参数混淆

```python
# 路径参数：写在 {} 里，是 URL 的一部分
@app.get("/users/{user_id}")        # 访问 /users/5 → user_id=5
def get_user(user_id: int): ...

# 查询参数：写在函数签名里（不在路径里），URL 用 ?key=value 传递
@app.get("/users")                   # 访问 /users?limit=10 → limit=10
def list_users(limit: int = 10): ...

# ❌ 错误理解：以为 /users/5 里的 5 是查询参数
# ❌ 错误写法：在路径里写查询参数
@app.get("/users?limit={n}")        # 这样写根本匹配不到
```

### ❌ 易错 5：用 `uvicorn.run(app, reload=True)` —— reload 不生效

```python
# ❌ 错误：传 app 实例时 reload 不会工作（uvicorn 没法重新导入它）
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)

# ✅ 正确：reload 必须传"模块:变量名字符串"
if __name__ == "__main__":
    uvicorn.run("demo:app", host="127.0.0.1", port=8000, reload=True)
```

> 原因：reload 需要重新导入模块，所以必须给 uvicorn 一个"字符串路径"，而不是已经实例化的对象。

---

## 六、本课小练习（附答案）

### 📝 练习 1：实现健康检查接口

**要求**：创建一个 FastAPI 应用，提供 `GET /health` 路由，返回：
```json
{"status": "ok", "service": "my-app"}
```

<details>
<summary>🔑 参考答案</summary>

```python
# health.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "my-app"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

测试：浏览器访问 `http://127.0.0.1:8000/health`

</details>

---

### 📝 练习 2：问候接口（路径参数 + 查询参数）

**要求**：
- `GET /greet/{name}` 返回问候语
- 支持查询参数 `?times=3`，控制问候语重复几次（默认 1）
- `name` 必须是字符串，`times` 必须是整数

**预期效果**：
- `/greet/Alice` → `{"message": "Hello, Alice!"}`
- `/greet/Bob?times=3` → `{"message": "Hello, Bob! Hello, Bob! Hello, Bob!"}`

<details>
<summary>🔑 参考答案</summary>

```python
# greet.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/greet/{name}")
def greet(name: str, times: int = 1):
    # 类型提示让 FastAPI 自动校验：
    #   - name 必须能转成字符串（永远可以，但显式声明更清晰）
    #   - times 必须是整数，否则返回 422 错误
    message = f"Hello, {name}! " * times
    return {"message": message.strip()}  # strip 去掉末尾多余空格

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

**额外实验**：
- 访问 `/greet/Alice?times=abc` → 看 FastAPI 怎么自动报错（422 + 详细提示）
- 访问 `http://127.0.0.1:8000/docs` → 看自动生成的文档里这两个参数怎么显示

</details>

---

## 📌 本课小结

| 概念 | 一句话记忆 |
|---|---|
| **Web 框架** | 封装 HTTP 脏活，让你专注业务 |
| **FastAPI** | 现代、异步、自带校验和文档的 Python API 框架 |
| **WSGI** | 同步网关，一请求一线程，I/O 时卡死 |
| **ASGI** | 异步网关，单线程高并发，I/O 时让出 CPU |
| **Uvicorn** | ASGI 服务器，负责接客；FastAPI 是厨师 |
| **async/await** | 协程语法，类似生成器 yield 的暂停/恢复，但更强大 |

**下一课预告**：我们会正式学习路由、路径参数、查询参数、请求体的完整用法，并动手做一个真正的小项目（比如待办事项 API）。