# -*- coding: utf-8 -*-
"""知识库训练：把蒸馏语料 + 内置教材注入知识库并重建 TF-IDF 索引，
输出训练指标（文档数/词表规模/检索命中率）。
"""
import json
from pathlib import Path

from core.config import data_dir
from core.knowledge import kb, KnowledgeBase
from training.distill import load_dataset, OUT_FILE

# 开箱内置的种子知识（不依赖网络/模型，保证冷启动可用）
SEED_DOCS = [
    {"id": "seed:py:memory", "title": "Python 内存管理与泄漏防范", "lang": "python",
     "tags": ["memory", "best-practice"], "source": "seed", "text": """
Python 使用引用计数+分代GC。常见泄漏点：1) 全局容器只增不减 2) 循环引用且带 __del__
3) 未关闭的文件/网络连接 4) 线程/定时器未回收 5) 闭包持有大对象 6) lru_cache 无 maxsize。
防范：with 管理资源；用 weakref 打破循环引用；线程设 daemon 并 join；定时器保存句柄及时 cancel；
大缓存用 functools.lru_cache(maxsize=128)。检测：tracemalloc 对比两轮快照的堆增长。
"""},
    {"id": "seed:py:func", "title": "Python 常用函数速查", "lang": "python",
     "tags": ["cheatsheet"], "source": "seed", "text": """
len(x) 长度; sorted(x, key=, reverse=) 排序不改原列表; enumerate(x) 带下标迭代;
zip(a,b) 并行迭代; map/filter 函数式; any/all 聚合判定; range(start,stop,step);
open(path, mode, encoding) 配 with; json.loads/dumps; re.match/search/sub;
collections.Counter 统计/deque 双端队列/defaultdict; itertools.product/permutations/combinations;
os.path.join/exists; datetime.now/strftime; random.choice/shuffle; sum/min/max。
"""},
    {"id": "seed:js:func", "title": "JavaScript 常用函数速查", "lang": "javascript",
     "tags": ["cheatsheet"], "source": "seed", "text": """
arr.map/filter/reduce/forEach/find/some/every/sort(注意比较器)/slice/splice;
Object.keys/values/entries; JSON.parse/stringify; Promise.all/race/allSettled;
fetch(url,{method,headers,body}) 返回 Promise 需 .json(); setTimeout/clearTimeout;
addEventListener/removeEventListener; document.querySelector/querySelectorAll;
class/extends/super; 模板字符串 `${}`; 解构赋值; 扩展运算符 ...; async/await + try/catch。
"""},
    {"id": "seed:java:func", "title": "Java 常用 API 速查", "lang": "java",
     "tags": ["cheatsheet"], "source": "seed", "text": """
ArrayList<String> list = new ArrayList<>(); list.add/get/set/remove/size;
HashMap<K,V>: put/get/getOrDefault/containsKey/entrySet; HashSet: add/contains;
Collections.sort/list.sort(Comparator.comparing()); Stream: filter/map/collect(Collectors.toList());
try-with-resources 自动关闭流; StringBuilder.append/toString; String.format/split/equals(勿用==);
synchronized/Lock; ExecutorService + shutdown; @Override/@FunctionalInterface。
"""},
    {"id": "seed:algo:ds", "title": "算法模板速查（力扣常用）", "lang": "general",
     "tags": ["algorithm"], "source": "seed", "text": """
二分查找: while l<=r, mid=(l+r)//2, 收缩区间防死循环。
两数之和: 哈希表一次遍历 O(n)。
反转链表: prev/cur 三指针迭代。
有效括号: 栈匹配, 左括号入栈, 右括号弹栈比对。
爬楼梯: 斐波那契, 滚动变量 O(1) 空间。
最大子数组: Kadane 前缀和/当前和。
无重复最长子串: 滑动窗口 + 字符最后位置表。
零钱兑换: 完全背包 dp[i]=min(dp[i-coins])+1。
LRU: 哈希表+双向链表, 头部最新尾部最旧。
复杂度: 数组遍历 O(n), 排序 O(nlogn), 嵌套循环警惕 O(n^2)。
"""},
    {"id": "seed:cpp:memory", "title": "C++ 内存管理与RAII", "lang": "c++",
     "tags": ["memory", "best-practice"], "source": "seed", "text": """
C++ 手动内存管理核心是 RAII：资源获取即初始化，把资源生命周期绑定到对象作用域。
new/delete 必须成对；优先用智能指针：unique_ptr 独占(零开销,不可复制)、shared_ptr 引用计数、
weak_ptr 打破循环引用。容器选型：vector 默认首选、map 红黑树有序、unordered_map 哈希更快。
禁用裸 new/delete；栈对象优先；返回值用值语义或 unique_ptr。检测泄漏：Valgrind/ASan。
"""},
    {"id": "seed:go:concurrency", "title": "Go 并发与工程要点", "lang": "go",
     "tags": ["concurrency", "best-practice"], "source": "seed", "text": """
goroutine 轻量协程：go f() 启动；channel 通信：ch := make(chan T, n)，无缓冲同步、有缓冲异步。
共享状态用 sync.Mutex 保护或干脆用 channel 传递数据（不要通过共享内存来通信）。
select 多路复用；context 控制超时与取消。defer 延迟释放资源(文件/锁)。
错误处理惯例：if err != nil 逐层返回；errors.Is/As 判类型。go test 表驱动测试。
net/http 标准库即可起 REST 服务；json.NewDecoder/Encoder 处理请求响应。
"""},
    {"id": "seed:sql:basics", "title": "SQL 核心速查", "lang": "sql",
     "tags": ["cheatsheet", "database"], "source": "seed", "text": """
CRUD: INSERT INTO t(cols) VALUES(...); SELECT cols FROM t WHERE cond ORDER BY col DESC LIMIT n;
UPDATE t SET c=v WHERE id=...; DELETE FROM t WHERE id=...（务必带WHERE）。
聚合: COUNT/SUM/AVG/MIN/MAX + GROUP BY + HAVING(聚合后过滤)。
JOIN: INNER JOIN 取交集、LEFT JOIN 保左表；子查询与 EXISTS。
索引加速 WHERE/JOIN 列；事务 BEGIN/COMMIT/ROLLBACK 保证原子性。
防注入：永远参数化查询(占位符?)，不拼接字符串。外键约束保证引用完整性。
"""},
    {"id": "seed:web:frontend", "title": "HTML/CSS 前端基础速查", "lang": "html-css",
     "tags": ["frontend", "cheatsheet"], "source": "seed", "text": """
HTML 骨架: <!DOCTYPE html> + html/head(meta charset/viewport, title)/body。
常用标签: div/span 语义化 header/nav/main/section/footer; a href; img alt; ul/ol/li; form+input/button。
CSS: 选择器(类./id#/后代空格); 盒子模型 content+padding+border+margin;
布局: Flex(align/justify 一维) 与 Grid(二维 grid-template-columns) 优先于 float;
定位 static/relative/absolute/fixed/sticky; 响应式 @media (max-width:768px);
变量 --c: value + var(--c); 交互 transition/transform/hover。
调试: F12 元素面板看盒子与样式; Console 看报错。
"""},
    {"id": "seed:py:mysql", "title": "Python 连接 MySQL(MariaDB) 速查", "lang": "python",
     "tags": ["database", "cheatsheet"], "source": "seed", "text": """
pip install pymysql（纯 Python 驱动，兼容 MySQL/MariaDB）。
连接: conn = pymysql.connect(host='127.0.0.1', port=3306, user='root',
     password='...', database='db', charset='utf8mb4', connect_timeout=5)
查询: with conn.cursor() as cur: cur.execute("SELECT ..."); rows = cur.fetchall()
写入: cur.execute("INSERT ...", params); conn.commit()（务必提交）
务必参数化查询防注入: cur.execute("SELECT * FROM t WHERE id=%s", (uid,))，不要 f-string 拼接。
用 try/finally 或上下文管理确保 conn.close()；查字段: cur.description。
本机学习助手可用 `python main.py db "SELECT ..."` 或 GUI 数据库页签直接操作。
"""},
    {"id": "seed:web:fullstack", "title": "前后端开发要点", "lang": "general",
     "tags": ["fullstack"], "source": "seed", "text": """
后端: RESTful 设计(GET查/POST增/PUT改/DELETE删); 参数校验; 统一错误处理; CORS 配置;
SQLite/MySQL 持久化; 密码哈希存储。前端: fetch 调 API + 加载/错误状态; 表单校验;
事件绑定防重复; XSS 防范(textContent 优先于 innerHTML)。联调: 先 curl 测后端, 再接前端;
跨域用后端 CORS 中间件解决。
"""},
    # ---- Python 进阶 ----
    {"id": "seed:py:oop", "title": "Python 类与面向对象要点", "lang": "python",
     "tags": ["oop"], "source": "seed", "text": """
class 定义类; __init__ 初始化; self 引用实例; @classmethod 操作类、@staticmethod 独立函数。
继承: class Child(Parent); super().__init__() 调用父类构造; 方法重写 override。
@property 把方法当属性读; @x.setter 写; 魔术方法 __str__/__repr__/__eq__/__hash__。
dataclass 自动生成 __init__/__repr__/__eq__; 组合优于继承; 接口约定用 ABC 抽象基类。
"""},
    {"id": "seed:py:async", "title": "Python 并发与异步要点", "lang": "python",
     "tags": ["concurrency"], "source": "seed", "text": """
线程: threading.Thread(target=f, daemon=True).start(); join() 等待; 共享状态加 Lock。
多进程: multiprocessing 绕过 GIL 跑 CPU 密集; 进程间用 Queue/Pipe。
异步: async def + await; asyncio.run(main()); asyncio.gather() 并发等待;
事件循环只调度协程, IO 密集才快; aiohttp 做异步请求; 注意 await 不要在同步代码里调用。
选择: IO 密集用 asyncio/线程池, CPU 密集用 multiprocessing。
"""},
    {"id": "seed:py:typehint", "title": "Python 类型提示与静态检查", "lang": "python",
     "tags": ["type"], "source": "seed", "text": """
类型注解: def f(x: int, y: str) -> bool: ...; 变量 x: list[int] = []。
泛型: from typing import List, Dict, Optional, Union, Callable, Tuple。
Optional[X] = X | None; Union[A,B] = A | B; Callable[[int], str] 表示函数类型。
Any 逃生舱(少用); TypeVar 定义泛型; mypy/pyright 静态检查; 运行时不强制, 靠工具保证。
dataclass + type hint 组合提升可读性; 复杂嵌套用 type alias。
"""},
    {"id": "seed:py:testing", "title": "Python 单元测试与调试", "lang": "python",
     "tags": ["testing"], "source": "seed", "text": """
unittest: class TestX(unittest.TestCase); def test_xxx(self); assertEqual/assertRaises。
pytest: 函数名 test_ 开头即用例; assert 直接用; fixture 用 @pytest.fixture 注入依赖。
pytest.raises(ValueError) 断言异常; parametrize 批量参数化; mock: unittest.mock.patch 替换依赖。
覆盖率: coverage run -m pytest; coverage report。调试: pdb 断点 breakpoint()/pdb.set_trace()。
"""},
    {"id": "seed:py:iter", "title": "Python 迭代器/生成器/装饰器速查", "lang": "python",
     "tags": ["cheatsheet"], "source": "seed", "text": """
迭代器: __iter__/__next__; for 循环自动调用 next(); StopIteration 结束。
生成器: yield 暂停返回; 惰性求值省内存; 生成器表达式 (x*2 for x in xs)。
装饰器: def deco(f): 内层 wrapper 返回; @functools.wraps(f) 保留元信息;
带参装饰器再包一层; 常用于日志/计时/缓存/鉴权; 闭包捕获外层变量(nonlocal 修改)。
next(gen) 手动取; list(gen) 一次耗尽。
"""},
    # ---- JavaScript 进阶 ----
    {"id": "seed:js:async", "title": "JavaScript 异步与 Promise 要点", "lang": "javascript",
     "tags": ["async"], "source": "seed", "text": """
Promise: new Promise((resolve,reject)=>{...}); then/catch/finally 链式; Promise.all/race/allSettled。
async 函数返回 Promise; await 等结果; try/catch 抓 reject; 事件循环: 宏任务(setTimeout) vs 微任务(Promise)。
fetch(url).then(r=>r.json()); 错误要 catch; async/await 里 fetch 记得 try。
避免回调地狱; 并发用 Promise.all; 串行用 for...of + await。
"""},
    {"id": "seed:js:closure", "title": "JavaScript 闭包/this/作用域要点", "lang": "javascript",
     "tags": ["closure"], "source": "seed", "text": """
var 函数级作用域有提升; let/const 块级作用域无提升; const 只绑不变量引用。
闭包: 内层函数引用外层变量, 外层执行完仍可访问; 用于私有变量/柯里化/防抖节流。
this: 普通函数看调用者(谁调用指向谁); 箭头函数无 this, 继承外层; 事件回调里箭头函数常用。
防抖 debounce(延迟执行)/节流 throttle(固定频率); 经典面试: 循环里 var + setTimeout 闭包陷阱用 let 或 IIFE 解决。
"""},
    {"id": "seed:js:module", "title": "JavaScript 模块化与工具链", "lang": "javascript",
     "tags": ["module"], "source": "seed", "text": """
ES 模块: export 具名导出/export default 默认导出; import {x} from / import d from。
CommonJS(Node): module.exports / require()。package.json: scripts 定义命令; dependencies/devDependencies。
npm install/add; npx 执行包; 打包器: Vite(快)/Webpack; 转译: Babel/TS。
eslint/prettier 规范代码; 环境变量 process.env 或 import.meta.env(Vite)。
"""},
    # ---- Java 进阶 ----
    {"id": "seed:java:collections", "title": "Java 集合框架速查", "lang": "java",
     "tags": ["cheatsheet"], "source": "seed", "text": """
List 接口: ArrayList(随机访问快)/LinkedList(插入删除快); add/get/remove/size/contains。
Map: HashMap(无序)/TreeMap(有序)/LinkedHashMap(插入序); put/get/getOrDefault/remove/containsKey。
Set: HashSet(去重无序)/TreeSet(有序)/LinkedHashSet; 去重依赖 equals+hashCode 同时重写。
Queue/Deque: ArrayDeque 栈和队列; PriorityQueue 优先队列。迭代安全: 遍历删除用 Iterator.remove。
Arrays.asList 返回定长; List.of 不可变; 排序 Collections.sort / list.sort(Comparator)。
"""},
    {"id": "seed:java:concurrency", "title": "Java 并发与线程安全要点", "lang": "java",
     "tags": ["concurrency"], "source": "seed", "text": """
线程: new Thread(r).start(); Runnable 接口; ExecutorService + submit + shutdown(awaitTermination)。
同步: synchronized 方法/块; Lock/ReentrantLock; volatile 保证可见性不保证原子性。
线程安全容器: ConcurrentHashMap; CopyOnWriteArrayList; 计数器 AtomicInteger。
线程池: Executors.newFixedThreadPool; 注意队列与拒绝策略; 避免在锁内做耗时操作。
wait/notify 配合 synchronized; 用 CompletableFuture 做异步编排。
"""},
    # ---- Go ----
    {"id": "seed:go:basics", "title": "Go 基础语法速查", "lang": "go",
     "tags": ["cheatsheet"], "source": "seed", "text": """
变量: var x int = 1 / x := 1(短声明); 常量 const; 类型 int/float64/string/bool/byte/rune。
容器: 数组 [n]T 定长; 切片 []T 动态 append; map[string]int; 遍历 for i,v := range。
函数: func f(a int) (int, error) 多返回值; 指针 *T/&x; 方法 func (r T) M()。
结构体 struct; 接口 interface{ M() } 隐式实现(鸭子类型); 类型断言 v, ok := i.(T)。
defer 后进先出, 资源释放; panic/recover 处理崩溃。
"""},
    {"id": "seed:go:concurrency2", "title": "Go goroutine 与 channel 进阶", "lang": "go",
     "tags": ["concurrency"], "source": "seed", "text": """
goroutine: go f() 轻量并发; channel: ch := make(chan T) 无缓冲同步 / make(chan T, n) 有缓冲。
发送 ch <- v; 接收 v := <-ch; 关闭 close(ch); range 遍历直到关闭。
select 多路复用+default 非阻塞; time.After 超时; context 传递取消信号。
sync.WaitGroup 等待协程; sync.Mutex/atomic 保护共享状态; 经典: 用 channel 传递数据而非共享内存。
死锁: 无缓冲 channel 收发需配对; goroutine 泄漏: 忘记退出条件。
"""},
    # ---- C++ ----
    {"id": "seed:cpp:stl", "title": "C++ STL 容器与算法速查", "lang": "c++",
     "tags": ["cheatsheet"], "source": "seed", "text": """
容器: vector 动态数组; string; map/unordered_map; set/unordered_set; deque; stack; queue; priority_queue。
常用: push_back/emplace_back; find(v.begin(),v.end(),x); sort(v.begin(),v.end());
algorithm 头: reverse/count/accumulate/lower_bound/upper_bound/binary_search。
迭代器 begin/end; 范围 for(auto& x : v); auto 类型推导; 注意 map 用 pair<const K,V>。
reserve 预分配减少扩容; 传引用避免拷贝; const 引用传参。
"""},
    {"id": "seed:cpp:pointer", "title": "C++ 指针/引用/智能指针要点", "lang": "c++",
     "tags": ["pointer"], "source": "seed", "text": """
指针: T* p = &x; *p 解引用; nullptr 空指针; 引用 T& 别名不可为空不可改绑。
智能指针: unique_ptr 独占(不可复制, move 转移); shared_ptr 引用计数; weak_ptr 打破循环引用。
make_unique/make_shared 优先于 new; 栈对象优先于堆对象。
new/delete 成对(现代 C++ 尽量不用裸 new); RAII 把资源绑定到对象生命周期。
数组退化为指针; 指针运算; 悬垂指针(释放后使用)与内存泄漏两大坑。
"""},
    # ---- SQL 进阶 ----
    {"id": "seed:sql:advanced", "title": "SQL 高级查询与优化速查", "lang": "sql",
     "tags": ["advanced"], "source": "seed", "text": """
窗口函数: ROW_NUMBER()/RANK()/DENSE_RANK() OVER (PARTITION BY x ORDER BY y)。
CTE: WITH t AS (SELECT ...) SELECT ... FROM t; 递归 CTE 处理层级数据。
分页: LIMIT n OFFSET m(大数据用 keyset 更稳); 去重 DISTINCT 与 GROUP BY 区别。
优化: WHERE 用索引列避免函数包裹; EXPLAIN 看执行计划; 避免 SELECT *。
EXISTS 半连接常快于 IN; UNION 去重 / UNION ALL 不去重; 事务隔离级别。
"""},
    {"id": "seed:sql:index", "title": "SQL 索引与事务要点", "lang": "sql",
     "tags": ["index"], "source": "seed", "text": """
索引: CREATE INDEX idx ON t(col); 加速 WHERE/JOIN/ORDER BY; B+树结构。
复合索引遵循最左前缀; 索引不是越多越好(写放大); 覆盖索引避免回表。
事务: BEGIN; ...; COMMIT/ROLLBACK; 原子性/一致性/隔离性/持久性(ACID)。
隔离级别: 读未提交/读已提交/可重复读/串行化; 脏读/不可重复读/幻读。
悲观锁 SELECT ... FOR UPDATE; 乐观锁用版本号; 外键保证引用完整性。
"""},
    # ---- 框架 ----
    {"id": "seed:fw:langchain", "title": "LangChain 核心概念速查", "lang": "langchain",
     "tags": ["framework"], "source": "seed", "text": """
核心: PromptTemplate 提示模板; LLM 封装; Chain 把多步串起来; Memory 记忆; Tool 工具。
LCEL: 用 | 管道连接 runnable; chain = prompt | model | output_parser。
RAG: DocumentLoader 加载 → TextSplitter 切分 → Embedding 向量化 → VectorStore 存储 → Retriever 检索。
@tool 装饰器注册函数; Agent 用 ReAct(Thought/Action/Observation) 规划调用工具。
OutputParser 把文本解析成结构化对象; ConversationBufferMemory 存对话历史。
"""},
    {"id": "seed:fw:fastapi", "title": "FastAPI 核心速查", "lang": "fastapi",
     "tags": ["framework"], "source": "seed", "text": """
@app.get/post/put/delete 路由; 路径参数 @app.get("/items/{id}"); 查询参数自动绑定。
Pydantic: class Item(BaseModel); 字段类型即校验; response_model 定义响应结构。
依赖注入 Depends(func); HTTPException(status_code, detail) 抛错误; APIRouter 分组路由。
async def 支持异步; UploadFile 文件上传; CORSMiddleware 跨域。
自带 Swagger /docs; 测试用 TestClient; 生产用 uvicorn 启动。
"""},
    {"id": "seed:fw:react", "title": "React Hooks 核心速查", "lang": "react",
     "tags": ["framework"], "source": "seed", "text": """
组件: function C(props); JSX; Props 传参只读。Hooks 规则: 顶层调用, 不放进循环/条件。
useState 状态; useEffect 副作用(依赖数组控制触发); useRef 引用 DOM/保存可变值不触发渲染。
useContext 跨层传值; useReducer 复杂状态; useMemo 缓存计算/useCallback 缓存函数。
条件渲染 &&/三元; 列表渲染 map 必须 key; 受控组件 value+onChange。
性能: memo 包裹组件; 状态提升; 避免在渲染里创建新对象。
"""},
    {"id": "seed:fw:vue", "title": "Vue 3 组合式 API 速查", "lang": "vue",
     "tags": ["framework"], "source": "seed", "text": """
组合式: <script setup>; ref 响应式基本类型(.value 访问); reactive 响应式对象。
computed 计算属性(缓存); watch 侦听; 模板语法 {{ }} / v-if / v-for(:key) / v-bind(:x) / v-on(@click)。
组件通信: props(defineProps) 父传子; emit(defineEmits) 子传父; provide/inject 跨层。
生命周期 onMounted/onUnmounted; v-model 双向绑定; 插槽 slot。
Pinia: defineStore 状态管理; Vue Router: createRouter + <router-view>。
"""},
    {"id": "seed:fw:springboot", "title": "Spring Boot 核心速查", "lang": "springboot",
     "tags": ["framework"], "source": "seed", "text": """
@RestController + @GetMapping/@PostMapping 写接口; @RequestBody/@PathVariable/@RequestParam 绑定。
分层: Controller(接收请求)/Service(业务)/Repository(数据); @Autowired 或构造注入依赖。
@ConfigurationProperties 配置; @Value 注入; application.yml 多环境 profile。
数据: Spring Data JPA @Entity + @Repository; @Transactional 事务。
异常: @ControllerAdvice + @ExceptionHandler 统一处理; @Valid + 校验注解。
"""},
    {"id": "seed:fw:django", "title": "Django 核心速查", "lang": "django",
     "tags": ["framework"], "source": "seed", "text": """
MTV: Model(数据)/Template(模板)/View(视图); 项目 startproject, 应用 startapp。
模型: class M(models.Model) 字段; makemigrations + migrate 迁移; ORM: M.objects.filter/get/create。
QuerySet 惰性求值; F()/Q() 复杂查询; select_related 优化外键。
视图函数 + URL 映射; 模板渲染 render; Form 表单校验。
DRF: Serializer/ModelViewSet; REST API; Admin 后台管理。
"""},
    {"id": "seed:fw:docker", "title": "Docker 核心速查", "lang": "docker",
     "tags": ["framework"], "source": "seed", "text": """
镜像: docker build -t name . 由 Dockerfile 构建; docker pull/push; 镜像分层缓存。
容器: docker run -p 8080:80 -v 卷:目录 -e ENV; docker ps/logs/exec/stop/rm。
Dockerfile: FROM 基础镜像; RUN 执行命令; COPY 拷贝文件; CMD 启动命令; ENTRYPOINT。
多阶段构建减小体积; .dockerignore 排除文件; ENTRYPOINT+CMD 组合传参。
Compose: docker-compose.yml 编排多服务; up/down; depends_on 依赖。
"""},
    {"id": "seed:fw:typescript", "title": "TypeScript 类型系统速查", "lang": "typescript",
     "tags": ["framework"], "source": "seed", "text": """
基础: string/number/boolean; interface 定义对象形状; type 类型别名; 联合 | 交叉 &。
泛型: function f<T>(x:T):T; 约束 <T extends U>; 工具类型 Partial/Pick/Omit/Record/ReturnType。
类型收窄: typeof instanceof 判断; 可选 ?; 非空断言 !; as 断言。
enum 枚举; readonly 只读; 函数重载; 索引签名 [key:string]:T。
tsc 编译; tsconfig strict 严格模式; 与 React 用 FC/PropsWithChildren。
"""},
    # ---- 算法进阶 ----
    {"id": "seed:algo:tree", "title": "树与图算法模板速查", "lang": "general",
     "tags": ["algorithm"], "source": "seed", "text": """
二叉树遍历: 前序(根左右)/中序(左根右)/后序(左右根)递归; 层序用队列 BFS。
DFS 递归带 visited 防环; BFS 队列求最短路径; 邻接表存图。
BST 二叉搜索树: 左小右大, 中序有序; 平衡用 AVL/红黑树。
并查集 union-find 处理连通性; 拓扑排序 Kahn 入度法。
递归三要素: 终止条件/递推/返回值; 树的题目多从「子问题」角度想。
"""},
    {"id": "seed:algo:dp", "title": "动态规划入门要点", "lang": "general",
     "tags": ["algorithm"], "source": "seed", "text": """
DP 步骤: 定义状态 dp[i] 含义 → 找转移方程 → 初始化边界 → 遍历顺序 → 空间优化。
经典: 爬楼梯/斐波那契; 背包 0-1/完全; 最长递增子序列; 编辑距离; 打家劫舍。
状态压缩: 只用前一两个状态时滚动变量/一维数组; 前缀和优化区间和。
记忆化搜索 = 递归 + 缓存; 子序列 vs 子数组(连续)。
复杂度: 状态数 × 每个状态转移代价; 空间 O(n) 或 O(1)。
"""},
    {"id": "seed:algo:complexity", "title": "算法复杂度分析速查", "lang": "general",
     "tags": ["algorithm"], "source": "seed", "text": """
时间复杂度: 看最坏执行次数随 n 增长; 常见 O(1)<O(logn)<O(n)<O(nlogn)<O(n^2)<O(2^n)。
空间复杂度: 额外开辟的存储(递归栈也算); 排序: 快排平均 O(nlogn); 归并稳定 O(nlogn)。
二分 O(logn); 哈希查 O(1) 平均; 遍历数组 O(n); 嵌套循环看是不是 O(n^2)。
主定理判分治; 摊还分析(如动态数组扩容); 大 O 忽略常数与低阶项。
选择结构: 数据量 1e5 内 O(nlogn) 通常可过, O(n^2) 会超时。
"""},
    {"id": "seed:algo:sliding", "title": "滑动窗口与双指针模板", "lang": "general",
     "tags": ["algorithm"], "source": "seed", "text": """
双指针: 相向(两数之和/回文)/同向(快慢指针判环)/左右边界(排序后夹逼)。
滑动窗口: 维护 [left,right) 窗口, right 扩展满足条件, left 收缩找最小。
典型: 无重复最长子串; 最小覆盖子串; 和为 target 的连续子数组。
技巧: 用哈希表记字符最后位置; 窗口内计数; 前缀和差。
复杂度 O(n): 两个指针各移动一次, 别写成 O(n^2)。
"""},
    {"id": "seed:algo:backtrack", "title": "回溯算法模板速查", "lang": "general",
     "tags": ["algorithm"], "source": "seed", "text": """
回溯 = 决策树遍历 + 剪枝; 模板: 选(递归)→撤销(回溯)。
排列/组合/子集: 组合用 start 索引避免重复; 排列用 used 标记; 子集含空集。
剪枝: 排序后跳过重复(与前一个相同且未用); 提前判断剩余不足; 限制条件提前 return。
N 皇后/数独/括号生成 都是典型回溯; 生成结果数可能指数级。
递归出口: 路径长度满足或到达叶子; 记得 path 的拷贝 list(path)。
"""},
]


