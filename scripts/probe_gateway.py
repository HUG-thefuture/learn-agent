# -*- coding: utf-8 -*-
"""DSH 网关通道体检脚本：下次模型更新时跑这个，用实测数据决定接入谁。

    python scripts/probe_gateway.py               # 探测当前白名单内的通道
    python scripts/probe_gateway.py --all         # 探测网关里所有通道（含未接入的）
    python scripts/probe_gateway.py --update      # 只打印建议（不改文件）

判定逻辑（与 core/llm.py 一致）：
- HTTP 2xx 且 content 非空           → 可用
- HTTP 2xx 但 content 空              → 推理模型烧光 max_tokens，加大重试一次
- 401/402/403                        → 未授权/未订阅，不接入
- 404/410                            → 模型已下线
- 429                                → 限额（可用，只是节奏问题）
- 5xx                                → 服务端故障（502 = 通道未打通）

为什么不能只跑一次短请求就判死：推理模型会先把 token 花在 thinking 上，
max_tokens 太小会导致 content 为空，被误判成「不可用」。这里失败会用
更大的 max_tokens 重试一次再下结论。
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from core.llm import LLMRouter  # noqa: E402

PROBE_MSG = [{"role": "user", "content": "只回复两个字：可用"}]


def _cred():
    return LLMRouter._dsh_gateway_credential()


def _base():
    return f"http://127.0.0.1:{LLMRouter._dsh_gateway_port()}/v1"


def list_all_models():
    r = requests.get(_base() + "/models",
                     headers={"Authorization": "Bearer " + _cred()}, timeout=15)
    r.raise_for_status()
    return [m["id"] for m in (r.json().get("data") or []) if m.get("id")]


def probe_one(model_id: str, max_tokens: int = 64) -> dict:
    """探测单个模型，返回 {status, http, content, seconds, note}。"""
    t0 = time.time()
    try:
        r = requests.post(
            _base() + "/chat/completions",
            headers={"Authorization": "Bearer " + _cred()},
            json={"model": model_id, "messages": PROBE_MSG, "max_tokens": max_tokens},
            timeout=120)
    except Exception as e:
        return {"status": "error", "http": None, "content": "",
                "seconds": round(time.time() - t0, 1),
                "note": f"{type(e).__name__}: {e}"}
    el = round(time.time() - t0, 1)
    if not r.ok:
        code = r.status_code
        body = r.text or ""
        low = body.lower()
        # 先看响应体再按状态码归类：网关会把上游的「额度用尽」包成 5xx/200，
        # 只看状态码会把「今天额度用完，明天还能用」误判成「通道坏了」。
        if (code == 429 or "额度已用尽" in body or "quota" in low
                or "rate limit" in low or "insufficient" in low):
            status = "quota"        # 能用，只是当前限额/额度窗口
        elif code in (401, 402, 403) or "not subscribed" in low or "forbidden" in low:
            status = "noauth"       # 无授权/未订阅
        elif code in (404, 410) or "not found" in low or "no longer" in low:
            status = "gone"         # 模型已下线
        else:
            status = "broken"       # 5xx 等
        return {"status": status, "http": code, "content": "",
                "seconds": el, "note": body[:120].replace("\n", " ")}
    try:
        msg = r.json()["choices"][0]["message"]
    except Exception:
        return {"status": "badjson", "http": r.status_code, "content": "",
                "seconds": el, "note": "响应结构异常"}
    content = (msg.get("content") or "").strip()
    reasoning = (msg.get("reasoning_content") or msg.get("thinking") or "")
    if not content and max_tokens < 512:
        # 可能只是被思考链吃光了预算，加大重试
        return probe_one(model_id, max_tokens=2048)
    return {"status": "ok" if content else "empty",
            "http": r.status_code, "content": content[:40],
            "seconds": el,
            "note": f"reasoning {len(reasoning)} 字" if reasoning else ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="探测网关里所有模型")
    ap.add_argument("--only", default="", help="只探测指定前缀，逗号分隔")
    ap.add_argument("--update", action="store_true", help="额外打印接入建议")
    a = ap.parse_args()

    if not _cred():
        print("找不到网关凭据（~/.dsh/openai-gateway/api-key 或 "
              "DSH_OPENAI_GATEWAY_API_KEY）")
        return 1
    try:
        all_ids = list_all_models()
    except Exception as e:
        print(f"连不上网关 {_base()}: {e}")
        return 1

    cls = LLMRouter
    if a.all:
        targets = all_ids
    elif a.only:
        pfx = tuple(p.strip() for p in a.only.split(",") if p.strip())
        targets = [m for m in all_ids if m.startswith(pfx)]
    else:
        targets = [m for m in all_ids if cls._is_gateway_model(m)]

    print(f"网关共 {len(all_ids)} 个模型，本次探测 {len(targets)} 个")
    print(f"网关地址: {_base()}\n")

    results = {}
    for i, mid in enumerate(targets, 1):
        res = probe_one(mid)
        results[mid] = res
        mark = {"ok": "✓", "quota": "限", "empty": "空", "gone": "✗",
                "noauth": "✗", "broken": "✗", "error": "!", "badjson": "!"}[res["status"]]
        extra = f"  {res['note']}" if res["note"] else ""
        print(f"  [{i:>3}/{len(targets)}] {mark} {mid:<48} "
              f"{res['status']:<7} {res['seconds']:>6.1f}s{extra}")

    # ---- 汇总 ----
    print("\n" + "=" * 72)
    by_status = defaultdict(list)
    for mid, res in results.items():
        by_status[res["status"]].append(mid)
    for status in ("ok", "quota", "empty", "gone", "noauth", "broken", "error", "badjson"):
        items = by_status.get(status) or []
        if items:
            print(f"{status:<8} {len(items):>3} 个")

    print("\n按通道汇总（可用数 / 总数）：")
    per_prefix = defaultdict(lambda: [0, 0])
    for mid, res in results.items():
        pfx = mid.split("/")[0]
        per_prefix[pfx][1] += 1
        if res["status"] in ("ok", "quota"):
            per_prefix[pfx][0] += 1
    for pfx, (ok, total) in sorted(per_prefix.items(), key=lambda kv: -kv[1][0]):
        flag = "✓" if ok else "✗"
        print(f"  {flag} {pfx:<22} {ok:>3}/{total}")

    if a.update:
        print("\n接入建议（把这行贴到 core/llm.py::GATEWAY_PREFIXES）：")
        good = [p for p, (ok, _t) in per_prefix.items() if ok > 0]
        print(f"  GATEWAY_PREFIXES = {tuple(p + '/' for p in good)}")
        bad = [p for p, (ok, _t) in per_prefix.items() if ok == 0]
        if bad:
            print(f"  # 实测不可用，不要接入: {', '.join(bad)}")

    out = ROOT / "data" / "gateway_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n明细已保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
