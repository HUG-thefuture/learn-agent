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
    {"id": "seed:web:fullstack", "title": "前后端开发要点", "lang": "general",
     "tags": ["fullstack"], "source": "seed", "text": """
后端: RESTful 设计(GET查/POST增/PUT改/DELETE删); 参数校验; 统一错误处理; CORS 配置;
SQLite/MySQL 持久化; 密码哈希存储。前端: fetch 调 API + 加载/错误状态; 表单校验;
事件绑定防重复; XSS 防范(textContent 优先于 innerHTML)。联调: 先 curl 测后端, 再接前端;
跨域用后端 CORS 中间件解决。
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
    report = {"knowledge_train": {**stats, "distilled_docs": n_dist,
                                  "hit_rate": ev["hit_rate"],
                                  "index": str(_kb.path)}}
    out = data_dir() / "knowledge" / "train_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[kb-train] docs={stats['docs']} vocab={stats['vocab']} "
          f"hit_rate={ev['hit_rate']} (新增蒸馏 {n_dist} 条)")
    return report


if __name__ == "__main__":
    run()
