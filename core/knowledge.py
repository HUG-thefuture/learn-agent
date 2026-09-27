# -*- coding: utf-8 -*-
"""知识库：TF-IDF 向量检索（纯 Python 实现，学习内容可沉淀为长期记忆）。

train(docs) 即"训练"：统计词频->计算 IDF->建立倒排索引，可评估检索命中率。
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

from core.config import data_dir

INDEX_FILE = "index.json"

_WORD = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{1,}")
_CJK = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str):
    """中英混合分词：英文按标识符/单词，中文按二元组。"""
    toks = [w.lower() for w in _WORD.findall(text or "")]
    cjk = _CJK.findall(text or "")
    toks += [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]
    return toks


class KnowledgeBase:
    def __init__(self, path: Path = None):
        self.path = path or (data_dir() / "knowledge" / INDEX_FILE)
        self.docs = []   # [{id,title,lang,tags,text,source}]
        self.idf = {}    # term -> idf
        self.tfs = []    # 每篇文档的词频 Counter
        if self.path.exists():
            self._load()

    # ---------- 持久化 ----------
    def _load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.docs = raw.get("docs", [])
        self.idf = raw.get("idf", {})
        self.tfs = [Counter(d) for d in raw.get("tfs", [])]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"docs": self.docs, "idf": self.idf,
                       "tfs": [dict(t) for t in self.tfs]},
                      f, ensure_ascii=False)

    # ---------- 训练（建立索引） ----------
    def train(self, new_docs: list = None) -> dict:
        """合并新文档并重建 TF-IDF 索引。返回训练统计。"""
        if new_docs:
            have = {d["id"] for d in self.docs}
            for d in new_docs:
                d.setdefault("id", d.get("title", "doc")[:60])
                d.setdefault("lang", "general")
                d.setdefault("tags", [])
                d.setdefault("source", "manual")
                if d["id"] not in have:
                    self.docs.append(d)
                    have.add(d["id"])
        self.tfs = [Counter(tokenize(d["title"] + " " + d["text"])) for d in self.docs]
        df = Counter()
        for tf in self.tfs:
            for t in tf:
                df[t] += 1
        n = max(len(self.docs), 1)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        self.save()
        return {"docs": len(self.docs), "vocab": len(self.idf)}

    # ---------- 检索 ----------
    def _vec(self, tf: Counter):
        return {t: (1 + math.log(c)) * self.idf.get(t, 1.0) for t, c in tf.items()}

    def search(self, query: str, k: int = 3, lang: str = None) -> list:
        if not self.docs:
            return []
        q = self._vec(Counter(tokenize(query)))
        hits = []
        for i, tf in enumerate(self.tfs):
            if lang and self.docs[i].get("lang") not in (lang, "general"):
                continue
            dv = self._vec(tf)
            score = sum(v * dv.get(t, 0.0) for t, v in q.items())
            hits.append((score, i))
        hits.sort(reverse=True)
        return [{"score": round(s, 4), **self.docs[i]} for s, i in hits[:k] if s > 0]

    # ---------- 评估：用标题当查询，看能否召回原文（自检命中率） ----------
    def evaluate(self, k: int = 3) -> dict:
        if not self.docs:
            return {"hit_rate": 0.0, "n": 0}
        hit = 0
        for i, d in enumerate(self.docs):
            for h in self.search(d["title"], k=k):
                if h["id"] == d["id"]:
                    hit += 1
                    break
        return {"hit_rate": round(hit / len(self.docs), 3), "n": len(self.docs)}

    def context_for(self, query: str, k: int = 2, max_chars: int = 1600) -> str:
        """拼装检索上下文，供提示词注入。"""
        parts = []
        for h in self.search(query, k=k):
            t = h["text"][:max_chars // max(k, 1)]
            parts.append(f"[{h['title']}] {t}")
        return "\n---\n".join(parts)


_kb = None


def kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
