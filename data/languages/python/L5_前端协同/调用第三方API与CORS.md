# L5 前端协同：调用第三方 API 与 CORS

## 1. 本课目标

- 能看懂并拆解一次第三方 API 调用：方法、URL、查询参数、请求头、JSON、状态码。
- 能用 Python 安全处理 API 响应：URL 编码、解析 JSON、检查状态码、超时与重试。
- 能解释浏览器的同源策略、CORS 预检请求和常见响应头，并知道什么时候该用后端代理。

> 本课练习框通常不能访问真实外网，所以我们用 `fake_*` 函数模拟“第三方 API”和“浏览器”。请把注意力放在请求结构、错误处理和 CORS 判断上。真实项目里把模拟函数换成 `urllib.request` 或 `requests` 即可，但检查逻辑不要省。

## 2. 概念讲解

### 2.1 第三方 API 是什么：去餐馆点菜，而不是自己种菜

API 可以理解成餐厅的菜单：  
你按菜单告诉服务员“我要什么”，服务员把订单送进厨房，最后端回来一盘菜。

换成程序语言：

- **你**：前端页面，或你的后端程序。
- **餐厅菜单**：API 文档，规定有哪些接口、参数怎么传。
- **点菜方式**：HTTP 方法，例如 `GET` 表示查询，`POST` 表示新建。
- **订单内容**：查询参数、请求头、请求体 JSON。
- **上菜结果**：HTTP 状态码 + 响应头 + 响应体。
- **第三方**：这个厨房不是你的服务器，可能限流、超时、改接口，所以必须做好错误处理。

API 返回的 JSON 本质上是一段**文本**，只是长得像 Python 字典。必须用 `json.loads()` 解析成 Python 对象，才能按键访问。

### 2.2 一次 API 请求的 5 个零件

1. **HTTP 方法**：`GET` 查询，`POST` 新建，`PUT/PATCH` 修改，`DELETE` 删除。
2. **URL 和查询参数**：例如 `/v1/weather?city=北京`。中文、空格、`&`、`=` 必须用 `urlencode` 编码。
3. **请求头**：例如 `Authorization: Bearer 密钥`、`Content-Type: application/json`、`Accept: application/json`。
4. **请求体**：`POST` 常用 JSON 字符串，不是 Python 字典本身。
5. **响应**：先看状态码，再看 JSON。`2xx` 成功；`4xx` 通常是你的请求有问题；`5xx` 通常是对方服务器有问题；`429` 表示请求太频繁。

一个很实用的习惯：**先看状态码，再解析业务字段。**  
因为错误响应里常常没有 `temp_c`、`items` 这类成功字段，直接取会得到 `KeyError`。

### 2.3 密钥安全：不要把秘密写进前端

大多数第三方 API 的密钥应该放在后端环境变量里，例如 `os.environ.get("WEATHER_API_KEY")`，由后端去调用第三方 API。前端只调用你自己的后端。

原因是浏览器里的 JavaScript、网络面板、打包文件都可能被用户看到。  
少数服务商提供“可公开的浏览器 key”，也会限制来源和权限；但这是例外，不是默认安全做法。

后端代理的典型路线是：

前端 → 你的后端 `/api/weather` → 第三方天气 API

这样密钥留在服务器，前端也不用直接处理第三方的 CORS 限制。

### 2.4 CORS：浏览器给前端设的“门卫”

先记住一句话：**CORS 是浏览器执行的跨域读取规则，不是服务器防火墙。**

“同源”要求三件事完全一致：

- 协议：`http` 还是 `https`
- 主机：`localhost` 还是 `api.example.com`
- 端口：`3000` 还是 `8000`

例如页面在 `http://localhost:3000`，请求 `http://localhost:8000/api/todos`，端口不同，就是跨域。

跨域时，浏览器会带上 `Origin` 请求头。服务器如果希望浏览器允许前端读取响应，就要返回类似：

- `Access-Control-Allow-Origin: http://localhost:3000`
- `Access-Control-Allow-Methods: GET, POST, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type, Authorization`

