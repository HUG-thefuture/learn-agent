好的，学员！欢迎来到 **L4 后端实战** 的第一课。你已经掌握了 Python 基础、HTTP 概念和代码规范，现在我们将进入激动人心的 Web 开发世界。本课将带你使用 **FastAPI** 框架，从零开始构建你的第一个 API 服务。

想象一下，你正在为一家餐厅开发一个点餐系统。顾客需要通过手机 App 查看菜单、下单。你的任务就是编写一个“服务员”程序（后端 API），它接收顾客的请求（查看菜单、提交订单），并返回相应的数据（菜单列表、订单确认）。FastAPI 就是帮你高效、优雅地实现这个“服务员”的得力工具。

---

### 1. 本课目标

学完本课，你将能够：

1.  **创建并运行**一个最基础的 FastAPI 应用，并理解其核心代码结构。
2.  **定义**一个带有路径参数和查询参数的 GET 接口，并理解其 URL 的构成。
3.  **使用** FastAPI 自动生成的交互式 API 文档（`/docs`）来测试你的接口。

---

### 2. 概念讲解

#### 2.1 什么是 Web 框架？什么是 FastAPI？

在之前的课程中，你写的 Python 脚本都是“一次性”的：运行它，它执行完就结束了。但 Web 服务不同，它需要**7x24 小时**不间断地运行，等待并响应来自世界各地（或你的浏览器）的请求。

**Web 框架**就是帮你构建这种“常驻”服务的工具箱。它处理了大量底层、重复的琐事，比如：
- **网络通信**：监听端口，接收 HTTP 请求。
- **路由分发**：根据 URL（比如 `/menu` 或 `/order`）找到对应的处理函数。
- **数据解析**：从请求中提取参数（比如订单里的菜品 ID）。
- **响应格式化**：将你的 Python 字典或列表转换成 JSON 格式的 HTTP 响应。

**FastAPI** 是 Python 生态中一个现代、高性能的 Web 框架。它最大的特点就是**基于 Python 类型提示**。这意味着你只需要在函数参数上标注类型（如 `item_id: int`），FastAPI 就会自动帮你完成：
- **数据校验**：如果请求参数不是整数，它会自动返回一个格式清晰的错误。
- **自动文档**：它会根据你的代码，自动生成一份漂亮的、可交互的 API 文档。

#### 2.2 认识 ASGI 和 Uvicorn

FastAPI 本身不直接与网络通信，它需要一个“服务器”来运行。这个服务器就是 **Uvicorn**。Uvicorn 是一个实现了 **ASGI**（异步服务器网关接口）的服务器。

你可以这样理解：
- **FastAPI** 是“厨师”，负责根据“菜单”（路由）烹饪出美味的“菜肴”（JSON 响应）。
- **Uvicorn** 是“传菜员”，负责把顾客的“订单”（HTTP 请求）传给厨师，再把“菜肴”端给顾客。

ASGI 是 FastAPI 和 Uvicorn 之间的“沟通协议”，它支持异步操作，让 FastAPI 能高效处理大量并发请求。

#### 2.3 第一个 FastAPI 应用

让我们来看一个最基础的 FastAPI 应用。它定义了一个根路径 `/` 的 GET 接口，当访问时返回一句问候。

```python
# 导入 FastAPI 类
from fastapi import FastAPI

# 创建一个 FastAPI 实例，这是你的应用的核心
app = FastAPI()

# 使用装饰器 @app.get("/") 告诉 FastAPI，当收到一个指向根路径 "/" 的 GET 请求时，执行下面的函数
@app.get("/")
async def root():
    # 函数返回一个字典，FastAPI 会自动将其转换为 JSON 格式的响应
    return {"message": "Hello World"}
```

**代码解释**：
- `from fastapi import FastAPI`：导入框架。
- `app = FastAPI()`：实例化应用，`app` 是约定俗成的变量名。
- `@app.get("/")`：这是一个**装饰器**，它将下面的函数 `root` 与 HTTP 的 `GET` 方法和路径 `/` 绑定。
- `async def root():`：定义了一个**异步**函数。`async` 关键字让这个函数支持异步操作，但现阶段你可以把它当作普通函数来写。
- `return {"message": "Hello World"}`：返回一个字典。FastAPI 会自动将其序列化为 JSON 字符串，并作为 HTTP 响应体发送给客户端。

