"""
营养 + 基准克重估算 — AI 直接估熟重（DeepSeek）
===============================================

承 demo-spec §4 / §5.4 / ADR-014：
- 营养层真·AI 估，不接库、不编死数。
- 营养以「每 100g 熟重密度」返回 → 最终营养 = 密度 × 克数 / 100。
  纠正分量后营养自动流转（用户确认的口径）。
- 同时给「单份/单单位熟重克数」基准，作未命中（含模糊修饰）时的兜底基准克重。

一餐一次调用，按菜名批量返回。零上下文（每次独立 system+user），不串对话历史。
"""

import json
import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

_client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

_SYSTEM = """你是饮食营养估算器。给你一组中文菜名，为每道菜估算熟食的营养与一份基准克重。只输出 JSON，不要任何解释或 markdown。

# 输出格式
{菜名: {"base_g": 整数, "kcal100": 整数, "protein100": 数字, "fat100": 数字, "carb100": 数字}, ...}
- 菜名必须和输入逐字一致。
- base_g：这道菜「一份/一个标准单位」的熟重克数（普通成年人一次摄入的常见量）。整数。
- kcal100 / protein100 / fat100 / carb100：每 100g 熟重的热量(千卡)/蛋白质(克)/脂肪(克)/碳水(克)。
- 取常识中位值，不要走极端。所有字段必填，不得为 null。

# 示例（仅供格式参考）
输入：["米饭","番茄炒蛋"]
输出：{"米饭":{"base_g":200,"kcal100":116,"protein100":2.6,"fat100":0.3,"carb100":25.9},"番茄炒蛋":{"base_g":250,"kcal100":95,"protein100":5.2,"fat100":6.8,"carb100":4.0}}"""


def estimate(dishes):
    """批量估算。入参 dishes: [菜名]。返回 {菜名: {base_g, kcal100, protein100, fat100, carb100}}。"""
    if not dishes:
        return {}
    resp = _client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": json.dumps(dishes, ensure_ascii=False)},
        ],
        extra_body={"thinking": {"type": "disabled"}},
        response_format={"type": "json_object"},
        temperature=0,
    )
    raw = (resp.choices[0].message.content or "").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    # 兜底：缺项填中性默认，避免 UI 空白
    out = {}
    for d in dishes:
        v = data.get(d) or {}
        out[d] = {
            "base_g": int(v.get("base_g") or 200),
            "kcal100": int(v.get("kcal100") or 150),
            "protein100": float(v.get("protein100") or 5),
            "fat100": float(v.get("fat100") or 5),
            "carb100": float(v.get("carb100") or 15),
        }
    return out
