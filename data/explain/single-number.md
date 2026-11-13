# LeetCode 136. 只出现一次的数字

> **题意**：非空整数数组 `nums`，除某个元素只出现一次外，其余每个元素都恰好出现两次。找出那个只出现一次的元素。
> **要求**：时间 O(n)，额外空间 O(1)。
> **约束**（原题）：`1 <= nums.length <= 3*10^4`，`-3*10^4 <= nums[i] <= 3*10^4`。

---

## 1) 思路推导

### 第一步：先想最朴素的解法

统计频次，返回频次为 1 的那个：

```python
from collections import Counter
Counter(nums)  # 找 value == 1 的 key
```

时间复杂度 O(n)，但空间是 **O(n)**——瓶颈就在这里。题目要求 O(1) 空间，说明必须找到一个**不需要"记住见过谁"**的办法。

### 第二步：什么样的运算能"自己抵消自己"？

我们要找一种运算，满足：**同一个数作用两次等于没作用**。逐一考察候选：

| 运算 | 能否自己抵消 | 问题 |
|---|---|---|
| 加法 | 否（a+a=2a） | 需要知道该加还是该减 → 又得存"见过与否"，O(n) 空间 |
| 减法 | 否 | 同上 |
| 乘法/除法 | 否 | 同上 |
| **异或 ^** | **是：`a ^ a = 0`** | 无需额外信息，天然抵消 ✅ |

异或的三条关键性质：

1. **自反性**：`x ^ x = 0`
2. **单位元**：`x ^ 0 = x`
3. **交换律 + 结合律**：`a ^ b = b ^ a`，`(a ^ b) ^ c = a ^ (b ^ c)`

> 换句话说，异或构成一个阿贝尔群，且**每个元素都是自己的逆元**。这正是"O(1) 空间"能成立的根本原因：重复出现的元素会互相消灭，我们不需要额外记账。

### 第三步：得出公式

设单身元素为 `s`，其余元素两两成对 `(a₁,a₁), (a₂,a₂), ..., (aₖ,aₖ)`，则：

```
nums[0] ^ nums[1] ^ ... ^ nums[n-1]
= s ^ (a₁^a₁) ^ (a₂^a₂) ^ ... ^ (aₖ^aₖ)     # 结合律重新分组
= s ^ 0 ^ 0 ^ ... ^ 0                        # 自反性
= s                                          # 单位元
```

因为异或满足交换律，**成对的元素在数组里隔多远都无所谓**，最终一定全部抵消。

### 第四步：手工模拟一遍

`nums = [4, 1, 2, 1, 2]`：

```
ans = 0
^4 → 4
^1 → 5   (100 ^ 001 = 101)
^2 → 7   (101 ^ 010 = 111)
^1 → 6   (111 ^ 001 = 110)
^2 → 4   (110 ^ 010 = 100)  ✅ 答案 4
```

可以看到 `1` 和 `2` 在过程中互相对消，最后只剩 `4`。

---

## 2) 推荐解法与代码（Python）

### 主解法：全体异或

```python
from typing import List


class Solution:
    def singleNumber(self, nums: List[int]) -> int:
        ans = 0
        for x in nums:
            ans ^= x          # 成对的元素互相抵消，剩下的就是答案
        return ans
```

### 函数式写法（一行）

```python
from functools import reduce
from operator import xor
from typing import List


class Solution:
    def singleNumber(self, nums: List[int]) -> int:
        return reduce(xor, nums, 0)   # 初值 0 既是单位元，也避免了空列表报错
```

> ⚠️ 细节：`reduce(xor, nums)` 在不给初值时，遇到空列表会抛 `TypeError`。本题保证非空，但**写可复用函数时建议带上初值 0**（更健壮），且 `0 ^ ...` 不影响结果。

### 自测用例（含边界）

```python
if __name__ == "__main__":
    s = Solution()
    assert s.singleNumber([2, 2, 1]) == 1
    assert s.singleNumber([4, 1, 2, 1, 2]) == 4
    assert s.singleNumber([1]) == 1            # 边界：数组只有一个元素
    assert s.singleNumber([0, 1, 1]) == 0      # 边界：答案恰好是 0
    assert s.singleNumber([-1, -1, -2]) == -2  # 边界：负数
    assert s.singleNumber([1, 1, 3, 3, 7]) == 7
    print("all tests passed")
```

> Python 的 `int` 是任意精度、按无限位补码语义做位运算，所以**负数异或完全没问题**，不需要额外处理符号。

---

