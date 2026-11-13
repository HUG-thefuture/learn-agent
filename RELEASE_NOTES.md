# learn-agent v2.0.0

编程学习与开发 Agent —— 本地 Ollama + 云端模型池 + DSH 通道网关 + 完整质量工作流。

## 这一版有什么

- **多模型智能路由**：`config.yaml` 云端模型池 + DSH 网关自动发现的账号模型
  （workbuddy-cn / qoder / qodercn / trae / buddy / cline / workbuddy /
  our-free-model / zcode），按「可用性优先、兼顾性能」在每次调用前动态重排；
  画像持久化，重启后不必从零试错。
- **版本感知启动器**：`launch.py` 对源码做内容指纹，改了代码双击图标就自动
  重启到新版；版本一致则复用现有实例。`check / stop / watch / --force` 齐全。
- **训练体系**：数据蒸馏 → 知识库 TF-IDF 训练 → `ollama create learn-agent`。
  训练 ETA 按真实耗时动态估算；报告完整不截断（验证回答与思考链分离）。
- **知识库两段式**：SYSTEM 常驻精华 + 运行时按查询检索注入
  （`kb_query` 已接入教程/测验/复习/速查表/练习/实战）；TF-IDF 长度归一化，
  修复了长文档刷分压过正确结果的问题。
- **Web 控制台**：语言学习侧边栏课程目录、力扣侧边栏讲解目录、历史练习回看
  （练习从磁盘读，服务重启后照样能做题判题）；讲解与教程按 Markdown 渲染，
  代码围栏是可编辑可运行的练习框。
- **桌面 GUI**：Tkinter 六页签；力扣页选中题目即显示本地讲解，练习可查看。

## 快速开始

```bash
# 1. 安装依赖（Python 3.11+）
pip install -r requirements.txt

# 2. 装 Ollama 并拉一个模型
ollama pull qwen3:8b

# 3a. Web 控制台（推荐）：双击 start-web.bat，或
python launch.py web

# 3b. 桌面 GUI：双击 learn-agent-gui.bat，或
python launch.py gui

# 3c. 命令行
python main.py chat
python main.py learn python 装饰器
python main.py modelpool
```

浏览器打开 <http://127.0.0.1:7860>。

> 克隆后**无需配置即可运行**：程序会自动回退读取脱敏的
> `config.example.yaml`。要用云端模型，把 `config.yaml`（从模板复制）里的
> `cloud.enabled` 改为 `true` 并填入自己的 API Key。
> 若本机装有 DeepSeek Harness，网关通道会自动发现，无需填任何第三方 Key。

## 改了代码怎么生效

双击图标即可。`launch.py` 会比对磁盘代码指纹，不一致就自动重启到新版：

```bash
python launch.py check    # 只看版本状态（有旧版在跑时退出码 = 1）
python launch.py watch    # 常驻守护，代码一变就重启
python launch.py stop     # 停止实例
```

## 配置说明

| 文件 | 用途 |
|---|---|
| `config.example.yaml` | 脱敏模板，入库，克隆即可运行 |
| `config.yaml` | 你的本机配置（Key/密码），已被 `.gitignore` 忽略 |

`data/` 下附了示例学习产物（教程、题解讲解、练习集、知识库索引），
下载后可直接在「历史练习」「讲解目录」「课程目录」里翻看。

## 测试

```bash
python -m unittest discover tests -v     # 105 项，需 Ollama 的 4 项自动跳过
node tests/lab_check.js                  # 教程围栏渲染回归
node tests/explain_render_check.js       # 讲解 Markdown 渲染回归
```

## 升级提示

- v2.0.0 起 `config.yaml` 不再入库。老用户从 `config.example.yaml` 复制一份
  并填回自己的 Key 即可。
- 模型顺序不再由配置写死，而是按历史可用性动态重排；`python main.py modelpool`
  查看当前实际顺序。

## 许可

MIT —— 见 [LICENSE](LICENSE)。