如果响应里缺少允许当前来源的 `Access-Control-Allow-Origin`，浏览器会阻止 JavaScript 读取响应。注意：请求可能已经到达服务器，服务器也可能已经处理了，只是浏览器不把结果交给前端 JS。所以 **CORS 不能代替登录、权限校验、参数校验和 CSRF 防护**。

有些请求会先发一个 `OPTIONS` 预检请求，比如：

- 使用 `PUT`、`DELETE`
- `Content-Type: application/json`
- 自定义请求头，例如 `Authorization`

预检通过后，浏览器才发真正的 `POST`、`PUT` 等请求。预检失败时，真正请求通常不会发出去。

带 Cookie 或 `credentials: "include"` 时，服务器的 `Access-Control-Allow-Origin` 不能是 `*`，必须是具体来源，并配合 `Access-Control-Allow-Credentials: true`。

如果第三方 API 不支持 CORS，前端直连就会失败。解决办法通常是：

1. 第三方明确支持浏览器跨域调用；
2. 由你的后端代理调用第三方，再把结果返回给前端；
3. 开发环境用 Vite/Next 等开发代理，把跨域请求伪装成同源请求。

Python 后端之间互相调用 API 时，一般没有浏览器 CORS 问题；CORS 主要发生在浏览器 JavaScript 发请求时。

## 3. 由浅入深的完整示例

### 示例1：拆解一次天气 API 请求：查询参数、状态码、JSON

```python
# 示例1：看清一次 API 请求：查询参数 + 请求头 + 状态码 + JSON 响应
import json
from urllib.parse import urlencode


def fake_weather_api(method, path, query, headers, body_text):
    """模拟第三方天气 API。真实项目中这里会换成网络请求。"""
    if method != "GET" or path != "/v1/weather":
        return 404, {"Content-Type": "application/json"}, json.dumps(
            {"error": "endpoint not found"}, ensure_ascii=False
        )

    if headers.get("Authorization") != "Bearer demo-key-123":
        return 401, {"Content-Type": "application/json"}, json.dumps(
            {"error": "invalid api key"}, ensure_ascii=False
        )

    city = query.get("city")
    if city == "北京":
        body = {
            "city": "北京",
            "temp_c": 26,
            "condition": "晴",
            "request_id": "req-1001",
        }
        return 200, {"Content-Type": "application/json"}, json.dumps(
            body, ensure_ascii=False
        )

    return 404, {"Content-Type": "application/json"}, json.dumps(
        {"error": f"city not found: {city}"}, ensure_ascii=False
    )


def get_weather(city, api_key):
    base_url = "https://api.weather-demo.test"
    path = "/v1/weather"
    query = {"city": city, "units": "metric", "lang": "zh"}

    # 查询参数必须编码，不能直接手拼中文、空格、& 和 =
    url = base_url + path + "?" + urlencode(query)
    print("请求 URL:", url)

    status, response_headers, response_text = fake_weather_api(
        method="GET",
        path=path,
        query=query,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        body_text="",
    )

    print("HTTP 状态:", status)

    # 响应体是 JSON 文本，要先解析成 Python 字典
    data = json.loads(response_text)

    if status != 200:
        raise RuntimeError(
            f"API 调用失败：{status}，原因：{data.get('error', '未知错误')}"
        )

    return data


weather = get_weather("北京", "demo-key-123")
print("解析后的 Python 字典:", weather)
print("北京温度:", weather["temp_c"], "摄氏度")
print("条件:", weather["condition"])

# 预期输出：
# 请求 URL: https://api.weather-demo.test/v1/weather?city=%E5%8C%97%E4%BA%AC&units=metric&lang=zh
# HTTP 状态: 200
# 解析后的 Python 字典: {'city': '北京', 'temp_c': 26, 'condition': '晴', 'request_id': 'req-1001'}
# 北京温度: 26 摄氏度
# 条件: 晴
```

### 示例2：网络会失败：超时、429、5xx 与重试

