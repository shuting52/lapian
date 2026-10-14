---
name: "video_deconstruction"
description: "拉片：以1:1复刻为目标，全维度逐镜头拆解用户上传的视频，输出复刻提示词并逐镜头生成验证一致性。全域类型覆盖：AI电商、影视短剧、动作模仿、白模视频等。用于视频拉片、镜头学习、复刻重拍；不做视频剪辑。"
---

# 视频拉片与复刻提示词

## Purpose
输入一条用户上传的视频，输出拉片表和逐镜头复刻提示词：按提示词重新生成，应能得到与原片镜头设计一模一样的视频。

## Workflow
1. **建档。** 运行 `scripts/probe_video.py <视频路径>`，记录时长、分辨率、画幅比、帧率、音频轨道，写入任务目录 `meta.json`。
2. **抽帧。** 运行 `scripts/extract_frames.py <视频路径> <输出目录>`：按场景切换抽关键帧，另加每秒 1 帧兜底。抽帧图只用于分析，不交付。
3. **切镜头与音频初检。** 先跑 `scripts/detect_cuts.py <视频> cuts.json` 得候选切点——注意手持素材里快速甩镜也会触发检测器，候选不等于切点。对可疑处跑 `scripts/zone_montage.py <视频> <起始秒> <时长> <out.jpg>` 建 10fps 联络表核验：相邻小图内容瞬间跳变是硬切，带方向性动态模糊渐变是连续甩镜。再编号 SH01、SH02…，记录每镜头的起止 timecode（秒，保留 1 位小数），首尾相接、无断档无重叠。镜头清单写入 `shots.json`，格式：`{"shots": [{"id": "SH01", "start": 0.0, "end": 3.2}]}`。同时跑 `scripts/analyze_audio.py <视频> audio.json` 得音量与静音段。
4. **类型识别。** 运行 `scripts/classify_video.py <视频> meta.json cuts.json audio.json` 得类型建议（含证据）——只是建议，必须人工确认后写入 `lapian.md`；拿不准就走全维度流程（[全域类型指南](references/domains.md) 通用兜底）。确认的类型决定第 5 步的逐帧拆解粒度，见 domains.md 各类型条目。
5. **逐镜头拉片（含逐帧拆解与同步建表）。** 逐张看抽帧图，按[镜头语言](references/shot-language.md)填写每镜头的：景别、机位角度、运镜（方向/速度/起止状态）、主体与动作、构图、光影影调、色彩倾向、转场方式、画面文字/字幕、音频。动作类镜头按第 4 步确认的类型跑对应粒度的逐帧拆解（舞蹈/动作模仿默认 10fps 联络表、动作节拍精确到 0.5 秒；换装变身加 morph 区联络表与运动曲线；见 domains.md）。音频内容类型（配乐/现场声/对白）必须人耳确认，无法确认标 `[待确认]`，不许从音量推断。有人声的视频逐句转录台词/旁白（带 timecode）写入 `transcript.md`。最后按[音画同步指南](references/sync-guide.md)建成 `sync-map.md`：每个时间片内画面、动作节拍、台词、BGM、自然音/音效六层对齐，变速段标出倍速。
6. **写复刻提示词。** 每个镜头一条，套用[提示词模板](assets/replica-prompt-template.md)：画面描述 + 运镜 + 时长 + 画幅 + 风格 + 音频说明 + 禁止项；动作节拍与变速要求从 `sync-map.md` 原样搬入，不简化。先完成拉片表再写提示词，不跳过。
7. **自检交付。** 跑 `scripts/detect_black.py <视频> black.json` 确认黑场/淡出——几帧的短黑尾是硬收尾，不是淡出，如实记录不写成淡出。再跑 `scripts/verify_lapian.py shots.json meta.json` 做机器自检（编号连续、timecode 首尾相接、总时长一致），最后对照 Output Contract 人工检查；看不清或不确定的信息标 `[待确认]`，不编造。完整写法见[完整示例](references/worked-example.md)。
8. **生成验证（必做）。** 按[复刻生成](references/replica-generation.md)逐镜头生成复刻片段（受单次生成数量上限约束时分批并如实告知用户），抽帧与原片同位置帧并排对比，按[一致性核对表](references/fidelity-checklist.md)逐项记录；再按 `sync-map.md` 装配音画（原片音轨取段、变速段重定时、台词对轴），用[音画同步指南](references/sync-guide.md)的核验方法检查同步，结论写入 `consistency-report.md`。有不一致处先修提示词/时间轴再重新生成，直到用户接受或生成上限用尽。

## 模式 B：AI 电商复刻（在拉片交付物基础上继续）

输入：原视频 + 用户产品实拍图 + 用户口播文案，输出"结构 1:1、画面全换"的带货复刻视频。
前置：原片已走完上面 8 步，拿到 `shots.json` / `meta.json` / `sync-map.md` / `replica-prompts.md`。
完整流程见 [AI 电商复刻模式](references/ecommerce-remake.md)，6 步：

1. **建换皮计划。** 跑 `scripts/remake_plan.py shots.json meta.json copy.txt products/ -o remake-plan.json`：
   逐镜头分配 timecode、口播文案、字幕槽位、产品图引用；`swap` 字段（原主体→新主体/新背景）留待第 3 步填。
   文案段数 ≠ 镜头数时先对齐文案，不动时间轴。
