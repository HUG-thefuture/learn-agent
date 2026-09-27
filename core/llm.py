# -*- coding: utf-8 -*-
"""LLM 路由层。

- 本地优先：Ollama 上的 qwen3:8b（快）/ qwen3:14b（深）
- 外部增强：OpenAI 兼容接口（百炼/DeepSeek/OpenAI 等），用于复杂审查与高质量蒸馏
- 自动降级：deep -> fast -> external -> 抛错；离线兜底由调用方处理
"""
import json
import re
import time

import requests

from core.config import cfg


class LLMError(RuntimeError):
    pass


class LLMRouter:
    def __init__(self):
        c = cfg()
        self.local = c["local_model"]
        self.ext = c.get("external_model", {})
        self.fail_streak = 0  # 连续失败计数，供工作流决定是否升级

    # ---------- 基础调用 ----------
    def _ollama_chat(self, model, messages, json_mode=False, think=False):
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": think,
            "options": {
                "temperature": self.local.get("temperature", 0.3),
                "num_ctx": self.local.get("num_ctx", 8192),
            },
        }
        if json_mode:
            payload["format"] = "json"
        r = requests.post(self.local["base_url"] + "/api/chat", json=payload,
                          timeout=300)
        if r.status_code == 400 and "think" in payload:
            payload.pop("think")  # 老版本不支持 think 参数
            r = requests.post(self.local["base_url"] + "/api/chat", json=payload,
                              timeout=300)
        r.raise_for_status()
        msg = r.json().get("message", {})
        return msg.get("content", "") or ""

    def _external_chat(self, messages, json_mode=False):
        if not self.ext.get("enabled"):
            raise LLMError("外部模型未启用")
        body = {
            "model": self.ext["model"],
            "messages": messages,
            "temperature": 0.3,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = requests.post(
            self.ext["base_url"].rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + self.ext["api_key"]},
            json=body, timeout=self.ext.get("timeout", 60))
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    # ---------- 统一入口 ----------
    def chat(self, messages, deep=False, json_mode=False, force=None) -> str:
        """force: None(默认路由) / 'local' / 'external'"""
        order = []
        if force == "external":
            order = ["external"]
        elif force == "local":
            order = ["deep", "fast"]
        else:
            if deep:
                order = ["deep", "fast", "external"]
            else:
                order = ["fast", "deep", "external"]
        last_err = None
        for which in order:
            try:
                if which == "external":
                    if not self.ext.get("enabled"):
                        continue
                    return self._external_chat(messages, json_mode)
                model = self.local["deep_model"] if which == "deep" else self.local["fast_model"]
                # 思考模式仅用于深度请求，且受配置总开关限制
                think = bool(deep and self.local.get("think", True))
                return self._ollama_chat(model, messages, json_mode, think=think)
            except Exception as e:  # 网络抖动/模型忙则尝试下一档
                last_err = e
                time.sleep(0.5)
        self.fail_streak += 1
        raise LLMError(f"所有模型通道均失败: {last_err}")

    def ok(self):
        self.fail_streak = 0

    # ---------- 便捷封装 ----------
    def ask(self, prompt, system=None, deep=False, force=None) -> str:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return self.chat(msgs, deep=deep, force=force)

    def ask_json(self, prompt, system=None, deep=True, force=None) -> dict:
        """强制 JSON 输出并解析。"""
        prompt = prompt.rstrip() + "\n\n只输出一个合法 JSON 对象，不要输出任何其他文字、注释或代码块标记。"
        text = self.chat(
            [{"role": "system", "content": system or "你是一个严谨的工程助手。"},
             {"role": "user", "content": prompt}],
            deep=deep, json_mode=True, force=force)
        data = extract_json(text)
        if data is None:
            raise LLMError("模型输出无法解析为 JSON: " + text[:200])
        return data


def extract_json(text: str):
    """从文本中提取第一个平衡的 JSON 对象（容忍 ```json 围栏/前后噪声）。"""
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
