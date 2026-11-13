// 教程围栏切分逻辑回归测试（Node，无浏览器依赖）
// 运行：node tests/lab_check.js   （依赖 webapp/static/labs.js）
// 背景：tutorialHtml 曾用 split(捕获组) 逐对假设偶=文本/奇=语言，导致代码块重复渲染为文本、
//       正文被塞进练习框；现改为正则全局扫描配对围栏，本测试守护该行为。
const fs = require('fs');
const path = require('path');

// ---- 最小 DOM mock ----
function makeDoc() {
  return {
    createElement(tag) {
      return { tag, children: [], style: {}, attrs: {},
        set className(v) { this.attrs.className = v; },
        get className() { return this.attrs.className; },
        set textContent(v) { this._text = v; },
        get textContent() { return this._text; },
        set value(v) { this._value = v; },
        get value() { return this._value; },
        appendChild(c) { this.children.push(c); return c; },
        setAttribute(k, v) { this.attrs[k] = v; },
        getAttribute(k) { return this.attrs[k]; } };
    }
  };
}
global.document = makeDoc();

// labs.js 顶层无 require/document 之外的依赖，直接 eval 进来
eval(fs.readFileSync(path.join(__dirname, '..', 'webapp', 'static', 'labs.js'), 'utf8'));

// 深度搜索节点树（button.go 在 lab → row → button 的第二层，直接 children 查不到）
function findDeep(node, pred) {
  if (pred(node)) return node;
  for (const c of node.children || []) {
    const hit = findDeep(c, pred);
    if (hit) return hit;
  }
  return null;
}
const hasRunBtn = n => !!findDeep(n, x => x.className === 'go');

// ---- 用例 1：标准双代码块教程 ----
const md1 = [
  '# 标题', '', '说明文字', '',
  '```python', 'print(1 + 1)', '```', '',
  '中间正文', '',
  '```python', 'def f(x):', '    return x * 2', 'print(f(21))', '```', ''
].join('\n');

const c1 = makeDoc().createElement('div');
tutorialHtml(c1, md1, 'python');

const textBlocks = c1.children.filter(n => n.className !== 'lab');
const labs = c1.children.filter(n => n.className === 'lab');
console.log('== 用例1：标准双代码块 ==');
console.log('text blocks =', textBlocks.length, '(期望 2)');
console.log('labs        =', labs.length, '(期望 2)');
textBlocks.forEach((n, i) => console.log(`  text[${i}]:`, JSON.stringify(n._text).slice(0, 60)));
labs.forEach((n, i) => {
  const ta = n.children.find(x => x.tag === 'textarea');
  console.log(`  lab[${i}] rows=${ta.rows} code:`, JSON.stringify(ta._value));
});

// ---- 用例 2：无围栏纯文本 ----
const c2 = makeDoc().createElement('div');
tutorialHtml(c2, '只有一段普通文字，没有代码块。', 'python');
console.log('== 用例2：纯文本 ==');
console.log('children =', c2.children.length, '(期望 1)');
c2.children.forEach((n, i) => console.log(`  child[${i}]:`, n.className, JSON.stringify(n._text).slice(0, 40)));

// ---- 用例 3：未闭合围栏（容错：按原文显示，不进练习框）----
const c3 = makeDoc().createElement('div');
tutorialHtml(c3, '开头\n```python\nprint("未闭合")\n后面没有围栏', 'python');
console.log('== 用例3：未闭合围栏 ==');
console.log('children =', c3.children.length, '(期望 1，按原文)');
c3.children.forEach((n, i) => console.log(`  child[${i}]:`, n.className, JSON.stringify(n._text).slice(0, 60)));

// ---- 用例 4：非 Python 围栏（bash：只读展示，不可运行）----
const c4 = makeDoc().createElement('div');
tutorialHtml(c4, '装依赖\n```bash\npip install requests\n```\n完', 'python');
const labs4 = c4.children.filter(n => n.className === 'lab');
console.log('== 用例4：bash 围栏 ==');
console.log('labs =', labs4.length, '(期望 1 且无运行按钮)');
labs4.forEach((n, i) => console.log(`  lab[${i}] runnable:`, hasRunBtn(n)));