```python
# 示例2：第三方 API 可能超时、限流、暂时不可用；要有重试上限
import json
import time


class ApiError(Exception):
    pass


def fake_transport(attempt, path):
    """每次 attempt 代表一次网络请求；返回 (状态码, 响应头, 响应文本)。"""
    if attempt == 1:
        raise TimeoutError("连接超时")

    if attempt == 2:
        return 429, {
            "Content-Type": "application/json",
            "Retry-After": "0.01",
        }, json.dumps({"error": "rate limited", "request_id": "req-2002"})

    if attempt == 3:
        return 503, {"Content-Type": "application/json"}, json.dumps(
            {"error": "temporary unavailable"}
        )

    return 200, {"Content-Type": "application/json"}, json.dumps(
        {
            "ok": True,
            "items": ["任务A", "任务B"],
            "request_id": "req-2004",
        },
        ensure_ascii=False,
    )


def call_todo_api(max_attempts=4):
    path = "/v1/todos"

    for attempt in range(1, max_attempts + 1):
        print(f"第 {attempt} 次请求开始")

        try:
            status, headers, text = fake_transport(attempt, path)
            print(f"  收到状态 {status}")

            # 429 和 5xx 可以等一等再重试
            if status == 429 or 500 <= status < 600:
                retry_after = headers.get("Retry-After")
                if retry_after is not None:
                    wait_seconds = float(retry_after)
                else:
                    wait_seconds = 0.01 * attempt

                if attempt < max_attempts:
                    print(f"  可重试错误，{wait_seconds:.2f} 秒后重试")
                    time.sleep(wait_seconds)
                    continue

                raise ApiError(f"重试 {attempt} 次仍失败，最后状态 {status}")

            # 4xx 中除 429 外，通常不要盲目重试，先检查参数或密钥
            if 400 <= status < 500:
                data = json.loads(text)
                raise ApiError(f"请求有误：{status}，{data.get('error')}")

            # 2xx 才解析成功结果
            data = json.loads(text)
            return data

        except TimeoutError as exc:
            print(f"  超时：{exc}")

            if attempt == max_attempts:
                raise ApiError("多次超时，停止重试") from exc

            wait_seconds = 0.01 * attempt
            print(f"  {wait_seconds:.2f} 秒后重试")
            time.sleep(wait_seconds)

    raise ApiError("没有拿到结果")


result = call_todo_api()
print("最终结果:", result)
print("第一个任务:", result["items"][0])

# 预期输出：
# 第 1 次请求开始
#   超时：连接超时
#   0.01 秒后重试
# 第 2 次请求开始
#   收到状态 429
#   可重试错误，0.01 秒后重试
# 第 3 次请求开始
#   收到状态 503
#   可重试错误，0.03 秒后重试
# 第 4 次请求开始
#   收到状态 200
# 最终结果: {'ok': True, 'items': ['任务A', '任务B'], 'request_id': 'req-2004'}
# 第一个任务: 任务A
```

### 示例3：浏览器 CORS 检查：预检、允许来源、无 CORS 被拦截

