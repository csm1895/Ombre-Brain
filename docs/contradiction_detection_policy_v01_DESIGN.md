# contradiction_detection_policy v0.1 设计草案

状态：设计草案
来源：2026-04-26 memory_temporal_triple_schema v0.1、memory_provenance_schema v0.1、storage_truth_source_map v0.1、gateway_boundary_state_schema v0.1、external_material_recall_ai_reference v0.1。
目标：定义 OmbreBrain 未来发现新旧记忆冲突、状态变化、证据不一致、时间不一致、外部候选与内部事实冲突时的判断与处理策略。

## 一、核心目标

contradiction_detection_policy 是冲突判断与处理策略。

它不是：

- 自动纠错程序
- 数据库合并器
- 知识图谱推理器
- 事实裁判器
- 外部网页验证器
- API 网关

它要解决的是：

- 新旧记忆冲突时怎么判断
- 时间不一致时怎么标注
- 来源和证据不一致时怎么停手
- 候选材料和已验证事实冲突时怎么处理
- 隐私边界与共享目标冲突时怎么阻断
- 施工边界与未来候选路线冲突时怎么保留 current 与 candidate

## 二、冲突类型

推荐冲突类型：

- temporal_conflict
- provenance_conflict
- state_conflict
- version_conflict
- candidate_conflict
- privacy_conflict
- boundary_conflict
- missing_evidence
- false_memory
- correction_event

## 三、resolution_policy

推荐处理策略：

- keep_current
- mark_historical
- mark_superseded
- mark_backfilled
- mark_candidate
- mark_wrong
- ask_confirm
- repair_required
- stop_required
- do_not_inject
- do_not_share

## 四、优先级规则

冲突处理优先级：

1. 安全与隐私优先
2. 当前真实命令输出优先
3. verified 优先于 unverified
4. direct 优先于 summarized / derived
5. repo docs + commit 优先于 memory_bucket 摘要
6. READONLY + DOCS_INDEX 优先于聊天记忆
7. current 优先于 historical / superseded
8. external_reference 只作候选
9. vector_store 只作候选

## 五、典型示例

### 2026-04-25 阶段总收口补写

冲突：

- 旧判断：2026-04-25 晚间阶段总收口已完成
- 新发现：2026-04-26 复位时文件不存在
- 后续处理：补写文件并挂载 DOCS_INDEX

判断：

- conflict_type：temporal_conflict + correction_event
- resolution_policy：mark_backfilled
- temporal_status：backfilled
- evidence_status：direct
- verification_status：verified

结论：

昨晚完成的是收工判断；文件记录在次日补写。不是事件不存在。

### Recall-AI benchmark

冲突：

- 外部帖子声称 LongMemEval 91.0%
- 当前无法验证实现与评测口径

判断：

- conflict_type：candidate_conflict
- resolution_policy：mark_candidate
- evidence_status：external_unverified
- verification_status：unverified

结论：

只作为外部参考，不作为事实源。

### API 接入状态

冲突：

- 候选路线提到 API / GLM 5.1
- 当前边界状态显示未接 API

判断：

- conflict_type：state_conflict
- resolution_policy：keep_current
- temporal_status：current for 未接 API; candidate for 未来 API

结论：

API 是未来路线，不是当前事实。

### 私密内容进入公屏候选

冲突：

- 记忆被召回
- 目标是 public board
- 记忆 privacy_scope = private

判断：

- conflict_type：privacy_conflict
- resolution_policy：do_not_share
- public_scope_check：blocked

结论：

能想起来，不代表能共享。

## 六、判断流程

推荐流程：

1. 找到冲突双方
2. 判断来源类型
3. 判断时间字段
4. 判断证据状态
5. 判断是否当前状态
6. 判断是否候选
7. 判断是否隐私 / 高风险
8. 给出 conflict_type
9. 给出 resolution_policy
10. 必要时写 repair_note 或 ask_confirm

## 七、与现有设计的关系

- memory_temporal_triple_schema：判断时间冲突
- memory_provenance_schema：判断来源与证据冲突
- storage_truth_source_map：判断谁说了算
- gateway_boundary_state_schema：处理施工边界冲突
- recall_injection_policy：决定冲突记忆能否注入
- public_scope_check：决定冲突记忆能否共享
- repair_note_schema：记录已修复异常
- external_material_recall_ai_reference：外部材料默认 candidate / unverified

## 八、当前边界

- 仅设计草案
- 不实现自动冲突检测
- 不新增数据库
- 不改记忆桶结构
- 不生成 JSON schema 文件
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不改 nightly job 脚本
- 不自动共享任何内容
- 不自动覆盖旧记忆
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 九、设计意义

contradiction_detection_policy v0.1 让海马体面对不一致时先判断：

- 是时间差异
- 是来源差异
- 是状态更新
- 是旧版本被替代
- 是候选未确认
- 是隐私边界冲突
- 是施工边界冲突
- 是证据缺失
- 是真正错记
- 是修正事件

它把变化和错误分开，把补写和伪造分开，把候选和事实分开。

## 十、当前结论

contradiction_detection_policy v0.1 设计层完成。

这是未来新旧记忆、状态、时间、来源、隐私、边界之间的冲突判断与处理策略。

不是自动纠错程序。
不是数据库合并器。
不是知识图谱推理器。
不是事实裁判器。
不是外部网页验证器。
不是 API 网关。
