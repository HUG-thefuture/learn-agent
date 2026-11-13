# 146. LRU 缓存（Least Recently Used）

## 1. 思路推导

### 1.1 把需求翻译成约束

题目要求两个操作：

| 操作 | 语义 | 时间复杂度目标 |
|---|---|---|
| `get(key)` | 命中则返回 value，并标记为「最近使用」；否则返回 -1 | 越低越好 |
| `put(key, value)` | 写入/更新，标记为「最近使用」；容量满时淘汰**最久未使用**的那条 | 越低越好 |

注意这里有两个**独立**的需求叠加在一起：

1. **按 key 快速定位**（这是哈希表的活）；
2. **维护一个随时可调整的"使用顺序"**，并且要能在任意位置做三种操作：把节点移到队首、删除队尾、删除任意节点（更新已有 key 时）（这是链表/有序结构的活）。

### 1.2 单结构为什么不够

- **只用哈希表**：get/put O(1) 没问题，但"谁是最久未用的"完全无从得知——除非每次遍历找最小时间戳，O(n)。
- **只用数组/链表**：顺序能维护，但 `get(key)` 要找 key 得遍历，O(n)。数组中间删除还会整体搬移，也是 O(n)。
- **用堆（按访问时间戳排序）**：淘汰 O(log n)，且节点被"访问"后时间戳变了，堆里会残留大量失效记录，需要惰性删除 + 版本号，复杂且慢。

### 1.3 组合拳：哈希表 + 双向链表

```
哈希表： key ──▶ 链表节点（O(1) 定位节点，不存 value 副本，避免两份数据不一致）
双向链表： head ⇄ [最近使用] ⇄ ... ⇄ [最久未用] ⇄ tail
```

- `get`：哈希表 O(1) 找到节点 → 把节点从当前位置摘下、插到 head 端（O(1)）。
- `put` 新 key：插到 head 端；若超容量，摘掉 `tail.prev`（最久未用）并**同步从哈希表删除**。
- `put` 老 key：更新 value 并移到 head 端。

**为什么必须是双向链表？** 摘除任意节点需要同时改它的**前驱**和**后继**。单向链表拿不到前驱，只能从头遍历 → O(n)。这就是本题"双向"二字的唯一理由，面试要能一句话讲清楚。

**为什么节点里要存 key？** 淘汰 `tail.prev` 时，我们只持有节点对象，必须靠 `node.key` 反查哈希表把它删掉。漏存 key 是本题最高频的 bug。

**为什么要哨兵（dummy head/tail）？** 链表首尾插入/删除是最容易写出 `if node.prev is None` 分支的地方。前后各放一个哨兵节点后，所有节点都有前驱后继，四行指针操作即可无分支完成，边界 bug 归零。

### 1.4 操作流程图（文字版）

```
get(k):
  node = map.get(k)
  if node is None: return -1
  move_to_front(node); return node.val

put(k, v):
  if cap == 0: return                      # 防御，题目保证 >=1
  if k in map:
      node.val = v; move_to_front(node); return
  if len(map) == cap:
      lru = tail.prev
      unlink(lru); del map[lru.key]        # 两步都要做！
  node = Node(k, v); map[k] = node; push_front(node)
```

---

## 2. 推荐解法与代码（Python）

### 2.1 手写双向链表版（面试标准答案）

```python
from __future__ import annotations
from typing import Optional


class _Node:
    __slots__ = ("key", "val", "prev", "next")   # 省内存：缓存可能有上万节点

    def __init__(self, key: int = 0, val: int = 0) -> None:
        self.key = key
        self.val = val
        self.prev: Optional[_Node] = None
        self.next: Optional[_Node] = None


class LRUCache:
    """哈希表 + 双向链表（带哨兵），get/put 均摊 O(1)。"""

    def __init__(self, capacity: int) -> None:
        if capacity < 0:
            raise ValueError("capacity 不能为负数")
        self._cap = capacity
        self._map: dict[int, _Node] = {}
        # head.next = 最近使用；tail.prev = 最久未用
        self._head = _Node()
        self._tail = _Node()
        self._head.next = self._tail
        self._tail.prev = self._head

    # ---------- 链表原子操作 ----------
    def _unlink(self, node: _Node) -> None:
        """把 node 从链表中摘下（node 一定在链表中，哨兵保证非空）。"""
        p, n = node.prev, node.next
        p.next = n            # type: ignore[union-attr]
        n.prev = p            # type: ignore[union-attr]
        node.prev = node.next = None   # 主动断链，不留悬挂引用

    def _push_front(self, node: _Node) -> None:
        node.next = self._head.next
        node.prev = self._head
        self._head.next.prev = node    # type: ignore[union-attr]
        self._head.next = node

    def _move_to_front(self, node: _Node) -> None:
        self._unlink(node)
        self._push_front(node)

    # ---------- 对外接口 ----------
    def get(self, key: int) -> int:
        node = self._map.get(key)
        if node is None:
            return -1
        self._move_to_front(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        if self._cap == 0:             # 防御：容量 0 时 put 全部丢弃
            return

        node = self._map.get(key)
        if node is not None:           # 已有 key：更新值 + 提到最前
            node.val = value
            self._move_to_front(node)
            return

        if len(self._map) == self._cap:          # 满：淘汰最久未用
            lru = self._tail.prev
            self._unlink(lru)                    # type: ignore[arg-type]
            del self._map[lru.key]               # type: ignore[union-attr]

        node = _Node(key, value)
        self._map[key] = node
        self._push_front(node)

    # ---------- 资源释放（长生命周期对象可主动调用） ----------
    def clear(self) -> None:
        cur = self._head.next
        while cur is not self._tail:
            nxt = cur.next
            cur.prev = cur.next = None
            cur = nxt
        self._head.next, self._tail.prev = self._tail, self._head
        self._map.clear()
```

