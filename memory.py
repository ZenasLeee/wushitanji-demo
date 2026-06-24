"""
个人记忆库 — key=(食物名, 单位) → 每单位基准克重
================================================

承 demo-spec §3 / ADR-018/019：
- key = (canonical 食物名, 单位)；canonical 由调用方用 normalize_dish 归一后传入（硬不变量 #1）。
- value = 每单位基准克重（如 (米饭,拳)→280）。
- 倍数不进 key、不持久化（当餐量 = 基准 × 倍数）。
- 跨会话存活：SQLite 文件持久化（demo-spec §9 自由裁量选存储技术）。

存储形态：单表 memory(food, unit, base_gram)，(food, unit) 为主键。

硬不变量 #3：读/写两端记日志（解析出的 key、是否命中、命中值），复用漏了能归因。

注：Railway 等平台容器文件系统会在重新部署/重启后重置，本文件持久化只覆盖
「同一次部署运行期内跨浏览器会话不丢」，不覆盖跨部署持久——如需后者要挂 Volume。
"""

import os
import sqlite3
import threading

STORE_PATH = os.path.join(os.path.dirname(__file__), "memory_store.db")
_LOCK = threading.Lock()


def _log(msg):
    print(f"[memory] {msg}", flush=True)


def _connect():
    conn = sqlite3.connect(STORE_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS memory ("
        "food TEXT NOT NULL, unit TEXT NOT NULL, base_gram INTEGER NOT NULL, "
        "PRIMARY KEY (food, unit))"
    )
    return conn


def get(food, unit):
    """查 (食物,单位) 的基准克重；命中返回数值，未命中返回 None。两端记日志。"""
    if not food or not unit:
        return None
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT base_gram FROM memory WHERE food=? AND unit=?", (food, unit)
            ).fetchone()
        finally:
            conn.close()
    val = row[0] if row else None
    if val is None:
        _log(f"READ  key=({food},{unit}) -> MISS")
    else:
        _log(f"READ  key=({food},{unit}) -> HIT {val}g")
    return val


def set_base(food, unit, base_gram):
    """写 (食物,单位)→基准克重（显式「记住」触发）。取最新覆盖。记日志。"""
    base_gram = int(round(float(base_gram)))
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO memory (food, unit, base_gram) VALUES (?, ?, ?) "
                "ON CONFLICT(food, unit) DO UPDATE SET base_gram=excluded.base_gram",
                (food, unit, base_gram),
            )
            conn.commit()
        finally:
            conn.close()
    _log(f"WRITE key=({food},{unit}) <- {base_gram}g")
    return base_gram


def delete(food, unit):
    """删除一条映射；返回是否删到。记日志。"""
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM memory WHERE food=? AND unit=?", (food, unit)
            )
            conn.commit()
            existed = cur.rowcount > 0
        finally:
            conn.close()
    _log(f"DELETE key=({food},{unit}) -> {'OK' if existed else 'NOT FOUND'}")
    return existed


def list_all():
    """列出全部条目：[{food, unit, base_gram}]，供记忆库面板展示。"""
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute("SELECT food, unit, base_gram FROM memory").fetchall()
        finally:
            conn.close()
    return [{"food": f, "unit": u, "base_gram": g} for f, u, g in rows]