def run(use_distilled: bool = True) -> dict:
    _kb = kb()
    docs = [dict(d) for d in SEED_DOCS]
    n_dist = 0
    if use_distilled and OUT_FILE.exists():
        for p in load_dataset():
            docs.append({"id": f"distill:{p['task']}:{p['topic']}:{n_dist}",
                         "title": f"{p['lang']} {p['topic']} {p['instruction'][:40]}",
                         "lang": p.get("lang", "general"),
                         "tags": [p["task"]], "source": "distill",
                         "text": p["instruction"] + "\n" + p["output"]})
            n_dist += 1
    stats = _kb.train(docs)
    ev = _kb.evaluate()
    quality = _retrieval_quality(_kb)
    report = {"knowledge_train": {**stats, "distilled_docs": n_dist,
                                  "hit_rate": ev["hit_rate"],
                                  "retrieval": quality,
                                  "index": str(_kb.path)}}
    out = data_dir() / "knowledge" / "train_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[kb-train] docs={stats['docs']} vocab={stats['vocab']} "
          f"hit_rate={ev['hit_rate']} "
          f"top1={quality['top1_rate']:.0%} top3={quality['top3_rate']:.0%} "
          f"(新增蒸馏 {n_dist} 条)")
    return report


def _retrieval_quality(_kb, sample: int = 200) -> dict:
    """检索质量自评：用每篇标题当查询，看原文排第几。

    比 hit_rate 严格——hit_rate 只问"进没进前 k"，这里还看平均排名。
    早期 TF-IDF 缺长度归一化时，长文档靠词频刷分把正确结果挤下去，
    hit_rate 仍显示 0.97（因为还在前 3），但真实排序是错的：
    查「背包问题 动态规划」时，真正讲背包的文档被只沾了"动态规划"
    三个字的题解压过，只能屈居第 2。
    """
    import random
    docs = _kb.docs
    if not docs:
        return {"top1_rate": 0.0, "top3_rate": 0.0, "avg_rank": 0.0, "n": 0}
    idx = list(range(len(docs)))
    if len(idx) > sample:
        random.Random(42).shuffle(idx)
        idx = idx[:sample]
    ranks = []
    for i in idx:
        title = docs[i].get("title") or ""
        if not title:
            continue
        hits = _kb.search(title, k=10)
        rank = next((j for j, h in enumerate(hits) if h["id"] == docs[i]["id"]),
                    len(hits))
        ranks.append(rank)
    if not ranks:
        return {"top1_rate": 0.0, "top3_rate": 0.0, "avg_rank": 0.0, "n": 0}
    return {"top1_rate": round(sum(1 for r in ranks if r == 0) / len(ranks), 3),
            "top3_rate": round(sum(1 for r in ranks if r < 3) / len(ranks), 3),
            "avg_rank": round(sum(ranks) / len(ranks), 2),
            "n": len(ranks)}


if __name__ == "__main__":
    run()
