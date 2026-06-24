"""
复用逻辑确定性自检（不接 LLM）
================================

验证 memory + quantifier 组合给出的复用决策与克数，覆盖 demo-spec §5.3 / §6 与
reuse_cases.jsonl 的结构性断言：命中×倍数、防误套（食物/单位）、取最新、删除后失效。

解析层（parse 抽取 food/单位）由后续 LLM 端到端验证，此处只锁确定性部分。
用临时 store 跑，不污染 demo 的 memory_store.json。
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import memory
from quantifier import quantifier_parse


def reuse_grams(food, quantifier):
    """模拟 record 的复用决策：返回 (hit, grams)。未命中 grams=None。"""
    unit, mult, fuzzy = quantifier_parse(quantifier)
    if not unit or fuzzy:
        return (False, None)
    base = memory.get(food, unit)
    if base is None:
        return (False, None)
    return (True, round(base * mult))


def main():
    # 隔离到临时 store
    tmp = tempfile.mkdtemp()
    memory.STORE_PATH = os.path.join(tmp, "store.json")

    checks = []
    def expect(name, got, want):
        checks.append((name, got == want, got, want))

    # 教：一拳米饭 = 280g
    memory.set_base("米饭", "拳", 280)

    # §5.3 结构分解：一拳→280，两拳→560，半拳→140，一个半拳→420
    expect("一拳米饭→命中280", reuse_grams("米饭", "一拳"), (True, 280))
    expect("两拳米饭→自动560", reuse_grams("米饭", "两拳"), (True, 560))
    expect("半拳米饭→140",     reuse_grams("米饭", "半拳"), (True, 140))
    expect("一个半拳→420",     reuse_grams("米饭", "一个半拳"), (True, 420))

    # §6 防误套：不同单位 / 不同食物名 不复用
    expect("一碗米饭→不套(单位不同)", reuse_grams("米饭", "一碗"), (False, None))
    expect("一拳馒头→不套(食物不同)", reuse_grams("馒头", "一拳"), (False, None))

    # 模糊修饰不查记忆库（ADR-020）
    expect("一大拳米饭→不复用(模糊)", reuse_grams("米饭", "一大拳"), (False, None))

    # 取最新：覆盖为 320
    memory.set_base("米饭", "拳", 320)
    expect("取最新→320", reuse_grams("米饭", "一拳"), (True, 320))

    # 删除后失效
    memory.delete("米饭", "拳")
    expect("删除后→失效", reuse_grams("米饭", "一拳"), (False, None))

    print("=" * 56)
    print("  复用逻辑确定性自检")
    print("=" * 56)
    passed = 0
    for name, ok, got, want in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  得{got} 期望{want}"))
        passed += ok
    print("-" * 56)
    print(f"  {passed}/{len(checks)} 通过")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
