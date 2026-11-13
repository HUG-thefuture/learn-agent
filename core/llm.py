# -*- coding: utf-8 -*-
"""LLM 路由层。

- 本地优先：Ollama 上的 qwen3-8b-16k（快）/ qwen3:14b（深）
- 云端模型池：多家服务商（Nvidia/商汤/AMD）多模型，按性能分 strong/fast 两档
- 难度自动选档：deep（规划/审查/难题）→ strong 档；非 deep（聊天/简单）→ fast 档；
  显式 tier='strong'|'fast' 可直接指定档位（如教程生成默认 fast、实战项目 strong）
- 云端优先开关：cloud_first=True 时先走云端，本地作兜底
- 自动降级：逐个模型尝试，失败换下一个；记录连续失败供工作流升级
- 配额冷却：429/限额类失败视为「节奏问题、模型未坏」，按条目 quota_cooldown
  （商汤类 5h 窗口配 18000s）挂起该条目、期间跳过但仍可尝试其它通道；
  普通 5xx/网络错误只做短冷却（60s）。冷却条目全部忙时仍会兜底再试。
- 进度反馈：线程级 progress 回调，通道尝试/跳过/完成都会上报阶段与耗时估计
  （估计来自各模型近期成功调用的 EMA）。
- 调用顺序（可用性优先、兼顾性能）：每次调用前把候选通道按「历史可用率 + 新近
  成功」重排——有成功记录的排在前面（可用率高、刚成功过的更靠前），从未调用过的
  保持配置/服务商原始顺序，只失败过从未成功过的沉到队尾。画像持久化在
  data/memory/llm_channels.json（7 天过期），重启后不必从零试错。
"""
import atexit
import json
import os
import re
import threading
import time
from pathlib import Path

import requests

from core.config import cfg

# 失败类别：模型坏 → 短冷却；配额限速 → 长冷却（可被条目 quota_cooldown 覆盖）
DEFAULT_ERROR_COOLDOWN = 60
DEFAULT_QUOTA_COOLDOWN = 900

# 同通道内强档模型排序关键词：命中越靠前越优先（旗舰/高版本号在前）
_STRONG_RANK_HINTS = (
    ("opus", 100), ("gpt-6.1", 98), ("gpt-6", 96), ("claude-sonnet-5", 94),
    ("sonnet", 90), ("grok", 88), ("ultra", 86), ("kimi-k3", 84),
    ("deepseek-v4-pro", 82), ("glm-5.3", 80), ("qwen3.8-max", 78),
    ("qmodel_38max", 78), ("qmodel_latest", 76), ("ultimate", 74),
    ("performance", 72), ("hy4", 70), ("kimi-k2.8", 68), ("kimi-k2.7", 66),
    ("kimi-k2.6", 64), ("glm-5.2", 62), ("hy3", 60), ("default-model", 40),
)


def _strong_rank(model_id: str) -> int:
    """通道内强档模型优先级分：命中旗舰关键词越高越靠前（同分按名字稳定排序）。"""
    low = (model_id or "").lower()
    best = 0
    for key, score in _STRONG_RANK_HINTS:
        if key in low and score > best:
            best = score
    return best

# 通道可用性画像的持久化文件（重启后仍能"可用性优先"排序，而不是从零开始试错）
HEALTH_FILE = "llm_channels.json"
HEALTH_TTL = 7 * 86400      # 超过 7 天没动静的画像记录直接丢弃（服务商可能已变）
HEALTH_SAVE_MIN_INTERVAL = 3.0  # 画像落盘节流（秒），避免高频写盘


class LLMError(RuntimeError):
    pass


def external_enabled() -> bool:
    """外部/云端增强是否可用（兼容新旧配置段）。

    老配置 external_model.enabled；新配置 cloud.enabled（云端模型池）。
    统一入口，避免散落的 cfg()["external_model"] 在新配置下 KeyError。
    """
    c = cfg()
    return bool((c.get("external_model") or {}).get("enabled")
                or (c.get("cloud") or {}).get("enabled"))


def tutorial_tier(default="fast") -> str:
    """教程/讲解类长文生成的档位：config cloud.tutorial_tier（默认 fast，快够用）。
    capstone 实战项目与工作流规划/审查不受影响，仍走 strong 档。"""
    try:
        t = (cfg().get("cloud") or {}).get("tutorial_tier", default)
    except Exception:
        t = default
    return t if t in ("fast", "strong") else default


