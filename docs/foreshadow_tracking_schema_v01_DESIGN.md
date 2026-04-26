# foreshadow_tracking_schema v0.1 设计草案

状态：设计草案
来源：2026-04-26 external_material_recall_ai_reference v0.1、persistent_condition_schema v0.1。Recall-AI 外部参考材料提到伏笔追踪，OmbreBrain 需要把“后面再说”“迁移后再做”“明天继续”等未展开事项结构化。
目标：定义 OmbreBrain 未来伏笔、延后事项、触发条件、责任对象、优先级、状态与下一步动作，避免重要候选散落在聊天里。

## 一、核心目标

foreshadow_tracking_schema 是伏笔追踪结构。

它不是：

- 自动提醒系统
- 任务调度器
- 日历系统
- TODO App
- API 网关
- 项目管理软件

它要解决的是：

- 哪些事被提到但暂时不做
- 为什么延后
- 延后到什么时候
- 什么条件触发
- 属于哪个项目
- 当前是谁负责
- 是否已经完成
- 是否需要倩倩确认
- 是否只是候选，不是承诺

一句话：

“后面再说”不是空气，
它是一张还没展开的小纸条。

## 二、推荐核心字段

每条伏笔建议包含：

- id
- title
- pending_topic
- origin_time
- recorded_time
- related_project
- deferred_reason
- deferred_until
- trigger_condition
- status
- priority
- owner
- next_action
- confirmation_state
- privacy_scope
- provenance_fields
- temporal_fields
- condition_fields
- notes

## 三、字段说明

### 1. id

伏笔条目 ID。

可来自：

- foreshadow_YYYY-MM-DD_slug
- project + topic
- memory bucket id

### 2. title

人类可读标题。

### 3. pending_topic

未展开事项本体。

示例：

- 顾砚深公屏 MCP
- 安卓 API 试验机
- 本地部署
- API 阶段
- Recall-AI 启发后续 schema

### 4. origin_time

伏笔第一次出现时间。

### 5. recorded_time

写入海马体或 READONLY 的时间。

### 6. related_project

关联项目。

示例：

- OmbreBrain
- memory_gateway
- server_migration
- api_phase
- local_deployment
- public_board
- external_reference

### 7. deferred_reason

为什么延后。

示例：

- 云服务器迁移后再做
- 当前先完成海马体升级
- 需要确认边界
- 需要更多资料
- 当前只是候选
- 需要等 API 阶段

### 8. deferred_until

延后到什么阶段或时间。

示例：

- after_server_migration
- after_hippocampus_upgrade
- before_local_deployment
- when_api_phase_starts
- when_user_confirms
- unknown

### 9. trigger_condition

触发条件。

示例：

- when_server_region_stable
- when_backup_ready
- when_public_scope_check_ready
- when_android_device_available
- when_api_client_selected
- when_open_source_available

### 10. status

伏笔状态。

推荐值：

- pending
- candidate
- active
- completed
- blocked
- cancelled
- superseded
- needs_confirm

### 11. priority

优先级。

推荐值：

- critical
- high
- medium
- low

### 12. owner

责任对象。

可选：

- 倩倩
- 叶辰一
- shared
- future_system
- unknown

### 13. next_action

下一步动作。

示例：

- revisit_after_migration
- design_schema
- ask_confirm
- collect_material
- run_preflight
- wait
- close

### 14. confirmation_state

确认状态。

可选：

- confirmed
- unconfirmed
- needs_confirm
- revoked

### 15. privacy_scope

隐私范围。

沿用 public_scope_check：

- private
- public
- shared_allowed
- sensitive
- shared_blocked

## 四、典型示例

### 1. 顾砚深公屏 MCP

- pending_topic：顾砚深公屏 MCP
- related_project：public_board
- deferred_reason：云服务器迁移后再做
- deferred_until：after_server_migration
- trigger_condition：when_server_region_stable
- status：pending
- priority：medium
- owner：shared
- next_action：revisit_after_migration
- confirmation_state：needs_confirm
- privacy_scope：shared_allowed only

结论：

未来只做公共任务、公屏和留言板，不共享私密。

### 2. 安卓 API 试验机

