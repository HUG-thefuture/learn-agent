## 力扣 70. 爬楼梯 题解

### 1) 思路推导

**问题本质**：这是一个经典的**斐波那契数列**变体问题。  
设 `f(n)` 表示爬到第 `n` 阶的方法数，则：

- 最后一步只能从 `n-1` 阶跨 1 步，或从 `n-2` 阶跨 2 步到达。
- 因此：`f(n) = f(n-1) + f(n-2)`。
- 边界条件：`f(1) = 1`，`f(2) = 2`。

**关键洞察**：  
- 这是一个**无后效性**的动态规划问题（当前状态只依赖前两个状态）。
- 不需要存储整个 DP 数组，只需两个变量滚动更新即可。

---

### 2) 推荐解法与代码（Python）

**推荐：滚动变量法（空间优化 DP）**

```python
def climbStairs(n: int) -> int:
    # 边界情况处理
    if n <= 2:
        return n
    
    # 初始化前两个状态
    prev2, prev1 = 1, 2  # f(1), f(2)
    
    # 从第3阶开始迭代
    for _ in range(3, n + 1):
        current = prev1 + prev2
        prev2, prev1 = prev1, current  # 滚动更新
    
    return prev1
```

**测试用例**：
```python
assert climbStairs(1) == 1
assert climbStairs(2) == 2
assert climbStairs(3) == 3  # 1+1+1, 1+2, 2+1
assert climbStairs(4) == 5
assert climbStairs(10) == 89
```

---

### 3) 复杂度分析

| 方法 | 时间复杂度 | 空间复杂度 | 说明 |
|------|-----------|-----------|------|
| 递归（朴素） | O(2^n) | O(n)（递归栈） | 大量重复计算，不可取 |
| 记忆化递归 | O(n) | O(n) | 用字典缓存结果 |
| **滚动变量 DP** | **O(n)** | **O(1)** | **推荐，最优** |
| 矩阵快速幂 | O(log n) | O(1) | 适合 n 极大时 |

---

### 4) 其他解法对比

#### 方法一：朴素递归（不推荐）
```python
def climbStairs_naive(n):
    if n <= 2:
        return n
    return climbStairs_naive(n-1) + climbStairs_naive(n-2)
```
- 缺点：指数级时间，n=40 就非常慢。

#### 方法二：记忆化递归（自顶向下）
```python
def climbStairs_memo(n, memo={}):
    if n in memo:
        return memo[n]
    if n <= 2:
        return n
    memo[n] = climbStairs_memo(n-1, memo) + climbStairs_memo(n-2, memo)
    return memo[n]
```
- 优点：直观，避免重复计算。
- 缺点：需要额外空间，且递归有栈溢出风险（n 很大时）。

#### 方法三：矩阵快速幂（进阶）
```python
def climbStairs_matrix(n):
    if n <= 2:
        return n
    # 使用矩阵 [[1,1],[1,0]] 的 n-1 次幂
    def matrix_mult(A, B):
        return [[A[0][0]*B[0][0]+A[0][1]*B[1][0], A[0][0]*B[0][1]+A[0][1]*B[1][1]],
                [A[1][0]*B[0][0]+A[1][1]*B[1][0], A[1][0]*B[0][1]+A[1][1]*B[1][1]]]
    
    def matrix_pow(mat, exp):
        result = [[1,0],[0,1]]
        while exp:
            if exp & 1:
                result = matrix_mult(result, mat)
            mat = matrix_mult(mat, mat)
            exp >>= 1
        return result
    
    base = [[1,1],[1,0]]
    result = matrix_pow(base, n-1)
    return result[0][0] + result[0][1]
```
- 优点：O(log n) 时间，适合 n 极大（如 10^18）。
- 缺点：代码复杂，对本题 n ≤ 45 来说大材小用。

---

### 5) 同类题拓展

| 题目 | 关联点 | 解法要点 |
|------|--------|----------|
| **746. 使用最小花费爬楼梯** | 变体：每步有代价 | DP 状态转移：`dp[i] = min(dp[i-1], dp[i-2]) + cost[i]` |
| **509. 斐波那契数** | 本质相同 | 直接套用滚动变量法 |
| **1137. 第 N 个泰波那契数** | 三阶递推 | `dp[i] = dp[i-1] + dp[i-2] + dp[i-3]` |
| **198. 打家劫舍** | 类似递推但带约束 | 状态转移：`dp[i] = max(dp[i-1], dp[i-2] + nums[i])` |
| **55. 跳跃游戏** | 贪心/DP | 维护最远可达距离 |

**进阶思考**：
- 如果每次可以爬 `1, 2, 3` 阶，则递推变为 `f(n) = f(n-1) + f(n-2) + f(n-3)`，边界 `f(1)=1, f(2)=2, f(3)=4`。
- 如果每次可以爬 `k` 种步长，则变为完全背包问题，可用 DP 解决。

---

### 总结
- **核心**：识别斐波那契递推关系。
- **最优解**：滚动变量 DP，时间 O(n)，空间 O(1)。
- **面试要点**：能写出递推公式，并说明空间优化思路。