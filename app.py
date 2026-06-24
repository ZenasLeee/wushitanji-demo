"""
吾食谈记 Demo — 后端
=====================

跑通主流程：自然语言 → 解析 → 查记忆 → 命中/待确认 → 营养估 → 可纠正。

硬不变量：
  #1 记忆 key 建在 score.py 同源 normalize_dish 管线上（直接 import，不另造）。
  #2 「新会话」是真·零上下文 LLM 调用：parse() 每次只传 system+本句 user，从不串对话历史；
     复用值只来自 memory（DB 注入），不来自对话。结构上即满足。
  #3 读/写两端记日志（见 memory.py + 下方解析日志）。

本仓库是从吾食谈记主项目里抽出的独立可部署 demo 快照（score.py 为同源裁剪版，
仅保留 parse/normalize_dish，去掉了主项目 eval 工具链里评测专用的部分）。
"""

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from score import parse, normalize_dish
import memory
from quantifier import quantifier_parse
from estimate import estimate

app = Flask(__name__)
CORS(app, origins=["capacitor://localhost", "http://localhost"])

_UNPARSEABLE = {"无法解析", "__PARSE_FAILED__"}


def _round(x):
    return int(round(x))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/record", methods=["POST"])
def record():
    text = (request.get_json(force=True) or {}).get("text", "").strip()
    if not text:
        return jsonify({"dishes": [], "unparseable": True})

    parsed = parse(text)
    print(f"[parse] 输入「{text}」 → l1={parsed['l1']}", flush=True)

    dishes = [d for d in parsed.get("l1", []) if d not in _UNPARSEABLE]
    if not dishes:
        return jsonify({"dishes": [], "unparseable": True})

    canon = {d: normalize_dish(d) for d in dishes}
    est = estimate(list({canon[d] for d in dishes}))

    results = []
    for d in dishes:
        food = canon[d]
        q = parsed.get("l2", {}).get(d, "未提供")
        unit, mult, fuzzy = quantifier_parse(q)
        oil = parsed.get("l3", {}).get(d, "无")
        e = est.get(food, {"base_g": 200, "kcal100": 150, "protein100": 5, "fat100": 5, "carb100": 15})

        # 模糊修饰不查记忆库、不可持久化（ADR-020）；无单位（份/个/块）不可复用
        reusable = bool(unit) and not fuzzy

        hit = False
        base_gram = None
        if reusable:
            mem = memory.get(food, unit)
            if mem is not None:
                hit = True
                base_gram = mem
        if base_gram is None:
            base_gram = e["base_g"]

        # 有单位（含模糊）→ 克数 = 基准 × 倍数；无单位 → 直接用 AI 单份克数
        grams = base_gram * mult if unit else base_gram

        nf = grams / 100.0
        results.append({
            "food": food,
            "raw_quantifier": q,
            "unit": unit,
            "multiplier": mult,
            "fuzzy": fuzzy,
            "reusable": reusable,
            "can_remember": reusable,   # 仅闭集单位、非模糊可教记忆
            "hit": hit,
            "pending": not hit,
            "base_gram": base_gram,
            "grams": _round(grams),
            "oil": oil if oil and oil != "无" else None,
            "nutrition": {
                "kcal": _round(e["kcal100"] * nf),
                "protein": _round(e["protein100"] * nf),
                "fat": _round(e["fat100"] * nf),
                "carb": _round(e["carb100"] * nf),
            },
        })

    return jsonify({"dishes": results, "unparseable": False})


@app.route("/api/remember", methods=["POST"])
def remember():
    """显式「以后这道菜都按这个」+ 记住 → 写 (食物,单位)→基准克重。"""
    body = request.get_json(force=True) or {}
    food = (body.get("food") or "").strip()
    unit = (body.get("unit") or "").strip()
    base_gram = body.get("base_gram")
    if not food or not unit or base_gram is None:
        return jsonify({"ok": False, "error": "缺 food/unit/base_gram"}), 400
    saved = memory.set_base(food, unit, base_gram)
    return jsonify({"ok": True, "base_gram": saved})


@app.route("/api/memory", methods=["GET"])
def memory_list():
    return jsonify({"entries": memory.list_all()})


@app.route("/api/memory/delete", methods=["POST"])
def memory_delete():
    body = request.get_json(force=True) or {}
    food = (body.get("food") or "").strip()
    unit = (body.get("unit") or "").strip()
    ok = memory.delete(food, unit)
    return jsonify({"ok": ok})


@app.route("/api/new_session", methods=["POST"])
def new_session():
    """会话边界：清可见对话（前端做），记忆库不动。后端无状态，此处仅记日志。"""
    print("[session] 新会话：清空可见对话，记忆库保留", flush=True)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