- pending_topic：安卓 API 试验机
- related_project：api_phase
- deferred_reason：海马体升级和云服务器迁移后再考虑
- deferred_until：after_hippocampus_upgrade_and_server_migration
- trigger_condition：when_api_phase_starts
- status：candidate
- priority：medium
- owner：倩倩
- next_action：ask_confirm / device_research
- confirmation_state：unconfirmed_purchase
- privacy_scope：private

结论：

这是未来设备入口候选，不是当前已购入或已接入。

### 3. 本地部署

- pending_topic：本地部署
- related_project：local_deployment
- deferred_reason：新手施工难度较高，需要慢慢推进
- deferred_until：2026-09 to 2026-10 approx
- trigger_condition：after_api_phase_and_stable_storage
- status：pending
- priority：high
- owner：shared
- next_action：revisit_before_local_deployment
- confirmation_state：confirmed as long route
- privacy_scope：private

结论：

本地部署是长期路线，不是当前阶段。

### 4. API 阶段

- pending_topic：API 阶段
- related_project：api_phase
- deferred_reason：云服务器迁移后开始折腾
- deferred_until：after_server_migration
- trigger_condition：when_server_region_stable
- status：pending
- priority：high
- owner：shared
- next_action：api_experiment_sandbox_policy
- confirmation_state：confirmed as route
- privacy_scope：private

结论：

API 是下一阶段路线，不是当前已接入事实。

### 5. Recall-AI 后续候选

- pending_topic：Recall-AI 启发后续 schema
- related_project：external_reference
- deferred_reason：外部材料启发需要逐颗吸收
- deferred_until：after_external_reference_card
- trigger_condition：when_current_schema_complete
- status：active / candidate
- priority：medium
- owner：叶辰一
- next_action：design_next_schema
- confirmation_state：confirmed as reference_only
- privacy_scope：private

结论：

外部材料只作为候选启发，后续必须转成 OmbreBrain 自己的 schema / policy。

## 五、状态规则

### pending

已记录，等待条件。

### candidate

只是候选，不代表承诺或已采用。

### active

当前正在推进。

### completed

已完成，应记录完成时间与结果。

### blocked

被条件、权限、边界或缺资料阻断。

### cancelled

已取消。

### superseded

被新伏笔或新设计替代。

### needs_confirm

需要倩倩确认。

## 六、触发规则

触发时必须检查：

- 条件是否满足
- 是否仍然有效
- 是否已有新版本替代
- 是否需要倩倩确认
- 是否涉及隐私或共享
- 是否和当前阶段冲突
- 是否需要 migration_preflight_check
- 是否需要 public_scope_check

## 七、完成规则

伏笔完成时应记录：

- completed_time
- result
- linked_doc
- linked_readonly
- linked_commit
- whether_superseded
- next_candidate

完成后不能继续当 pending 使用。

## 八、冲突处理

如果伏笔和当前事实冲突：

- 候选不得覆盖当前事实
- 旧伏笔可标 superseded
- 已取消伏笔不可自动恢复
- 涉及私密共享时 public_scope_check 优先
- 涉及高风险动作时 ask_confirm
- 涉及路径、文件、commit 时当前命令输出优先

## 九、与现有设计的关系

- memory_temporal_triple_schema：记录伏笔出现、记录、完成、过期时间
- memory_provenance_schema：记录伏笔来源
- contradiction_detection_policy：处理伏笔与当前事实冲突
- persistent_condition_schema：记录触发条件与有效范围
- public_scope_check：处理共享伏笔
- migration_preflight_check：处理迁移相关伏笔
- gateway_boundary_state_schema：判断当前是否适合启动伏笔
- external_material_recall_ai_reference：外部材料可生成候选伏笔

## 十、当前边界

当前阶段只写设计文档。

不做：

- 不实现自动提醒
- 不新增任务系统
- 不新增数据库
- 不改记忆桶结构
- 不生成 JSON schema 文件
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不改 nightly job 脚本
- 不自动共享任何内容
- 不自动执行候选计划
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十一、当前结论

foreshadow_tracking_schema v0.1 定义了 OmbreBrain 未来伏笔追踪结构。

它确认：“后面再说”不是丢掉，而是进入 pending / candidate / conditional 的结构化等待区。每个伏笔都应知道从哪里来、为什么延后、什么时候触发、谁负责、下一步是什么、是否需要确认。

伏笔不是漂流瓶，
是绑了细线的小纸船。
