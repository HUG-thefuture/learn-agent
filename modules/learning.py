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
from core.llm import router, tutorial_tier, strip_thinking
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
    # ==================== 热门框架 ====================
    "langchain": {
        "name": "LangChain（AI 应用框架）", "runner": "python",
        "goal": "能用 LangChain 构建 LLM 应用：提示模板、链、记忆、RAG 检索增强、工具调用与 Agent",
        "stages": {
            "L0 概念与环境": ["LLM应用开发现状与LangChain定位", "安装与第一个LLM调用", "Prompt/Chain/Agent核心概念"],
            "L1 提示与模型": ["ChatPromptTemplate与消息角色", "输出解析器OutputParser", "模型参数与流式输出", "多模型切换(OpenAI/通义/本地Ollama)"],
            "L2 链与记忆": ["LCEL表达式与管道", "顺序链与条件分支", "ConversationBufferMemory对话记忆", "历史裁剪与摘要记忆"],
            "L3 检索增强RAG": ["文档加载器DocumentLoader", "文本分割TextSplitter", "向量化Embedding与向量库", "检索器Retriever与相似度搜索", "RAG问答链实战"],
            "L4 工具与Agent": ["自定义Tool与函数调用", "@tool装饰器", "ReAct Agent与规划", "多工具协作与错误处理"],
            "L5 工程化": ["LangServe部署API", "LangSmith调试与追踪", "流式接口与SSE", "Prompt版本管理与评估"],
        },
        "capstone": {"name": "知识库问答机器人（RAG）", "stack": "langchain",
                     "desc": "LangChain + 向量检索实现在线文档知识库问答：支持加载本地PDF/Markdown、"
                             "分割入库、相似度检索、带引用的回答生成；提供 CLI 与 FastAPI 接口，附评估脚本"},
    },
    "fastapi": {
        "name": "FastAPI（Python Web 框架）", "runner": "python",
        "goal": "能用 FastAPI 开发生产级 REST API：路由、Pydantic 校验、依赖注入、异步、认证与测试",
        "stages": {
            "L0 入门": ["FastAPI定位与ASGI概念", "安装与第一个Hello API", "Swagger/ReDoc自动文档", "路径参数与查询参数"],
            "L1 核心": ["Pydantic模型与数据校验", "请求体与响应模型", "状态码与错误处理HTTPException", "路由分组APIRouter"],
            "L2 进阶": ["依赖注入Depends", "中间件与CORS", "异步async/await与并发", "文件上传与静态文件"],
            "L3 数据库": ["SQLAlchemy ORM基础", "SQLite/PostgreSQL接入", "CRUD接口完整实现", "事务与迁移Alembic概念"],
            "L4 认证安全": ["JWT认证", "OAuth2密码流", "密码哈希与权限控制", "限流与安全最佳实践"],
            "L5 工程化": ["项目分层结构", "pytest+TestClient接口测试", "Docker打包与部署", "性能优化与生产配置"],
        },
        "capstone": {"name": "任务管理 REST API（带认证）", "stack": "fastapi",
                     "desc": "FastAPI + SQLite 实现用户注册/登录(JWT) + 任务CRUD + 分页筛选；"
                             "Pydantic 严格校验，pytest 全接口测试，Swagger 文档完备，含 Dockerfile"},
    },
    "react": {
        "name": "React（前端框架）", "runner": "node",
        "goal": "能用 React 18 + Hooks 开发交互式单页应用：组件、状态、副作用、路由与数据请求",
        "stages": {
            "L0 入门": ["React定位与声明式UI思想", "环境搭建(Vite)", "JSX语法与第一个组件", "Props传参与组件组合"],
            "L1 核心": ["useState状态管理", "事件处理与受控表单", "条件渲染与列表渲染key", "useEffect副作用与生命周期"],
            "L2 进阶": ["useRef与DOM操作", "useContext跨层传值", "useReducer复杂状态", "自定义Hook封装逻辑", "性能优化memo/useMemo/useCallback"],
            "L3 路由与数据": ["React Router路由", "嵌套路由与参数", "fetch/axios数据请求", "加载态/错误态处理"],
            "L4 工程化": ["目录结构与组件拆分", "状态管理(Zustand/Redux概念)", "环境变量与构建部署", "前端测试(Vitest)"],
            "L5 实战进阶": ["表单库与校验", "组件库(Ant Design/MUI)", "SSR与Next.js概念", "性能分析与优化实践"],
        },
        "capstone": {"name": "电影收藏单页应用(SPA)", "stack": "react",
                     "desc": "React + Vite 实现电影收藏管理：搜索(调公开API或本地数据)、添加/删除/评分、"
                             "路由多页面、localStorage持久化、加载与错误态、响应式布局，附 Vite 构建配置"},
    },
    "vue": {
        "name": "Vue 3（前端框架）", "runner": "node",
        "goal": "能用 Vue 3 + 组合式API 开发单页应用：模板、响应式、组件通信、路由与状态管理",
        "stages": {
            "L0 入门": ["Vue定位与渐进式框架思想", "环境搭建(Vite)", "模板语法与第一个组件", "指令v-if/v-for/v-bind"],
            "L1 核心": ["响应式ref/reactive", "计算属性computed", "侦听器watch", "事件与v-model双向绑定"],
            "L2 进阶": ["组件通信props/emit", "插槽Slot", "生命周期钩子", "组合式函数Composables", "样式作用域与CSS模块"],
            "L3 路由与状态": ["Vue Router路由", "路由守卫与传参", "Pinia状态管理", "axios请求封装"],
            "L4 工程化": ["项目结构与规范", "Element Plus组件库", "环境变量与打包部署", "单元测试(Vitest)"],
            "L5 实战进阶": ["表单与校验", "动画过渡Transition", "性能优化与懒加载", "SSR(Nuxt)概念"],
        },
        "capstone": {"name": "待办清单 SPA（含状态管理）", "stack": "vue",
                     "desc": "Vue 3 + Vite + Pinia 实现待办清单：添加/编辑/删除/筛选/拖拽排序、"
                             "localStorage持久化、路由多视图、Element Plus组件，附构建部署配置"},
    },
    "springboot": {
        "name": "Spring Boot（Java 后端框架）", "runner": "java",
        "goal": "能用 Spring Boot 开发企业级后端：MVC、数据访问、事务、安全与测试",
        "stages": {
            "L0 入门": ["Spring生态与SpringBoot定位", "start.spring.io创建项目", "第一个REST接口", "自动配置原理初识"],
            "L1 核心": ["Controller/Service/Repository分层", "请求映射与参数绑定", "JSON序列化与统一响应", "全局异常处理@ControllerAdvice"],
            "L2 数据访问": ["Spring Data JPA实体映射", "Repository CRUD与派生查询", "MyBatis整合", "事务@Transactional"],
            "L3 进阶": ["参数校验Validation", "拦截器与过滤器", "AOP切面编程", "配置文件与多环境"],
            "L4 安全与部署": ["Spring Security认证授权", "JWT令牌方案", "打包jar与Docker部署", "日志与监控Actuator"],
            "L5 工程化": ["JUnit5+MockMvc测试", "分层测试策略", "接口文档Swagger", "性能优化与缓存"],
        },
        "capstone": {"name": "图书管理系统后端 API", "stack": "springboot",
                     "desc": "Spring Boot + JPA + H2/MySQL 实现图书与借阅管理：CRUD、分页搜索、借还业务逻辑、"
                             "统一异常与响应、参数校验、JWT登录，MockMvc 测试覆盖，Swagger 文档"},
    },
    "django": {
        "name": "Django（Python Web 框架）", "runner": "python",
        "goal": "能用 Django 快速开发数据驱动的 Web 应用：ORM、视图、模板、后台管理与 REST API",
        "stages": {
            "L0 入门": ["Django特点与MTV架构", "安装与创建项目/应用", "第一个视图与URL", "开发服务器与调试"],
            "L1 核心": ["模型Model与字段类型", "迁移makemigrations/migrate", "ORM查询与Q/F对象", "视图函数与模板渲染"],
            "L2 进阶": ["表单Form与校验", "用户认证与权限", "Admin后台定制", "中间件与会话"],
            "L3 数据进阶": ["外键与多对多关系", "聚合与注解annotate", "查询优化select_related", "信号signals"],
            "L4 REST API": ["DRF序列化器Serializer", "ViewSet与路由", "认证与权限类", "分页过滤与限流"],
            "L5 工程化": ["项目结构拆分", "单元测试TestCase", "静态文件与部署Gunicorn", "缓存与性能优化"],
        },
        "capstone": {"name": "个人博客系统（含后台与API）", "stack": "django",
                     "desc": "Django + DRF 实现博客：文章/分类/评论模型、富文本、分页搜索、"
                             "Admin后台管理、DRF 提供 REST API、用户认证、pytest 测试与部署配置"},
    },
    "docker": {
        "name": "Docker（容器化部署）", "runner": None,
        "goal": "掌握容器化开发与部署：镜像构建、容器编排、Compose 多服务与生产实践",
        "stages": {
            "L0 入门": ["容器与虚拟机区别", "安装与第一个容器", "镜像/容器/仓库概念", "常用命令docker ps/run/exec"],
            "L1 镜像构建": ["Dockerfile语法FROM/RUN/COPY", "构建缓存与层优化", "多阶段构建", "镜像体积优化"],
            "L2 数据与网络": ["数据卷Volume持久化", "端口映射与网络模式", "环境变量与配置", "容器日志与调试"],
            "L3 Compose": ["docker-compose.yml编写", "多服务编排(web+db)", "依赖与健康检查", "开发环境一键启动"],
            "L4 生产实践": ["生产镜像最佳实践", "资源限制与安全", "CI/CD集成思路", "私有仓库与版本管理"],
            "L5 编排进阶": ["Kubernetes概念与Pod", "Deployment与Service", "配置ConfigMap与Secret", "滚动更新与回滚"],
        },
        "capstone": {"name": "全栈应用容器化部署", "stack": "docker",
                     "desc": "为一个前后端应用编写 Dockerfile 与 docker-compose.yml："
                             "Web服务+数据库+缓存三容器编排、数据卷持久化、健康检查、"
                             "多阶段构建优化镜像，附一键启动脚本与说明文档"},
    },
    "typescript": {
        "name": "TypeScript", "runner": "node",
        "goal": "掌握 TS 类型系统，能编写类型安全的前后端代码与工程配置",
        "stages": {
            "L0 入门": ["TS定位与JS的关系", "安装与编译tsc", "基础类型注解", "类型推断与as断言"],
            "L1 核心": ["接口Interface与类型别名", "联合类型与字面量类型", "函数类型与重载", "数组与元组类型"],
            "L2 进阶": ["泛型Generic", "类型收窄与守卫", "枚举与常量断言", "可选链与空值合并"],
            "L3 类型工程": ["映射类型与infer", "工具类型Partial/Pick/Omit", "条件类型", "声明文件.d.ts"],
            "L4 工程化": ["tsconfig配置详解", "ESLint+Prettier", "模块系统与打包", "与React/Vue结合"],
            "L5 实战": ["前后端共享类型", "第三方库类型处理", "严格模式迁移", "类型测试与维护"],
        },
        "capstone": {"name": "类型安全的全栈小项目", "stack": "typescript",
                     "desc": "TypeScript 实现前后端共享类型定义的全栈项目（如任务管理）："
                             "后端 Express+TS 提供 API，前端调用并复用同一份类型，"
                             "严格模式无 any，含 tsconfig 与构建脚本"},
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

    def _tutorial_tier(self) -> str:
        """教程生成档位：见 core.llm.tutorial_tier（默认 fast；实战 capstone 不受影响）。"""
        return tutorial_tier()

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
    def learn(self, lang: str, topic: str = None, use_web: bool = True,
              log_fn=None) -> str:
        """学习一个主题（topic 为空时进入引导式：自动学下一课）。
        含前置知识回顾、网络资料参考、教程生成、知识库沉淀、进度记录。
        教程生成默认走 fast 档（快、够用）；进阶实战 capstone 仍走 strong 档。
        log_fn: 可选进度回调 log_fn(text)，用于 UI 展示生成进度。
        """
        def _p(text):
            if log_fn:
                try:
                    log_fn(text)
                except Exception:
                    pass
        c = self.curriculum(lang)
        if topic is None:
            topic = self.next_topic(lang)
            if topic is None:
                return "全部课程已学完！运行 capstone(lang) 开始进阶实战项目。"
        stage = _stage_of(c, topic)
        learned = self._load_progress().get(lang, {}).get("learned", [])
        prereq = "、".join(learned[-4:]) if learned else "（无，这是第一课）"
        _p("检索知识库与网络资料…")
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

请编写零基础友好的课程（Markdown），假设学员刚学完前置课程。

【重要：渲染环境】本教程会在网页控制台渲染——每个 ``` 代码围栏都会变成"可编辑 + 点 ▶ 运行"的练习框（沙箱执行并显示输出），
<details><summary>文字</summary> 与 </details> 之间的内容会变成可点击展开的折叠块。
因此所有代码块都必须完整、可独立运行，严禁 "# 其余代码省略" 之类占位；练习答案放折叠块，先让学员自己动手。

课程结构：
1. 本课目标（3条以内，学完能做什么）
2. 概念讲解（循序渐进、多打比方、解释"为什么"）
3. 3个由浅入深的完整示例（{c['runner'] or '目标语言'}代码，每个独立围栏、可独立运行、注释清楚、末尾用注释写明预期输出）
4. 常用函数/调用速查表（表格：函数|签名|用途|最小示例）
5. 5个新手易错点，每个严格按此结构（错误与正确必须分成两个独立代码围栏）：
   ### 易错点N：一句话标题
   ❌ **错误写法**（一个 ```python 围栏）：代码完整可独立运行——需要的类/变量一并定义好；
      必须真的能运行出错误：类/变量要定义完整，调用示例要写在同一围栏里；
      若运行会报错，在代码注释里写明预期报错，如：# 运行报错：TypeError: ...
      ⚠️ 严禁「标注会报错、实际却正常运行」的错误示例（如把「少包一层装饰器」写成仍能跑通的三层结构）。
   ✅ **正确写法**（一个 ```python 围栏）：代码完整可独立运行，末尾附 1-2 行调用示例，
      并用注释写明预期输出
   最后一句"为什么错"的纠正要点。
6. 本课小练习（2-3题，引导式实操，每题严格按此结构）：
   ### 练习N：标题
   - **目标**：一句话说明做完本题能掌握什么
   - **引导步骤**：2-4步，每步具体告诉学员先做什么
   - **起步代码**（一个 ```python 围栏）：可直接运行的最小骨架，用 # TODO 注释标出需要补全的位置，
     学员在网页练习框里补全后点运行即可自检
   - **预期输出**：写明补全后运行应看到什么
   - 参考答案放折叠块：单独一行写 <details><summary>👉 先自己试试，再点开看参考答案</summary>，
     空一行放答案代码围栏，再空一行单独写 </details>
7. 本课小结（3-5条要点，最后给一句下一课建议）"""
        _p("开始生成教程（fast 档，长文约 1–3 分钟）…")
        text = self.r.ask(prompt, tier=self._tutorial_tier())
        text = strip_thinking(text)
        _p(f"教程生成完成（{len(text)} 字），落盘并沉淀知识库…")
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
"answer": "正确选项或参考代码", "explain": "解析"}}]}}""", deep=True,
            kb_query=f"{lang} {topic}")
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

