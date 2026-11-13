# L4 后端实战：HTTP与REST API概念

## 本课目标

学完本课，你将能够：
1. 理解 HTTP 协议的核心概念（请求方法、状态码、URL 结构）
2. 掌握 REST API 设计的基本原则（资源命名、方法语义）
3. 用 Python 标准库编写一个简单的 HTTP 客户端，验证 REST API 行为

---

## 1. 概念讲解

### 1.1 HTTP 是什么？—— 快递员与包裹

想象你在网上购物：
- **你（客户端）** 下单 → 这是**请求**
- **快递员（HTTP协议）** 负责运输 → 这是**传输**
- **商家（服务器）** 处理订单 → 这是**响应**

HTTP 就是客户端和服务器之间的"快递协议"，它规定了：
- **怎么寄**（请求方法：GET、POST、PUT、DELETE）
- **寄给谁**（URL 地址）
- **收到后怎么回复**（状态码：200、404、500）

### 1.2 REST API 是什么？—— 餐厅点餐系统

REST 不是一种技术，而是一种**设计风格**。就像餐厅有固定菜单：
- **资源** = 菜单上的菜品（如：用户、订单、商品）
- **URL** = 菜品编号（如：`/users/123`）
- **HTTP方法** = 你对菜品的操作：
  - GET = 查看菜品（获取资源）
  - POST = 点新菜（创建资源）
  - PUT = 换掉整盘菜（全量更新）
  - DELETE = 退菜（删除资源）

### 1.3 为什么用 Python 标准库学？

我们不用 FastAPI 或 Flask，而是用 Python 自带的 `urllib` 和 `http.server`，因为：
1. **零依赖**：任何环境都能运行
2. **看清本质**：理解 HTTP 底层机制，再学框架事半功倍
3. **调试友好**：能直接看到请求/响应的原始数据

---

## 2. 三个由浅入深的示例

### 示例 1：用 Python 发送第一个 HTTP 请求

```python
"""
示例1：使用 urllib 发送 GET 请求
目标：理解 HTTP 请求的基本流程
"""
from urllib.request import urlopen
from urllib.error import HTTPError

# 发送 GET 请求到 httpbin.org（一个免费的 HTTP 测试服务）
url = "https://httpbin.org/get"
try:
    # urlopen 发送请求并获取响应
    response = urlopen(url, timeout=5)
    
    # 读取响应内容（字节）并解码为字符串
    body = response.read().decode('utf-8')
    
    # 打印状态码和响应体
    print(f"状态码: {response.status}")
    print(f"响应头 Content-Type: {response.headers.get('Content-Type')}")
    print(f"响应体（前200字符）: {body[:200]}")
    
except HTTPError as e:
    print(f"HTTP 错误: {e.code} - {e.reason}")
except Exception as e:
    print(f"请求失败: {e}")

# 预期输出：
# 状态码: 200
# 响应头 Content-Type: application/json
# 响应体（前200字符）: {"args":{}, "headers":{...}, "origin":"...", "url":"..."}
```

### 示例 2：用 Python 启动一个简易 HTTP 服务器

```python
"""
示例2：用 http.server 创建简易服务器
目标：理解服务器如何响应请求
运行后访问 http://127.0.0.1:8000/hello
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class SimpleHandler(BaseHTTPRequestHandler):
    """自定义请求处理器"""
    
    def do_GET(self):
        """处理 GET 请求"""
        # 根据路径返回不同内容
        if self.path == '/hello':
            # 构造 JSON 响应
            data = {"message": "你好，世界！", "method": "GET"}
            self._send_json(data)
        elif self.path == '/users':
            data = {"users": ["张三", "李四", "王五"]}
            self._send_json(data)
        else:
            # 404 响应
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "路径不存在"}).encode())
    
    def _send_json(self, data):
        """辅助方法：发送 JSON 响应"""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def log_message(self, format, *args):
        """简化日志输出"""
        print(f"[服务器日志] {self.address_string()} - {format % args}")

# 启动服务器
if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8000), SimpleHandler)
    print("服务器启动在 http://127.0.0.1:8000")
    print("试试访问 /hello 或 /users")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.shutdown()

# 预期输出（在浏览器访问时）：
# 服务器启动在 http://127.0.0.1:8000
# [服务器日志] 127.0.0.1 - GET /hello HTTP/1.1
```