```python
# 示例3：模拟浏览器跨域请求。真实浏览器会自己执行这些安全检查。
import json
from urllib.parse import urlsplit


def origin_of(url):
    """提取 origin：协议 + 主机 + 端口。"""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def api_server(method, url, request_headers, body_text, request_origin):
    """模拟后端 API。它通过 CORS 响应头告诉浏览器允许谁读取。"""
    path = urlsplit(url).path

    allow_headers = {
        "Access-Control-Allow-Origin": request_origin,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }

    if path == "/api/todos" and method == "OPTIONS":
        return 204, allow_headers, ""

    if path == "/api/todos" and method == "POST":
        data = json.loads(body_text)
        body = {"id": 1, "title": data["title"]}
        return 201, allow_headers, json.dumps(body, ensure_ascii=False)

    if path == "/api/no-cors" and method == "GET":
        # 故意不返回 CORS 头，模拟没有配置 CORS 的第三方接口
        return 200, {"Content-Type": "application/json"}, json.dumps(
            {"secret": "only same-origin"}, ensure_ascii=False
        )

    return 404, allow_headers, json.dumps(
        {"error": "not found"}, ensure_ascii=False
    )


class Browser:
    def __init__(self, page_url):
        self.origin = origin_of(page_url)

    def fetch(self, method, url, headers=None, body_text=""):
        headers = headers or {}

        # 同源请求不走 CORS 检查
        if origin_of(url) == self.origin:
            status, response_headers, text = api_server(
                method, url, headers, body_text, self.origin
            )
            print("同源请求直接放行")
            return status, response_headers, text

        content_type = headers.get("Content-Type", "").lower()
        simple_methods = {"GET", "HEAD", "POST"}
        simple_content_types = {
            "",
            "text/plain",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
        }
        simple_header_names = {
            "accept",
            "accept-language",
            "content-language",
            "content-type",
        }

        is_simple = (
            method in simple_methods
            and content_type in simple_content_types
            and all(name.lower() in simple_header_names for name in headers)
        )

        # 非简单请求先发 OPTIONS 预检
        if not is_simple:
            print("浏览器先发 OPTIONS 预检")
            p_status, p_headers, p_text = api_server(
                "OPTIONS", url, headers, "", self.origin
            )
            allow_origin = p_headers.get("Access-Control-Allow-Origin")
            allow_methods = p_headers.get("Access-Control-Allow-Methods", "")
            print("预检状态:", p_status)
            print("预检允许来源:", allow_origin)

            if allow_origin != self.origin:
                raise PermissionError("CORS 拦截：预检没有允许当前来源")

            allowed_methods = [item.strip() for item in allow_methods.split(",")]
            if method not in allowed_methods:
                raise PermissionError("CORS 拦截：预检没有允许当前方法")

        # 预检通过或简单请求，浏览器发实际请求
        status, response_headers, text = api_server(
            method, url, headers, body_text, self.origin
        )
        print("实际请求状态:", status)

        allow_origin = response_headers.get("Access-Control-Allow-Origin")
        if allow_origin != self.origin:
            raise PermissionError("CORS 拦截：实际响应没有允许当前来源")

        return status, response_headers, text


browser = Browser("http://localhost:3000")
print("页面来源:", browser.origin)

status, headers, text = browser.fetch(
    "POST",
    "http://localhost:8000/api/todos",
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer demo-token",
    },
    body_text=json.dumps({"title": "写 CORS 练习"}, ensure_ascii=False),
)
print("前端拿到的响应:", text)
print("解析后:", json.loads(text))

# 再演示一个没有 CORS 头的接口会被浏览器拦截
try:
    browser.fetch("GET", "http://localhost:8000/api/no-cors")
except PermissionError as exc:
    print("被拦截:", exc)

# 预期输出：
# 页面来源: http://localhost:3000
# 浏览器先发 OPTIONS 预检
# 预检状态: 204
# 预检允许来源: http://localhost:3000
# 实际请求状态: 201
# 前端拿到的响应: {"id": 1, "title": "写 CORS 练习"}
# 解析后: {'id': 1, 'title': '写 CORS 练习'}
# 实际请求状态: 200
# 被拦截: CORS 拦截：实际响应没有允许当前来源
```

## 4. 常用函数/调用速查表

| 函数/调用 | 签名 | 用途 | 最小示例 |
|---|---|---|---|
| `json.loads` | `json.loads(s)` | JSON 文本转 Python 对象 | `json.loads('{"id": 1}')` → `{'id': 1}` |
| `json.dumps` | `json.dumps(obj, ensure_ascii=False)` | Python 对象转 JSON 文本，中文不转义 | `json.dumps({"城市": "北京"}, ensure_ascii=False)` |
| `urlencode` | `urlencode(query_dict)` | 安全编码查询参数 | `urlencode({"city": "北京", "page": 2})` |
| `parse_qs` | `parse_qs(query_string)` | 把查询字符串解析成字典，值是列表 | `parse_qs("city=%E5%8C%97%E4%BA%AC")` |
| `urlsplit` | `urlsplit(url)` | 拆出协议、主机、端口、路径 | `urlsplit("http://a.com/x?q=1").netloc` → `'a.com'` |
| `urllib.request.Request` | `Request(url, data=None, headers=None, method="GET")` | 构造 HTTP 请求 | `Request("https://api.example.com", headers={"Authorization": "Bearer KEY"})` |
| `urllib.request.urlopen` | `urlopen(req, timeout=10)` | 发请求并设置超时 | `urlopen(req, timeout=10)` |
| `response.status` | `response.status` | 检查 HTTP 状态码 | `if response.status >= 400: print("错误")` |
| `response.headers.get` | `response.headers.get("Content-Type")` | 读取响应头 | `response.headers.get("Content-Type")` |
| CORS 来源检查 | `headers.get("Access-Control-Allow-Origin")` | 浏览器检查是否允许当前 Origin | `headers.get("Access-Control-Allow-Origin") == origin` |
| `os.environ.get` | `os.environ.get("API_KEY")` | 从环境变量安全读取密钥 | `os.environ.get("WEATHER_API_KEY")` |

