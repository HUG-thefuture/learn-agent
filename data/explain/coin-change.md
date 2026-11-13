# LeetCode 322. 零钱兑换 题解

## 1. 思路推导

### 1.1 把问题抽象成「最优化 + 无限次选择」

- 每种硬币可以用**任意多次**（数量无限）→ 典型的**完全背包**模型。
- 目标不是「能不能」，而是「**最少用几枚**」→ 最优化问题。
- 无解时返回 `-1` → 需要一个「不可达」的哨兵值。

### 1.2 为什么不能贪心

直觉做法是「每次尽量用最大的硬币」，但**任意面额下贪心不成立**：

```
coins = [1, 3, 4], amount = 6
贪心：4 + 1 + 1 = 3 枚
最优：3 + 3       = 2 枚   ← 反例
```

面额不成「规范币制」时，局部最优 ≠ 全局最优，必须用 DP / 搜索。

### 1.3 最优子结构 + 重叠子问题

定义 `f(x)` = 凑出金额 `x` 的最少硬币数。考虑最优解里**最后一枚硬币**面额为 `c`，则剩余部分 `x - c` 也必须用最优方式凑出（否则替换后整体更优），于是：

```
f(0) = 0
f(x) = min_{c ∈ coins, c ≤ x} ( f(x - c) + 1 )
f(x) = +∞  表示不可达
```

画一下递归树（`coins=[1,2,5], x=11`）会发现 `f(6)`、`f(9)` 等被反复计算 —— **重叠子问题**，必须记忆化或自底向上递推。

> 状态只需要「金额」一个维度：硬币无限 + 只关心数量，不需要记录用了哪些硬币（无后效性）。

---

## 2. 推荐解法：自底向上 DP

`dp[i]` 表示凑出金额 `i` 的最少硬币数。

```python
from typing import List


class Solution:
    def coinChange(self, coins: List[int], amount: int) -> int:
        if amount == 0:
            return 0
        if amount < 0:
            return -1

        # 预处理：去重，并丢弃「非正」或「大于 amount」的硬币（永远用不上）
        coins = sorted({c for c in coins if 0 < c <= amount})
        if not coins:
            return -1

        # 任何可行方案最多用 amount 枚（每枚面额 >= 1），用它作"不可达"哨兵，天然防溢出
        INF = amount + 1
        dp = [INF] * (amount + 1)
        dp[0] = 0

        for i in range(1, amount + 1):          # 按金额从小到大递推
            for c in coins:                     # coins 已升序
                if c > i:
                    break                       # 后面的硬币更大，直接剪掉
                if dp[i - c] + 1 < dp[i]:       # dp[i-c] == INF 时不会误更新
                    dp[i] = dp[i - c] + 1

        return -1 if dp[amount] == INF else dp[amount]


if __name__ == "__main__":
    s = Solution()
    assert s.coinChange([1, 2, 5], 11) == 3
    assert s.coinChange([2], 3) == -1
    assert s.coinChange([1], 0) == 0
    assert s.coinChange([1, 3, 4], 6) == 2          # 贪心反例
    assert s.coinChange([186, 419, 83, 408], 6249) == 20
    assert s.coinChange([1, 2147483647], 2) == 2    # 大面额需被过滤，防溢出
    assert s.coinChange([], 5) == -1
    print("All tests passed")
```

### 示例推演：`coins=[1,2,5], amount=11`

| i | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|----|
| dp[i] | 0 | 1 | 1 | 2 | 2 | 1 | 2 | 2 | 3 | 3 | 2 | 3 |

`dp[11] = dp[10] + 1 = 2 + 1 = 3`（5 + 5 + 1）。✅

### 另一种等价写法（硬币在外层）

```python
for c in coins:                      # 完全背包标准写法
    for i in range(c, amount + 1):   # 正序 → 同一硬币可重复使用
        dp[i] = min(dp[i], dp[i - c] + 1)
```

两种顺序都正确 —— 因为 `min` 运算可交换，本题对「凑钱顺序」不敏感。但改成**计数**类问题（518/377）时顺序就至关重要了，见第 5 节。

---

## 3. 复杂度分析

设 `n = len(coins)`，`A = amount`。

| 维度 | 复杂度 | 说明 |
|---|---|---|
| 时间 | **O(A · n)** | 状态数 `A`，每个状态枚举 `n` 个硬币 |
| 空间 | **O(A)** | 一维 `dp` 数组；预处理 `O(n log n)` 可忽略 |

- 本题 `A ≤ 10⁴`、`n ≤ 12`，约 `1.2×10⁵` 次操作，轻松通过。
- 内存：`dp` 长度为 `A+1` 的 `list[int]`，无泄漏风险（Python 引用计数即时回收，无循环引用）。
- 无法再压缩空间：`dp[i]` 依赖 `dp[i-c]`（不同 `c`），不像 01 背包那样能只留一维的滚动方向优化 —— 现在这已经是最省的形式了。

---

## 4. 其他解法对比

### 4.1 自顶向下记忆化搜索