### 2.2 工程简洁版：`collections.OrderedDict`

`OrderedDict` 内部就是「哈希表 + 双向循环链表」，`move_to_end` / `popitem(last=False)` 都是 O(1) 的 C 实现。

```python
from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity: int) -> None:
        self._cap = capacity
        self._od: OrderedDict[int, int] = OrderedDict()   # 尾部 = 最近使用

    def get(self, key: int) -> int:
        if key not in self._od:
            return -1
        self._od.move_to_end(key)
        return self._od[key]

    def put(self, key: int, value: int) -> None:
        if key in self._od:
            self._od[key] = value        # 已存在：改值（不会改变顺序）
            self._od.move_to_end(key)
            return
        if len(self._od) >= self._cap:
            self._od.popitem(last=False) # 弹出最早插入 = 最久未用
        self._od[key] = value
```

> 面试策略：**先讲清原理，再给手写版**；如果面试官说"可以调库"，再补 OrderedDict 版。只写 OrderedDict 版容易被追问"它内部怎么实现的"，答不上来会掉分。

### 2.3 高频易错点（提交前自查）

1. **淘汰时只摘链表、忘记 `del map[key]`** → 哈希表泄漏，之后 `get` 返回已淘汰的值。最典型 bug。
2. **节点不存 key** → 淘汰时无法反查哈希表。
3. **`put` 已存在的 key 时直接 `map[key] = new_node`** → 链表里残留旧节点，顺序错乱 + 内存泄漏。
4. **`update` 已有 key 时忘了 `move_to_front`** → 顺序错，测试可能"侥幸"通过部分用例。
5. **用单向链表** → 没法 O(1) 摘除任意节点。
6. **哨兵写错导致首尾分支** → 用两个哨兵基本可以消灭这类 bug。
7. **并发场景直接复用此实现**：`get` 会改链表和哈希表，多线程下不是只读操作，需加锁（见第 5 节）。

---

## 3. 复杂度分析

| 维度 | 手写双向链表 | OrderedDict |
|---|---|---|
| `get` | 均摊 O(1)：哈希查找 O(1) + 4 次指针赋值 | 均摊 O(1)（`move_to_end` 为链表操作） |
| `put` | 均摊 O(1)：哈希查找/插入 + 链表摘挂 | 均摊 O(1)（`popitem(last=False)` 为链表头删） |
| 空间 | O(capacity)：每个 key 一个 `_Node`（key、val、prev、next 四个槽，`__slots__` 后约 64B） | O(capacity)，C 层实现开销更小 |
| 最坏情况 | 哈希冲突退化时哈希查找 O(n)，但链表操作严格 O(1) | 同左（Python 的 dict 对冲突有扰动，实际近乎 O(1)） |

> 讲"均摊 O(1)"是标准答法。空间上要能说出「额外 O(capacity) 的节点 + 哈希表」而不是笼统的 O(n)。

---

## 4. 其他解法对比

| 方案 | `get` | `put` | 评价 |
|---|---|---|---|
| **哈希表 + 双向链表（推荐）** | O(1) | O(1) | 标准解，面试要手写出来 |
| `OrderedDict` / Java `LinkedHashMap(accessOrder=true)` | O(1) | O(1) | 原理相同，代码 10 行；需能解释内部实现 |
| 哈希表 + 数组（存 `(key, val, last_used_ts)`） | O(1) | 淘汰 O(n) | 淘汰要线性扫描找最小时间戳；写入简单但不符合 O(1) |
| 哈希表 + 二叉堆（按访问时间） | O(1) 逻辑 + 惰性删除 | O(log n) | 堆中旧记录失效，需要版本号/惰性 pop，实现复杂且更慢 |
| 哈希表 + 单链表 | O(1) + 定位 O(n) | 同 | 拿不到前驱，除非哈希表额外存 prev，得不偿失 |
| 哈希表 + 有序字典（普通 `dict` 技巧，见下） | 均摊 O(1) | 均摊 O(1) | 依赖 CPython 细节，短小但不适合当主答案 |
| **近似 LRU（Redis 策略）** | O(1) | O(1) | 随机采样 N 个 key 淘汰其中最久未用，牺牲精度换内存/吞吐 |
| **Clock / 二次机会算法** | O(1) | O(1) | 环形缓冲区 + 引用位，近似 LRU，常用于 OS 页置换 |
| `functools.lru_cache` | — | — | C 实现，底层同样是 dict + 双向链表，可用于佐证思路 |