**如何运行？**
你需要一个 ASGI 服务器（Uvicorn）来运行这个 `app`。在终端中，进入包含 `main.py` 文件的目录，然后运行：
```bash
uvicorn main:app --reload
```
- `main`：你的 Python 文件名（`main.py`）。
- `app`：你在 `main.py` 中创建的 FastAPI 实例名。
- `--reload`：开发模式下的热重载，代码修改后服务器会自动重启，非常方便。

---

### 3. 三个由浅入深的完整示例

#### 示例 1：你好，FastAPI！

这是你的第一个可运行的 API。我们将创建一个文件 `main.py`，并运行它。

```python
# main.py
from fastapi import FastAPI

# 创建 FastAPI 应用实例
app = FastAPI()

# 定义一个根路径的 GET 接口
@app.get("/")
async def read_root():
    """返回一个简单的问候语"""
    return {"message": "你好，FastAPI！"}

# 预期输出（在浏览器访问 http://127.0.0.1:8000/ 后）：
# {"message": "你好，FastAPI！"}
```

#### 示例 2：带路径参数的接口

现在，我们让接口能接收来自 URL 路径中的参数。比如，访问 `/items/5`，我们希望返回 `item_id` 为 5 的信息。

```python
# main.py
from fastapi import FastAPI

app = FastAPI()

# 定义一个带路径参数的 GET 接口
# 花括号 {} 中的内容就是路径参数，FastAPI 会自动提取它
@app.get("/items/{item_id}")
async def read_item(item_id: int):
    """
    接收一个路径参数 item_id，并返回包含该参数的信息。
    注意：我们声明了 item_id 的类型是 int，FastAPI 会自动进行类型转换和校验。
    """
    return {"item_id": item_id, "name": f"这是编号为 {item_id} 的商品"}

# 预期输出（在浏览器访问 http://127.0.0.1:8000/items/42 后）：
# {"item_id": 42, "name": "这是编号为 42 的商品"}
```

#### 示例 3：带查询参数的接口

查询参数是 URL 中 `?` 后面的部分，用于过滤或排序。比如 `/items/?skip=0&limit=10`。

```python
# main.py
from fastapi import FastAPI

app = FastAPI()

# 模拟一个数据库中的商品列表
fake_items_db = [
    {"item_name": "苹果"},
    {"item_name": "香蕉"},
    {"item_name": "橙子"},
    {"item_name": "西瓜"},
]

# 定义一个带查询参数的 GET 接口
@app.get("/items/")
async def list_items(skip: int = 0, limit: int = 10):
    """
    接收两个查询参数 skip 和 limit，用于分页。
    它们都有默认值，所以访问 /items/ 时可以不提供。
    """
    # 从数据库中切片，模拟分页
    return fake_items_db[skip : skip + limit]

# 预期输出（在浏览器访问 http://127.0.0.1:8000/items/?skip=1&limit=2 后）：
# [{"item_name": "香蕉"}, {"item_name": "橙子"}]
```

---

### 4. 常用函数/调用速查表

| 函数/装饰器 | 签名/用法 | 用途 | 最小示例 |
| :--- | :--- | :--- | :--- |
| `FastAPI()` | `app = FastAPI()` | 创建 FastAPI 应用实例 | `app = FastAPI()` |
| `@app.get()` | `@app.get("/path")` | 注册一个处理 HTTP GET 请求的路由 | `@app.get("/")` |
| `@app.post()` | `@app.post("/path")` | 注册一个处理 HTTP POST 请求的路由（本课未涉及，但很常用） | `@app.post("/items/")` |
| `uvicorn` | `uvicorn main:app --reload` | 在终端启动开发服务器 | `uvicorn main:app --reload` |
| 路径参数 | `@app.get("/items/{item_id}")` | 在 URL 路径中定义动态参数 | `@app.get("/users/{user_id}")` |
| 查询参数 | `async def f(skip: int = 0)` | 在函数参数中定义查询参数，可带默认值 | `async def f(q: str = None)` |

---

### 5. 五个新手易错点