### 示例 3：完整的 REST API 模拟（客户端 + 服务器）

```python
"""
示例3：模拟 REST API 的完整流程
包含：服务器（处理请求）+ 客户端（发送请求）
运行后会自动测试所有 REST 方法
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import json
import threading

# ---------- 服务器部分 ----------
class RestHandler(BaseHTTPRequestHandler):
    """模拟一个简单的用户资源 REST API"""
    
    # 模拟数据库
    users = {
        1: {"name": "张三", "age": 25},
        2: {"name": "李四", "age": 30}
    }
    
    def do_GET(self):
        """处理 GET：获取资源"""
        if self.path == '/users':
            self._send_json(200, list(self.users.values()))
        elif self.path.startswith('/users/'):
            user_id = int(self.path.split('/')[-1])
            user = self.users.get(user_id)
            if user:
                self._send_json(200, user)
            else:
                self._send_json(404, {"error": "用户不存在"})
        else:
            self._send_json(404, {"error": "路径不存在"})
    
    def do_POST(self):
        """处理 POST：创建资源"""
        if self.path == '/users':
            # 读取请求体
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
            
            # 创建新用户
            new_id = max(self.users.keys()) + 1
            self.users[new_id] = body
            self._send_json(201, {"id": new_id, **body})
        else:
            self._send_json(404, {"error": "路径不存在"})
    
    def do_DELETE(self):
        """处理 DELETE：删除资源"""
        if self.path.startswith('/users/'):
            user_id = int(self.path.split('/')[-1])
            if user_id in self.users:
                del self.users[user_id]
                self._send_json(200, {"message": f"用户{user_id}已删除"})
            else:
                self._send_json(404, {"error": "用户不存在"})
        else:
            self._send_json(404, {"error": "路径不存在"})
    
    def _send_json(self, status, data):
        """发送 JSON 响应"""
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def log_message(self, format, *args):
        pass  # 静默模式

# ---------- 客户端测试函数 ----------
def test_api():
    """测试 REST API 的各种方法"""
    base_url = 'http://127.0.0.1:8000'
    
    # 1. GET 获取所有用户
    print("=== 测试 GET /users ===")
    resp = urlopen(f'{base_url}/users')
    print(f"状态码: {resp.status}")
    print(f"响应: {resp.read().decode()}\n")
    
    # 2. GET 获取单个用户
    print("=== 测试 GET /users/1 ===")
    resp = urlopen(f'{base_url}/users/1')
    print(f"状态码: {resp.status}")
    print(f"响应: {resp.read().decode()}\n")
    
    # 3. POST 创建新用户
    print("=== 测试 POST /users ===")
    data = json.dumps({"name": "王五", "age": 28}).encode()
    req = Request(f'{base_url}/users', data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    resp = urlopen(req)
    print(f"状态码: {resp.status}")
    print(f"响应: {resp.read().decode()}\n")
    
    # 4. DELETE 删除用户
    print("=== 测试 DELETE /users/2 ===")
    req = Request(f'{base_url}/users/2', method='DELETE')
    resp = urlopen(req)
    print(f"状态码: {resp.status}")
    print(f"响应: {resp.read().decode()}\n")
    
    # 5. 测试 404
    print("=== 测试不存在的资源 ===")
    try:
        urlopen(f'{base_url}/users/999')
    except HTTPError as e:
        print(f"状态码: {e.code}")
        print(f"响应: {e.read().decode()}")

# ---------- 主程序 ----------
if __name__ == '__main__':
    # 启动服务器线程
    server = HTTPServer(('127.0.0.1', 8000), RestHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    
    print("REST API 服务器已启动，开始测试...\n")
    
    # 运行测试
    test_api()
    
    # 关闭服务器
    server.shutdown()
    print("\n测试完成，服务器已关闭")

# 预期输出：
# REST API 服务器已启动，开始测试...
# === 测试 GET /users ===
# 状态码: 200
# 响应: [{"name": "张三", "age": 25}, {"name": "李四", "age": 30}]
# ...（后续测试类似）
```

---

## 3. 常用函数/调用速查表

