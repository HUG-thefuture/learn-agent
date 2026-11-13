// 教程实操模块
let _runSeq = 0;
var NL = String.fromCharCode(10);

function codeLab(src, lang) {
  var id = "lab" + (++_runSeq);
  var py = !lang || /^(py|python|python3)$/i.test(lang);
  var lines = src.split("\n").length;
  var rows = Math.min(18, Math.max(4, lines));
  var d = document.createElement("div");
  d.className = "lab";
  var bar = document.createElement("div");
  bar.className = "row";
  var tag = document.createElement("span");
  tag.className = "pill";
  tag.textContent = lang || "python";
  bar.appendChild(tag);
  if (py) {
    var btn = document.createElement("button");
    btn.className = "go";
    btn.textContent = "▶ 运行";
    btn.onclick = function () { runLab(id); };
    bar.appendChild(btn);
    var st = document.createElement("span");
    st.className = "stat";
    st.id = id + "-st";
    bar.appendChild(st);
  }
  d.appendChild(bar);
  var ta = document.createElement("textarea");
  ta.id = id;
  ta.rows = rows;
  ta.spellcheck = false;
  ta.style.fontFamily = "Consolas,Monaco,Courier New,monospace";
  ta.style.fontSize = "13px";
  ta.style.width = "100%";
  ta.style.tabSize = "4";
  ta.style.lineHeight = "1.5";
  ta.style.whiteSpace = "pre";
  ta.value = src;
  d.appendChild(ta);
  var out = document.createElement("pre");
  out.id = id + "-out";
  out.className = "result";
  out.style.display = "none";
  out.style.maxHeight = "260px";
  d.appendChild(out);
  return d;
}

async function runLab(id) {
  var ta = document.getElementById(id);
  var out = document.getElementById(id + "-out");
  var st = document.getElementById(id + "-st");
  if (!ta || !out || !st) return;
  st.innerHTML = "<span class=\"st-running\">运行中…</span>";
  out.style.display = "none";
  try {
    var resp = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: ta.value })
    });
    var r = await resp.json();
    var text = r.output || "";
    if (r.error) text += (text ? NL + "[error] " : "") + r.error;
    if (!text) text = "(无输出)";
    out.textContent = text;
    out.style.display = "";
    if (r.ok) {
      st.innerHTML = "<span class=\"st-done\">✓ 运行成功</span>";
    } else {
      st.innerHTML = "<span class=\"bad\">✗ 有错误</span>";
    }
  } catch (err) {
    out.textContent = "请求失败: " + err;
    out.style.display = "";
    st.innerHTML = "<span class=\"bad\">✗ 请求失败</span>";
  }
}

// 按 ``` 围栏解析：围栏外文本 → <pre>，围栏内代码 → codeLab 练习框。
// 用正则全局扫描配对围栏（开头 ```lang 行 + 结尾 ``` 行），未闭合围栏按原文显示，不会串块。
// <details><summary>…</summary>…</details> 渲染为原生可折叠块（练习参考答案常用），
// 折叠块内外的练习框/文本各归其位；未闭合的 <details> 收尾时也会挂载。
function tutorialHtml(container, content, defaultLang) {
  var s = String(content);
  var re = /^```([A-Za-z0-9+#-]*)[ \t]*\r?\n([\s\S]*?)\r?\n?^```[ \t]*(?=\r?\n|$)/gm;
  var stack = [container];   // 挂载点栈：进入 <details> 后节点挂到折叠块内
  var pending = [];          // 缓冲的普通文本行
  function cur() { return stack[stack.length - 1]; }
  function flush() {
    var t = pending.join("\n").replace(/^\r?\n+/, "").replace(/\r?\n+$/, "");
    pending = [];
    if (!t.trim()) return;
    var pre = document.createElement("pre");
    pre.className = "result";
    pre.style.whiteSpace = "pre-wrap";
    pre.textContent = t;
    cur().appendChild(pre);
  }
  function addText(t) {
    String(t).split(/\r?\n/).forEach(function (line) {
      if (/^\s*<details>\s*$/i.test(line)) {
        flush();
        var d = document.createElement("details");
        d.style.margin = "10px 0";
        stack.push(d);
        return;
      }
      var m = line.match(/^\s*<summary>([\s\S]*?)<\/summary>\s*$/i);
      if (m) {
        flush();
        var sum = document.createElement("summary");
        sum.textContent = m[1];
        sum.style.cursor = "pointer";
        cur().appendChild(sum);
        return;
      }
      if (/^\s*<\/details>\s*$/i.test(line)) {
        flush();
        if (stack.length > 1) {
          var d = stack.pop();   // 先出栈再挂载：cur() 求值时栈顶已换回外层
          cur().appendChild(d);
        }
        return;
      }
      pending.push(line);
    });
  }
  var m, last = 0;
  while ((m = re.exec(s)) !== null) {
    addText(s.slice(last, m.index));
    flush();
    var body = m[2].replace(/^\r?\n/, "").replace(/\r?\n$/, "");
    if (body.trim()) {
      cur().appendChild(codeLab(body, m[1] || defaultLang || "python"));
    }
    last = re.lastIndex;
  }
  addText(s.slice(last));
  flush();
  while (stack.length > 1) {
    var d = stack.pop();   // 未闭合的 <details> 收尾兜底挂载
    cur().appendChild(d);
  }
}