2. **抽帧定构图。** 沿用 `extract_frames.py` 抽每镜关键帧，人工确认构图后再开工生成。
3. **写重绘提示词。** 套用 `assets/remake-prompt-template.md`：景别/运镜/构图/光影从原片照搬，
   主体换成用户产品 + 新场景；**双 reference**（对标关键帧定构图 + 实拍产品图定产品），产品主体禁止纯文本生成。
4. **生成与质检。** 逐镜头生成 → 抽帧并排对比 → 按 `domains.md` 电商条目核对产品外观/Logo/文字不错位；
   AI 生成画面显著打标。
5. **TTS 配音。** 口播文案逐镜转语音（`voice/SH01.wav`…）；单镜配音超长时改文案或调语速，不许动时间轴。
6. **装配与交付。** 跑 `scripts/assemble_remake.py remake-plan.json clips/ voice/ -o remake.mp4`，
   再跑 `scripts/verify_remake.py remake-plan.json remake.mp4` 质检，人工对照一致性核对表后交付。

## Output Contract
在任务目录下交付：
- `lapian.md`：拉片表（镜头编号 / timecode / 景别 / 运镜 / 内容一句话 / 音频），格式见[拉片模板](references/analysis-template.md)
- `replica-prompts.md`：逐镜头复刻提示词，每条可独立投喂视频生成模型
- `consistency-report.md`：逐镜头一致性结论（对上的项 / 没对上的项 / 修正记录），含同步核验结论
- `transcript.md`：台词/旁白逐句转录（带 timecode），无对白时写"无"
- `sync-map.md`：音画同步时间轴（时间/画面/动作节拍/台词/BGM/自然音-音效六层对齐）
- `shots.json`：镜头清单（机器可读，供 verify 脚本校验）
- `meta.json`：视频元数据（机器可读）
- `cuts.json` / `audio.json` / `black.json`：切点候选、音频分析、黑场检测的机器可读记录

模式 B（AI 电商复刻）额外交付：
- `remake-plan.json`：换皮计划（每镜 timecode / 口播文案 / 字幕槽位 / 产品图引用 / swap 待填项），`remake_plan.py` 生成
- `remake-prompts.md`：逐镜头换皮重绘提示词（套用 `assets/remake-prompt-template.md`，双 reference 声明）
- `remake.mp4`：复刻成片（`assemble_remake.py` 装配，总时长与原片误差 ≤0.5s，配音只编码一次 AAC）

## Operating Rules
1. 只分析用户本次上传的视频；不确定的画面细节标注 `[待确认]`，绝不编造。
2. 每条复刻提示词必须自包含：画幅比、时长秒数、运镜、主体、风格、禁止项缺一不可。
3. timecode 精确到 0.1 秒，镜头之间首尾相接。
4. 原片音频/画面仅可用于本片的复刻验证（如为复刻版铺原片音轨），不得用于其他用途或对外发布；不承诺逐帧像素级一致，目标是镜头设计一模一样。
5. 用户的语言偏好优先；默认中文输出。
6. **1:1 复刻是硬目标。** 解析不允许用概括代替细节；单个镜头的提示词必须包含复刻所需的全部视觉要素；看不清的标 `[待确认]`，不省略、不编造。
7. **提示词必须跑通生成验证。** 每个镜头至少生成一条复刻片段，抽帧与原片对比，一致性结论写入 `consistency-report.md`；未经生成验证的提示词不得交付为"可复刻"。
8. **全域类型覆盖。** 不预设视频类型，任何视频走同一套全维度流程；各类型关键维度见[全域类型指南](references/domains.md)；某维度不适用填"不适用"，不跳过思考。
9. **音画同步是复刻的一部分。** 动作节拍、台词/旁白、BGM、自然音/音效都要有时间轴，装配时按 `sync-map.md` 对齐；同步核验不通过不得交付。
10. **类型先识别后确认。** 每个视频先跑 `classify_video.py` 得类型建议，人工确认后再拉片；建议与人工判断冲突时以人工为准，并记录原因。
11. **1:1 验收门。** 交付"可复刻"前，`consistency-report.md` 必须满足：所有适用项 ✅；❌ 项有修正记录或明确标注工具限制；零未核验项。达不到就继续迭代，不粉饰、不降级交付。
12. **时长 1:1。** 复刻版总时长必须与原片一致（误差不超过 0.5 秒）；分段复刻时段数按总时长规划，交叉淡化时长计入总时长。
13. **产品主体必须用实拍图（模式 B）。** AI 不画产品主体；重绘提示词必须声明双 reference（对标关键帧定构图 + 实拍产品图定产品）；
    产品 logo/颜色/款式走样即返工，能看清产品的镜头宁可用实拍图直接合成。
14. **换皮三件套（模式 B）。** 只换产品、文案、背景；镜序、每镜时长、字幕条样式/位置、转场、节奏一律不动。
15. **不搬运（模式 B）。** 不直接使用原片画面、原片口播文案、原片水印/logo；AI 生成画面显著打标；文案用用户自己的口播；
    "1:1"指结构复刻（镜头数/时长/转场/字幕样式对齐），不是像素复制——接单时先说清。