// ---- 用例 5：Python 围栏必须有运行按钮（深度查找 row 内的 button.go）----
const c5 = makeDoc().createElement('div');
tutorialHtml(c5, '试运行\n```python\nprint("ok")\n```', 'python');
const labs5 = c5.children.filter(n => n.className === 'lab');
console.log('== 用例5：python 围栏运行按钮 ==');
console.log('labs =', labs5.length, 'runnable:', labs5.map(hasRunBtn).join(','), '(期望 1,true)');

// ---- 用例 6：<details> 折叠块：summary 可读，内部练习框嵌套其中 ----
const c6 = makeDoc().createElement('div');
tutorialHtml(c6,
  '练习说明文字\n' +
  '<details>\n' +
  '<summary>👉 先自己试试，再点开看参考答案</summary>\n\n' +
  '```python\nprint("答案")\n```\n\n' +
  '</details>\n' +
  '结尾文字', 'python');
const details6 = c6.children.filter(n => n.tag === 'details');
const labIn6 = details6.length ? findDeep(details6[0], n => n.className === 'lab') : null;
const sum6 = details6.length ? details6[0].children.find(n => n.tag === 'summary') : null;
console.log('== 用例6：details 折叠块 ==');
console.log('details =', details6.length, '(期望 1)');
if (details6.length) {
  console.log('  summary:', JSON.stringify(sum6 && sum6._text));
  console.log('  内部 lab:', labIn6 ? JSON.stringify(labIn6.children.find(x => x.tag === 'textarea')._value) : '无');
  console.log('  外部文本残留 <details>:', c6.children.some(n => (n._text || '').includes('<details>')));
}

// ---- 用例 7：未闭合 <details>（收尾兜底挂载，不丢内容）----
const c7 = makeDoc().createElement('div');
tutorialHtml(c7, '<details>\n<summary>没关上的答案</summary>\n```python\nprint(1)\n```', 'python');
const details7 = c7.children.filter(n => n.tag === 'details');
console.log('== 用例7：未闭合 details ==');
console.log('details =', details7.length, '(期望 1，兜底挂载)');
if (details7.length) console.log('  内部 lab 存在:', !!findDeep(details7[0], n => n.className === 'lab'));

// ---- 汇总 ----
const ok1 = textBlocks.length === 2 && labs.length === 2
  && JSON.stringify(textBlocks.map(n => n._text)) === JSON.stringify(['# 标题\n\n说明文字', '中间正文'])
  && labs[0].children.find(x => x.tag === 'textarea')._value === 'print(1 + 1)'
  && labs[1].children.find(x => x.tag === 'textarea')._value === 'def f(x):\n    return x * 2\nprint(f(21))'
  && labs.every(hasRunBtn);
const ok2 = c2.children.length === 1 && c2.children[0]._text === '只有一段普通文字，没有代码块。';
const ok3 = c3.children.length === 1 && c3.children[0].className === 'result';
const ok4 = labs4.length === 1 && labs4.every(n => !hasRunBtn(n));
const ok5 = labs5.length === 1 && labs5.every(hasRunBtn);
const ok6 = details6.length === 1
  && sum6 && sum6._text === '👉 先自己试试，再点开看参考答案'
  && labIn6 && labIn6.children.find(x => x.tag === 'textarea')._value === 'print("答案")'
  && !c6.children.some(n => (n._text || '').includes('<details>'))
  && c6.children.some(n => n._text === '练习说明文字') && c6.children.some(n => n._text === '结尾文字');
const ok7 = details7.length === 1 && !!findDeep(details7[0], n => n.className === 'lab');
const all = ok1 && ok2 && ok3 && ok4 && ok5 && ok6 && ok7;
console.log(`case1=${ok1 ? 'PASS' : 'FAIL'} case2=${ok2 ? 'PASS' : 'FAIL'} case3=${ok3 ? 'PASS' : 'FAIL'} case4=${ok4 ? 'PASS' : 'FAIL'} case5=${ok5 ? 'PASS' : 'FAIL'} case6=${ok6 ? 'PASS' : 'FAIL'} case7=${ok7 ? 'PASS' : 'FAIL'}`);
console.log(all ? '\nRESULT: PASS' : '\nRESULT: FAIL');
process.exit(all ? 0 : 1);