## 5. 5 个新手易错点

### 易错点1：把 JSON 文本直接当字典用，忘记 `json.loads`

❌ **错误写法**

```python
import json

# 第三方 API 返回的 body 本质上是一段文本
body_text = '{"city": "北京", "temp_c": 26}'

# 错误：字符串不能按字典键取值
print(body_text["city"])

# 运行报错：TypeError: string indices must be integers, not 'str'
```

✅ **正确写法**

```python
import json

body_text = '{"city": "北京", "temp_c": 26}'
data = json.loads(body_text)
print(data["city"])
print(data["temp_c"])

# 预期输出：
# 北京
# 26
```

**为什么错**：网络响应体首先是一段 JSON 文本，必须先用 `json.loads()` 变成 Python 字典或列表，才能按键或下标访问。

### 易错点2：只看 JSON 内容，不检查 HTTP 状态码

❌ **错误写法**

```python
import json

# 模拟第三方 API 返回 404，但响应体仍然是合法 JSON
status = 404
body_text = '{"error": "city not found", "request_id": "req-404"}'
data = json.loads(body_text)

# 错误：把错误响应当成成功响应，直接取业务字段
print("温度:", data["temp_c"])

# 运行报错：KeyError: 'temp_c'
```

✅ **正确写法**

```python
import json

status = 404
body_text = '{"error": "city not found", "request_id": "req-404"}'
data = json.loads(body_text)

if status != 200:
    print("调用失败，HTTP 状态:", status)
    print("错误信息:", data.get("error"))
    print("请求编号:", data.get("request_id"))
else:
    print("温度:", data["temp_c"])

# 预期输出：
# 调用失败，HTTP 状态: 404
# 错误信息: city not found
# 请求编号: req-404
```

**为什么错**：HTTP 状态码代表请求是否成功，业务字段只有在成功响应里才可靠；应先判断状态码，再用 `.get()` 安全读取错误信息。

### 易错点3：手工拼接查询参数，不编码 `&`、空格、中文

❌ **错误写法**

```python
from urllib.parse import parse_qs

city = "北京&unit=metric"  # 假设用户输入里含有 &
bad_query = f"city={city}"
parsed = parse_qs(bad_query)
print("解析结果:", parsed)
print("取到的城市:", parsed["city"][0])

# 自检：期望完整保留城市名，但手工拼接会把它截断
assert parsed.get("city", [""])[0] == city, "查询参数被 & 截断，说明没有做 URL 编码"

# 运行报错：AssertionError: 查询参数被 & 截断，说明没有做 URL 编码
```

✅ **正确写法**

```python
from urllib.parse import urlencode, parse_qs

city = "北京&unit=metric"
good_query = urlencode({"city": city})
parsed = parse_qs(good_query)
print("编码后的查询串:", good_query)
print("解析结果:", parsed)
print("完整城市名:", parsed["city"][0])

# 预期输出：
# 编码后的查询串: city=%E5%8C%97%E4%BA%AC%26unit%3Dmetric
# 解析结果: {'city': ['北京&unit=metric']}
# 完整城市名: 北京&unit=metric
```

**为什么错**：用户输入、中文、空格、`&`、`=` 都可能改变 URL 结构，应统一用 `urlencode()`，不要用 f-string 手工拼查询参数。