// 渲染完成后把占位 div 填成带代码实操的教程正文
function hydrateTutorials(jobs) {
  var byId = {};
  (jobs || []).forEach(function (j) { byId[j.id] = j; });
  var nodes = document.querySelectorAll(".tut-body[data-job]");
  for (var k = 0; k < nodes.length; k++) {
    var el = nodes[k];
    if (el.getAttribute("data-done") === "1") continue;
    var job = byId[el.getAttribute("data-job")];
    if (!job || job.status !== "done") continue;
    var text = (job.result || {}).summary || "";
    el.innerHTML = "";
    tutorialHtml(el, text, "python");
    el.setAttribute("data-done", "1");
  }
}

// ====== 强化学习闭环：练习判题 + 智能复习卡渲染 ======
var _pracResults = {};

function hydratePractices(jobs) {
  var byId = {};
  (jobs || []).forEach(function (j) { byId[j.id] = j; });
  var nodes = document.querySelectorAll(".prac-body[data-job]");
  for (var k = 0; k < nodes.length; k++) {
    var el = nodes[k];
    if (el.getAttribute("data-done") === "1") continue;
    var job = byId[el.getAttribute("data-job")];
    if (!job || job.status !== "done") continue;
    el.setAttribute("data-done", "1");
    el.innerHTML = "";
    var r = job.result || {};
    if (job.kind === "smartreview") {
      tutorialHtml(el, r.summary || "", "python");
      continue;
    }
    var set = null;
    try { set = JSON.parse(r.summary || "{}"); } catch (e) { set = null; }
    if (!set || !set.items || !set.items.length) {
      var err = document.createElement("p");
      err.className = "stat bad";
      err.textContent = r.summary || "练习数据无效";
      el.appendChild(err);
      continue;
    }
    buildPracticeSet(el, job, set);
  }
}

function buildPracticeSet(el, job, set) {
  var lang = set.lang || "python";
  var head = document.createElement("p");
  head.className = "stat";
  head.textContent = "🎯 练习集：" + (set.topic || "") + " · 共 " + set.items.length + " 题（改代码后点▶运行判题，错题自动记入薄弱点）";
  el.appendChild(head);
  _pracResults[job.id] = { lang: lang, topic: set.topic || "", total: set.items.length, passed: {} };
  for (var i = 0; i < set.items.length; i++) {
    el.appendChild(buildPracticeItem(job.id, i, set.items[i]));
  }
  var banner = document.createElement("div");
  banner.id = "prac-banner-" + job.id;
  el.appendChild(banner);
}

function buildPracticeItem(jobId, idx, it) {
  var box = document.createElement("div");
  box.className = "lab";
  var h = document.createElement("b");
  h.textContent = "练习" + (idx + 1) + "：" + (it.title || "");
  box.appendChild(h);
  var task = document.createElement("pre");
  task.className = "result";
  task.style.whiteSpace = "pre-wrap";
  task.textContent = it.task || "";
  box.appendChild(task);
  var id = "prac-" + jobId + "-" + idx;
  var ta = document.createElement("textarea");
  ta.id = id;
  ta.rows = Math.min(16, Math.max(5, String(it.starter || "").split(NL).length));
  ta.spellcheck = false;
  ta.style.fontFamily = "Consolas,Monaco,Courier New,monospace";
  ta.style.fontSize = "13px";
  ta.style.width = "100%";
  ta.style.whiteSpace = "pre";
  ta.value = it.starter || "";
  box.appendChild(ta);
  var bar = document.createElement("div");
  bar.className = "row";
  var btn = document.createElement("button");
  btn.className = "go";
  btn.textContent = "▶ 运行判题";
  btn.onclick = function () { judgePracticeItem(jobId, idx, it, id); };
  bar.appendChild(btn);
  var st = document.createElement("span");
  st.className = "stat";
  st.id = id + "-st";
  bar.appendChild(st);
  box.appendChild(bar);
  var out = document.createElement("pre");
  out.id = id + "-out";
  out.className = "result";
  out.style.display = "none";
  box.appendChild(out);
  return box;
}

async function judgePracticeItem(jobId, idx, it, taId) {
  var ta = document.getElementById(taId);
  var out = document.getElementById(taId + "-out");
  var st = document.getElementById(taId + "-st");
  if (!ta || !out || !st) return;
  st.innerHTML = "<span class=\"st-running\">运行中…</span>";
  out.style.display = "none";
  var state = _pracResults[jobId] || {};
  try {
    var resp = await fetch("/api/practice/judge", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: ta.value, expects: it.expects || [] })
    });
    var r = await resp.json();
    out.textContent = (r.output || r.error || "") || "(无输出)";
    out.style.display = "";
    if (r.ok) {
      st.innerHTML = "<span class=\"st-done\">✓ 通过</span>";
      _pracResults[jobId].passed[idx] = true;
    } else {
      st.innerHTML = "<span class=\"bad\">✗ 未通过，已记入薄弱点</span>";
      _pracResults[jobId].passed[idx] = false;
    }
    fetch("/api/practice/record", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lang: state.lang, topic: state.topic,
        title: it.title || "", passed: !!r.ok })
    });
    var all = state.total, ok = 0;
    for (var k2 in state.passed) if (state.passed[k2]) ok++;
    var banner = document.getElementById("prac-banner-" + jobId);
    if (banner && ok === all) {
      banner.innerHTML = "<p class=\"stat\">🎉 本组全部通过！可以学下一课，或点🧠智能复习巩固记忆。</p>";
    }
  } catch (err) {
    out.textContent = "判题请求失败: " + err;
    out.style.display = "";
    st.innerHTML = "<span class=\"bad\">✗ 请求失败</span>";
  }
}