| 函数/类 | 签名 | 用途 | 最小示例 |
|---------|------|------|----------|
| `urlopen` | `urlopen(url, timeout=None)` | 发送 HTTP 请求 | `resp = urlopen('http://example.com')` |
| `Request` | `Request(url, data=None, method='GET')` | 创建自定义请求 | `req = Request(url, method='POST')` |
| `HTTPError` | `HTTPError` | 捕获 HTTP 错误 | `except HTTPError as e:` |
| `HTTPServer` | `HTTPServer(addr, handler)` | 创建 HTTP 服务器 | `server = HTTPServer(('', 8000), Handler)` |
| `BaseHTTPRequestHandler` | `BaseHTTPRequestHandler` | 请求处理器基类 | `class MyHandler(BaseHTTPRequestHandler)` |
| `json.dumps` | `json.dumps(obj, ensure_ascii=False)` | 对象转 JSON 字符串 | `json.dumps({"a": 1})` |
| `json.loads` | `json.loads(str)` | JSON 字符串转对象 | `json.loads('{"a": 1}')` |

---

## 4. 新手易错点

### 易错点1：忘记设置请求头 Content-Type

❌ **错误写法**
```python
from urllib.request import urlopen, Request
import json

# 错误：POST 请求没有设置 Content-Type
data = json.dumps({"name": "测试"}).encode()
req = Request('http://httpbin.org/post', data=data, method='POST')

try:
    resp = urlopen(req)
    print(resp.read().decode())
except Exception as e:
    print(f"请求失败: {e}")
    # 运行可能报错：HTTP Error 400: BAD REQUEST
    # 因为服务器无法解析没有 Content-Type 的请求体
```

✅ **正确写法**
```python
from urllib.request import urlopen, Request
import json

# 正确：显式设置 Content-Type
data = json.dumps({"name": "测试"}).encode()
req = Request('http://httpbin.org/post', data=data, method='POST')
req.add_header('Content-Type', 'application/json')  # 关键！

try:
    resp = urlopen(req)
    print(f"状态码: {resp.status}")
    print(resp.read().decode())
except Exception as e:
    print(f"请求失败: {e}")

# 预期输出：
# 状态码: 200
# {"args": {}, "data": "{\"name\": \"测试\"}", ...}
```

**为什么错**：服务器需要知道请求体的格式才能正确解析。没有 `Content-Type` 头，服务器可能返回 400 错误或无法解析数据。

---

### 易错点2：GET 请求错误地携带请求体

❌ **错误写法**
```python
from urllib.request import urlopen, Request
import json

# 错误：GET 请求不应该有 body
data = json.dumps({"query": "python"}).encode()
req = Request('http://httpbin.org/get', data=data, method='GET')

try:
    resp = urlopen(req)
    print(resp.read().decode())
except Exception as e:
    print(f"请求失败: {e}")
    # 运行可能报错：HTTP Error 400: BAD REQUEST
    # 或返回意外结果，因为 GET 的 body 通常被忽略
```

✅ **正确写法**
```python
from urllib.request import urlopen
from urllib.parse import urlencode

# 正确：GET 参数放在 URL 查询字符串中
params = urlencode({"query": "python"})
url = f'http://httpbin.org/get?{params}'

try:
    resp = urlopen(url)
    print(f"状态码: {resp.status}")
    print(resp.read().decode())
except Exception as e:
    print(f"请求失败: {e}")

# 预期输出：
# 状态码: 200
# {"args": {"query": "python"}, ...}
```

**为什么错**：GET 的语义是"获取资源"，参数应该放在 URL 的查询字符串中。携带 body 不仅不符合规范，还可能导致兼容性问题。

---

### 易错点3：读取响应时忘记解码

❌ **错误写法**
```python
from urllib.request import urlopen

# 错误：直接打印字节对象
resp = urlopen('http://httpbin.org/get')
body = resp.read()  # 这是 bytes 类型
print(body)
# 输出：b'{"args": {}, ...}'  —— 前面有 b 前缀，不美观
```

✅ **正确写法**
```python
from urllib.request import urlopen

# 正确：解码为字符串
resp = urlopen('http://httpbin.org/get')
body = resp.read().decode('utf-8')  # 解码
print(body)
# 输出：{"args": {}, ...}  —— 干净的 JSON 字符串
```