class LLMRouter:
    def __init__(self):
        c = cfg()
        self.local = c["local_model"]
        self.cloud = c.get("cloud", {}) or {}
        self._tl = threading.local()  # 线程级 cloud_first / progress 覆盖
        self.fail_streak = 0  # 连续失败计数，供工作流决定是否升级
        self._muted = threading.Lock()
        self._muted_until = {}  # label -> epoch seconds（配额/故障冷却表）
        self._lat = {}          # label -> {"ema": sec, "n": int}（成功耗时估计）
        self._health = {}       # label -> {"ok","fail","last_ok","last_fail"}（可用性画像）
        self._health_saved_at = 0.0
        self._load_health()

    # ---------- 通道可用性画像持久化 ----------
    @staticmethod
    def _health_path() -> Path:
        """画像文件路径：data/memory/llm_channels.json（与其它记忆文件同目录）。"""
        from core.config import data_dir
        return data_dir() / "memory" / HEALTH_FILE

    def _load_health(self):
        """启动时载入历史画像；丢弃过期记录，避免旧结论永久压制某通道。"""
        try:
            p = self._health_path()
            if not p.exists():
                return
            raw = json.loads(p.read_text(encoding="utf-8")) or {}
            now = time.time()
            with self._muted:
                for label, h in raw.items():
                    if label == "__latency__" or not isinstance(h, dict):
                        continue  # 保留键与脏数据跳过
                    last = max(float(h.get("last_ok") or 0),
                               float(h.get("last_fail") or 0))
                    if last and now - last > HEALTH_TTL:
                        continue  # 过期画像：当作「未知」重新实测
                    self._health[label] = {
                        "ok": int(h.get("ok") or 0),
                        "fail": int(h.get("fail") or 0),
                        "last_ok": float(h.get("last_ok") or 0.0),
                        "last_fail": float(h.get("last_fail") or 0.0),
                    }
                lat = raw.get("__latency__") or {}
                if isinstance(lat, dict):
                    for label, rec in lat.items():
                        if isinstance(rec, dict) and rec.get("ema"):
                            self._lat[label] = {"ema": float(rec["ema"]),
                                                "n": int(rec.get("n") or 1)}
        except Exception:
            pass  # 画像损坏不影响主流程

    def _save_health(self, force: bool = False):
        """节流落盘画像（成功/失败与耗时估计）。写盘失败静默忽略。

        节流只影响「中间态」：进程退出时由 flush_health() 强制落盘，
        保证最后一次调用结果不会被节流丢掉。
        """
        now = time.time()
        if not force and now - self._health_saved_at < HEALTH_SAVE_MIN_INTERVAL:
            return
        self._health_saved_at = now
        try:
            with self._muted:
                payload = {k: dict(v) for k, v in self._health.items()}
                payload["__latency__"] = {k: dict(v) for k, v in self._lat.items()}
            p = self._health_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        except Exception:
            pass

    def flush_health(self):
        """强制把当前画像写盘（进程退出/任务结束时调用）。"""
        self._save_health(force=True)

    # ---------- 线程级云端优先覆盖 ----------
    def set_cloud_first(self, val):
        """webapp 后台任务调用：为当前线程设置 cloud_first 覆盖。"""
        if val is None:
            self._tl.cloud_first = None
        else:
            self._tl.cloud_first = bool(val)

    @property
    def cloud_first_effective(self):
        v = getattr(self._tl, "cloud_first", None)
        return self.cloud.get("cloud_first", False) if v is None else v

    def set_progress(self, fn):
        """为当前线程设置进度回调 fn(stage_text, pct_hint=None)。任务结束时清 None。"""
        self._tl.progress = fn

    def _progress(self, text, pct=None):
        fn = getattr(self._tl, "progress", None)
        if fn is None:
            return
        try:
            fn(text, pct)
        except Exception:
            pass  # 进度上报绝不影响主流程

    # ---------- 失败冷却（配额限速 vs 模型故障）----------
    @staticmethod
    def _classify_error(e):
        """返回 'quota'（节奏/限额问题，模型没坏）或 'transient'（普通故障）。"""
        s = f"{type(e).__name__} {e}".lower()
        if ("429" in s or "too many requests" in s or "rate limit" in s
                or "ratelimit" in s or "quota" in s or "insufficient" in s
                or "5h" in s or "hour limit" in s or "per hour" in s
                or "限额" in s or "限流" in s or "频率" in s):
            return "quota"
        return "transient"

    def _cooldown_sec(self, entry, kind):
        if kind == "quota":
            if entry is not None and entry.get("quota_cooldown"):
                return float(entry["quota_cooldown"])
            return DEFAULT_QUOTA_COOLDOWN
        return DEFAULT_ERROR_COOLDOWN

    def _mark_muted(self, label, entry, kind):
        sec = self._cooldown_sec(entry, kind)
        with self._muted:
            self._muted_until[label] = time.time() + sec
        return sec

    def _muted_left(self, label):
        with self._muted:
            until = self._muted_until.get(label, 0)
        return max(0.0, until - time.time())

    def _note_latency(self, label, sec):
        with self._muted:
            rec = self._lat.get(label)
            if rec is None:
                self._lat[label] = {"ema": sec, "n": 1}
            else:
                rec["ema"] = rec["ema"] * 0.6 + sec * 0.4
                rec["n"] += 1
        self._save_health()

    def _note_health(self, label, ok):
        """可用性画像：累计成功/失败次数与最近时间，供 _order_cloud 动态排序。"""
        with self._muted:
            h = self._health.get(label)
            if h is None:
                h = self._health[label] = {"ok": 0, "fail": 0, "last_ok": 0.0, "last_fail": 0.0}
            if ok:
                h["ok"] += 1
                h["last_ok"] = time.time()
            else:
                h["fail"] += 1
                h["last_fail"] = time.time()
        self._save_health()

    def _channel_score(self, target) -> float:
        """通道排序分（供外部/UI 查询）：可用率 + 新近度，越高越可用。"""
        label = target.get("name") if isinstance(target, dict) else str(target)
        with self._muted:
            h = self._health.get(label)
        if not h or h["ok"] == 0:
            return None
        now = time.time()
        total = h["ok"] + h["fail"]
        success_rate = h["ok"] / total if total else 0.0
        fresh_bonus = 0.2 if (now - h["last_ok"]) < 900 else 0.0
        fresh_penalty = 0.3 if (now - h["last_fail"]) < 300 else 0.0
        return success_rate + fresh_bonus - fresh_penalty

    def _order_cloud(self, entries: list) -> list:
        """按「可用性优先、兼顾性能」排序云端通道。

        分桶后稳定拼接：
        1. 有成功历史：可用率/新近度主导；同分再按实测耗时（EMA）快者优先
           —— 这就是「兼顾性能」：能用的通道里挑快的先跑。
        2. 从未调用过：保持原相对顺序（配置/服务商优先级，避免未经测试者乱序）
        3. 只失败过、从未成功过：排到最后（同样保持相对顺序）
        """
        if len(entries) <= 1:
            return list(entries)
        now = time.time()
        with self._muted:
            health_snapshot = {k: dict(v) for k, v in self._health.items()}
            latency_snapshot = {k: dict(v) for k, v in self._lat.items()}

        def _score(e):
            h = health_snapshot.get(e.get("name"))
            if not h:
                return None  # 从未调用
            if h["ok"] == 0:
                return "failed-only"  # 只失败过
            total = h["ok"] + h["fail"]
            success_rate = h["ok"] / total if total else 0.0
            fresh_bonus = 0.2 if (now - h["last_ok"]) < 900 else 0.0
            fresh_penalty = 0.3 if (now - h["last_fail"]) < 300 else 0.0
            return success_rate + fresh_bonus - fresh_penalty

        def _eta_of(e):
            """实测耗时 EMA；无记录视为中等（不惩罚未测通道，仅在确有对比时才生效）。"""
            rec = latency_snapshot.get(e.get("name"))
            return rec["ema"] if rec and rec.get("ema") else 120.0

        success, fresh, failed_only = [], [], []
        for e in entries:
            s = _score(e)
            if s == "failed-only":
                failed_only.append(e)
            elif s is None:
                fresh.append(e)
            else:
                success.append((s, e))
        # 主键：可用性分降序；次键：实测耗时升序（快的先试）；末键：成功次数降序（更可信）
        success.sort(key=lambda se: (-se[0],
                                     _eta_of(se[1]),
                                     -health_snapshot[se[1]["name"]]["ok"]))
        return [e for _, e in success] + fresh + failed_only

    def _eta(self, label, default=120.0):
        rec = self._lat.get(label)
        return round(rec["ema"], 1) if rec and rec["n"] >= 1 else default

    def cloud_models(self):
        """供 UI 展示：返回云端模型池（跳过 enabled:false 的待激活模板）。

        额外合并 DeepSeek Harness 本机通道网关（Our Free Model 的 OpenAI 兼容
        loopback 端点，127.0.0.1:8326）：它能借 DSH 里已登录的 QoderCN / Trae /
        Buddy 等账号模型生成内容，且无需在本项目里存任何第三方凭据。
        """
        models = [m for m in self.cloud.get("models", [])
                  if m.get("enabled", True) is not False]
        try:
            models += self._dsh_gateway_entries()
        except Exception:
            pass
        return models

    # ---------- DeepSeek Harness 通道网关（QoderCN/Trae/Buddy 等账号） ----------
    @staticmethod
    def _dsh_home() -> str:
        """DSH 数据根：优先环境变量，其次 ~/.dsh。"""
        env = os.environ.get("DSH_HOME") or ""
        if env.strip():
            return env.strip()
        return str(Path.home() / ".dsh")

    @classmethod
    def _dsh_gateway_credential(cls) -> str:
        p = Path(cls._dsh_home()) / "openai-gateway" / "api-key"
        try:
            k = p.read_text(encoding="utf-8").strip()
        except Exception:
            k = ""
        return os.environ.get("DSH_OPENAI_GATEWAY_API_KEY") or k

    @staticmethod
    def _dsh_gateway_port() -> int:
        raw = os.environ.get("DSH_OPENAI_GATEWAY_PORT") or "8326"
        try:
            p = int(raw)
        except ValueError:
            p = 8326
        return p if 1 <= p <= 65535 else 8326

    # 网关通道清单一律以「实测结果」为准（scripts/probe_gateway.py 可随时复测）：
    #   ✓ 可用    ：workbuddy-cn / qodercn / qoder / trae / buddy / cline(部分) /
    #               workbuddy / our-free-model / zcode(仅额度，会按日恢复)
    #   ✗ 无授权  ：pi-github-copilot(502) / deepseek-official(402)
    #   ✗ 已失效  ：st-daily-use(502)
    GATEWAY_PREFIXES = ("workbuddy-cn/", "qodercn/", "qoder/", "trae/",
                        "buddy/", "cline/", "workbuddy/", "our-free-model/",
                        "zcode/")

    # 只接这两类子路径的 cline 模型（cline-pass 需要额外订阅，实测 403）
    CLINE_OK_SUBPATHS = ("anthropic/", "openai/", "google/", "moonshotai/",
                         "nvidia/", "poolside/", "reflection/", "cline-free/")

    # Qoder(中国版/国际版) 短代码：这些是快档；其余（qmodel/gmodel/ultimate…）算强档
    QODER_FAST_KEYS = {"qfmodel", "q37fmodel", "dfmodel", "gfmodel",
                       "efficient", "smodel", "fast"}

    @classmethod
    def _is_gateway_model(cls, mid: str) -> bool:
        """该网关 model id 是否属于「已验证可用」的通道。"""
        pfx = next((p for p in cls.GATEWAY_PREFIXES if mid.startswith(p)), None)
        if pfx is None:
            return False
        if pfx == "cline/":
            rest = mid[len("cline/"):]
            if rest.startswith("cline-pass/"):
                return False  # 需额外订阅，实测 403
            return rest.startswith(cls.CLINE_OK_SUBPATHS)
        if pfx == "workbuddy/":
            low = mid.lower()
            # workbuddy 的 gpt-*/grok-* 实测 400（该账号无权限），只留 glm/kimi/minimax 系
            return not any(k in low for k in ("gpt-", "grok-", "gemini-"))
        return True

    @classmethod
    def _dsh_gateway_entries(cls, strong_limit=26, fast_limit=32) -> list:
        """枚举 DSH 网关 `GET /v1/models`，把「已实测可用」的账号模型转成本项目条目。

        - 通道白名单见 GATEWAY_PREFIXES / _is_gateway_model（按实测结果，不是猜的）。
        - 模型本体仍是 OpenAI 兼容 /v1/chat/completions，兼容 _cloud_entry_chat。
        - 档位映射：名字含 flash/lite/nano/fast/seed 等 → fast；qoder 短代码精确映射。
        - 每个通道都有配额，用「每通道限额」保证不把鸡蛋放一个篮子：
          每通道最多 3 个 strong + 4 个 fast，总量 strong_limit/fast_limit 封顶。
        """
        cred = cls._dsh_gateway_credential()
        if not cred:
            return []
        port = cls._dsh_gateway_port()
        base = f"http://127.0.0.1:{port}/v1"
        try:
            r = requests.get(base + "/models",
                             headers={"Authorization": "Bearer " + cred}, timeout=8)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []
        ids = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
        prefixes = cls.GATEWAY_PREFIXES
        prio = {p: i for i, p in enumerate(prefixes)}

        def _tier(mid: str) -> str:
            low = mid.lower()
            if low.startswith(("qodercn/", "qoder/")):
                key = low.split("/", 1)[1]
                return "fast" if key in cls.QODER_FAST_KEYS else "strong"
            is_fast = ("flash" in low or "lite" in low or "nano" in low
                       or "fast" in low or "seed" in low or "mini" in low
                       or "2b" in low or "4b" in low or "8b" in low or "20b" in low
                       or "6.8" in low or "u1-fast" in low or "u1.5-lite" in low)
            return "fast" if is_fast else "strong"

        entries = []
        for mid in ids:
            if not cls._is_gateway_model(mid):
                continue
            pfx = next(p for p in prefixes if mid.startswith(p))
            tier = _tier(mid)
            entries.append({
                "name": "DSH-" + mid.replace("/", "·"),
                "provider": "dsh-gateway",
                "base_url": base,
                "api_key": cred,
                "model": mid,
                "tier": tier,
                "timeout": 420,
                # 推理模型会先烧思考链：给足 max_tokens，避免正文被挤空
                "max_tokens": 8192,
                "_prio": prio[pfx],
                "_strong": tier == "strong",
            })
        # 每通道限额，保证通道多样性（某一家挂了还有其他家兜底）
        per_prefix_strong, per_prefix_fast = 3, 4
        strong_buckets, fast_buckets = [], []
        for pfx_i in range(len(prefixes)):
            # 注意：必须「先排序再切片」——否则按网关返回顺序截前 3 个，
            # 会把该通道最好的旗舰模型（如 cline 的 opus-5.5）直接切掉。
            sp = [e for e in entries
                  if e["_strong"] and e["_prio"] == pfx_i]
            fp = [e for e in entries
                  if not e["_strong"] and e["_prio"] == pfx_i]
            sp.sort(key=lambda e: (-_strong_rank(e["model"]), e["name"]))
            fp.sort(key=lambda e: e["name"])
            if sp:
                strong_buckets.append(sp[:per_prefix_strong])
            if fp:
                fast_buckets.append(fp[:per_prefix_fast])

        def _round_robin(buckets, limit):
            """按通道轮转分配给总量上限：先每家分第一个，再第二个…
            这样上限收紧时是「每家少给一点」，而不是「后面的通道全丢」。"""
            out, depth = [], 0
            while len(out) < limit:
                added = False
                for b in buckets:
                    if depth < len(b):
                        out.append(b[depth])
                        added = True
                        if len(out) >= limit:
                            break
                if not added:
                    break
                depth += 1
            return out

        strongs = _round_robin(strong_buckets, strong_limit)
        fasts = _round_robin(fast_buckets, fast_limit)
        merged = strongs + fasts
        for e in merged:
            e.pop("_prio", None)
            e.pop("_strong", None)
        return merged

    def channel_state(self):
        """供 UI 展示：各通道冷却剩余、耗时估计与可用性画像。

        注意：_channel_score 内部也会取 self._muted 锁，而 threading.Lock 不可重入，
        所以这里先在锁内拷出快照，出锁后再算分数，避免自死锁。
        """
        with self._muted:
            now = time.time()
            muted_snapshot = dict(self._muted_until)
            latency_snapshot = {k: dict(v) for k, v in self._lat.items()}
            health_snapshot = {k: dict(v) for k, v in self._health.items()}
        out = []
        for label, until in muted_snapshot.items():
            left = until - now
            if left > 0:
                out.append({"label": label, "cooldown_left": round(left),
                            "reason": "quota" if left > DEFAULT_ERROR_COOLDOWN + 1 else "error"})
        health = {}
        for label, h in health_snapshot.items():
            total = h["ok"] + h["fail"]
            score = self._channel_score({"name": label})
            health[label] = {
                "ok": h["ok"], "fail": h["fail"],
                "success_rate": round(h["ok"] / total, 3) if total else None,
                "last_ok_ago": (round(now - h["last_ok"]) if h["last_ok"] else None),
                "last_fail_ago": (round(now - h["last_fail"]) if h["last_fail"] else None),
                "score": round(score, 3) if score is not None else None,
            }
        return {"muted": out,
                "latency": {k: round(v["ema"], 1) for k, v in latency_snapshot.items()},
                "health": health}

    # ---------- 基础调用 ----------
    def _ollama_chat(self, model, messages, json_mode=False, think=False):
        timeout = self.local.get("timeout", 120)
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": think,
                "options": {
                "temperature": self.local.get("temperature", 0.3),
                "num_ctx": self.local.get("num_ctx", 8192),
                "num_predict": self.local.get("num_predict", 4096),
            },
        }
        if json_mode:
            payload["format"] = "json"
        r = requests.post(self.local["base_url"] + "/api/chat", json=payload,
                          timeout=timeout)
        if r.status_code == 400 and "think" in payload:
            payload.pop("think")  # 老版本不支持 think 参数
            r = requests.post(self.local["base_url"] + "/api/chat", json=payload,
                              timeout=timeout)
        r.raise_for_status()
        msg = r.json().get("message", {})
        return msg.get("content", "") or ""

    def _cloud_entry_chat(self, entry, messages, json_mode=False):
        """调用单个云端模型条目（OpenAI 兼容接口）。

        长文（教程/题解）必须显式给足 max_tokens，否则服务端默认上限会截断内容；
        若仍因长度截断（finish_reason=length），自动续写并拼接，保证内容完整。
        """
        base_body = {
            "model": entry["model"],
            "messages": messages,
            "temperature": entry.get("temperature", 0.3),
            "max_tokens": entry.get("max_tokens", 8192),
        }
        if json_mode:
            base_body["response_format"] = {"type": "json_object"}
            base_body.update(entry.get("json_extra") or {})  # 按模型关思考等（如 enable_thinking:false）
        base_body.update(entry.get("extra") or {})  # 如商汤需 temperature:1

        def _once(msgs):
            body = dict(base_body)
            body["messages"] = msgs
            r = requests.post(
                entry["base_url"].rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + entry["api_key"]},
                json=body, timeout=entry.get("timeout", 700))
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                return "", None, ""
            choices = data.get("choices") or []
            if not choices:
                return "", None, ""
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if not isinstance(content, str):
                content = ""
            reasoning = msg.get("reasoning_content") or ""
            return content, choices[0].get("finish_reason"), reasoning

        content, finish, reasoning = _once(messages)
        for _ in range(3):
            if finish != "length" or not content:
                break
            cont = list(messages)
            cont.append({"role": "assistant", "content": content})
            cont.append({"role": "user",
                         "content": "请紧接着从中断处继续输出剩余内容，不要重复已输出的部分。"})
            more, finish, _reasoning = _once(cont)
            if not more:
                break
            content += _overlap_trim(content, more)
        # 推理模型可能把最终 JSON 写进 reasoning_content（content 为空）。
        # 仅在 reasoning 本身含可解析 JSON 时才回退；纯思考文字不会被当答案（返回空，交给路由层换通道）。
        if json_mode and not content and reasoning and extract_json(reasoning) is not None:
            content = reasoning
        return content
    def _cloud_tier(self, strong):
        tier = "strong" if strong else "fast"
        if not self.cloud.get("enabled"):
            return []
        # 条目 enabled: false 为待激活模板（如未填 token），不参与调用
        models = [m for m in self.cloud.get("models", [])
                  if m.get("tier") == tier and m.get("enabled", True) is not False]
        # 云端优先时，把 DSH 网关账号模型并进对应档位（作兜底通道，排在配置模型之后）
        if self.cloud_first_effective:
            try:
                gated = [e for e in self._dsh_gateway_entries()
                         if e.get("tier") == tier]
            except Exception:
                gated = []
            # 去重：DSH 网关条目以 name 标识
            seen = {m.get("name") for m in models}
            for e in gated:
                if e.get("name") not in seen:
                    models.append(e)
        return models

    # ---------- 统一入口 ----------
    def chat(self, messages, deep=False, json_mode=False, force=None,
             cloud_first=None, tier=None) -> str:
        """force: None(默认路由) / 'local' / 'external'
        cloud_first: None(用配置/线程覆盖) / True / False（本次显式覆盖）
        tier: None(按 deep 自动选档) / 'strong' / 'fast'（显式档位，如教程 fast、实战 strong）"""
        cf = self.cloud_first_effective if cloud_first is None else bool(cloud_first)
        if force == "external":
            cf = True
        elif force == "local":
            cf = False

        # 选档：显式 tier 优先；否则 deep→strong，非 deep→fast
        strong = (tier == "strong") if tier in ("strong", "fast") else bool(deep)
        tier_main = self._order_cloud(self._cloud_tier(strong=strong))
        tier_other = self._order_cloud(self._cloud_tier(strong=not strong))
        # 本地通道顺序：strong 时先深后快，否则先快后深
        local_order = ([self.local["deep_model"], self.local["fast_model"]]
                       if strong else [self.local["fast_model"], self.local["deep_model"]])

        def local_chan(model):
            think = bool(strong and self.local.get("think", True))
            return self._ollama_chat(model, messages, json_mode, think=think)

        # 构造有序通道列表：(kind, target)
        chans = []
        if cf:  # 云端优先：strong/fast 主档 → 另一档 → 本地
            chans += [("cloud", e) for e in tier_main]
            chans += [("cloud", e) for e in tier_other]
            chans += [("local", m) for m in local_order]
        else:    # 本地优先：本地 → 云端主档 → 云端另一档
            chans += [("local", m) for m in local_order]
            chans += [("cloud", e) for e in tier_main]
            chans += [("cloud", e) for e in tier_other]

        self._progress(f"路由开始（{'云端' if cf else '本地'}优先，"
                       f"档位 {tier or ('strong' if deep else 'fast')}，{len(chans)} 条通道）", 2)
        last_err = None
        tried = []
        skipped = []  # 第一轮因冷却跳过的通道，全部失败后第二轮兜底再试
        for kind, target in chans:
            entry = target if kind == "cloud" else None
            label = (target.get("name") if kind == "cloud"
                     else f"ollama:{target}")
            left = self._muted_left(label)
            if left > 0:
                skipped.append((kind, target, label, left))
                self._progress(f"{label} 冷却中({int(left)}s)，跳过")
                continue
            tried.append(label)
            eta = self._eta(label)
            self._progress(f"调用 {label}（预计约 {eta:.0f}s）", 10)
            t0 = time.time()
            try:
                if kind == "cloud":
                    out = self._cloud_entry_chat(target, messages, json_mode)
                else:
                    out = local_chan(target)
                out = self._validate_out(out, json_mode, label)
                self._note_latency(label, time.time() - t0)
                self._note_health(label, True)
                self._progress(f"{label} 完成，用时 {time.time() - t0:.0f}s", 95)
                return out
            except Exception as e:  # 网络抖动/模型忙/限额：按类别冷却后换下一个
                last_err = e
                self._note_health(label, False)
                kind_err = self._classify_error(e)
                sec = self._mark_muted(label, entry, kind_err)
                note = ("限额/节奏问题，模型未坏"
                        if kind_err == "quota" else "临时故障")
                self._progress(f"{label} 失败（{note}，冷却 {int(sec)}s）：{str(e)[:120]}")
                time.sleep(0.5)
        # 所有可用通道都失败且存在冷却中通道：兜底再试（配额窗口可能已恢复）
        for kind, target, label, _left in skipped:
            tried.append(label)
            self._progress(f"其它通道均失败，兜底重试冷却中的 {label}")
            entry = target if kind == "cloud" else None
            t0 = time.time()
            try:
                if kind == "cloud":
                    out = self._cloud_entry_chat(target, messages, json_mode)
                else:
                    out = local_chan(target)
                out = self._validate_out(out, json_mode, label)
                self._note_latency(label, time.time() - t0)
                self._note_health(label, True)
                self._progress(f"{label} 完成，用时 {time.time() - t0:.0f}s", 95)
                return out
            except Exception as e:
                last_err = e
                self._note_health(label, False)
        self.fail_streak += 1
        raise LLMError(f"所有模型通道均失败（已试 {len(tried)} 个: {', '.join(tried)}）: {last_err}")

    @staticmethod
    def _validate_out(out, json_mode, label):
        """通道输出校验：json_mode 下必须能解析出 JSON；否则空响应视为失败。

        推理模型常把 token 烧在 reasoning_content 上导致 content 为空/非 JSON，
        这里把这类通道判为失败（走 except 换下一条通道），而不是把垃圾抛给 ask_json。
        """
        out = out or ""
        if json_mode:
            if extract_json(strip_thinking(out)) is None:
                raise ValueError(f"{label} 未返回合法 JSON")
        elif not out.strip():
            raise ValueError(f"{label} 返回空内容")
        return out

    def ok(self):
        self.fail_streak = 0

    # ---------- 便捷封装 ----------
    @staticmethod
    def _kb_context(query: str, k: int = 3, max_chars: int = 2200) -> str:
        """按查询从知识库检索相关片段，供提示词注入。

        这是「知识库不只是 system prompt」的落点：system prompt 只能装 ~6000 字
        （num_ctx 限制），而知识库会持续增长到几百上千篇。正确做法是
        每次调用按当前问题检索最相关的几篇塞进去，而不是把整库塞进 system。
        检索失败绝不影响主流程。
        """
        if not query or not query.strip():
            return ""
        try:
            from core.knowledge import kb
            return kb().context_for(query, k=k, max_chars=max_chars)
        except Exception:
            return ""

    def ask(self, prompt, system=None, deep=False, force=None,
            cloud_first=None, tier=None, kb_query=None, kb_k=3) -> str:
        """kb_query：从知识库检索该查询的相关片段注入提示词。

        None = 不注入（默认，避免给每次调用都增加 token）；
        传 True = 用 prompt 本身作为检索查询；传字符串 = 用该字符串检索。
        """
        if kb_query is True:
            kb_query = prompt[:500]
        if kb_query:
            ctx = self._kb_context(kb_query, k=kb_k)
            if ctx:
                prompt = (f"{prompt}\n\n# 知识库参考（自动检索，优先采用）\n{ctx}")
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return self.chat(msgs, deep=deep, force=force, cloud_first=cloud_first,
                         tier=tier)

    def ask_json(self, prompt, system=None, deep=True, force=None,
                 cloud_first=None, tier=None, kb_query=None, kb_k=3) -> dict:
        """强制 JSON 输出并解析。kb_query 语义同 ask()。"""
        if kb_query is True:
            kb_query = prompt[:500]
        if kb_query:
            ctx = self._kb_context(kb_query, k=kb_k)
            if ctx:
                prompt = (f"{prompt}\n\n# 知识库参考（自动检索，优先采用）\n{ctx}")
        prompt = prompt.rstrip() + "\n\n只输出一个合法 JSON 对象，不要输出任何其他文字、注释或代码块标记。"
        text = self.chat(
            [{"role": "system", "content": system or "你是一个严谨的工程助手。"},
             {"role": "user", "content": prompt}],
            deep=deep, json_mode=True, force=force, cloud_first=cloud_first,
            tier=tier)
        data = extract_json(strip_thinking(text))
        if data is None:
            raise LLMError("模型输出无法解析为 JSON（所有通道均未返回合法 JSON）: " + text[:300])
        return data