```python
from functools import lru_cache
import sys


class SolutionMemo:
    def coinChange(self, coins, amount):
        coins = sorted({c for c in coins if 0 < c <= amount})
        if amount == 0:
            return 0
        if not coins:
            return -1

        sys.setrecursionlimit(amount + 10)   # 关键：amount 可达 1e4，默认深度 1000 会爆栈

        @lru_cache(maxsize=None)
        def dfs(rest: int) -> int:
            if rest == 0:
                return 0
            best = float("inf")
            for c in coins:
                if c > rest:
                    break
                best = min(best, dfs(rest - c) + 1)
            return best

        ans = dfs(amount)
        return -1 if ans == float("inf") else ans
```

- 时间复杂度与 DP 相同 **O(A·n)**，空间 **O(A)**（缓存）+ **O(A)** 递归栈。
- 缺点：递归深度可能达到 `A`，Python 下必须手动 `setrecursionlimit`，且常数更大、易栈溢出，**工程上不推荐**。优点是思路直观，适合从暴力递归自然过渡。

### 4.2 BFS（把问题看成无权最短路）

节点 `0..amount`，边 `i → i+c` 权重为 1，求 `0 → amount` 的最短路，用 BFS 层级即答案。

```python
from collections import deque


class SolutionBFS:
    def coinChange(self, coins, amount):
        if amount == 0:
            return 0
        # 降序排列：优先尝试大面额，通常更快收敛
        coins = sorted({c for c in coins if 0 < c <= amount}, reverse=True)
        if not coins:
            return -1

        visited = [False] * (amount + 1)
        visited[0] = True
        q = deque([0])
        steps = 0

        while q:
            steps += 1
            for _ in range(len(q)):          # 按层展开
                cur = q.popleft()
                for c in coins:
                    nxt = cur + c
                    if nxt == amount:
                        return steps
                    if nxt < amount and not visited[nxt]:
                        visited[nxt] = True  # 必须入队时标记，否则重复入队会内存爆炸
                        q.append(nxt)
        return -1
```

- 最坏时间 **O(A·n)**，空间 **O(A)**。
- 优点：一旦搜到 `amount` 立即返回，平均远快于 DP（尤其答案很小时）。
- 缺点：最坏情况下 `queue` + `visited` 的内存峰值高于 DP 的一维数组；且需要小心「出队才标记」导致的重复入队。

### 4.3 解法横向对比

| 解法 | 时间 | 空间 | 评价 |
|---|---|---|---|
| **自底向上 DP** | O(A·n) | O(A) | ✅ **推荐**：无递归、稳定、易调试 |
| 记忆化搜索 | O(A·n) | O(A) + 栈 | 思路直观，但深度受限、常数大 |
| BFS 最短路 | O(A·n) 最坏 | O(A) | 常见用例更快，最坏风险高 |
| 贪心 | O(n log n) | O(1) | ❌ **错误**，`[1,3,4], 6` 即反例 |

> 进阶（面试加分）：当 `amount` 极大而 `coins` 很小时，可用「同余最短路」（以 `min(coins)` 为模建图跑 Dijkstra）或 BFS/DP + 周期性质优化，把复杂度降到与 `amount` 无关的量级。本题数据范围用不到。

### 4.4 常见坑

1. `amount == 0` 必须返回 `0`（空硬币组合合法），不要返回 `-1`。
2. `INF` 取 `amount + 1` 而不是 `10**9`：可行解最多 `amount` 枚（面额 ≥ 1），既保证「更优」判断正确，又避免 `INF + 1` 溢出/误判。
3. 必须过滤 `c > amount` 的面额，否则白白多跑循环，还可能引入大数。
4. 不要用 `dp[i] == -1` 当哨兵再在转移里特判 —— 用 `INF` 更简洁。
5. 循环顺序：`coins` 升序 + `break` 是有效剪枝；未排序时不能 `break`。

---

## 5. 同类题拓展

### 5.1 完全背包家族（无限次选取）

| 题目 | 变化点 | 循环顺序关键 |
|---|---|---|
| **322. 零钱兑换** | 求**最少个数** | 任意顺序皆可（`min` 可交换） |
| **518. 零钱兑换 II** | 求**组合数** | 必须**外层硬币、内层金额**，才不重复计数 |
| **377. 组合总和 Ⅳ** | 求**排列数** | 必须**外层金额、内层硬币** |
| **279. 完全平方数** | 硬币变成 `1,4,9,16...` | 与 322 完全同构 |
| **面试题 08.11. 硬币** | 求方案数（取模） | 同 518 |
| **1449. 数位成本和为目标值的最大数字** | 求最大数字（字符串比较） | 变形的完全背包 |

> 记忆口诀：**求最少/最多 → 顺序随意；求组合（不重）→ 物品在外；求排列（有序）→ 容量在外。**

### 5.2 01 背包 / 其他最优化 DP

- **416. 分割等和子集** —— 能否恰好装满（布尔 DP）
- **494. 目标和** —— 装满的方案数（符号转换）
- **474. 一和零** —— 二维容量（01 背包，内层逆序）
- **1049. 最后一块石头的重量 II** —— 最小化差值
- **983. 最低票价** —— 带「有效期」的 DP（依赖前若干状态）
- **139. 单词拆分** —— 状态转移条件变成「字符串匹配」

### 5.3 一句话迁移

> 322 是「完全背包 + 求最小物品数」的原型题。掌握了**状态定义 → 转移方程 → 哨兵值 → 循环顺序**这四步，就能把这一套模板迁移到上面全部题目。