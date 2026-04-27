# memory_temporal_triple_schema v0.1 设计草案

状态：设计草案
来源：2026-04-26 external_material_recall_ai_reference v0.1、stage_boundary_snapshot v0.1、storage_truth_source_map v0.1。
目标：定义 OmbreBrain 未来记忆条目的三时态结构，用于区分事情什么时候发生、什么时候被知道、什么时候被写入记录，以及何时被更新或替代。

## 一、核心目标

memory_temporal_triple_schema 是记忆时间结构。

它不是：

- 知识图谱实现
- 数据库表
- 时间推理引擎
- 自动纠错器
- 向量库
- API 网关

它要解决的是：

- 事情实际发生在什么时候
- 我们什么时候知道这件事
- 什么时候把它写进海马体、READONLY、DOCS_INDEX 或仓库
- 后续什么时候更新过这条记忆
- 旧状态是否已经被新事实替代
- 是否属于补写、候选、历史、过时或当前有效

## 二、核心字段

- event_time：事情实际发生时间
- known_time：系统 / 叶辰一 / 倩倩知道这件事的时间
- recorded_time：写入海马体、READONLY、DOCS_INDEX、记忆桶或仓库的时间
- updated_time：后续更新这条记忆的时间
- superseded_time：被新事实替代的时间

## 三、推荐完整字段

- id
- title
- event_time
- known_time
- recorded_time
- updated_time
- superseded_time
- temporal_status
- source_time_hint
- certainty
- source
- source_path
- derived_from
- notes

## 四、temporal_status

推荐状态：

- current
- old_but_valid
- historical
- corrected
- superseded
- stale
- wrong
- backfilled
- candidate

## 五、关键示例

### 2026-04-25 阶段总收口补写

- event_time：2026-04-25 22:00 approx
- known_time：2026-04-25 22:14 approx
- recorded_time：2026-04-26 15:55 approx
- updated_time：2026-04-26 15:55 approx
- temporal_status：backfilled
- source：readonly_card
- source_path：/Users/yangyang/Desktop/海马体/_docs/OmbreBrain_2026-04-25_STAGE_CLOSEOUT.md

说明：

昨晚已完成收工判断，但文件未落盘，次日复位时补写。recorded_time 晚于 event_time，不改变事件本身发生在 2026-04-25 晚间。

### Recall-AI 外部参考

- event_time：unknown
- known_time：2026-04-26 16:10 approx
- recorded_time：2026-04-26 17:20 approx
- temporal_status：candidate
- source：external_reference

说明：

外部材料仅作启发来源，未验证，不作为事实源。

## 六、时间冲突处理原则

- 当前真实命令输出优先于旧记忆
- 明确用户时间戳优先于推断时间
- 文件 recorded_time 不等于事件 event_time
- 补写记录必须标 backfilled
- 被新事实替代的旧状态标 superseded 或 historical
- 外部材料没有明确时间时标 unknown 或 approximate
- 不能把候选材料写成 current

## 七、与现有设计的关系

- storage_truth_source_map：定义不同信息类型以哪里为准
- gateway_boundary_state_schema：记录当前边界状态
- stage_boundary_snapshot：记录某一刻阶段快照
- recall_result_schema：未来可携带 temporal_status
- recall_injection_policy：注入前判断是否 current / stale / candidate
- contradiction_detection_policy：未来处理时间冲突与事实冲突
- memory_provenance_schema：未来记录来源与溯源
- external_material_recall_ai_reference：提供三时态启发来源

## 八、当前边界

- 仅设计草案
- 不实现知识图谱
- 不新增数据库
- 不改记忆桶结构
- 不生成 JSON schema 文件
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不改 nightly job 脚本
- 不自动共享任何内容
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 九、当前结论

memory_temporal_triple_schema v0.1 定义了未来记忆条目的三时态结构。

它让海马体能区分：事情什么时候发生、我们什么时候知道、什么时候写入、后来是否更新或被替代。