def strip_thinking(text):
    """剥离推理模型写进正文的思考/规划段（中英文均防）。"""
    if not isinstance(text, str) or not text.strip():
        return text or ""
    lines = text.split(chr(10))
    in_fence = False
    idx_h = None
    idx_any = None
    for idx, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if idx_any is None and re.match(r"^#{1,3}\s+\S", ln):
            idx_any = idx
        if re.match(r"^#{1,2}\s+\S", ln):
            idx_h = idx
            break
    if idx_h:
        head = chr(10).join(lines[:idx_h])
        markers = ("The user", "Let me", "I will", "I need",
                   "分析请求", "我的任务", "任务要求",
                   "思考过程", "输出要求", "角色：", "学员：")
        if any(k in head for k in markers):
            return chr(10).join(lines[idx_h:]).lstrip(chr(10))
    if idx_any:
        head = chr(10).join(lines[:idx_any])
        if not head.strip():
            return text
        cjk = len(re.findall(r"[一-鿿]", head))
        latin = len(re.findall(r"[A-Za-z]", head))
        if latin > cjk * 2 and latin > 200:
            return chr(10).join(lines[idx_any:]).lstrip(chr(10))
    return text

def _overlap_trim(base, extra):
    """续写去重：若续写开头与已有内容尾部重叠，裁掉重叠部分。"""
    if not base or not extra:
        return extra
    maxo = min(len(base), len(extra), 2000)
    for n in range(maxo, 0, -1):
        if base.endswith(extra[:n]):
            return extra[n:]
    return extra


def extract_json(text):
    """从文本中提取第一个平衡的 JSON 对象（容忍 ```json 围栏/前后噪声）。"""
    if not isinstance(text, str) or not text.strip():
        return None
    text = text.strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.M).strip()
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None
    return None


_router = None


def router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


def flush_health():
    """把路由器当前的通道可用性画像强制落盘（进程退出/任务收尾时调用）。"""
    if _router is not None:
        try:
            _router.flush_health()
        except Exception:
            pass


atexit.register(flush_health)  # 正常退出时确保画像不丢（节流窗口内的最后一次结果）