#### 易错点 1：忘记安装 FastAPI 和 Uvicorn

❌ **错误写法**
```python
# 直接运行会报错：ModuleNotFoundError: No module named 'fastapi'
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello"}
# 运行报错：ModuleNotFoundError: No module named 'fastapi'
```

✅ **正确写法**
```bash
# 在终端中先安装依赖
pip install fastapi uvicorn
```
```python
# 然后再运行你的代码
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello"}
# 预期输出：在浏览器访问 http://127.0.0.1:8000/ 看到 {"message": "Hello"}
```
**为什么错**：FastAPI 和 Uvicorn 是第三方库，必须先安装才能导入和使用。

#### 易错点 2：运行 `uvicorn` 时文件路径或实例名错误

❌ **错误写法**
```bash
# 假设你的文件叫 my_api.py，但你在终端运行了：
uvicorn main:app --reload
# 运行报错：ERROR:    Error loading ASGI app. Could not import module "main".
```

✅ **正确写法**
```bash
# 如果你的文件叫 my_api.py，并且里面创建的实例叫 application，那么应该运行：
uvicorn my_api:application --reload
```
**为什么错**：`uvicorn` 命令的格式是 `uvicorn <文件名>:<实例名>`，必须与你的实际文件名和变量名完全一致。

#### 易错点 3：路径参数和查询参数混淆

❌ **错误写法**
```python
from fastapi import FastAPI

app = FastAPI()

# 错误：试图用查询参数的方式定义路径参数
@app.get("/items/{item_id}")
async def read_item(item_id: int = 0):  # 这里给了默认值，但路径参数不应该有默认值
    return {"item_id": item_id}
# 运行不会报错，但访问 /items/ 会返回 404，因为路径参数是必须的
```

✅ **正确写法**
```python
from fastapi import FastAPI

app = FastAPI()

# 正确：路径参数是 URL 的一部分，不能有默认值
@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}

# 正确：查询参数是 URL 中 ? 后面的部分，可以有默认值
@app.get("/list/")
async def list_items(skip: int = 0, limit: int = 10):
    return {"skip": skip, "limit": limit}
# 预期输出：访问 /items/5 返回 {"item_id": 5}；访问 /list/?skip=1 返回 {"skip": 1, "limit": 10}
```
**为什么错**：路径参数是 URL 路径的必需部分，而查询参数是可选或带默认值的。混淆它们会导致路由定义错误或参数获取不到。

#### 易错点 4：忘记使用 `async` 关键字（或过度使用）

❌ **错误写法**
```python
from fastapi import FastAPI

app = FastAPI()

# 错误：虽然能运行，但 FastAPI 官方推荐使用 async def
@app.get("/")
def root():
    return {"message": "Hello"}
# 运行正常，但不符合最佳实践
```

✅ **正确写法**
```python
from fastapi import FastAPI

app = FastAPI()

# 正确：使用 async def 定义异步路由函数
@app.get("/")
async def root():
    return {"message": "Hello"}
# 预期输出：访问 / 返回 {"message": "Hello"}
```
**为什么错**：`async def` 是 FastAPI 的推荐写法，它能更好地利用异步 I/O 提升性能。虽然同步 `def` 也能工作，但为了最佳实践和未来扩展，请使用 `async def`。

#### 易错点 5：在代码中直接运行 `uvicorn` 命令

❌ **错误写法**
```python
# main.py
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello"}

# 错误：在代码里直接调用 uvicorn.run()
if __name__ == "__main__":
    uvicorn.run(app)
# 运行正常，但这不是标准做法，不利于代码清晰和部署
```

✅ **正确写法**
```python
# main.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello"}

# 正确：代码只负责定义应用，启动交给终端命令
# 在终端运行：uvicorn main:app --reload
```
**为什么错**：将启动命令写在代码里会混淆代码职责。标准做法是代码只定义 `app`，由外部命令（如 `uvicorn`）来启动它，这样更清晰、更易于部署。

---

### 6. 本课小练习

#### 练习 1：创建一个“用户”接口

- **目标**：掌握路径参数的基本用法。
- **引导步骤**：
  1.  创建一个 FastAPI 应用实例。
  2.  定义一个 GET 接口，路径为 `/users/{user_id}`。
  3.  让这个接口接收一个 `user_id` 参数（类型为 `int`），并返回一个包含该 ID 的字典。
