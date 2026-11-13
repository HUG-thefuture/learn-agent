# 217. 存在重复元素 题解

## 1. 思路推导

**题目本质**：判断数组中是否有任意元素出现至少两次。

**核心思考路径**：
- 暴力法：双重循环比较所有元素对 → O(n²)，太慢
- 排序法：排序后相邻元素比较 → O(n log n)
- **哈希表法**：利用集合去重特性，一次遍历 → O(n)

**关键洞察**：我们不需要知道重复元素是谁，只需要知道"是否存在"。哈希表能在 O(1) 时间内完成"是否见过这个元素"的查询，这是最优解的基础。

---

## 2. 推荐解法与代码（Python）

### 解法一：集合去重（最简洁）
```python
def containsDuplicate(nums):
    return len(nums) != len(set(nums))
```

### 解法二：哈希集合遍历（更通用，便于扩展）
```python
def containsDuplicate(nums):
    seen = set()
    for num in nums:
        if num in seen:
            return True
        seen.add(num)
    return False
```

**推荐解法二**，原因：
- 提前终止：遇到重复立即返回，无需处理完整个数组
- 可扩展性：如果需要返回重复元素或索引，此结构容易修改
- 内存可控：最坏情况才存储所有元素

---

## 3. 复杂度分析

| 方法 | 时间复杂度 | 空间复杂度 |
|------|-----------|-----------|
| 集合去重 | O(n) | O(n) |
| 哈希遍历 | O(n)（平均） | O(n) |

**详细说明**：
- 时间：每个元素插入/查询哈希表平均 O(1)，总 O(n)
- 空间：最坏情况所有元素不重复，需要存储 n 个元素
- 注意：Python 的 `set` 底层是哈希表，最坏理论 O(n) 但实际几乎不会发生

---

## 4. 其他解法对比

| 解法 | 时间 | 空间 | 优点 | 缺点 |
|------|------|------|------|------|
| 暴力双循环 | O(n²) | O(1) | 无需额外空间 | 太慢，不实用 |
| 排序后比较 | O(n log n) | O(1)（原地排序） | 空间效率高 | 修改原数组（除非拷贝） |
| 哈希集合 | O(n) | O(n) | 时间最优，不修改原数组 | 需要额外空间 |
| 位图法（值域受限时） | O(n) | O(值域) | 空间固定 | 仅适用于非负小整数 |

**选择建议**：
- 追求时间 → 哈希集合
- 空间敏感且允许排序 → 排序法
- 数据量小 → 暴力法也可接受

---

## 5. 同类题拓展

### 变体一：219. 存在重复元素 II
**要求**：重复元素索引差 ≤ k
**解法**：哈希表存储 `{值: 最近索引}`，遍历时检查索引差

```python
def containsNearbyDuplicate(nums, k):
    pos = {}
    for i, num in enumerate(nums):
        if num in pos and i - pos[num] <= k:
            return True
        pos[num] = i
    return False
```

### 变体二：220. 存在重复元素 III
**要求**：存在 |nums[i] - nums[j]| ≤ t 且索引差 ≤ k
**解法**：桶排序思想，每个桶大小 t+1

```python
def containsNearbyAlmostDuplicate(nums, k, t):
    if t < 0: return False
    buckets = {}
    for i, num in enumerate(nums):
        bucket_id = num // (t + 1)
        if bucket_id in buckets:
            return True
        if bucket_id - 1 in buckets and num - buckets[bucket_id - 1] <= t:
            return True
        if bucket_id + 1 in buckets and buckets[bucket_id + 1] - num <= t:
            return True
        buckets[bucket_id] = num
        if i >= k:
            del buckets[nums[i - k] // (t + 1)]
    return False
```

### 变体三：287. 寻找重复数
**要求**：数组值在 [1, n] 内，找唯一重复数（不修改数组）
**解法**：Floyd 判圈算法（快慢指针），时间 O(n)，空间 O(1)

---

## 总结要点

1. **哈希表是"存在性"问题的首选**，空间换时间
2. 注意 Python 中 `set` 的底层实现，插入和查询都是 O(1)
3. 变体题核心是**在哈希表基础上增加约束条件**（索引差、值差）
4. 面试时先问清楚：数据范围、是否允许修改数组、空间限制

掌握这道题，你就掌握了哈希表解决存在性问题的基本范式，后续变体都是在此基础上的扩展。