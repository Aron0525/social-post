# 淘汰记录 · 04-10 用「说到底」抽共性

- 阶段 1.5 三重验证，判定淘汰
- 来源 `candidates/04-argument.md` 候选 10
- 判定版本 上游新版 V1 来源充分性 / V2 可执行性 / V3 任务增益，附加旧版 V1 跨域门

## 判定

| 门 | 结果 |
| --- | --- |
| V1 来源充分性 | 不成立。全书仅 5 帖 |
| V2 可执行性 | 可执行，但属于禁用项 |
| V3 任务增益 | 负增益。触发 Aron 现行 `human-writing` 硬规则 |

## 证据

`posts.jsonl` 精确统计 `说到底` 命中 5 帖，占 4052 帖的 0.12%。`candidates/03-diction.md` 与 `BOOK_OVERVIEW.md` 都核到同一数字。原书里它承担收束与抽共性的功能，但这个量级说明作者本人也很少用，不足以称为手法。

`human-writing` 明令禁止「说到底」「说白了」「先说结论」「更微妙的是」这类洞察路标词。即使 `strict_default_on` 置 false，这一项仍在 `check_style.py` 的 always FAIL 组里，不受开关影响。

## 淘汰边界

淘汰整条候选。同类路标词与商业黑话一并登记为受限词表，见 `references/03-diction.md`。

## 去向

`check_style.py` 的洞察路标词规则设为 always FAIL。`BOOK_OVERVIEW.md` 已把初稿「在样本里反复出现」更正为「全书仅 5 帖，占比很低，不构成主要冲突」。
