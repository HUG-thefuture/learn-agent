# -*- coding: utf-8 -*-
"""本地 MySQL/MariaDB 访问模块（Agent 数据库工具 + SQL 学习实践）。

凭据见 config.yaml 的 database 段。提供三类能力：
- databases()                    列出数据库
- schema(database)               列出库中表与字段
- query(sql, database)           执行 SQL（默认禁止 DROP DATABASE 等高危语句）
"""
import re

import pymysql

from core.config import cfg

_FORBIDDEN = re.compile(r"\b(drop\s+(database|schema)|grant\s|create\s+user)\b", re.I)


class DBTool:
    def __init__(self):
        d = cfg()["database"]
        self.host = d["host"]
        self.port = d.get("port", 3306)
        self.user = d["user"]
        self.password = d["password"]
        self.max_rows = d.get("max_rows", 50)

    def _connect(self, database: str = None):
        return pymysql.connect(host=self.host, port=self.port, user=self.user,
                               password=self.password, database=database or None,
                               connect_timeout=5, charset="utf8mb4")

    def ping(self) -> dict:
        try:
            c = self._connect()
            with c.cursor() as cur:
                cur.execute("SELECT VERSION()")
                v = cur.fetchone()[0]
            c.close()
            return {"ok": True, "server": f"{self.host}:{self.port}", "version": v}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    def databases(self) -> list:
        c = self._connect()
        with c.cursor() as cur:
            cur.execute("SHOW DATABASES")
            rows = [r[0] for r in cur.fetchall()]
        c.close()
        return rows

    def schema(self, database: str) -> list:
        """返回 [{table, columns:[(name,type,key)]}]"""
        c = self._connect(database)
        out = []
        with c.cursor() as cur:
            cur.execute("SHOW TABLES")
            tables = [r[0] for r in cur.fetchall()]
            for t in tables:
                cur.execute(f"SHOW COLUMNS FROM `{t}`")
                cols = [(r[0], r[1], r[3]) for r in cur.fetchall()]
                out.append({"table": t, "columns": cols})
        c.close()
        return out

    def query(self, sql: str, database: str = None) -> dict:
        """执行一条 SQL。SELECT/SHOW 返回行数据；其余返回受影响行数。"""
        if _FORBIDDEN.search(sql or ""):
            return {"ok": False, "error": "拒绝执行高危语句(DROP DATABASE/GRANT/CREATE USER)。"}
        sql = sql.strip().rstrip(";")
        try:
            c = self._connect(database)
        except Exception as e:
            return {"ok": False, "error": f"连接失败: {str(e)[:200]}"}
        try:
            with c.cursor() as cur:
                cur.execute(sql)
                if cur.description:  # 有结果集
                    cols = [d[0] for d in cur.description]
                    rows = cur.fetchmany(self.max_rows)
                    total = cur.rowcount
                    return {"ok": True, "columns": cols,
                            "rows": [[_cell(v) for v in r] for r in rows],
                            "shown": len(rows), "total": total,
                            "note": f"最多显示 {self.max_rows} 行" if total > len(rows) else ""}
                c.commit()
                return {"ok": True, "affected": cur.rowcount, "columns": [], "rows": []}
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}
        finally:
            c.close()


def _cell(v):
    if hasattr(v, "isoformat"):
        return str(v)
    return v


_db = None


def db() -> DBTool:
    global _db
    if _db is None:
        _db = DBTool()
    return _db
