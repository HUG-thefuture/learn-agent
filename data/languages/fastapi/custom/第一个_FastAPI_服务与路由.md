# 🚀 第一个 FastAPI 服务与路由

## 🎯 本课目标

学完本课，你将能够：

1. **创建并运行第一个 FastAPI 应用**，在浏览器中看到返回的 JSON 数据。
2. **理解路由（Route）的概念**，能自己添加不同的路径（如 `/`、`/hello`、`/users/5`）。
3. **掌握路径参数和查询参数**，能写出接收动态数据的接口。

---

## 🧠 概念讲解

### 1. 回顾：FastAPI 是什么？

还记得前置课程吗？FastAPI 是一个 Python Web 框架，它帮你处理"HTTP 请求解析"和"响应打包"这些繁琐工作。你只需要：

```python
# 你只需要写这个函数
def get_user(user_id: int):
    return {"user_id": user_id}
```

FastAPI 会自动帮你：
- 解析浏览器发来的请求字符串
- 提取出路径中的 `user_id`
- 调用你的函数
- 把返回的字典打包成 JSON 响应

### 2. 什么是"路由"？

想象一个餐厅：

```
顾客（浏览器）说："我要点菜"
服务员（FastAPI）问："您要哪个菜？"
顾客说："我要菜单上的第 5 道菜"（路径：/menu/5）
服务员（FastAPI）去后厨（你的代码）找到做第 5 道菜的厨师（路由函数）
厨师做好菜（函数返回值）
服务员把菜端给顾客（返回响应）
```

**路由**就是"路径 → 函数"的映射关系。FastAPI 用装饰器 `@app.get()` 来建立这种关系。

### 3. 为什么用 `@app.get()` 而不是 `@app.post()`？

HTTP 协议定义了多种"请求方法"：
- `GET`：获取数据（比如看网页）
- `POST`：提交数据（比如登录）
- `PUT`：更新数据
- `DELETE`：删除数据

`@app.get()` 表示"当浏览器用 GET 方法访问这个路径时，执行这个函数"。

### 4. 路径参数 vs 查询参数

```
路径参数：/users/5        → 5 是路径的一部分
查询参数：/users?id=5     → id=5 跟在 ? 后面
```

路径参数适合"资源定位"（哪个用户），查询参数适合"筛选条件"（按什么条件找）。

---

## 💻 三个由浅入深的示例

### 示例 1：Hello World（最简版）

```python
# 文件名：main.py
from fastapi import FastAPI

# 创建 FastAPI 应用实例
app = FastAPI()

# 定义路由：当访问根路径 "/" 时，执行这个函数
@app.get("/")
def read_root():
    return {"message": "Hello World"}

# 运行方式：在终端执行
# uvicorn main:app --reload
# 然后浏览器访问 http://127.0.0.1:8000
```

**运行步骤**：
1. 保存为 `main.py`
2. 终端运行：`pip install fastapi uvicorn`
3. 运行：`uvicorn main:app --reload`
4. 浏览器打开 `http://127.0.0.1:8000`

**看到什么**：`{"message": "Hello World"}`

---

### 示例 2：路径参数（动态路由）

```python
from fastapi import FastAPI

app = FastAPI()

# 路径参数：{user_id} 是动态的
# 访问 /users/5 时，user_id = 5
@app.get("/users/{user_id}")
def get_user(user_id: int):
    # 注意：这里声明了 user_id: int，FastAPI 会自动转换类型
    return {"user_id": user_id, "message": f"获取用户 {user_id} 的信息"}
```

**测试**：
- 访问 `http://127.0.0.1:8000/users/5` → `{"user_id": 5, "message": "获取用户 5 的信息"}`
- 访问 `http://127.0.0.1:8000/users/abc` → 会报错（因为 `abc` 不是整数）

**为什么用 `int`**：FastAPI 看到类型注解 `int`，会自动做两件事：
1. 把字符串 `"5"` 转换成整数 `5`
2. 如果转换失败（如 `"abc"`），自动返回 422 错误

---

### 示例 3：查询参数 + 路径参数（综合）

```python
from fastapi import FastAPI

app = FastAPI()

# 模拟一个用户数据库（实际中会用真正的数据库）
fake_db = {
    1: {"name": "小明", "age": 20},
    2: {"name": "小红", "age": 22},
}

# 路径参数：user_id 定位用户
# 查询参数：?age=21 筛选年龄大于等于 21 的用户
@app.get("/users/{user_id}")
def get_user(user_id: int, age: int = None):
    """
    获取用户信息
    - user_id: 路径参数，必填
    - age: 查询参数，可选（默认 None）
    """
    user = fake_db.get(user_id)
    if not user:
        return {"error": "用户不存在"}
    
    # 如果传了 age 参数，就检查年龄是否匹配
    if age is not None and user["age"] < age:
        return {"error": "用户年龄不满足要求"}
    
    return {"user_id": user_id, **user}

# 另一个接口：获取所有用户
@app.get("/users")
def get_all_users():
    return fake_db
```