**普通 dict 技巧版**（利用 Python 3.7+ 保证的插入有序）：

```python
class LRUCache:
    def __init__(self, capacity: int) -> None:
        self._cap = capacity
        self._d: dict[int, int] = {}      # 插入顺序 = 使用顺序，最早 = 最久未用

    def get(self, key: int) -> int:
        if key not in self._d:
            return -1
        v = self._d.pop(key)
        self._d[key] = v                  # 先删后插 → 挪到"最新"位置
        return v

    def put(self, key: int, value: int) -> None:
        if key in self._d:
            self._d.pop(key)
        elif len(self._d) >= self._cap:
            oldest = next(iter(self._d))  # 取最早插入的 key
            del self._d[oldest]
        self._d[key] = value
```

优点：代码最短，无自定义类。缺点：`pop + 重新插入` 每次都要重算哈希、可能累积 dummy 槽位（CPython 实现细节），常数比 OrderedDict 大；且"dict 有序"这个前提要说清楚是 3.7+ 的语言规范。**面试可作为"你知道 Python 实现"的加分补充，不建议作为主答案。**

---

## 5. 同类题拓展

### 5.1 直接同源题（必须一起刷）

| 题号 | 题目 | 与本题关系 |
|---|---|---|
| **460** | **LFU 缓存** | 升级版：按「访问频次」淘汰，同频次再按 LRU。做法是 `key → 频次`，每个频次维护一条 LRU 链表，再维护 `minFreq`，仍可做到 O(1)。先把 146 的链表操作写熟再来 |
| **432** | 全 O(1) 的数据结构 | `inc/dec/maxKey/minKey` 全 O(1)：频次桶 + 双向链表，思想与 LFU 完全一致 |
| **380 / 381** | O(1) 插入、删除、随机取（可重复版） | 哈希表 + **数组**（尾插 + 与末尾交换删除），是"哈希 + 另一个结构"组合套路的另一支 |
| **705 / 706** | 设计哈希集合/映射 | 哈希表本身的手写实现（拉链法 / 开放寻址） |
| **355** | 设计推特 | 关注关系用哈希集合，时间线用「链表头插 + k 路归并/堆」，也考数据结构组合 |
| **1146 / 588** | 快照数组 / 文件系统 | 偏设计，但同样考"读多写少场景下的结构选择" |

### 5.2 面试常见追问与变体

1. **「加个 TTL（过期时间）怎么做？」**
   在 `_Node` 上加 `expire_at`，`get` 时惰性判断是否过期（过期就删并返回 -1）；后台可再加一个按过期时间排序的定时任务/最小堆做主动清理。注意：删除时必须同时清理两处索引。
2. **「线程安全版本？」**
   `get` 会改链表，**不是只读操作**，必须加锁。最简单 `threading.RLock` 包住两个方法；高并发可做分段锁 / 每段一个 LRU（类似 `ConcurrentHashMap` 分段思想），或者读多写少时用读写锁但 `get` 仍需写锁。
3. **「容量按权重（每个 entry 大小不同）怎么改？」**
   `_Node` 加 `size`，维护 `cur_size`，淘汰循环 `while cur_size > cap` 而不是 `len == cap`；同时要给单个超大 entry 定策略（拒收或独占）。
4. **「为什么 Redis 用近似 LRU 而不是精确 LRU？」**
   精确 LRU 要为所有 key 维护一条全局双向链表，内存和锁竞争成本高；Redis 改为每个对象记 24 位时钟，淘汰时随机采样 5 个 key 选最久未用的，精度换吞吐，工程上足够用。
5. **「把 LRU 换成 FIFO 要改什么？」**
   命中时**不**移动节点，其余一样——这也说明本题的核心难点只在"移动节点"这一句。
6. **「为什么不直接用 `@lru_cache`？」**
   它是函数装饰器，以参数元组为 key，无法对任意 key 手动 `get/put`，也不暴露淘汰控制。但它的源码结构（`dict` + 双向循环链表）正是本题的参考答案，值得一读。

### 5.3 一句话总结

> LRU = **「哈希表管"找得到"，双向链表管"排得序"」**。两个结构各管一件事，节点里存 key 做双向索引，哨兵节点消除边界分支，淘汰时两处索引同步删除。把这四点讲清楚，这道题就答满了。