- **起步代码**：
```python
from fastapi import FastAPI

app = FastAPI()

# TODO: 在这里定义一个 GET 接口，路径为 /users/{user_id}
# 函数名为 get_user，接收一个 int 类型的路径参数 user_id
# 返回一个字典，例如 {"user_id": user_id, "name": "用户"}
```
- **预期输出**：访问 `/users/123` 后，返回 `{"user_id": 123, "name": "用户"}`。

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return {"user_id": user_id, "name": "用户"}

# 访问 http://127.0.0.1:8000/users/123 预期输出：
# {"user_id": 123, "name": "用户"}
```

</details>

#### 练习 2：为接口添加查询参数

- **目标**：掌握查询参数的定义和默认值。
- **引导步骤**：
  1.  基于练习 1 的代码。
  2.  为 `/users/{user_id}` 接口添加一个查询参数 `details`，类型为 `bool`，默认值为 `False`。
  3.  当 `details` 为 `True` 时，在返回的字典中增加一个 `"email": "user@example.com"` 字段。
- **起步代码**：
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    # TODO: 添加一个查询参数 details: bool = False
    # 如果 details 为 True，则返回的字典中增加 "email" 字段
    user_info = {"user_id": user_id, "name": "用户"}
    # 在这里编写条件判断逻辑
    return user_info
```
- **预期输出**：访问 `/users/123?details=true` 后，返回 `{"user_id": 123, "name": "用户", "email": "user@example.com"}`。

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, details: bool = False):
    user_info = {"user_id": user_id, "name": "用户"}
    if details:
        user_info["email"] = "user@example.com"
    return user_info

# 访问 http://127.0.0.1:8000/users/123?details=true 预期输出：
# {"user_id": 123, "name": "用户", "email": "user@example.com"}
```

</details>

#### 练习 3：组合路径和查询参数

- **目标**：综合运用路径参数和查询参数。
- **引导步骤**：
  1.  创建一个新的 GET 接口，路径为 `/products/{product_id}`。
  2.  它接收一个 `product_id`（int）路径参数和一个 `q`（str）查询参数，`q` 的默认值为 `None`。
  3.  返回一个字典，包含 `product_id` 和 `q` 的值。
- **起步代码**：
```python
from fastapi import FastAPI

app = FastAPI()

# TODO: 定义一个 GET 接口，路径为 /products/{product_id}
# 接收 int 类型的路径参数 product_id
# 接收一个 str 类型的查询参数 q，默认值为 None
# 返回 {"product_id": product_id, "query": q}
```
- **预期输出**：访问 `/products/99?q=test` 后，返回 `{"product_id": 99, "query": "test"}`。

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/products/{product_id}")
async def get_product(product_id: int, q: str = None):
    return {"product_id": product_id, "query": q}

# 访问 http://127.0.0.1:8000/products/99?q=test 预期输出：
# {"product_id": 99, "query": "test"}
```

</details>

---

### 7. 本课小结

恭喜你完成了第一个 FastAPI 实战课程！让我们回顾一下今天学到的关键点：

1.  **FastAPI 是一个现代、高性能的 Python Web 框架**，它基于类型提示，能自动生成文档和进行数据校验。
2.  **Uvicorn 是运行 FastAPI 的 ASGI 服务器**，你需要通过 `uvicorn main:app --reload` 命令来启动你的应用。
3.  **路径参数**（`/items/{item_id}`）是 URL 路径的一部分，**查询参数**（`?skip=0&limit=10`）是 URL 中 `?` 后面的部分，两者都可以在函数参数中定义。
4.  **使用 `async def` 定义路由函数**是 FastAPI 的推荐做法。
5.  **FastAPI 会自动为你生成交互式 API 文档**，启动应用后访问 `http://127.0.0.1:8000/docs` 即可查看和测试你的所有接口。

下一课，我们将深入 FastAPI 的核心功能——**使用 Pydantic 模型定义请求体**，并学习如何处理 `POST` 请求，从而真正实现数据的“增删改查”。准备好迎接新的挑战了吗？