### 易错点4：跨域响应忘了返回 `Access-Control-Allow-Origin`

❌ **错误写法**

```python
# 模拟浏览器读取跨域响应
def browser_read_response(page_origin, response_headers):
    allow_origin = response_headers.get("Access-Control-Allow-Origin")
    if allow_origin != page_origin:
        raise PermissionError(
            "CORS 拦截：响应缺少允许当前来源的 Access-Control-Allow-Origin"
        )
    return "前端可以读取响应"


page_origin = "http://localhost:3000"

# 错误：API 只返回了业务头，没有返回 CORS 头
response_headers = {"Content-Type": "application/json"}
print(browser_read_response(page_origin, response_headers))

# 运行报错：PermissionError: CORS 拦截：响应缺少允许当前来源的 Access-Control-Allow-Origin
```

✅ **正确写法**

```python
def browser_read_response(page_origin, response_headers):
    allow_origin = response_headers.get("Access-Control-Allow-Origin")
    if allow_origin != page_origin:
        raise PermissionError(
            "CORS 拦截：响应缺少允许当前来源的 Access-Control-Allow-Origin"
        )
    return "前端可以读取响应"


page_origin = "http://localhost:3000"
response_headers = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": page_origin,
}
print(browser_read_response(page_origin, response_headers))

# 预期输出：
# 前端可以读取响应
```

**为什么错**：跨域响应必须由服务器明确允许调用方 Origin；请求可能已经到达服务器，但浏览器读不到响应时前端仍会报 CORS 错误。

### 易错点5：带 Cookie/凭证的跨域请求用 `Access-Control-Allow-Origin: *`

❌ **错误写法**

```python
# 模拟浏览器对“凭证模式 + 通配符来源”的 CORS 检查
def browser_check_credentials(allow_origin, allow_credentials):
    if allow_credentials and allow_origin == "*":
        raise PermissionError(
            "CORS 拦截：凭证模式不能用 Access-Control-Allow-Origin: *"
        )
    return "通过"


# 错误：前端要带 Cookie，却让服务端返回 *
print(browser_check_credentials("*", True))

# 运行报错：PermissionError: CORS 拦截：凭证模式不能用 Access-Control-Allow-Origin: *
```

✅ **正确写法**

```python
def browser_check_credentials(allow_origin, allow_credentials):
    if allow_credentials and allow_origin == "*":
        raise PermissionError(
            "CORS 拦截：凭证模式不能用 Access-Control-Allow-Origin: *"
        )
    return "通过"


page_origin = "http://localhost:3000"
allow_credentials = True
print(browser_check_credentials(page_origin, allow_credentials))
print(browser_check_credentials(page_origin, False))

# 预期输出：
# 通过
# 通过
```

**为什么错**：带 Cookie 或 `credentials: "include"` 时，浏览器不允许 `*` 通配符，必须返回具体 Origin，并配合 `Access-Control-Allow-Credentials: true`，同时服务端仍要做权限和 CSRF 防护。

## 6. 本课小练习

### 练习1：安全拼出搜索请求并解析 JSON

- **目标**：掌握 `urlencode()`、`parse_qs()`、状态码检查和 JSON 解析。
- **引导步骤**：
  1. 用 `urlencode({"title": title, "page": 1})` 生成查询串。
  2. 用 `parse_qs()` 把查询串变回普通字典，注意值是列表。
  3. 调用 `fake_book_api()`，先检查 `status` 是否为 200，再返回 `data`。
  4. 运行后确认能打印第一条书的标题。
- **起步代码**：