## 3) 复杂度分析

| 维度 | 值 | 说明 |
|---|---|---|
| 时间 | **O(n)** | 遍历一次，每个元素做一次定长（32/64 位）异或，O(1) |
| 额外空间 | **O(1)** | 只有 `ans` 一个累加变量，不计输入数组与输出 |
| 是否修改输入 | 否 | 纯读取，无副作用 |

补充说明：

- 严格来说，Python 大整数异或的代价与位数相关，但本题值域被限制在 `±3*10^4` 内，位数固定，可视为 O(1)。
- 异或解法**唯一依赖的前提**是"其余元素出现偶数次（本题为恰好两次）"。若出现次数改成 3 次，本解法立即失效——见第 5 节的 137 题。

---

## 4) 其他解法对比

### 解法 A：哈希表计数

```python
from collections import Counter
from typing import List


class Solution:
    def singleNumber(self, nums: List[int]) -> int:
        cnt = Counter(nums)
        for k, v in cnt.items():
            if v == 1:
                return k
```

- 时间 O(n)，空间 **O(n)**。
- 优点是**最通用**：无论其余元素出现几次都能解。面试中建议先说这个，再优化到异或，体现推导过程。

### 解法 B：数学法（集合求和）

```python
class Solution:
    def singleNumber(self, nums: List[int]) -> int:
        return 2 * sum(set(nums)) - sum(nums)
```

- 原理：`2 * (所有不同元素之和) - 数组总和 = 单身元素`。
- 时间 O(n)，空间 **O(n)**（`set` 本身就是额外空间）。
- 只适用于"其余恰好出现两次"；且 C++/Java 中 `2*sum` 可能溢出（需 `long long`），Python 无此问题。

> ❌ **常见错误**：写成 `sum(nums) - sum(set(nums))`，这是"重复元素之和 "，不是答案。必须是 `2 * sum(set(nums)) - sum(nums)`。

### 解法 C：排序后两两比较

```python
class Solution:
    def singleNumber(self, nums: List[int]) -> int:
        nums = sorted(nums)                # 用 sorted 而非 sort，避免修改入参
        i = 0
        while i + 1 < len(nums):
            if nums[i] != nums[i + 1]:
                return nums[i]
            i += 2
        return nums[-1]                    # 单身元素在末尾的情况
```

- 时间 **O(n log n)**，不满足题目要求，但作为对照很好。
- 注意 `nums.sort()` 会**修改调用方传入的列表**（副作用），`sorted()` 则要 O(n) 额外空间。只有 C/C++ 原地快排这类实现，才可能在"不额外开数组"下做到 O(1) 辅助空间（递归栈除外）。

### 解法 D：按位统计（通用版）

逐位统计 1 的个数，对 2 取模，重建答案：

```python
class Solution:
    def singleNumber(self, nums: List[int]) -> int:
        ans = 0
        for i in range(32):
            cnt = sum((x >> i) & 1 for x in nums)   # 第 i 位上 1 的总数
            ans |= (cnt & 1) << i                   # 成对抵消，只剩单身元素的那一位
        # 把 32 位补码解释为有符号数
        return ans - (1 << 32) if ans >= (1 << 31) else ans
```

- 时间 O(32n) = O(n)（常数因子约 32 倍），空间 O(1)。
- **价值在于可推广**：把 `cnt & 1` 改成 `cnt % k`，就能解"其余元素出现 k 次"（如 137 题 k=3）。想清楚这一点，137 题就迎刃而解。

### 汇总对比

| 解法 | 时间 | 额外空间 | 通用性 | 备注 |
|---|---|---|---|---|
| **异或** ⭐ | O(n) | **O(1)** | 仅"偶数次抵消" | 最优解，代码最短 |
| 哈希计数 | O(n) | O(n) | 任意频次 | 直观，适合先讲思路 |
| 数学求和 | O(n) | O(n) | 仅"其余恰两次" | 有溢出/写错风险 |
| 排序两两比 | O(n log n) | O(1)~O(n) | 需按频次调整 | 慢，且易改输入 |
| 按位统计 | O(32n) | O(1) | 余数任意 k | 是 137 的通用模板 |

**易错点小结**：

1. 数学法写成 `sum(nums) - sum(set(nums))`（漏乘 2）。
2. 排序法直接 `nums.sort()` 污染调用方数据。
3. 答案恰好是 `0` 时，别把它当成"没找到"（初始值 `0` 与真实答案 `0` 无法区分，但本题逻辑上无歧义）。
4. 误以为异或对负数无效——实际有效。

