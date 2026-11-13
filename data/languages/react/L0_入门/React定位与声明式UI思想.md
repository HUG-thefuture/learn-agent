# L0 入门 · 第1课：React 定位与声明式 UI 思想

> 前置说明：这是 React 第一课，不要求你会 React。  
> 只要你见过一点 JavaScript（变量、函数、数组）就足够了；用到的语法我会逐行解释。

---

## 一、本课目标

学完本课，你将能够：

1. **说清楚 React 是什么、为什么用它**：它是一个构建用户界面的 JavaScript 库。
2. **理解“声明式 UI”和“命令式 UI”的区别**，记住核心公式：`UI = f(state)`。
3. **用 Node 跑通第一个 React 声明式渲染示例**，看到“状态变，UI 自动变”的效果。

---

## 二、概念讲解

### 1. 先搞清楚：网页上的 UI 是怎么来的？

你在浏览器里看到的按钮、列表、弹窗，本质上都是 **DOM 元素**。

比如一个待办列表：

```html
<h1>我的待办</h1>
<ul>
  <li>学 React</li>
  <li>写组件</li>
</ul>
```

传统 JavaScript 的做法是：**一步一步操作 DOM**。

```js
// 命令式：像给机器人下每一步指令
const h1 = document.createElement('h1');
h1.textContent = '我的待办';
document.body.appendChild(h1);

const ul = document.createElement('ul');
document.body.appendChild(ul);

const li1 = document.createElement('li');
li1.textContent = '学 React';
ul.appendChild(li1);

const li2 = document.createElement('li');
li2.textContent = '写组件';
ul.appendChild(li2);
```

这种写法叫 **命令式**：你告诉浏览器“先做这个，再做那个”。

问题来了：如果数据变了，比如新增一条待办，你必须自己找到对应的 DOM，手动插入、删除、更新。  
页面一复杂，就很容易漏掉某一步，导致 **数据和界面不一致**。

---

### 2. 声明式：像点外卖，而不是自己做饭

React 提倡 **声明式**。

- **命令式**：自己买菜、洗菜、切菜、炒菜，每一步都要管。
- **声明式**：你点外卖，只说“我要一份番茄炒蛋”，平台负责做饭、配送。

在 React 里，你不再说“先创建 div，再创建 h1，再 appendChild”。  
你只说：

> “当状态是 `{ title: '我的待办', todos: ['学 React', '写组件'] }` 时，UI 应该长这样。”

至于怎么创建 DOM、怎么更新、怎么删除，React 负责。

生活类比：

- **命令式装修**：你亲自当工头，指挥工人砸墙、找平、贴砖。
- **声明式装修**：你给设计师一张效果图，说“我要一个现代简约白色厨房”。设计师负责调度工人。

React 里的“效果图”，就是你的 **组件渲染结果**。

---

### 3. React 的定位：它不是完整框架，而是 UI 库

React 官方定位是：**用于构建用户界面的 JavaScript 库**。

关键词：

- **用户界面**：主要管“页面长什么样”。
- **库**：只解决一部分问题。路由、状态管理、请求数据，通常要配合其他工具。
- **声明式**：你描述 UI 应该是什么样，React 负责高效更新。
- **组件化**：把页面拆成一个个可复用的“乐高积木”。

所以 React 不是“前端全部”，而是“前端视图层”的核心工具。

---

### 4. 组件化：用乐高积木搭页面

一个网页可以拆成很多组件：

```text
App
├── Header
├── TodoList
│   ├── TodoItem
│   └── TodoItem
└── Footer
```

每个组件都是一个函数，接收 `props`，返回 UI。

```js
function Welcome(props) {
  return React.createElement('h1', null, `你好，${props.name}！`);
}
```

组件的好处：

- **可复用**：一个 `Button` 组件到处用。
- **可维护**：出问题只查一个组件。
- **好理解**：每个组件只做一件事。

---

### 5. 核心公式：UI = f(state)

这是声明式 UI 的灵魂。

