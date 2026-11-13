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
        """文档/查询向量：sublinear tf * idf，再做 L2 归一化。

        为什么必须归一化（踩过的坑）：
        原实现 score = Σ (1+log tf_d) * idf² 没有长度归一化，导致长文档靠
        "某个词出现很多次"刷分。实测查询「背包问题 动态规划」时，
        真正讲背包的《动态规划入门要点》(205字) 得分 88.75，
        而只沾了"动态规划"三个字的题解《爬楼梯》(456字) 却拿到 100.85，
        正确的文档反而排第 2——检索失败，用户看到的"知识库太少"只是表象。

        L2 归一化保证：文档向量长度恒为 1，得分 = 方向余弦相关度，
        "命中多少个不同的词"比"某个词重复多少次"重要得多。
        """
        if not tf:
            return {}
        vec = {t: (1 + math.log(c)) * self.idf.get(t, 1.0) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def search(self, query: str, k: int = 3, lang: str = None,
               min_coverage: float = 0.0) -> list:
        """按相关度检索。

        min_coverage：查询词被文档覆盖的比例下限（0~1）。
        中文按二元组分词时，长查询里总会有一两个二元组碰巧命中别的词
        （"完全不相关"里的"相关"），单看余弦分数容易放进噪声。
        用「命中词数 / 查询词数」再筛一道，能有效滤掉这种假阳性。
        """
        if not self.docs:
            return []
        q_tf = Counter(tokenize(query))
        q = self._vec(q_tf)
        if not q:
            return []
        n_terms = max(len(q_tf), 1)
        hits = []
        for i, tf in enumerate(self.tfs):
            if lang and self.docs[i].get("lang") not in (lang, "general"):
                continue
            dv = self._vec(tf)
            score = sum(v * dv.get(t, 0.0) for t, v in q.items())
            if score <= 0:
                continue
            if min_coverage > 0:
                matched = sum(1 for t in q_tf if dv.get(t))
                if matched / n_terms < min_coverage:
                    continue
            hits.append((score, i))
        hits.sort(reverse=True)
        return [{"score": round(s, 4), **self.docs[i]} for s, i in hits[:k]]

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

    def context_for(self, query: str, k: int = 2, max_chars: int = 1600,
                    min_score: float = 0.045, min_coverage: float = 0.4) -> str:
        """拼装检索上下文，供提示词注入。

        双阈值过滤弱相关命中，避免把噪声塞进提示词干扰模型：

        - **min_coverage（主）**：查询词被文档覆盖的比例。
          中文二元组分词会产生大量假阳性——"完全不相关"里含"相关"，
          "查询"也是个常见词，于是无意义查询也能凑出 22~33% 覆盖率。
          实测真实查询覆盖率 50~100%、噪声 22~33%，取 0.4 作为分界。
        - **min_score（辅）**：余弦相关度下限（强相关通常 >0.10）。
        """
        hits = [h for h in self.search(query, k=k * 2, min_coverage=min_coverage)
                if h["score"] >= min_score][:k]
        if not hits:
            return ""
        parts = []
        per = max(max_chars // max(len(hits), 1), 200)
        for h in hits:
            # 按段落边界截断，别把一句话切两半
            t = (h["text"] or "").strip()
            if len(t) > per:
                cut = t.rfind("\n", 0, per)
                t = t[:cut if cut > per * 0.6 else per].rstrip() + "…"
            parts.append(f"[{h['title']}] {t}")
        return "\n---\n".join(parts)

    def stats(self) -> dict:
        """知识库概览：用于报告里解释「为什么只注入 N 篇」。"""
        from collections import Counter
        by_source = Counter()
        chars_by_source = Counter()
        for d in self.docs:
            src = str(d.get("source") or "?")
            # source 可能是文件路径，归一成一个简短类别
            if src == "seed":
                key = "seed 内置精华"
            elif src == "cheatsheet" or "cheatsheet" in (d.get("tags") or []):
                key = "cheatsheet 速查"
            elif src == "distill":
                key = "distill 蒸馏语料"
            elif src.startswith("learn:") or "learn" in (d.get("tags") or []):
                key = "learn 学习沉淀"
            else:
                key = "教程/其他"
            by_source[key] += 1
            chars_by_source[key] += len(d.get("text") or "")
        return {"total": len(self.docs),
                "total_chars": sum(chars_by_source.values()),
                "by_source": dict(by_source),
                "chars_by_source": dict(chars_by_source)}


_kb = None


def kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