**为什么错**：`read()` 返回的是字节对象（bytes），需要调用 `.decode()` 转换为字符串才能正常显示和处理。

---

### 易错点4：服务器端口被占用

❌ **错误写法**
```python
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

# 错误：没有处理端口占用异常
server = HTTPServer(('127.0.0.1', 8000), Handler)
server.serve_forever()
# 运行报错：OSError: [Errno 98] Address already in use
```

✅ **正确写法**
```python
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

# 正确：捕获端口占用异常
try:
    server = HTTPServer(('127.0.0.1', 8000), Handler)
    print("服务器启动成功")
    server.serve_forever()
except OSError as e:
    print(f"端口被占用: {e}")
    print("请尝试：1) 关闭占用端口的程序 2) 换一个端口")
    sys.exit(1)

# 预期输出：
# 服务器启动成功
# 或
# 端口被占用: [Errno 98] Address already in use
```

**为什么错**：端口是有限资源，如果之前运行的程序没有正常关闭，再次启动会失败。必须处理这个异常。

---

### 易错点5：URL 拼接错误

❌ **错误写法**
```python
from urllib.request import urlopen

# 错误：URL 拼接缺少斜杠
base = 'http://httpbin.org'
path = 'get'  # 缺少前导斜杠
url = base + path  # 结果是 http://httpbin.orgget

try:
    resp = urlopen(url)
    print(resp.read().decode())
except Exception as e:
    print(f"请求失败: {e}")
    # 运行报错：URLError: <urlopen error [Errno -2] Name or service not known>
```

✅ **正确写法**
```python
from urllib.request import urlopen

# 正确：确保路径有前导斜杠
base = 'http://httpbin.org'
path = '/get'  # 有前导斜杠
url = base + path  # 结果是 http://httpbin.org/get

try:
    resp = urlopen(url)
    print(f"状态码: {resp.status}")
    print(resp.read().decode())
except Exception as e:
    print(f"请求失败: {e}")

# 预期输出：
# 状态码: 200
# {"args": {}, ...}
```

**为什么错**：URL 的路径部分必须以 `/` 开头，否则会被当作域名的一部分，导致 DNS 解析失败。

---

## 5. 本课小练习

### 练习1：构建一个查询参数的 GET 请求

- **目标**：掌握如何正确地在 GET 请求中传递参数
- **引导步骤**：
  1. 使用 `urllib.parse.urlencode` 将字典转为查询字符串
  2. 拼接完整的 URL
  3. 发送请求并打印响应

- **起步代码**：
```python
from urllib.request import urlopen
from urllib.parse import urlencode

# 要发送的参数
params = {"name": "张三", "age": 25}

# TODO: 1. 使用 urlencode 将 params 转为查询字符串
# TODO: 2. 拼接完整 URL: http://httpbin.org/get?查询字符串
# TODO: 3. 发送请求并打印响应

# 预期输出：状态码 200，响应中包含你发送的参数
```

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
from urllib.request import urlopen
from urllib.parse import urlencode

# 要发送的参数
params = {"name": "张三", "age": 25}

# 1. 将字典转为查询字符串
query_string = urlencode(params)
print(f"查询字符串: {query_string}")

# 2. 拼接完整 URL
url = f'http://httpbin.org/get?{query_string}'
print(f"完整 URL: {url}")

# 3. 发送请求并打印响应
resp = urlopen(url)
print(f"状态码: {resp.status}")
print(resp.read().decode())

# 预期输出：
# 查询字符串: name=%E5%BC%A0%E4%B8%89&age=25
# 完整 URL: http://httpbin.org/get?name=%E5%BC%A0%E4%B8%89&age=25
# 状态码: 200
# {"args": {"name": "张三", "age": "25"}, ...}
```
</details>

---

### 练习2：处理 JSON 响应

- **目标**：学会解析 JSON 格式的响应数据
- **引导步骤**：
  1. 发送 GET 请求到 `http://httpbin.org/json`
  2. 读取响应并解码
  3. 用 `json.loads` 解析为 Python 字典
  4. 提取并打印特定字段