- `state`：数据，比如待办列表、用户名、是否登录。
- `f`：你的组件函数。
- `UI`：最终页面。

你只需要写：

```js
UI = f(state)
```

状态一变，React 重新调用 `f`，算出新的 UI，然后自动更新页面。

类比 Excel：

- 你写公式 `=A1+B1`。
- 改 A1，结果自动变。
- 你不需要手动重新算。

React 就是这个“自动重算并更新界面”的系统。

---

## 三、3 个由浅入深的完整示例

> 运行环境：Node.js。  
> 示例 1 不需要安装任何包。  
> 示例 2、3 需要先安装 React。

### 准备环境

新建一个文件夹，比如 `react-l0`：

```bash
mkdir react-l0
cd react-l0
npm init -y
npm install react react-dom
```

然后创建对应的 `.js` 文件，用 `node 文件名.js` 运行。

---

### 示例 1：命令式 vs 声明式（纯 JS，先理解思想）

文件：`01-imperative-vs-declarative.js`

```js
// ============================================
// 示例 1：命令式 vs 声明式
// 这个例子不依赖 React，只用纯 JS 展示思想
// 运行：node 01-imperative-vs-declarative.js
// 资源释放：普通脚本运行完自动退出，无额外资源
// ============================================

// ---------- 命令式：一步步拼出 UI ----------
let ui = '';

function addTitleCommand(title) {
  ui += `<h1>${title}</h1>`;
}

function addItemCommand(item) {
  ui += `<li>${item}</li>`;
}

addTitleCommand('我的待办');
addItemCommand('学 React');
addItemCommand('写组件');

console.log('命令式结果：');
console.log(ui);

// ---------- 声明式：描述“状态对应的 UI 是什么样” ----------
function renderUI(state) {
  // 根据 state 直接算出完整 UI
  const items = state.todos
    .map((todo) => `<li>${todo}</li>`)
    .join('');

  return `<h1>${state.title}</h1><ul>${items}</ul>`;
}

const state = {
  title: '我的待办',
  todos: ['学 React', '写组件'],
};

console.log('\n声明式结果：');
console.log(renderUI(state));

// 如果状态变了，只需要重新调用 renderUI
const newState = {
  title: '我的待办',
  todos: ['学 React', '写组件', '理解声明式'],
};

console.log('\n状态变化后的声明式结果：');
console.log(renderUI(newState));
```

**重点理解：**

- 命令式：你手动 `addTitleCommand`、`addItemCommand`。
- 声明式：你只写 `renderUI(state)`，状态变，重新调用即可。

---

### 示例 2：第一个 React 元素和组件

文件：`02-react-hello.js`

```js
// ============================================
// 示例 2：用 React.createElement 创建元素和组件
// 运行前先安装：npm install react react-dom
// 运行：node 02-react-hello.js
// 资源释放：普通脚本运行完自动退出，无额外资源
// ============================================

const React = require('react');
const ReactDOMServer = require('react-dom/server');

// 函数组件：接收 props，返回 React 元素
// 注意：组件名必须大写开头，React 才会把它当组件
function Welcome(props) {
  return React.createElement('h1', null, `你好，${props.name}！`);
}

// 用 React.createElement 创建元素树
// 参数：标签名/组件、属性对象、子元素...
const app = React.createElement(
  'div',
  null,
  React.createElement(Welcome, { name: '小明' }),
  React.createElement(Welcome, { name: '小红' })
);

// 在 Node 中把 React 元素渲染成 HTML 字符串
const html = ReactDOMServer.renderToStaticMarkup(app);

console.log('React 渲染出的 HTML：');
console.log(html);
```

运行结果类似：

```html
<div><h1>你好，小明！</h1><h1>你好，小红！</h1></div>
```

**重点理解：**

- `React.createElement` 是 React 创建元素的底层函数。
- 函数组件就是一个返回 React 元素的普通函数。
- `props` 是父组件传给子组件的数据。
- `renderToStaticMarkup` 把 React 元素变成 HTML 字符串，方便在 Node 里观察。