```python
import json
from urllib.parse import urlencode, parse_qs


def fake_book_api(query):
    if query.get("title") == "Python API":
        return 200, json.dumps(
            {"items": [{"id": 7, "title": "Python API", "price": 59.0}]},
            ensure_ascii=False,
        )
    return 404, json.dumps({"error": "not found"}, ensure_ascii=False)


def search_books(title):
    # TODO 1：用 urlencode 把 {"title": title, "page": 1} 编码成查询串
    query_string = ""
    if not query_string:
        print("TODO：请先完成 URL 编码")
        return None

    # TODO 2：把 query_string 解析成普通字典
    # 提示：parse_qs(query_string) 的值是列表，要取第一个元素
    query = {}

    # TODO 3：调用 fake_book_api(query)，检查 status 是否为 200
    status, response_text = 500, "{}"
    data = json.loads(response_text)
    if status != 200:
        print("请求失败，状态码:", status)
        return None
    return data


result = search_books("Python API")
if result is not None:
    print("API 返回:", result)
    print("第一条标题:", result["items"][0]["title"])
```

- **预期输出**：补全并运行后，应看到：

```text
API 返回: {'items': [{'id': 7, 'title': 'Python API', 'price': 59.0}]}
第一条标题: Python API
```

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
import json
from urllib.parse import urlencode, parse_qs


def fake_book_api(query):
    if query.get("title") == "Python API":
        return 200, json.dumps(
            {"items": [{"id": 7, "title": "Python API", "price": 59.0}]},
            ensure_ascii=False,
        )
    return 404, json.dumps({"error": "not found"}, ensure_ascii=False)


def search_books(title):
    query_string = urlencode({"title": title, "page": 1})
    parsed = parse_qs(query_string)
    query = {key: values[0] for key, values in parsed.items()}

    status, response_text = fake_book_api(query)
    data = json.loads(response_text)

    if status != 200:
        print("请求失败，状态码:", status, "错误:", data.get("error"))
        return None

    return data


result = search_books("Python API")
if result is not None:
    print("API 返回:", result)
    print("第一条标题:", result["items"][0]["title"])

# 预期输出：
# API 返回: {'items': [{'id': 7, 'title': 'Python API', 'price': 59.0}]}
# 第一条标题: Python API
```

</details>

### 练习2：给 API 客户端加超时和重试

- **目标**：能对 `TimeoutError`、`429` 和 `5xx` 做有限次重试，成功后再解析 JSON。
- **引导步骤**：
  1. 在循环里调用 `fake_api(attempt)`，拿到 `status` 和 `text`。
  2. 如果状态是 `429` 或 `5xx`，且还没到最后一次，就打印提示并 `continue`。
  3. 捕获 `TimeoutError`，最后一次超时则抛出 `RuntimeError`。
  4. 成功时用 `json.loads(text)` 返回结果。
- **起步代码**：

```python
import json
import time


def fake_api(attempt):
    if attempt == 1:
        raise TimeoutError("第一次超时")
    if attempt == 2:
        return 429, json.dumps({"error": "rate limited"})
    return 200, json.dumps({"ok": True, "message": "成功"}, ensure_ascii=False)


