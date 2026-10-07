# -*- coding: utf-8 -*-
"""题库完整性回归：全部内置题目的参考解答必须通过判题器。

防止题库数据/判题器改动导致的隐性损坏。运行: python -m tests.test_bank_reference
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modules.leetcode import PROBLEMS, check_solution, _fname  # noqa: E402

REFERENCES = {
    "two-sum": "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i\n",
    "valid-parentheses": "def is_valid(s):\n    pairs = {')': '(', ']': '[', '}': '{'}\n    stack = []\n    for ch in s:\n        if ch in '([{':\n            stack.append(ch)\n        elif not stack or stack.pop() != pairs.get(ch):\n            return False\n    return not stack\n",
    "binary-search": "def search(nums, target):\n    lo, hi = 0, len(nums) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if nums[mid] == target:\n            return mid\n        if nums[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1\n",
    "climbing-stairs": "def climb_stairs(n):\n    a, b = 1, 1\n    for _ in range(n - 1):\n        a, b = b, a + b\n    return b\n",
    "max-subarray": "def max_sub_array(nums):\n    best = cur = nums[0]\n    for x in nums[1:]:\n        cur = max(cur + x, x)\n        best = max(best, cur)\n    return best\n",
    "merge-sorted-lists": "def merge_two_lists(l1, l2):\n    dummy = ListNode(0)\n    cur = dummy\n    while l1 and l2:\n        if l1.val <= l2.val:\n            cur.next, l1 = l1, l1.next\n        else:\n            cur.next, l2 = l2, l2.next\n        cur = cur.next\n    cur.next = l1 or l2\n    return dummy.next\n",
    "valid-anagram": "def is_anagram(s, t):\n    from collections import Counter\n    return Counter(s) == Counter(t)\n",
    "contains-duplicate": "def contains_duplicate(nums):\n    return len(set(nums)) < len(nums)\n",
    "reverse-linked-list": "def reverse_list(head):\n    prev = None\n    while head:\n        head.next, prev, head = prev, head, head.next\n    return prev\n",
    "lru-cache": ("from collections import OrderedDict\n"
                  "class LRUCache:\n"
                  "    def __init__(self, capacity: int):\n"
                  "        self.cap = capacity\n"
                  "        self.od = OrderedDict()\n"
                  "    def get(self, key: int) -> int:\n"
                  "        if key not in self.od:\n"
                  "            return -1\n"
                  "        self.od.move_to_end(key)\n"
                  "        return self.od[key]\n"
                  "    def put(self, key: int, value: int) -> None:\n"
                  "        if key in self.od:\n"
                  "            self.od.move_to_end(key)\n"
                  "        self.od[key] = value\n"
                  "        if len(self.od) > self.cap:\n"
                  "            self.od.popitem(last=False)\n"),
    "longest-substring": "def length_of_longest_substring(s):\n    last, start, best = {}, 0, 0\n    for i, ch in enumerate(s):\n        if ch in last and last[ch] >= start:\n            start = last[ch] + 1\n        last[ch] = i\n        best = max(best, i - start + 1)\n    return best\n",
    "coin-change": "def coin_change(coins, amount):\n    INF = float('inf')\n    dp = [0] + [INF] * amount\n    for i in range(1, amount + 1):\n        for c in coins:\n            if c <= i and dp[i - c] + 1 < dp[i]:\n                dp[i] = dp[i - c] + 1\n    return dp[amount] if dp[amount] != INF else -1\n",
    "plus-one": "def plus_one(digits):\n    res = digits[:]\n    for i in range(len(res) - 1, -1, -1):\n        if res[i] < 9:\n            res[i] += 1\n            return res\n        res[i] = 0\n    return [1] + res\n",
    "roman-to-integer": "def roman_to_int(s):\n    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}\n    total = 0\n    for i, ch in enumerate(s):\n        v = vals[ch]\n        if i + 1 < len(s) and vals[s[i + 1]] > v:\n            total -= v\n        else:\n            total += v\n    return total\n",
    "palindrome-number": "def is_palindrome(x):\n    s = str(x)\n    return s == s[::-1]\n",
    "single-number": "def single_number(nums):\n    r = 0\n    for n in nums:\n        r ^= n\n    return r\n",
    "majority-element": "def majority_element(nums):\n    count = cand = 0\n    for n in nums:\n        if count == 0:\n            cand = n\n        count += 1 if n == cand else -1\n    return cand\n",
    "move-zeroes": "def move_zeroes(nums):\n    w = 0\n    for r in range(len(nums)):\n        if nums[r] != 0:\n            nums[w], nums[r] = nums[r], nums[w]\n            w += 1\n    return\n",
    "search-insert-position": "def search_insert(nums, target):\n    lo, hi = 0, len(nums)\n    while lo < hi:\n        mid = (lo + hi) // 2\n        if nums[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid\n    return lo\n",
    "best-time-buy-sell-stock": "def max_profit(prices):\n    best, low = 0, None\n    for p in prices:\n        if low is None or p < low:\n            low = p\n        elif p - low > best:\n            best = p - low\n    return best\n",
}


class TestBankReference(unittest.TestCase):
    def test_all_have_reference(self):
        for p in PROBLEMS:
            self.assertIn(p["slug"], REFERENCES, f"{p['slug']} 缺参考解答")

    def test_all_reference_pass_judge(self):
        results = {}
        for p in PROBLEMS:
            r = check_solution(p, REFERENCES[p["slug"]])
            results[p["slug"]] = r
            with self.subTest(slug=p["slug"]):
                self.assertEqual(r["static"], [], f"{p['slug']} 静态问题: {r['static']}")
                self.assertTrue(r["passed"], f"{p['slug']} 判题失败: "
                                + json.dumps(r["tests"], ensure_ascii=False, default=str)[:500])
        leak_checked = {s: r["leak"] for s, r in results.items() if r.get("leak")}
        for slug, leak in leak_checked.items():
            self.assertFalse(leak["leaky"], f"{slug} 泄漏: {leak['detail']}")
        self.assertEqual(len(results), len(PROBLEMS))
        print(f"\n题库回归: {len(results)} 题全部通过; 泄漏抽检 {len(leak_checked)} 题")


if __name__ == "__main__":
    unittest.main(verbosity=2)