---

## 5) 同类题拓展

异或这套思路的核心是：**成对出现的信息可以被"自逆运算"消灭**。沿着这条线能串起一串题：

### ① 137. 只出现一次的数字 II（其余出现 **3** 次）

3 是奇数，异或不再抵消。两条路：

**(a) 按位 mod 3**（即上面解法 D）：`cnt % 3` 得到单身元素该位的值。

**(b) 双掩码状态机**（O(1) 空间，常数更小）：

```python
class Solution:
    def singleNumber(self, nums: List[int]) -> int:
        ones = twos = 0
        for x in nums:
            ones = (ones ^ x) & ~twos   # 出现 1 次的位
            twos = (twos ^ x) & ~ones   # 出现 2 次的位；第 3 次自动清零
        return ones
```

> 直观理解：每个数用 `(twos, ones)` 两个 bit 记录"当前位出现过 0/1/2 次"，第 3 次归零，等价于一个 **mod 3 计数器**。

### ② 260. 只出现一次的数字 III（**两个**单身元素）

全体异或得到 `x = a ^ b`。因为 `a != b`，`x != 0`，取最低位的 1 `lowbit = x & -x`（`a`、`b` 在这一位上必然不同），据此把数组分成两组，各组内部异或即得答案：

```python
class Solution:
    def singleNumber(self, nums: List[int]) -> List[int]:
        x = 0
        for v in nums:
            x ^= v
        lowbit = x & -x          # x 中最低位的 1
        a = b = 0
        for v in nums:
            if v & lowbit:
                a ^= v
            else:
                b ^= v
        return [a, b]
```

> 这是"分组异或"的经典技巧，也是 136 题最重要的变体。

### ③ 268. 缺失数字（0..n 中缺一个）

把"下标"和"元素"一起异或，缺的那个就剩下来了：

```python
class Solution:
    def missingNumber(self, nums: List[int]) -> int:
        ans = len(nums)                     # 补上最后的 n
        for i, v in enumerate(nums):
            ans ^= i ^ v
        return ans
```

### ④ 389. 找不同（两个字符串，t 比 s 多一个字符）

字符异或，`ord` 层面等价于整数异或：

```python
from functools import reduce
from operator import xor

class Solution:
    def findTheDifference(self, s: str, t: str) -> str:
        return chr(reduce(xor, map(ord, s + t), 0))
```

### ⑤ 540. 有序数组中的单一元素

数组**已排序**，此时**二分**更优（O(log n)）：用"配对下标奇偶性"判断单身元素在左半还是右半。

```python
class Solution:
    def singleNonDuplicate(self, nums: List[int]) -> int:
        lo, hi = 0, len(nums) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if mid % 2 == 1:
                mid -= 1                # 保证 mid 为偶数，配对为 (mid, mid+1)
            if nums[mid] == nums[mid + 1]:
                lo = mid + 2            # 左侧完全成对
            else:
                hi = mid
        return nums[lo]
```

### ⑥ 645. 错误的集合（一个数重复、一个数缺失）

可用异或（思路同 260，再根据数值关系区分哪个是重复、哪个是缺失），也可用"下标和之差 + 平方和之差"的数学法。

### ⑦ 287. 寻找重复数（反例，别硬套异或）

数组是 1..n 中有一个数重复，但**没有"成对抵消"的结构**，异或不适用。正解是把 `i → nums[i]` 看作链表指针，用 **Floyd 快慢指针**找环入口，O(n) 时间 O(1) 空间。

### ⑧ 面试常见变体

| 变体 | 思路 |
|---|---|
| 其余两次，**两个**单身 | 分组异或（同 260） |
| 其余出现 k 次，一个单身 | 按位 mod k；或状态机（k 小） |
| 其余两次，一个单身，但**数组只读** | 异或（天然不修改输入，正合要求） |
| 其余两次，一个单身，元素范围极大 | 异或不受值域影响，仍然 O(1) 空间 |
| 要求返回**所有**只出现一次的元素 | 通用做法：哈希计数；若"其余恰两次且单身只有 2 个"则用 260 |

---

## 一句话总结

> **异或是"自带逆元"的运算：`a ^ a = 0`。把整个数组异或起来，成对的元素自动两两消灭，剩下的就是那个落单的。** 它正好命中本题的两个硬指标——一次遍历（O(n)）+ 一个变量（O(1)），而"按位 mod k"和"分组异或"则是这把钥匙打开 137、260、268 等一串题目的通用形态。