**测试**：
- `http://127.0.0.1:8000/users` → 返回所有用户
- `http://127.0.0.1:8000/users/1` → 返回用户 1 的信息
- `http://127.0.0.1:8000/users/1?age=21` → 用户 1 年龄 20 < 21，返回错误
- `http://127.0.0.1:8000/users/2?age=21` → 用户 2 年龄 22 ≥ 21，返回成功

**注意**：`/users` 和 `/users/{user_id}` 是两个不同的路由，不会冲突。

---

## 📋 常用函数/调用速查表

| 函数/装饰器 | 签名 | 用途 | 最小示例 |
|------------|------|------|---------|
| `FastAPI()` | `FastAPI()` | 创建应用实例 | `app = FastAPI()` |
| `@app.get()` | `@app.get(path)` | 定义 GET 路由 | `@app.get("/")` |
| `@app.post()` | `@app.post(path)` | 定义 POST 路由 | `@app.post("/login")` |
| `@app.put()` | `@app.put(path)` | 定义 PUT 路由 | `@app.put("/users/1")` |
| `@app.delete()` | `@app.delete(path)` | 定义 DELETE 路由 | `@app.delete("/users/1")` |
| 路径参数 | `{param}` 写在路径中 | 从 URL 中提取值 | `@app.get("/users/{id}")` |
| 查询参数 | 函数参数（非路径参数） | 从 `?` 后面提取值 | `def f(age: int = None)` |
| 类型注解 | `param: int` | 自动类型转换和验证 | `def f(id: int)` |

---

## ⚠️ 5 个新手易错点

### 错误 1：忘记安装依赖
```bash
# ❌ 错误：直接运行报错 ModuleNotFoundError
python main.py

# ✅ 正确：先安装依赖
pip install fastapi uvicorn
# 然后用 uvicorn 运行（不是 python）
uvicorn main:app --reload
```

### 错误 2：路由顺序错误
```python
# ❌ 错误：/users/{user_id} 会拦截 /users/new
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}

@app.get("/users/new")
def new_user():
    return {"message": "创建用户"}

# ✅ 正确：把固定路径放在前面
@app.get("/users/new")
def new_user():
    return {"message": "创建用户"}

@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}
```

### 错误 3：路径参数类型不匹配
```python
# ❌ 错误：访问 /users/abc 会报错
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}

# ✅ 正确：如果希望接受任意字符串，用 str
@app.get("/users/{user_id}")
def get_user(user_id: str):
    return {"user_id": user_id}
```

### 错误 4：忘记 `--reload` 参数
```bash
# ❌ 错误：修改代码后不生效，需要手动重启
uvicorn main:app

# ✅ 正确：加上 --reload，修改代码自动重启
uvicorn main:app --reload
```

### 错误 5：函数名和文件名混淆
```python
# ❌ 错误：运行 uvicorn main:app 报错
# 因为文件名是 myapp.py，但运行命令写的是 main

# ✅ 正确：运行命令要和文件名一致
# 如果文件叫 myapp.py，运行：uvicorn myapp:app --reload
```

---

## ✏️ 本课小练习

### 练习 1：创建"问候"接口

创建一个 FastAPI 应用，要求：
- 路径：`/greet/{name}`
- 功能：返回 `{"message": "你好，{name}！"}`

**答案**：
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/greet/{name}")
def greet(name: str):
    return {"message": f"你好，{name}！"}

# 运行：uvicorn main:app --reload
# 测试：http://127.0.0.1:8000/greet/小明
```

### 练习 2：实现"计算器"接口

创建一个 FastAPI 应用，要求：
- 路径：`/calc`
- 查询参数：`a`（整数）、`b`（整数）、`op`（字符串，可选，默认 `"add"`）
- 功能：根据 `op` 执行加法（add）、减法（sub）、乘法（mul）、除法（div）
- 除法时注意：如果 `b` 为 0，返回错误信息

**答案**：
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/calc")
def calc(a: int, b: int, op: str = "add"):
    if op == "add":
        return {"result": a + b}
    elif op == "sub":
        return {"result": a - b}
    elif op == "mul":
        return {"result": a * b}
    elif op == "div":
        if b == 0:
            return {"error": "除数不能为 0"}
        return {"result": a / b}
    else:
        return {"error": f"不支持的运算符: {op}"}

# 测试：
# http://127.0.0.1:8000/calc?a=10&b=5&op=add → {"result": 15}
# http://127.0.0.1:8000/calc?a=10&b=0&op=div → {"error": "除数不能为 0"}
```

---

## 🎉 恭喜完成！

现在你已经能：
- ✅ 创建 FastAPI 应用
- ✅ 定义路由（GET 方法）
- ✅ 使用路径参数和查询参数
- ✅ 处理简单的业务逻辑

下一步可以学习：**POST 请求与请求体（Body）**，让接口能接收前端传来的 JSON 数据。