# -*- coding: utf-8 -*-
"""core/llm.py 长文续写去重回归测试（独立脚本，不发真实请求）。

运行：python tests/llm_overlap_check.py   （退出码 0 = 全部通过）

守护点：
1. _overlap_trim：续写开头与已有内容尾部重叠时裁掉重叠，无重叠原样返回；
2. _cloud_entry_chat：显式 max_tokens；finish_reason=length 时自动续写最多 3 轮，
   拼接时经 _overlap_trim 去重；finish_reason=stop 不触发续写。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import py_compile
ROOT = Path(__file__).resolve().parents[1]
for f in ("core/llm.py", "webapp/app.py"):
    py_compile.compile(str(ROOT / f), doraise=True)
print("[OK] py_compile: core/llm.py, webapp/app.py")

from core.llm import _overlap_trim, LLMRouter

# ---- _overlap_trim 纯函数 ----
cases = [
    # (base, extra, 期望)
    ("……内容AB", "AB后续内容", "后续内容"),          # 续写开头与尾部重叠 → 裁掉
    ("……内容AB", "全新内容", "全新内容"),            # 无重叠 → 原样
    ("", "任意", "任意"),                            # base 为空
    ("任意", "", ""),                                # extra 为空
    ("短", "开头重叠", "开头重叠"),              # 无重叠：base 过短也不误裁
    ("短", "短开头重叠", "开头重叠"),            # base 过短但确有 1 字重叠 → 裁掉
    ("……最后一段。", "最后一段。请继续", "请继续"),   # 句级重复
]
for base, extra, want in cases:
    got = _overlap_trim(base, extra)
    assert got == want, f"_overlap_trim({base!r}, {extra!r}) = {got!r}, want {want!r}"
print(f"[OK] _overlap_trim: {len(cases)} 个用例通过")

# ---- _cloud_entry_chat 续写拼接（mock requests，不真正发请求） ----
router = LLMRouter()
entry = {"model": "m", "base_url": "http://fake", "api_key": "k"}

class FakeResp:
    def __init__(self, data):
        self._d = data
    def raise_for_status(self):
        pass
    def json(self):
        return self._d

# 3 轮响应：第 1、2 轮 length 截断，续写开头与已拼接内容尾部重叠（AB、CD）
SEQ = [
    {"choices": [{"message": {"content": "第一部分内容AB"}, "finish_reason": "length"}]},
    {"choices": [{"message": {"content": "AB第二部分CD"}, "finish_reason": "length"}]},
    {"choices": [{"message": {"content": "CD结尾"}, "finish_reason": "stop"}]},
]

call_no = [0]
def fake_post(url, headers=None, json=None, timeout=None):
    assert json.get("max_tokens") == 8192, "缺显式 max_tokens"
    msgs = json.get("messages") or []
    assert len(msgs) in (1, 3, 5), f"消息数异常: {len(msgs)}"
    if len(msgs) > 1:
        assert msgs[-2]["role"] == "assistant" and msgs[-1]["role"] == "user"
    i = min(call_no[0], len(SEQ) - 1)
    call_no[0] += 1
    return FakeResp(SEQ[i])

import core.llm as llm_mod
llm_mod.requests.post = fake_post
out = router._cloud_entry_chat(entry, [{"role": "user", "content": "写长文"}])
assert call_no[0] == 3, f"应调用 3 次，实际 {call_no[0]}"
expect = "第一部分内容AB第二部分CD结尾"
assert out == expect, f"拼接结果 {out!r} != {expect!r}"
print(f"[OK] _cloud_entry_chat: 3 轮续写拼接正确，无重复（{len(out)} 字）")

# finish_reason=stop 时不再续写
call_no[0] = 0
SEQ2 = [{"choices": [{"message": {"content": "一次到位"}, "finish_reason": "stop"}]}]
def fake_post2(url, headers=None, json=None, timeout=None):
    call_no[0] += 1
    return FakeResp(SEQ2[0])
llm_mod.requests.post = fake_post2
out2 = router._cloud_entry_chat(entry, [{"role": "user", "content": "短文"}])
assert call_no[0] == 1 and out2 == "一次到位", (call_no[0], out2)
print("[OK] _cloud_entry_chat: 非 length 截断不触发续写")

print("\nRESULT: PASS")