def call_with_retry(max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        print("尝试", attempt)
        try:
            # TODO 1：调用 fake_api(attempt)，把返回值写成 status, text
            status, text = 500, "{}"

            # TODO 2：如果 status 是 429 或 5xx，且还有次数，就打印并 continue
            if status == 429 or 500 <= status < 600:
                print("TODO：请补全可重试逻辑")
                return None

            # TODO 3：非 2xx 的错误不要盲目重试；2xx 才 json.loads 并返回
            data = json.loads(text)
            return data
        except TimeoutError as exc:
            print("超时:", exc)
            # TODO 4：最后一次超时就抛出 RuntimeError，否则继续下一次
            return None

    raise RuntimeError("没有拿到结果")


result = call_with_retry()
print("结果:", result)
```

- **预期输出**：补全并运行后，应看到：

```text
尝试 1
超时: 第一次超时
尝试 2
可重试状态: 429
尝试 3
结果: {'ok': True, 'message': '成功'}
```

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
import json
import time


def fake_api(attempt):
    if attempt == 1:
        raise TimeoutError("第一次超时")
    if attempt == 2:
        return 429, json.dumps({"error": "rate limited"})
    return 200, json.dumps({"ok": True, "message": "成功"}, ensure_ascii=False)


def call_with_retry(max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        print("尝试", attempt)

        try:
            status, text = fake_api(attempt)

            if status == 429 or 500 <= status < 600:
                if attempt < max_attempts:
                    print("可重试状态:", status)
                    time.sleep(0.01)
                    continue
                raise RuntimeError(f"重试结束仍失败：{status}")

            if status >= 400:
                raise RuntimeError(f"不可重试错误：{status}, {text}")

            return json.loads(text)

        except TimeoutError as exc:
            print("超时:", exc)
            if attempt == max_attempts:
                raise RuntimeError("多次超时") from exc
            time.sleep(0.01)

    raise RuntimeError("没有拿到结果")


result = call_with_retry()
print("结果:", result)

# 预期输出：
# 尝试 1
# 超时: 第一次超时
# 尝试 2
# 可重试状态: 429
# 尝试 3
# 结果: {'ok': True, 'message': '成功'}
```

</details>

### 练习3：写一个简化版浏览器 CORS 判断函数

- **目标**：能根据 Origin、允许方法、是否带凭证，判断浏览器是否允许跨域请求。
- **引导步骤**：
  1. 如果 `credentials=True` 且 `allow_origin == "*"`，直接返回 `False`。
  2. 判断来源是否允许：通配符 `*` 或等于当前 `origin`。
  3. 判断方法是否在 `allow_methods` 的逗号列表中。
  4. 两个条件都满足才返回 `True`。
- **起步代码**：

```python
def browser_allows(origin, allow_origin, allow_methods, request_method="POST", credentials=False):
    # TODO 1：凭证模式不能用 "*"
    # TODO 2：判断 allow_origin 是否等于 "*" 或 origin
    # TODO 3：判断 request_method 是否在 allow_methods 的逗号列表中
    return False


page_origin = "http://localhost:3000"
print("案例1:", browser_allows(page_origin, page_origin, "GET, POST", credentials=True))
print("案例2:", browser_allows(page_origin, "*", "GET, POST", credentials=False))
print("案例3:", browser_allows(page_origin, "*", "GET", credentials=True))
print("案例4:", browser_allows(page_origin, page_origin, "GET", request_method="POST", credentials=True))
```

- **预期输出**：补全并运行后，应看到：

```text
案例1: True
案例2: True
案例3: False
案例4: False
```

<details><summary>👉 先自己试试，再点开看参考答案</summary>

```python
def browser_allows(origin, allow_origin, allow_methods, request_method="POST", credentials=False):
    if credentials and allow_origin == "*":
        return False

    origin_ok = allow_origin == "*" or allow_origin == origin
    allowed_methods = [item.strip().upper() for item in allow_methods.split(",")]
    method_ok = request_method.upper() in allowed_methods

    return origin_ok and method_ok


page_origin = "http://localhost:3000"
print("案例1:", browser_allows(page_origin, page_origin, "GET, POST", credentials=True))
print("案例2:", browser_allows(page_origin, "*", "GET, POST", credentials=False))
print("案例3:", browser_allows(page_origin, "*", "GET", credentials=True))
print("案例4:", browser_allows(page_origin, page_origin, "GET", request_method="POST", credentials=True))

# 预期输出：
# 案例1: True
# 案例2: True
# 案例3: False
# 案例4: False
```

</details>

## 7. 本课小结

- 第三方 API 是一次 HTTP 合同：先确认方法、URL、请求头、状态码，再解析 JSON 业务字段。
- 查询参数用 `urlencode`，响应文本用 `json.loads`，失败响应先看状态码，错误信息用 `.get()` 安全读取。
- 网络调用要有超时和有限重试；`429`、`5xx` 可退避重试，普通 `4xx` 更可能是参数、密钥或权限问题。
- CORS 是浏览器同源策略下的读取规则，不是服务器权限系统；跨域 JSON POST 常触发 `OPTIONS` 预检，带凭证时不能用 `*`。
- 第三方密钥优先放后端环境变量；前端直连只适合对方明确支持 CORS 且 key 可公开的场景，否则用后端代理。

下一课建议：用 Flask 或 FastAPI 写一个最小后端代理接口，把第三方 API 调用藏到后端，并亲手配置一次 CORS。