---

### 示例 3：声明式 UI = f(state)，并用 HTTP 服务器展示状态变化

文件：`03-declarative-state.js`

```js
// ============================================
// 示例 3：声明式 UI = f(state)
// 运行前先安装：npm install react react-dom
// 运行：node 03-declarative-state.js
// 然后浏览器打开：http://localhost:3000/
// 试试：http://localhost:3000/?todos=学React,写组件,理解声明式
// 资源释放：10 秒后自动关闭 HTTP 服务器，避免端口一直被占用
// ============================================

const http = require('http');
const React = require('react');
const ReactDOMServer = require('react-dom/server');

// 组件：只关心“根据 props 渲染什么”
function TodoApp(props) {
  const { title, todos } = props;

  return React.createElement(
    'div',
    null,
    React.createElement('h1', null, title),
    React.createElement(
      'ul',
      null,
      // 列表渲染时，每个 li 最好有 key，帮助 React 识别每一项
      ...todos.map((todo, index) =>
        React.createElement('li', { key: index }, todo)
      )
    )
  );
}

// 声明式渲染函数：UI = f(state)
function renderPage(state) {
  const element = React.createElement(TodoApp, {
    title: state.title,
    todos: state.todos,
  });

  const body = ReactDOMServer.renderToStaticMarkup(element);

  return `<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>React 声明式 UI</title>
  </head>
  <body>${body}</body>
</html>`;
}

const server = http.createServer((req, res) => {
  // 用 URL 查询参数模拟状态变化
  // 例如：/?todos=学React,写组件,理解声明式
  const url = new URL(req.url, 'http://localhost');
  const todosParam = url.searchParams.get('todos');

  const todos = todosParam
    ? todosParam.split(',')
    : ['学 React', '写组件'];

  // 状态
  const state = {
    title: '我的待办',
    todos,
  };

  // 根据状态渲染页面
  const html = renderPage(state);

  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(html);
});

server.listen(3000, () => {
  console.log('服务器已启动：http://localhost:3000/');
  console.log('试试：http://localhost:3000/?todos=学React,写组件,理解声明式');
});

// 10 秒后自动关闭服务器，释放端口资源
// 如果你想多试一会儿，把 10000 改成 60000（60 秒）
setTimeout(() => {
  server.close(() => {
    console.log('服务器已关闭，资源释放完成');
  });
}, 10000);
```

**重点理解：**

- 你只改了 `state.todos`，页面就自动变成新的待办列表。
- 在真实浏览器里，React 会对比新旧 UI，只更新变化的部分，而不是全部重画。
- 这个例子用服务端渲染模拟“状态变，UI 变”，帮助你理解 `UI = f(state)`。

---

## 四、常用函数/调用速查表

| 函数/概念 | 签名 | 用途 | 最小示例 |
|---|---|---|---|
| `React.createElement` | `React.createElement(type, props, ...children)` | 创建 React 元素 | `React.createElement('h1', null, 'Hello')` |
| `ReactDOMServer.renderToStaticMarkup` | `renderToStaticMarkup(element)` | 把 React 元素渲染成 HTML 字符串 | `renderToStaticMarkup(React.createElement('p', null, 'Hi'))` |
| 函数组件 | `function Component(props) { return element; }` | 定义 UI 组件 | `function Hello(props) { return React.createElement('h1', null, props.name); }` |
| `props` | 组件接收的参数对象 | 父组件向子组件传数据 | `React.createElement(Hello, { name: '小明' })` |
| `children` | `props.children` | 组件标签之间的内容 | `React.createElement('div', null, '文本')` |
| `key` | 列表元素的特殊 prop | 帮助 React 识别列表项 | `React.createElement('li', { key: id }, text)` |
| `React.Fragment` | `React.createElement(React.Fragment, null, ...children)` | 返回多个根元素，不额外加 div | `React.createElement(React.Fragment, null, React.createElement('h1', null, 'A'), React.createElement('p', null, 'B'))` |
| `UI = f(state)` | 概念公式 | 声明式 UI 核心 | `render(state)` 返回 UI |

