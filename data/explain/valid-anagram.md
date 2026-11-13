# 力扣 242. 有效的字母异位词 题解

## 1. 思路推导

**题目本质**：判断两个字符串是否由完全相同的字符集合构成，且每个字符的出现次数完全一致。

**核心观察**：
- 异位词不要求字符顺序一致，只要求字符“多集”（multiset）相等
- 因此问题转化为：**比较两个字符串的字符频率统计是否相同**

**边界条件**：
- 长度不同 → 直接返回 False（最快速的剪枝）
- 空字符串 → 互为异位词（True）
- 包含 Unicode 字符？题目限定小写字母，但解法可扩展

---

## 2. 推荐解法与代码（Python）

### 解法一：哈希表计数（推荐）

```python
class Solution:
    def isAnagram(self, s: str, t: str) -> bool:
        # 长度不同直接排除
        if len(s) != len(t):
            return False
        
        # 使用字典统计字符频率
        count = {}
        for ch in s:
            count[ch] = count.get(ch, 0) + 1
        
        # 遍历 t，逐个抵消
        for ch in t:
            if ch not in count:
                return False
            count[ch] -= 1
            if count[ch] < 0:  # 出现次数超过 s 中的
                return False
        
        return True
```

**更简洁的写法**（利用 Counter）：

```python
from collections import Counter

class Solution:
    def isAnagram(self, s: str, t: str) -> bool:
        return Counter(s) == Counter(t)
```

---

## 3. 复杂度分析

| 方法 | 时间复杂度 | 空间复杂度 |
|------|-----------|-----------|
| 哈希表计数 | O(n) | O(1)（字符集固定为26时） |
| 排序比较 | O(n log n) | O(1)（若原地排序） |

**详细说明**：
- 时间：遍历两个字符串各一次 → O(n)
- 空间：哈希表最多存储 26 个键（小写字母）→ O(1)；若字符集不固定则为 O(k)，k 为不同字符数

---

## 4. 其他解法对比

### 解法二：排序比较

```python
class Solution:
    def isAnagram(self, s: str, t: str) -> bool:
        return sorted(s) == sorted(t)
```

**对比**：
- 优点：代码极简，无需额外空间
- 缺点：O(n log n) 时间，大数据量下性能差

### 解法三：数组计数（针对小写字母）

```python
class Solution:
    def isAnagram(self, s: str, t: str) -> bool:
        if len(s) != len(t):
            return False
        counts = [0] * 26
        for ch in s:
            counts[ord(ch) - ord('a')] += 1
        for ch in t:
            counts[ord(ch) - ord('a')] -= 1
        return all(c == 0 for c in counts)
```

**对比**：
- 优点：数组访问比哈希表快，空间固定 O(1)
- 缺点：仅适用于小写字母，扩展性差

### 解法四：异或运算（不可行）

**注意**：异或只能判断字符集合是否相同，无法判断数量。例如 `"aa"` 和 `"ab"` 异或结果相同但非异位词。**此方法错误，不推荐**。

---

## 5. 同类题拓展

| 题目 | 关联点 |
|------|--------|
| **49. 字母异位词分组** | 将异位词分组，可用排序后字符串作为 key |
| **438. 找到字符串中所有字母异位词** | 滑动窗口 + 频率统计 |
| **567. 字符串的排列** | 判断 s2 是否包含 s1 的排列（滑动窗口） |
| **383. 赎金信** | 判断 magazine 能否构成 ransomNote（频率包含关系） |
| **1002. 查找共用字符** | 多字符串频率统计取交集 |

**进阶思考**：
- 如果输入包含 Unicode 字符，哈希表方案依然有效，数组方案失效
- 如果要求内存极低，可考虑先排序再比较（但时间上升）
- 如果字符串超长，可考虑并行统计（分治 + 合并）

---

**总结**：哈希表计数是最平衡的解法，兼顾时间、空间、可扩展性。面试时建议先写哈希表方案，再补充排序方案作为对比。