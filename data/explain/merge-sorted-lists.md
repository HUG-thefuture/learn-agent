## 21. 合并两个有序链表 题解

### 1. 思路推导

**核心思想**：归并排序的合并阶段（Merge Step）。

**关键观察**：
- 两个链表已有序，每次只需比较两个链表的当前头结点，取较小者接入结果链表
- 链表天然适合指针操作，无需额外空间（相比数组归并）
- 需要维护一个**哨兵节点（dummy）**避免处理头结点为空的特殊情况

**边界条件**：
- 两个链表都为空 → 返回空
- 其中一个为空 → 直接返回另一个
- 节点值相等时 → 取哪个都可以（稳定性要求时取第一个）

---

### 2. 推荐解法与代码（Python）

**迭代法（推荐）**：

```python
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def mergeTwoLists(list1: ListNode, list2: ListNode) -> ListNode:
    # 哨兵节点，避免处理头结点为空的边界
    dummy = ListNode(0)
    current = dummy
    
    # 双指针遍历，直到某个链表耗尽
    while list1 and list2:
        if list1.val <= list2.val:
            current.next = list1
            list1 = list1.next
        else:
            current.next = list2
            list2 = list2.next
        current = current.next
    
    # 直接接上剩余部分（链表天然有序，无需继续比较）
    current.next = list1 if list1 else list2
    
    return dummy.next  # 跳过哨兵节点
```

**递归法（简洁但需注意栈深度）**：

```python
def mergeTwoLists_recursive(list1: ListNode, list2: ListNode) -> ListNode:
    # 递归终止条件
    if not list1:
        return list2
    if not list2:
        return list1
    
    # 选择较小节点作为头，递归合并剩余部分
    if list1.val <= list2.val:
        list1.next = mergeTwoLists_recursive(list1.next, list2)
        return list1
    else:
        list2.next = mergeTwoLists_recursive(list1, list2.next)
        return list2
```

---

### 3. 复杂度分析

| 方法 | 时间复杂度 | 空间复杂度 | 说明 |
|------|-----------|-----------|------|
| 迭代法 | O(m+n) | O(1) | 只遍历每个节点一次，仅用常数额外空间 |
| 递归法 | O(m+n) | O(m+n) | 递归调用栈深度为合并后链表长度 |

**详细分析**：
- **时间**：每次迭代/递归比较两个节点，总比较次数 ≤ m+n，每个节点最多被处理一次
- **空间**：
  - 迭代法：仅使用 `dummy` 和 `current` 两个指针，常数空间
  - 递归法：最坏情况（如一个链表全小于另一个）递归深度为 m+n，栈空间 O(m+n)

---

### 4. 其他解法对比

**方法对比**：

| 方法 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 迭代法 | 空间O(1)，无栈溢出风险 | 代码稍长 | **生产环境首选** |
| 递归法 | 代码简洁，逻辑清晰 | 空间O(n)，链表长时可能栈溢出 | 面试展示思路，链表较短时 |
| 原地修改（不建新节点） | 空间最优 | 会破坏原链表结构 | 允许修改输入时 |

**关键差异**：
- 迭代法通过 `current.next` 逐步构建结果，不创建新节点（只创建哨兵）
- 递归法通过函数调用栈隐式保存状态，代码更声明式
- 两者都不需要额外数组/链表存储，优于"先转数组再排序"的方案

---

### 5. 同类题拓展

**直接相关**：
- **23. 合并K个升序链表**：本题的进阶版，可用优先队列（堆）或分治法
- **88. 合并两个有序数组**：数组版本，需要从后往前填充避免覆盖

**思路延伸**：
- **148. 排序链表**：链表归并排序的核心就是本题的合并操作
- **2. 两数相加**：链表遍历+进位处理，与本题的指针移动模式类似
- **21. 合并两个有序链表** 的变体：合并后去重、合并后逆序等

**进阶技巧**：
- 合并K个链表时，用最小堆维护K个头结点，每次弹出最小者，时间复杂度 O(N log K)
- 分治法合并K个链表：两两合并，时间复杂度同样 O(N log K)，但空间更优

---

**总结**：本题是链表操作的基础题，核心是**双指针+哨兵节点**技巧。掌握迭代法后，可以轻松扩展到合并K个链表、链表排序等更复杂问题。面试时建议先写迭代法，再补充递归法展示思维灵活性。