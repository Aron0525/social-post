# PIPELINE_STATE — 《旷野之心》写作手法蒸馏

> 断点续跑用。流水线为 cangjie-skill RIA-TV++，蒸馏对象从「书里的方法论」改为「书里的写作手法」，五路提取器按维度重新映射。

- 书：《旷野之心》2026 版，Morris，X @Morris_LT
- 源文件：`C:\Users\Aron\Desktop\旷野之心25年-26年3月.pdf`
- 产物目录：`E:\workbuddy\杂\books\kuangyezhixin\`
- 交付目录：`dist\kuangye-writing\`
- 输出模式：single（用户要求一份 skill，符合 single-first）
- 处理时间：2026-11-15

## 当前阶段

- [x] 阶段 0 整书理解 → `BOOK_OVERVIEW.md`。语料抽取 `analyze_corpus.py` 产出 `corpus.md`、`posts.jsonl`、`stats.md`、`samples.md`。
- [x] 阶段 1 五路并行提取 → `candidates\01-structure.md`（13 条）、`02-syntax.md`（12 条）、`03-diction.md`（11 条）、`04-argument.md`（11 条）、`05-boundary.md`（14 条）。共 61 条候选。第五路子代理被中断，由主流程按同规格补齐。
- [x] 阶段 1.5 三重验证 → `verified.md`。通过 42，降级为参考 14，淘汰 5。按上游新版 V1 来源充分性、V2 可执行性、V3 任务增益判定，附加旧版 V1 跨域门。
- [x] 阶段 1.6 晋级门 → 8 个能力卡全部走 `served_by` 路由入口，`promoted` 为空，可发现入口 1 个，低于软预算 8。
- [x] 阶段 2 RIA++ 能力卡 → `CAPABILITY_CARDS.md` 合订 8 张，`build_bundle.py` 拆入 `.cangjie\capabilities\cards\`。
- [x] 阶段 3 Zettelkasten 链接 → `CAPABILITY_CARDS.md` 末尾链接表、`GLOSSARY.md`、Bundle 的 `also_read`。
- [x] 阶段 4 压力测试 → `scripts\check_style.py` 实测三模式通过，见下方记录。
- [x] 阶段 5 编译与交付 → `DIGEST.md`、`dist\kuangye-writing\SKILL.md`、`references\` 七份、`scripts\check_style.py`、`examples\sample.md`。

## 阶段 4 实测记录

用 `examples\sample.md` 四段做触发评测，含一段合规短帖、一段含翻案句与冒号感叹号的违规帖、一段 116 字长句、一段省略号截断帖。

| 模式 | 结果 |
| --- | --- |
| 默认严格模式 | 段落 4，FAIL 7，WARN 2，退出码 1。合规段判 OK，违规段准确命中中文冒号、感叹号、翻案句、洞察路标词，长段命中句长 FAIL，截断段命中省略号 FAIL |
| `--corpus` 语料模式 | 已检 3，跳过截断 1，FAIL 5。截断段不参与收尾统计 |
| `--json` | 输出合法 JSON，summary 与 results 结构完整 |

这是脚本层实测，不是宿主内 skill 触发实测。真实触发评测留待安装后补做。

## 关键决议

1. 1981 帖以省略号收尾是推文字数上限造成的导出截断，不是文风。所有收尾结论只用 2071 条完整帖。
2. 2025/12 与 2026/01 无数据，不做时间演变判断。
3. 原书高频触犯 Aron 现行 `human-writing` 硬规则。设 `strict_default_on` 默认 true，冲突分级表见 `verified.md` 与 `candidates\05-boundary.md` C-0514。
4. 原书错别字与未经核实的数字不继承。事实数字须由用户提供或标注待核实。
5. 本机 cangjie-skill 的 SKILL.md 与上游仓库的三重验证判据不一致，本次按上游新版判定并附加旧版跨域门，两套结果在本书上无分歧。未改动已安装的 skill。

## 收尾自检（2026-11-15 补做）

- 修正关键决议 2 的日期笔误，`2015/12` 改为 `2025/12`。
- `verified.md` 两处编号自相矛盾已修。`cap.kuangye.closing` 的合并来源移除已淘汰的 02-12；淘汰表把「01-13 末句留白用省略号」改写为派生动作，明确 01-13 候选主体保留在 closing 能力卡。
- `rejected\` 补齐五张逐条审计卡，含 V1/V2/V3 判定、证据、淘汰边界与去向。
- 交付包改为自包含。新增 `capabilities\cards\` 八张卡、`capabilities\verified.yaml`、`capabilities\destinations.json`、`audit\` 四份、`rejected\` 五份。`SKILL.md` 内全部路径改指包内，Grep 复查无 `../../` 与 `.cangjie` 残留。
- `SKILL.md` 命令示例补 `--corpus` 一行。
- 复跑脚本三模式。默认严格模式 FAIL 7 / WARN 2，`--corpus` 已检 3 跳过截断 1 / FAIL 5，`--json` 输出合法 JSON。交付包共 30 个文件。

## 2026-11-15 边界变更（Aron 决定）

上游 `C:\Users\Aron\.workbuddy\skills\cangjie-skill\SKILL.md` 的 description 原写 `NOT for simple summarization, book reviews, or role-playing as the author`，Aron 要求把角色扮演改成可以。该文件四处同步改动。description 与 description_en 补上角色扮演支持，description_zh 补中文，正文边界段把「作者人设角色扮演」从不做移到做，生态定位段注明不再强制转交 nuwa-skill。

本交付包跟着放开。`dist\kuangye-writing\SKILL.md` 的 description 补角色扮演触发词，使命段删掉「不扮演作者」，调用判断加角色扮演一档，新增路径四给出七步执行契约，硬规则加第 11 条，不学清单把「作者人设」换为「冒用真实账号身份与编造书中没有的观点」，末尾加版本说明。

`candidates\` 与 `references\` 五路文件里「不含模仿作者人设、扮演作者」是阶段 1 的提取范围说明，按审计轨迹原样保留，不覆盖旧结论，与本变更记录并列存档。

`strict_default_on` 默认值不变，角色扮演不改变它。`human-writing` 里「不创建作者画像、个人规则库」的规则仍在，两者适用范围不同，本次未改动该 skill。

## 2026-11-15 第二次变更 · 作者画像与协作风格

Aron 要求 skill 能生成作者个人画像、协作风格等内容。上游 `C:\Users\Aron\.workbuddy\skills\cangjie-skill\SKILL.md` 三处 description 补触发词，边界段加一项，流水线图阶段 5 补 `PERSONA.md`，新增「作者画像与协作风格」整节，定义 A / B / C 三层证据标注、九个必填字段、阶段映射与四条硬约束。

下游 `dist\kuangye-writing\SKILL.md` 的 description 补触发词，使命段改为五条路径，调用判断加人设卡一档，新增路径五给出七步执行契约，硬规则加第 12 条，文件清单补四行，版本说明同步。

新增四份产物。`PERSONA.md` 是基于全书语料生成的真实人设卡，`scripts\analyze_persona.py` 是可复现的统计脚本，`audit\persona_stats.md` 是证据快照，`data\posts.jsonl` 是随包分发的 4052 帖语料。画像卡的引用逐条用 `posts.jsonl` 核验过 id、日期、页码与原文，主题分布与语气标记由脚本输出，不凭印象写。

证据分层是这次的关键判断。语料是单向发布短帖，没有对话记录，所以协作风格九维全部标 B 层，写成设计约定而非作者真实互动实录。生平、职业、真实互动归 C 层，留空不推断。用户补充新材料时可把字段从 C 或 B 升到 A，新旧结论并列保留。

`human-writing` 第 166 行「不建立长期作者画像」是成文规范，与拆书流水线不同场景，本次未改动。`strict_default_on` 默认值不变。

## 下一步

流水线全部完成，交付包已可独立安装。未做的事只有安装与宿主内真实触发验证，两件都需要 Aron 点头。把 `dist\kuangye-writing\` 复制到 `C:\Users\Aron\.workbuddy\skills\kuangye-writing\` 完成安装，再跑一次真实触发验证。若要接入 darwin-skill 自动进化，可把 `examples\sample.md` 扩成带兄弟诱饵与互斥负例的评测集。

安装前需按宿主规则做 skill 安全审计。本包为本地生成，不含外部下载代码，`scripts\check_style.py` 只读输入、不联网、不删文件。

## 2026-11-15 安装与打包整理

Aron 要求「整理成一个 skill 包」，本次完成安装前的规范性修复与安装。

修了三处。`capabilities\verified.yaml` 顶层 mapping 后直接跟 sequence，是非法 YAML，`yaml.safe_load` 报 `expected <block end>, but found '-'`。把 8 条能力收进 `capabilities:` 键下并缩进，字段一字未改，重解析通过，`card` 路径 8 条全部命中。`SKILL.md` 末尾统计口径段引用了包外的 `corpus.md` 与裸 `posts.jsonl`，改为 `data\posts.jsonl` 并说明按行 Grep 的命中数不作准，顺带注明 `audit\` 与 `rejected\` 是审计痕迹、日常不必加载。新增 `BUILD_MANIFEST.json`，记 34 个文件的 sha256 与 `bundle_sha256`，供后续更新时比对本地手改。

安装到 `C:\Users\Aron\.workbuddy\skills\kuangye-writing\`，35 个文件，2.1 MB。脚本层验收五项全过。默认严格模式 FAIL 7 / WARN 2，`--corpus` 已检 3 跳过截断 1 / FAIL 5，`--no-strict` FAIL 5 / WARN 2，`--json` 输出合法 JSON 且 summary 与 results 结构完整，stdin 通道正常。`analyze_persona.py` 重跑后 `audit\persona_stats.md` 的 sha256 与原文件一致，结果可复现。frontmatter 解析通过，`name`、`description`（532 字）与 `metadata.strict_default_on=true` 均就位，SKILL.md 内 19 处文件引用在安装后全部命中。

安全审计结论，两个脚本都只用标准库，`check_style.py` 读入稿件或 stdin 后只打印，`analyze_persona.py` 只写包内 `audit\persona_stats.md`，均不联网、不删文件、不执行外部命令，无 P0 与 P1 风险。

未做的是宿主内真实触发评测。这一项需要在本机会话里对着 skill 列表实测，属于运行时验证，不是文件层能确认的。