---

## 五、5 个新手易错点

| 错误写法 | 正确写法 | 为什么 |
|---|---|---|
| `function welcome(props) { ... }` | `function Welcome(props) { ... }` | 组件名必须大写开头，否则 React 会把它当普通 HTML 标签。 |
| `props.name = '小红'` | 只读 `props`，用新数据重新渲染 | `props` 是只读的，不能直接修改。 |
| `todos.map(todo => React.createElement('li', null, todo))` | `todos.map((todo, index) => React.createElement('li', { key: index }, todo))` | 列表项需要 `key`，帮助 React 高效更新。 |
| `return React.createElement('h1', null, 'A'), React.createElement('p', null, 'B')` | 用 `div` 或 `React.Fragment` 包起来 | 组件只能返回一个根元素。 |
| 在组件里直接操作 DOM，比如 `document.querySelector(...).innerHTML = ...` | 根据 `props/state` 返回 UI，让 React 更新 | 这是命令式思维，会破坏声明式模型，容易导致状态和界面不一致。 |
| 在 Node 里直接写 JSX：`return <h1>Hello</h1>` | 用 `React.createElement`，或配置 Babel 编译 JSX | Node 默认不认识 JSX 语法。本课用 `createElement` 避免编译。 |

---

## 六、本课小练习

### 练习 1

用 `React.createElement` 创建一个组件 `UserCard`，接收 `name` 和 `age`，返回一个 `<div>`，里面有一个 `<h2>` 显示名字，一个 `<p>` 显示年龄。然后用 `renderToStaticMarkup` 输出 HTML。

**答案：**

```js
const React = require('react');
const ReactDOMServer = require('react-dom/server');

function UserCard(props) {
  return React.createElement(
    'div',
    null,
    React.createElement('h2', null, props.name),
    React.createElement('p', null, `年龄：${props.age}`)
  );
}

const html = ReactDOMServer.renderToStaticMarkup(
  React.createElement(UserCard, { name: '小明', age: 18 })
);

console.log(html);
// 输出：<div><h2>小明</h2><p>年龄：18</p></div>
```

---

### 练习 2

用自己的话解释“命令式”和“声明式”的区别。然后写一个声明式函数 `renderList(items)`，输入字符串数组，返回 `<ul><li>...</li></ul>` 的 HTML 字符串。可以用纯 JS，也可以用 React。

**答案：**

区别：

- **命令式**：你一步步告诉程序怎么做，比如“创建 li、设置文本、添加到 ul”。
- **声明式**：你只描述“给定 items，UI 应该是什么样”，具体怎么创建和更新交给 React 或渲染函数。

纯 JS 版本：

```js
function renderList(items) {
  const lis = items.map((item) => `<li>${item}</li>`).join('');
  return `<ul>${lis}</ul>`;
}

console.log(renderList(['苹果', '香蕉']));
// 输出：<ul><li>苹果</li><li>香蕉</li></ul>
```

React 版本：

```js
const React = require('react');
const ReactDOMServer = require('react-dom/server');

function List(props) {
  return React.createElement(
    'ul',
    null,
    ...props.items.map((item, index) =>
      React.createElement('li', { key: index }, item)
    )
  );
}

const html = ReactDOMServer.renderToStaticMarkup(
  React.createElement(List, { items: ['苹果', '香蕉'] })
);

console.log(html);
// 输出：<ul><li>苹果</li><li>香蕉</li></ul>
```

---

## 本课小结

- React 是一个 **声明式、组件化** 的 UI 库。
- 声明式的核心是：**你描述 UI 应该是什么样，React 负责更新过程**。
- 记住公式：**UI = f(state)**。
- 组件就是返回 UI 的函数，接收 `props`，名字要大写。
- 列表渲染要加 `key`，`props` 不能直接修改。

下一课我们会继续深入：**JSX 是什么，为什么它写起来像 HTML**。