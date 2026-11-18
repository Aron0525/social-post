# 术语词典

| 术语 | 定义 | 出处或依据 |
| --- | --- | --- |
| 完整帖 | 不以省略号收尾的帖子，全书 2071 条，长度中位 76 字 | `posts.jsonl` 截断核验 |
| 截断帖 | 以省略号收尾且长度落在 140 至 159 字的帖子，1981 条，推文字数上限造成的导出截断 | `candidates/05-boundary.md` C-0509 |
| 单句成帖 | 整帖压成一个可独立摘抄的判断句，628 帖占 15.5% | `candidates/01-structure.md` 01 |
| 断言领起 | 首句直接下判断，第二句只补一层细化、依据或第二人称担保 | `candidates/01-structure.md` 02 |
| 补证层 | 判断之后追加的那一层细化或依据，只允许一层 | `candidates/04-argument.md` 01 |
| 两句对举 | 字数相近、结构镜像的短句并置，不写连接词 | `candidates/02-syntax.md` 03 |
| 槽句 | 带可替换名词的固定句式，用于同构排比 | `candidates/02-syntax.md` 04 |
| 设问自答 | 问句压在首句且 ≤20 字，第二句立刻自答 | `candidates/02-syntax.md` 05 |
| 翻案句 | 先否定一个流行理解再给新定义，`不是……而是……` 397 帖占 9.8% | `candidates/02-syntax.md` 06 |
| 定义句 | `X 的第一性原理是 A，不是 B`，把抽象词重新钉一遍 | `candidates/02-syntax.md` 07 |
| 编号清单体 | 先报总数再逐项给 8 至 20 字短语，项内不展开 | `candidates/04-argument.md` 07 |
| 具体锚 | 替掉抽象程度词的硬数字、年龄、物件或最小案例 | `CAPABILITY_CARDS.md` concrete-anchor |
| 最小案例 | 带时间、人物、地点或数字里至少两项的事实片段，只写事实不写评价 | `candidates/04-argument.md` 05 |
| 分层对照 | 选一个切分维度，把同一判断按 3 至 4 段用同一句式铺开 | `candidates/04-argument.md` 08 |
| 收尾四型 | 金句判断、回扣开头、落到动作、留白短句 | `candidates/01-structure.md` 10 至 13 |
| 倒着删 | 从末段开始删总结、号召与解释性分句，只留最硬的一句 | `CAPABILITY_CARDS.md` closing |
| 绝对化断言 | 用「一定」「所有」「最」「永远不要」写成无例外的全称句 | `candidates/03-diction.md` 05、06 |
| 断言项 | 校验脚本标出、需要人工确认是否补限定条件的绝对化句 | `scripts/check_style.py` INFO 级 |
| 逗号句号比 | 全书 29374 比 10892，约 2.70 比 1，合格区间 2 比 1 至 3 比 1 | `stats.md` |
| strict_default_on | 默认 true 的开关，关闭与 human-writing 冲突的手法 | `candidates/05-boundary.md` C-0514 |
| 三重验证 | V1 来源充分性、V2 可执行性、V3 任务增益，本次按上游新版判据 | `verified.md` |
| Capability Bundle | 阶段 2 产出的唯一编译事实源，含 verified.yaml 与八张能力卡 | `.cangjie/capabilities/` |
| RIA 能力卡 | R 原文、I 自述、A1 案例、A2 触发、E 执行、B 边界六段 | `methodology/04-stage2-ria-plus.md` |
