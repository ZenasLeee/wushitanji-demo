"""
量词分解 — 单位 × 小数倍数（确定性）
====================================

承 ADR-018/019/020：
- 单位为有限闭集 {碗拳掌盘杯勺指}，每单位基准克重按食物名存（进记忆 key）。
- 倍数为当餐级小数标量，不进 key、不持久化。
- 模糊修饰（大/小）→ 软待确认、默认倍数 = 1.0、不持久化（ADR-020）。
- 非闭集量词（份/个/块/撮）与计量单位（g/ml）→ 不可复用，返回 (None, None, False)。

输出：(unit, multiplier, fuzzy)
  - unit=None 表示不可复用（无确定性单位）；此时 multiplier=None。
  - fuzzy=True 表示倍数来自模糊修饰兜底（1.0），UI 走待确认引导。

权威用例：quantifier_cases.jsonl（自检见文件末 __main__）。
"""

import re

# 可持久化单位闭集（身体部位量 + 容器量），承 ADR-018/019
PERSISTABLE_UNITS = set("碗拳掌盘杯勺指")

# 模糊修饰字符 → 走 ADR-020 软待确认
FUZZY_CHARS = set("大小")

CN_NUM = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

# 解析层未提供份量时的占位
_EMPTY = {"未提供", "无", "", None}


def quantifier_parse(text):
    """把 L2 量词字符串分解为 (unit, multiplier, fuzzy)。"""
    if text in _EMPTY:
        return (None, None, False)

    # 1. 单位：必须命中可持久化闭集，否则不可复用
    unit = next((ch for ch in text if ch in PERSISTABLE_UNITS), None)
    if unit is None:
        return (None, None, False)

    # 2. 模糊修饰：默认倍数 1.0，软待确认（ADR-020），不再解析数字
    if any(ch in FUZZY_CHARS for ch in text):
        return (unit, 1.0, True)

    # 3. 小数：如 0.8碗 / 1.2杯
    m = re.search(r"\d+\.?\d*", text)
    if m:
        return (unit, float(m.group()), False)

    # 4. 中文数字 + 半。覆盖：一拳 / 两碗 / 半碗 / 一个半拳 / 一碗半
    half = 0.5 if "半" in text else 0.0
    base = next((CN_NUM[ch] for ch in text if ch in CN_NUM), None)
    if base is None:
        # 仅「半X」：无整数部分
        return (unit, half if half else 1.0, False)
    return (unit, base + half, False)


# ====================================================================
# 自检：对 quantifier_cases.jsonl 全量比对
# ====================================================================
if __name__ == "__main__":
    import json
    import os
    import sys

    cases_path = os.path.join(os.path.dirname(__file__), "quantifier_cases.jsonl")
    passed = failed = 0
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            unit, mult, fuzzy = quantifier_parse(c["input"])
            exp_u, exp_m, exp_f = c["expect_unit"], c["expect_multiplier"], c["expect_fuzzy"]
            ok = unit == exp_u and mult == exp_m and fuzzy == exp_f
            if ok:
                passed += 1
            else:
                failed += 1
                print(
                    f"  FAIL [{c['id']}] 「{c['input']}」 "
                    f"得 ({unit},{mult},{fuzzy}) 期望 ({exp_u},{exp_m},{exp_f})"
                )
    print(f"\n量词自检：{passed} 通过 / {failed} 失败 / 共 {passed + failed}")
    sys.exit(0 if failed == 0 else 1)
