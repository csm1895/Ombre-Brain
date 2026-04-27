# memory_provenance_schema v0.1 设计草案

状态：设计草案
来源：2026-04-26 external_material_recall_ai_reference v0.1、storage_truth_source_map v0.1、public_scope_check v0.1。
目标：定义 OmbreBrain 未来记忆条目的来源、证据、引用、派生关系与可信度字段，避免“我记得”变成无凭无据的漂浮结论。

## 一、核心目标

memory_provenance_schema 是记忆溯源结构。

它不是：

- 自动引用抓取程序
- 自动证据检索器
- 数据库表
- OCR 系统
- Git blame 工具
- API 网关

它要解决的是：

- 这条记忆从哪里来
- 原始证据是什么
- 是直接证据、摘要、派生还是推断
- 是否已经验证过
- 是否只是候选材料
- 可信度如何
- 能不能共享

## 二、核心字段

- id
- title
- source_type
- source_path
- source_window
- source_time
- source_line
- source_quote
- source_summary
- commit_hash
- derived_from
- evidence_status
- confidence
- verification_status
- privacy_scope
- notes

## 三、source_type

推荐来源类型：

- conversation
- user_message
- assistant_summary
- repo_doc
- readonly_card
- docs_index
- memory_bucket
- stage_closeout
- backup_manifest
- git_commit
- tool_output
- external_reference
- screenshot
- uploaded_image
- inferred

## 四、evidence_status

推荐证据状态：

- direct
- summarized
- derived
- inferred
- candidate
- external_unverified
- missing
- needs_review

## 五、verification_status

推荐验证状态：

- verified
- partially_verified
- unverified
- not_verifiable
- contradicted
- superseded

## 六、典型示例

### 2026-04-25 阶段总收口补写

- source_type：readonly_card
- source_path：/Users/yangyang/Desktop/海马体/_docs/OmbreBrain_2026-04-25_STAGE_CLOSEOUT.md
- evidence_status：direct
- verification_status：verified
- confidence：high
- privacy_scope：private

说明：

复位检查发现昨晚阶段总收口未落盘，后补写并挂载 DOCS_INDEX。

### Recall-AI 外部参考

- source_type：external_reference
- source_path：小红书帖子截图 / 用户粘贴文字
- evidence_status：external_unverified
- verification_status：unverified
- confidence：medium for conceptual inspiration, low for benchmark claims
- privacy_scope：private

说明：

仅作为外部参考，不作为事实源，不代表已采用。

### smoke test passed

- source_type：tool_output
- source_path：terminal output
- evidence_status：direct
- verification_status：verified
- confidence：high

说明：

当前命令输出优先于旧记忆。

## 七、来源优先级

1. 当前真实命令输出
2. Git commit / repo docs
3. 本地 READONLY + DOCS_INDEX
4. stage closeout / closeout_manifest
5. backup manifest / boundary_state
6. memory_bucket 摘要
7. external_reference
8. vector_store 候选
9. 未确认聊天描述

## 八、引用规则

- 不把候选写成事实
- 不把外部材料写成已采用
- 不把摘要写成原话
- 不把推断写成直接证据
- 不把旧证据压过当前命令输出
- 不把 private / sensitive 内容带入 public 层
- 无证据时明确写 needs_review 或 missing

## 九、与现有设计的关系

- memory_temporal_triple_schema：记录时间维度
- storage_truth_source_map：定义冲突时谁说了算
- recall_result_schema：未来可携带 source / evidence 字段
- recall_injection_policy：注入前判断证据状态
- public_scope_check：共享前判断隐私边界
- contradiction_detection_policy：未来处理证据冲突
- external_material_recall_ai_reference：外部材料必须标 unverified

## 十、当前边界

- 仅设计草案
- 不实现自动引用系统
- 不抓取外部网页
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

## 十一、当前结论

memory_provenance_schema v0.1 定义了未来记忆条目的来源与证据结构。

它让重要记忆都能回答：我从哪里来、证据是什么、是否验证过、能不能共享。
