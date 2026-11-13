// 验证 tutorialHtml 的围栏切分能正确处理讲解 Markdown（讲解与教程同一套渲染）
// 用法: node tests/explain_render_check.js
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const explainDir = path.join(root, 'data', 'explain');

// 与 webapp/static/labs.js 中的正则保持一致
const FENCE = /^```([A-Za-z0-9+#-]*)[ \t]*\r?\n([\s\S]*?)\r?\n?^```[ \t]*(?=\r?\n|$)/gm;

function splitFences(content) {
  const blocks = [];
  let m, last = 0;
  while ((m = FENCE.exec(content)) !== null) {
    if (m.index > last) blocks.push({ type: 'text', body: content.slice(last, m.index) });
    blocks.push({ type: 'code', lang: m[1] || 'python', body: m[2] });
    last = FENCE.lastIndex;
  }
  if (last < content.length) blocks.push({ type: 'text', body: content.slice(last) });
  return blocks;
}

let files = [];
try {
  files = fs.readdirSync(explainDir).filter(f => f.endsWith('.md'));
} catch (e) {
  console.log('SKIP: 没有 data/explain 目录');
  process.exit(0);
}
if (!files.length) {
  console.log('SKIP: 没有讲解文件');
  process.exit(0);
}

let bad = 0, totalCode = 0, totalText = 0;
files.forEach(f => {
  const content = fs.readFileSync(path.join(explainDir, f), 'utf8');
  const blocks = splitFences(content);
  const codes = blocks.filter(b => b.type === 'code');
  const texts = blocks.filter(b => b.type === 'text');
  totalCode += codes.length;
  totalText += texts.length;

  // 关键校验：所有的 ``` 都应被切成块（奇数个围栏说明有未闭合）
  const fenceCount = (content.match(/^```/gm) || []).length;
  const consumed = codes.length * 2;
  const ok = fenceCount === consumed;
  if (!ok) {
    bad++;
    console.log(`  FAIL ${f}: 围栏 ${fenceCount} 个，切成 ${codes.length} 块（消耗 ${consumed}）`);
  }
  // 代码块里不能残留围栏标记
  codes.forEach((c, i) => {
    if (c.body.includes('```')) {
      bad++;
      console.log(`  FAIL ${f} 第${i + 1}个代码块残留围栏标记`);
    }
  });
});

console.log(`检查 ${files.length} 个讲解文件：代码块 ${totalCode} 个，文本块 ${totalText} 个`);
if (bad) {
  console.log(`EXPLAIN_RENDER_FAIL (${bad} 处问题)`);
  process.exit(1);
}
console.log('EXPLAIN_RENDER_OK');