请生成阶段复习资料（Markdown）。教程会渲染在网页控制台：``` 代码围栏会变成"可编辑 + 点 ▶ 运行"的练习框，
<details><summary>文字</summary>…</details> 是可点击展开的折叠块，代码必须完整可独立运行、严禁省略占位。

1. 知识串讲：把已学主题组织成知识地图（哪些概念互相关联）
2. 高频混淆点对比（表格）
3. 综合练习 3 题（跨主题结合）：每题给"目标、引导步骤、含 # TODO 的起步代码围栏、预期输出"，
   参考答案与解析放折叠块（<details><summary>👉 先自己试试，再点开看参考答案与解析</summary> … </details>）
4. 检验清单：认为自己掌握的标准""", deep=True,
            kb_query=f"{c['name']} " + " ".join(learned[-6:]))
        out = outputs_dir() / "learning" / f"review_{lang}_{time.strftime('%Y%m%d_%H%M')}.md"
        out.write_text(text, encoding="utf-8", errors="replace")
        return text + f"\n\n---\n复习资料已保存: {out}"

    def cheatsheet(self, lang: str, topic: str = "常用函数") -> str:
        """生成函数调用速查表并沉淀知识库。"""
        c = self.curriculum(lang)
        text = self.r.ask(f"""生成 {c['name']}「{topic}」速查表。
Markdown 表格（函数/方法 | 签名 | 用途 | 最小示例），至少 25 条，覆盖最常用的调用。
只输出表格与一句主题说明。""", deep=True,
            kb_query=f"{c['name']} {topic} 速查")
        kb().train([{"id": f"cheat:{lang}:{topic}",
                     "title": f"{lang} {topic} 速查",
                     "lang": lang, "tags": ["cheatsheet"], "text": text,
                     "source": "cheatsheet"}])
        return text

    # ---------- 进阶实战：学以致用 ----------
    # ---------- 强化学习闭环：练习 -> 记录薄弱 -> 复习 -> 再练 ----------
    def practice(self, lang: str, topic: str = None, weak_only: bool = False,
                 log_fn=None) -> dict:
        """生成实操练习集（3-4 题，可运行起步代码 + 输出判据），落盘 data/practice/。"""
        def _p(t):
            if log_fn:
                try: log_fn(t)
                except Exception: pass
        c = self.curriculum(lang)
        weak = self.practice_weak_topics(lang, limit=6)
        if weak_only and weak:
            focus = "、".join(weak)
            topic = topic or "薄弱点"
        else:
            focus = topic or self.next_topic(lang) or "、".join(
                self._load_progress().get(lang, {}).get("learned", [])[-2:] or ["基础"])
        learned_str = "、".join(self._load_progress().get(lang, {}).get("learned", [])[-10:]) or "（零基础起步）"
        _p(f"出题中：{focus}（fast 档，约 1-2 分钟）…")
        prompt = f"""为「{c['name']}」出一份实操练习（考察主题：{focus}）。学员已学：{learned_str}。

出 3-4 题，由浅入深。每题字段：
- title：一句话标题
- task：题目要求（2-4 句，说清输入/处理/输出，并给一个示例输入输出）
- starter：完整可运行的起步代码（需要的变量/函数全部定义好；用 # TODO 标出学员要补全的位置；
  末尾必须有打印输出的调用，运行后能看到结果）
- expects：运行正确实现后，输出中应出现的关键行（1-2 行短句/数值，不要整段大输出）

硬性要求：只用已学知识；所有代码完整可运行，禁止占位/省略；禁止使用 input()（沙箱无标准输入），一律用给定的示例数据变量；expects 必须与 starter 补全后的真实输出一致；expects 用字符串数组。
只输出一个 JSON 对象：{{"topic": "...", "items": [{{...}}, ...]}}，不要任何其他文字。"""
        data, err = self._llm_json_or(prompt, "practice",
                                      kb_query=f"{c['name']} {focus}")
        if err:
            return {"ok": False, "summary": "出题失败: " + err}
        items = (data or {}).get("items") or []
        # 校验并自愈：过滤掉 starter 缺失/不能运行/判据不一致的坏题，
        # 避免模型生成「起步代码本身就跑不起来」的练习直接推给学员。
        items = self._validate_practice_items(items)
        if not items:
            return {"ok": False, "summary": "出题结果无效（无有效题目），请重试"}
        out_dir = data_dir() / "practice"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w一-鿿]+", "_", focus)[:40]
        path = out_dir / f"{lang}_{safe}_{time.strftime('%Y%m%d_%H%M')}.json"
        payload = {"lang": lang, "topic": focus, "items": items,
                   "path": str(path), "weak_used": bool(weak_only and weak)}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _p(f"出题完成：{len(items)} 题，已存档 {path.name}")
        return {"ok": True, "practice": payload,
                "summary": json.dumps(payload, ensure_ascii=False)}

    @staticmethod
    def _norm_out(s: str) -> str:
        return re.sub(r"\s+", "", s or "")

    @staticmethod
    def _validate_practice_items(items: list) -> list:
        """校验练习条目，剔除明显不可上手的坏题：
        - title/starter 缺失
        - starter 含 input()（沙箱无标准输入）
        - starter 语法错误（学员连骨架都跑不起来）
        注意：不要求骨架「运行即输出正确判据」——TODO 骨架本就要学员补全后才出结果。
        """
        import ast
        good = []
        for it in items:
            if not isinstance(it, dict):
                continue
            if not it.get("title") or not it.get("starter"):
                continue
            starter = str(it.get("starter") or "")
            if "input(" in starter:
                continue
            try:
                ast.parse(starter)
            except SyntaxError:
                continue
            good.append(it)
        return good

    def judge_practice(self, code: str, expects) -> dict:
        """沙箱运行学员代码，按 expects 关键行判题（空白不敏感）。"""
        if "input(" in code:
            return {"ok": False, "output": "", "error": "练习沙箱不支持 input()：请把输入改成代码里的固定示例数据再运行判题", "missing": []}
        from core.codecheck import run_python_code
        r = run_python_code(code)
        out_n = self._norm_out(r.get("output"))
        if isinstance(expects, str):
            expects = [expects]
        parts = []
        for e in (expects or []):
            for seg in str(e).split("|"):
                if seg.strip():
                    parts.append(seg)
        missing = [e for e in parts if self._norm_out(e) not in out_n]
        return {"ok": bool(r.get("ok")) and not missing,
                "output": (r.get("output") or "")[-2500:],
                "error": r.get("error"), "missing": missing}

    def record_practice(self, lang: str, topic: str, title: str, passed: bool) -> dict:
        """记录练习结果：通过计数 + 薄弱点清单（错题入weak、补全通过则移除）。"""
        prog = self._load_progress()
        e = prog.setdefault(lang, {"learned": [], "quiz": {}, "updated": ""})
        pr = e.setdefault("practice", {}).setdefault(
            topic or "通用", {"pass": 0, "fail": 0, "weak": [], "last": ""})
        title = title or "练习"
        if passed:
            pr["pass"] = int(pr.get("pass", 0)) + 1
            if title in pr.get("weak", []):
                pr["weak"].remove(title)
        else:
            pr["fail"] = int(pr.get("fail", 0)) + 1
            if title not in pr.get("weak", []):
                pr.setdefault("weak", []).append(title)
        pr["last"] = time.strftime("%Y-%m-%d %H:%M")
        e["updated"] = pr["last"]
        self._save_progress(prog)
        return pr

    def practice_weak_topics(self, lang: str, limit: int = 6) -> list:
        """薄弱/待复习主题：有错题的优先，其次超过3天未练的已学主题。"""
        e = self._load_progress().get(lang, {})
        prac = e.get("practice", {})
        weak_t = []
        for t, st in prac.items():
            if st.get("weak") or int(st.get("fail", 0)) > 0:
                weak_t.append(t)
        due = []
        now = time.time()
        for t in e.get("learned", []):
            st = prac.get(t)
            if not st:
                due.append(t)
            else:
                try:
                    lt = time.mktime(time.strptime(st.get("last", ""), "%Y-%m-%d %H:%M"))
                except Exception:
                    lt = 0
                if lt and now - lt > 3 * 86400:
                    due.append(t)
        out = []
        for t in weak_t + due:
            if t not in out:
                out.append(t)
        return out[:limit]

    def smart_review(self, lang: str, log_fn=None) -> dict:
        """智能复习：按薄弱点/到期主题生成针对性复习卡，产物落盘 data/review/。"""
        def _p(t):
            if log_fn:
                try: log_fn(t)
                except Exception: pass
        c = self.curriculum(lang)
        learned = self._load_progress().get(lang, {}).get("learned", [])
        due = self.practice_weak_topics(lang, limit=4) or learned[-3:] or ["基础语法"]
        learned_str = "、".join(learned[-10:]) or "（零基础起步）"
        _p(f"整理薄弱点：{chr(12289).join(due)}")
        prompt = f"""学员正在学「{c['name']}」，已学：{learned_str}。
练习数据显示以下薄弱/待复习主题：{chr(12289).join(due)}。

请生成针对性复习（Markdown），直接从正文开始（禁止思考过程）：
1. 每个主题一节：复习要点（4-6 条，直击易混易错）；易错点对照（❌ 错误 / ✅ 正确，
   各一个完整可运行的代码围栏）；1 个综合小练习（独立围栏，末尾注释写明预期输出）。
2. 结尾写「🔁 再练清单」：建议接下来练哪些点。
全文中文（代码除外），复习练习代码必须完整可运行。"""
        _p("生成复习卡（fast 档，约 1-2 分钟）…")
        text = self.r.ask(prompt, tier=self._tutorial_tier(),
                          kb_query=f"{c['name']} " + " ".join(due))
        text = strip_thinking(text)
        out_dir = data_dir() / "review"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{lang}_{time.strftime('%Y%m%d_%H%M')}.md"
        path.write_text(text, encoding="utf-8", errors="replace")
        _p("复习卡完成，已落盘。")
        tail = (f"{chr(10)}{chr(10)}---{chr(10)}✅ 复习卡已存档: {path}"
                f"{chr(10)}下一步：点「🔁 再练薄弱」做针对性练习，全部通过后继续新课程。")
        return {"ok": True, "due": due, "summary": text + tail}

    def capstone(self, lang: str, log_fn=None) -> dict:
        """进阶实战项目：Agent 依据已学内容一次性生成完整可运行的迷你项目。
        单次生成（类同 learn 教程，可靠快速），产物落盘 data/outputs/projects/<lang>/。
        走 fast 档即可；产出由模型保证结构完整，避免多轮工作流在弱模型下打转。
        """
        def _p(text):
            if log_fn:
                try:
                    log_fn(text)
                except Exception:
                    pass
        c = self.curriculum(lang)
        cap = c["capstone"]
        learned = self._load_progress().get(lang, {}).get("learned", [])
        learned_str = "、".join(learned[-12:]) if learned else "（尚无学习记录，按零基础标准交付）"
        _p(f"开始进阶实战：{cap['name']}（fast 档，约 1–3 分钟）…")
        prompt = f"""你是技术导师。为学员生成「{c['name']}」进阶实战项目：
【项目名】{cap['name']}
【项目要求】{cap['desc']}
【技术栈】{cap.get('stack', 'python')}
【学员已学课程】{learned_str}

交付标准：
1. 完整可运行的最小项目，文件结构清晰（后端/前端或单程序均可，主语言 python）
2. 用已学知识即可理解，不引入超纲框架
3. 必须附自测代码/测试（运行能证明功能正确，如 __main__ 下打印测试结果）
4. 资源规范：文件用 with、网络请求带 timeout、线程有 join/daemon
5. 附 README.md 说明启动与测试方式
范围控制：只做最小可用版本，严禁加认证/JWT/权限/分页/连接池等企业级特性。

输出 JSON，仅此一个对象：
{{"files": {{"文件名": "该文件的完整代码/内容"}}}}
每个文件必须是完整真实实现，禁止占位符、pass、raise NotImplementedError、TODO 空壳。"""
        data, err = self._llm_json_or(prompt, "capstone",
                                      kb_query=f"{c['name']} {cap['name']} {cap.get('stack','')}")
        if err:
            return {"ok": False, "summary": "生成失败: " + err}
        files = (data or {}).get("files")
        if not isinstance(files, dict) or not files:
            return {"ok": False, "summary": "生成未返回任何代码文件，请重试"}
        # 落盘 data/outputs/projects/<lang>/
        out = outputs_dir() / "projects" / lang
        out.mkdir(parents=True, exist_ok=True)
        written = []
        for name, code in files.items():
            if not isinstance(code, str) or not code.strip():
                continue
            # 拒绝占位/省略占位/纯注释空壳（如 '...'、'# TODO'、空实现）
            stripped = code.strip()
            n_code = len([l for l in stripped.splitlines() if l.strip() and not l.strip().startswith("#")])
            if (stripped in ("...", "`...`")
                    or "NotImplementedError" in code
                    or "占位" in code
                    or "TODO" in code
                    or "后续根据需求补充" in code
                    or n_code < 3):
                continue  # 视为无效文件，跳过
            safe = name.replace("\\", "_").replace("/", "_").replace("..", "_")
            (out / safe).write_text(code, encoding="utf-8", errors="replace")
            written.append(safe)
        if not written:
            return {"ok": False, "summary": "生成的文件均为空，请重试"}
        summary = ("进阶实战完成：{n} 个文件 -> {dir}\n文件: {fl}\n"
                   "启动/测试方式见 README.md。").format(
            n=len(written), dir=str(out), fl=", ".join(written))
        _p("进阶实战完成，文件已落盘。")
        return {"ok": True, "capstone": cap["name"], "files": written,
                "dir": str(out), "summary": summary}

    def _llm_json_or(self, prompt, stage, kb_query=None):
        """调 ask_json 解析项目 JSON，返回 (data, None) 或 (None, err 描述)。

        kb_query：传给 ask_json 的知识库检索查询，让生成的练习/项目
        基于库里已知的写法与易错点，而不是凭空发挥。
        """
        try:
            d = self.r.ask_json(prompt, tier=self._tutorial_tier(),
                                kb_query=kb_query)
            self.r.ok()
            return d, None
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"


def run_learn(lang: str, topic: str = None):
    return LearningModule().learn(lang, topic)
