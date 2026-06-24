# 吾食谈记 Demo

跑通「记录→纠正→隔会话沿用」最小闭环。核心差异化——量词映射的纠正复用——做成可当面演示、可部署访问的网页闭环。

本仓库是从吾食谈记主项目抽出的独立可部署快照：`score.py` 是主项目 `eval/score.py` 的同源裁剪版（只保留 `parse`/`normalize_dish`，去掉了评测专用的三层评分函数），其余文件与主项目 `demo/` 目录一致。

## 本地跑起来

```bash
pip install -r requirements.txt
python app.py    # → http://127.0.0.1:5000
```

需仓库根目录有 `.env`（不进 git），内含 `DEEPSEEK_API_KEY`（解析层与营养估算都走真 DeepSeek V4-Flash）。

## 30 秒演示脚本

1. 输入「中午吃了一拳米饭」→ 出「待确认」徽章，AI 估的克数。
2. 点「纠正分量」→ 改成你的量（如 280g）→ 选「以后这道菜都按这个」→ 保存。右侧记忆库出现 `(米饭, 拳) → 280g`。
3. 点「+ 新会话」（清空对话、**记忆库保留**，触发一次零上下文解析）。
4. 再输入「中午吃了一拳米饭」→ 出「命中个人记忆」徽章，直接 280g。**它记住了。**
5. 加分：「两拳米饭」→ 自动 560g（存的是 单位×倍数 结构，非记死字符串）；「一拳馒头」→ 不套 280（不同食物名不同 key）。

## 结构

| 文件 | 职责 |
|---|---|
| `app.py` | Flask 后端，串主流程 |
| `score.py` | 解析层：DeepSeek 结构化解析 + 菜名归一化（同源裁剪版） |
| `quantifier.py` | 量词→(单位, 倍数, fuzzy) 确定性分解 |
| `memory.py` | 个人记忆库 key=(食物名,单位)→基准克重，SQLite 持久化 |
| `estimate.py` | AI 估熟重营养密度 + 单份基准克重 |
| `templates/index.html` | 单页前端：对话 + 记忆库面板 + 纠正/新会话，含 ≤600px 响应式断点 |
| `selfcheck_reuse.py` | 复用逻辑确定性自检（不接 LLM） |

## 硬不变量落地

1. 记忆 key 直接复用 `score.py` 的 `normalize_dish(parse() 的 L1)`，与主项目评测同源。
2. 「新会话」是真·零上下文解析：`parse()` 每次只传 system+本句，从不串对话历史；复用值只来自 `memory_store.db`（DB 注入）。
3. 读/写两端记日志（`[memory]`/`[parse]`），命中漏了能归因。

## 自检

```bash
python quantifier.py        # 量词分解 23/23（对 quantifier_cases.jsonl）
python selfcheck_reuse.py   # 复用逻辑 9/9（命中×倍数 / 防误套 / 取最新 / 删除后失效）
```

## 部署（Railway）

1. Railway 连接本仓库，构建器会按 `requirements.txt` 装依赖、按 `Procfile` 启动（`gunicorn app:app --bind 0.0.0.0:$PORT`）。
2. 加环境变量 `DEEPSEEK_API_KEY`。
3. `memory_store.db`（SQLite）写在容器本地文件系统——同一次部署运行期内跨浏览器会话不丢，但重新部署/重启会重置。这版只保证前者；如需跨部署持久要挂 Railway Volume。
4. 部署出 URL 后，把 `templates/index.html` 顶部的 `API_BASE` 改成该 URL（前端与后端不同源时还需要 `app.py` 里已配的 CORS 白名单覆盖到实际来源）。

## 已知简化（仅作用于本 demo 验证物）

- 阈值激活门：不实现，认用户显式「记住」意图。
- 自定义食物：未做。
- 油量/成分声明：桩（仅展示原文，不入星）。