- **起步代码**：
```python
from urllib.request import urlopen
import json

# TODO: 1. 发送 GET 请求到 http://httpbin.org/json
# TODO: 2. 读取响应并解码为字符串
# TODO: 3. 用 json.loads 解析为字典
# TODO: 4. 打印字典的 keys 和其中一个值

# 预期输出：状态码 200，能打印出解析后的字典内容
```

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
from urllib.request import urlopen
import json

# 1. 发送 GET 请求
resp = urlopen('http://httpbin.org/json')
print(f"状态码: {resp.status}")

# 2. 读取并解码
body = resp.read().decode('utf-8')

# 3. 解析为字典
data = json.loads(body)

# 4. 打印内容
print(f"解析后的类型: {type(data)}")
print(f"顶层 keys: {list(data.keys())}")
print(f"slideshow 标题: {data['slideshow']['title']}")

# 预期输出：
# 状态码: 200
# 解析后的类型: <class 'dict'>
# 顶层 keys: ['slideshow']
# slideshow 标题: Sample Slide Show
```
</details>

---

### 练习3：模拟一个简单的 REST 客户端

- **目标**：综合运用 GET、POST 方法操作资源
- **引导步骤**：
  1. 定义 `get_user(user_id)` 函数：GET 请求获取用户
  2. 定义 `create_user(name, age)` 函数：POST 请求创建用户
  3. 调用这两个函数测试

- **起步代码**：
```python
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import json

BASE_URL = 'http://httpbin.org'

def get_user(user_id):
    """获取用户信息"""
    # TODO: 1. 构造 GET 请求 URL
    # TODO: 2. 发送请求并处理响应
    pass

def create_user(name, age):
    """创建新用户"""
    # TODO: 3. 构造 POST 请求（需要设置 Content-Type）
    # TODO: 4. 发送请求并处理响应
    pass

# 测试代码
if __name__ == '__main__':
    # TODO: 5. 调用 get_user 获取用户 1
    # TODO: 6. 调用 create_user 创建新用户
    pass

# 预期输出：两个函数都能正常返回并打印结果
```

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import json

BASE_URL = 'http://httpbin.org'

def get_user(user_id):
    """获取用户信息"""
    try:
        # 构造 GET 请求
        url = f'{BASE_URL}/get?user_id={user_id}'
        resp = urlopen(url)
        data = json.loads(resp.read().decode())
        print(f"GET 状态码: {resp.status}")
        print(f"GET 响应: {data['args']}")
        return data
    except HTTPError as e:
        print(f"GET 错误: {e.code}")
        return None

def create_user(name, age):
    """创建新用户"""
    try:
        # 构造 POST 请求
        url = f'{BASE_URL}/post'
        payload = json.dumps({"name": name, "age": age}).encode()
        req = Request(url, data=payload, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        resp = urlopen(req)
        data = json.loads(resp.read().decode())
        print(f"POST 状态码: {resp.status}")
        print(f"POST 响应: {data['json']}")
        return data
    except HTTPError as e:
        print(f"POST 错误: {e.code}")
        return None

if __name__ == '__main__':
    # 测试 GET
    print("=== 测试 GET ===")
    get_user(1)
    
    # 测试 POST
    print("\n=== 测试 POST ===")
    create_user("王五", 28)

# 预期输出：
# === 测试 GET ===
# GET 状态码: 200
# GET 响应: {'user_id': '1'}
# 
# === 测试 POST ===
# POST 状态码: 200
# POST 响应: {'name': '王五', 'age': 28}
```
</details>

---

## 6. 本课小结

🎯 **核心要点回顾**：

1. **HTTP 是客户端和服务器之间的通信协议**，包含请求方法（GET/POST/PUT/DELETE）、状态码（200/404/500）和 URL 三要素
2. **REST 是一种设计风格**，把数据看作"资源"，用 URL 定位资源，用 HTTP 方法操作资源
3. **Python 标准库足够实现 HTTP 通信**：`urllib` 做客户端，`http.server` 做服务器
4. **请求头很重要**：`Content-Type` 告诉服务器请求体的格式
5. **响应需要解码**：`read()` 返回字节，要用 `.decode('utf-8')` 转字符串

🚀 **下一课预告**：你已经掌握了 HTTP 和 REST 的基础，下一课我们将学习 **FastAPI 框架**——用更简洁的代码构建生产级的 REST API，自动生成文档、支持异步处理，让开发效率提升 10 倍！