// 多开 / 边学边练 布局逻辑回归（无需浏览器：解析 JS 源码做静态断言 + 校验 DOM 挂点）
// 用法: node tests/layout_multi_check.js
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'webapp', 'templates', 'index.html'), 'utf8');

let fail = 0;
function ok(cond, msg) {
  if (cond) { console.log('  PASS ' + msg); }
  else { console.log('  FAIL ' + msg); fail++; }
}

console.log('== 1) 多开模式 ==');
ok(html.includes('id="multi-mode"'), '有「多开模式」开关');
ok(html.includes('body.multi main'), '多开时 main 用网格布局');
ok(html.includes('toggleMultiMode'), '有多开切换函数');
ok(html.includes('function isMultiMode'), '有模式判断函数');
ok(/localStorage\.setItem\('la-multi-mode'/.test(html), '多开状态持久化');
// 多开点击应 toggle 而不是一律清空
const tabClick = html.slice(html.indexOf('document.querySelectorAll(\'nav button\').forEach(b => b.onclick'),
                            html.indexOf('function toggleMultiMode'));
ok(tabClick.includes('classList.toggle'), '多开时点击页签是 toggle（可并存）');
ok(tabClick.includes('if (!multi)'), '单开/多开走不同分支');
ok(tabClick.includes('至少保留一个可见') || tabClick.includes('querySelector(\'nav button.active\')'),
   '不会把所有页签都关掉');

console.log('\n== 2) 学习页双栏工作台 ==');
ok(html.includes('id="learn-main"'), '有工作台容器 #learn-main');
ok(html.includes('wb-left') && html.includes('wb-right'), '有左右两栏');
ok(html.includes('id="wb-resizer"'), '有可拖拽分隔条');
ok(html.includes('toggleSplitWorkbench'), '有双栏开关函数');
ok(/localStorage\.setItem\('la-learn-split'/.test(html), '双栏状态持久化');
ok(html.includes('display:contents'), '单栏时用 display:contents 保持原布局');
ok(html.includes('.learn-main.split'), '双栏时切 grid 布局');
ok(html.includes('position:sticky'), '右栏 sticky 常驻');
ok(html.includes('overflow-y:auto'), '右栏独立滚动');

console.log('\n== 3) 边学边练联动 ==');
ok(html.includes('openTopicBoth'), '有一键双开函数');
const both = html.slice(html.indexOf('async function openTopicBoth'),
                         html.indexOf('async function openExtraCourse'));
ok(both.includes('toggleSplitWorkbench'), '双开函数会开启双栏');
ok(both.includes('openCourseFromToc'), '双开函数在左栏打开教程');
ok(both.includes('showTopicPractices'), '双开函数在右栏打开练习');
ok(html.includes('wb-btn'), '课程目录有 ⇔ 快捷按钮');
// 双栏下练习区不应被"再点收起"清空
const prac = html.slice(html.indexOf('async function showPracticeList'),
                        html.indexOf('async function openSavedPractice'));
ok(prac.includes('split'), '练习列表感知双栏模式');
ok(prac.includes('const split'), '双栏时不做收起');

console.log('\n== 4) 分隔条拖拽 ==');
ok(html.includes('initResizer'), '有分隔条初始化');
ok(html.includes('col-resize'), '拖拽时光标变化');
ok(html.includes('--wb-left'), '拖拽写入左栏宽度变量');

console.log('\n== 5) 初始化恢复 ==');
ok(html.includes('restoreLayoutPrefs'), '有恢复上次布局的函数');
const initCall = html.indexOf('restoreLayoutPrefs();');
ok(initCall > 0, 'init 中调用了恢复逻辑');

console.log('\n' + (fail ? `LAYOUT_CHECK_FAIL (${fail} 项)` : 'LAYOUT_CHECK_OK'));
process.exit(fail ? 1 : 0);
