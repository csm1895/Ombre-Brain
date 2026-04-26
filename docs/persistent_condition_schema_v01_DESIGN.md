# persistent_condition_schema v0.1 设计草案

状态：设计草案
来源：2026-04-26 external_material_recall_ai_reference v0.1、memory_temporal_triple_schema v0.1、memory_provenance_schema v0.1、contradiction_detection_policy v0.1。Recall-AI 外部参考材料提到“持久条件”，OmbreBrain 需要把长期有效、阶段有效、条件有效、已过期、需要确认的设定结构化。
目标：定义 OmbreBrain 未来长期条件、阶段条件、触发条件、失效条件、确认条件与隐私条件的记录方式，避免把一次性事件误当长期规则，也避免长期约定在迁移、换窗、换模型后丢失。

## 一、核心目标

persistent_condition_schema 是持久条件结构。

它不是：

- 自动规则引擎
- 数据库表
- 权限系统
- 提醒系统
- API 网关
- 本地部署程序

它要解决的是：

- 哪些内容长期有效
- 哪些内容只在某一阶段有效
- 哪些内容满足条件才有效
- 哪些内容已经过期
- 哪些内容需要倩倩确认
- 哪些内容不能自动共享
- 哪些内容是候选，不是当前事实
- 如何避免旧条件压过当前状态

一句话：

有些记忆是事件，
有些记忆是门规。

## 二、推荐字段

每条持久条件建议包含：

- id
- title
- condition_type
- condition_status
- scope
- trigger
- valid_from
- valid_until
- invalidation_rule
- confirmation_required
- privacy_scope
- source
- evidence_status
- related_memory
- notes

## 三、condition_type

推荐类型：

- long_term
- stage_bound
- conditional
- candidate
- temporary
- deprecated
- private_boundary
- technical_boundary
- migration_boundary

### 1. long_term

长期有效条件。

示例：

- 私密不共享
- 外部材料不直接写成事实
- 当前命令输出优先于旧记忆
- 核心海马体平台无关

### 2. stage_bound

阶段有效条件。

示例：

- PR #2 Open 期间不 Merge
- nightly-job-v01-readonly 分支施工期间不动 main
- 当前阶段只做设计，不接 API

### 3. conditional

条件触发后有效。

示例：

- 服务区迁移前必须先收口
- 稳定云服务区选定后做本地保存与备份
- 云服务器迁移后再考虑顾砚深公屏 MCP
- 海马体升级后再考虑安卓 API 试验机

### 4. candidate

候选条件。

示例：

- GLM 5.1 作为未来 model_adapter 候选
- 安卓手机作为未来 API App 试验机候选
- Recall-AI 启发的多层检索漏斗候选

### 5. temporary

临时条件。

示例：

- 当前窗口内暂停新设计，先看外部材料
- 当前先用剪贴板写入法绕开 heredoc
- 当前只读检查，不写文件

### 6. deprecated

已过期条件。

示例：

- 旧路径判断被修正
- 旧写入方式被替代
- 旧状态被新状态覆盖

### 7. private_boundary

私密边界条件。

示例：

- private / sensitive / shared_blocked 不进入公屏
- 共享前必须走 public_scope_check
- 私密不共享给顾砚深公屏

### 8. technical_boundary

技术边界条件。

示例：

- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release
- 不接 API
- 不接 GLM 5.1
- 不接本地模型

### 9. migration_boundary

迁移边界条件。

示例：

- 服务区迁移前先阶段收口
- 迁移前必须有 backup manifest
- 迁移前必须有 boundary_state
- 迁移前必须排除敏感信息

## 四、condition_status

推荐状态：

- active
- inactive
- candidate
- pending_confirm
- expired
- superseded
- blocked
- unknown

### active

当前有效。

### inactive

当前不生效，但不一定过期。

### candidate

候选条件，不能写成当前事实。

### pending_confirm

需要倩倩确认后才生效。

### expired

已过期。

### superseded

被新条件替代。

### blocked

被隐私、安全或边界规则阻断。

### unknown

状态不明，需要复查。

## 五、scope

作用范围。

推荐值：

- global
- project
- branch
- stage
- conversation
- memory_gateway
- backup
- migration
- public_board
- private_relationship
- model_adapter
- device_adapter

## 六、trigger

触发条件。

示例：

- before_server_migration
- after_stable_region
- before_local_deployment
- before_public_share
- before_backup_package
- when_external_material
- when_conflict_detected
- when_api_experiment
- when_user_confirms

## 七、invalidation_rule

失效规则。

示例：

- user_updates
- new_version_replaces
- stage_closed
- migration_completed
- explicit_cancel
- contradicted_by_verified_source
- privacy_block
- time_expired

## 八、confirmation_required

是否需要倩倩确认。

推荐值：

- yes
- no
- high_risk_only
- before_write
- before_share
- before_execute

## 九、典型示例

### 1. 私密不共享

- title: 私密不共享
- condition_type: private_boundary
- condition_status: active
- scope: global / public_board
- trigger: before_public_share
- confirmation_required: before_share
- privacy_scope: private / sensitive / shared_blocked
- source: public_scope_check
- evidence_status: direct
- notes: 顾砚深公屏只共享公共任务、施工状态、交接摘要等，私密不共享。

### 2. 服务区迁移前先收口

- title: 服务区迁移前先收口
- condition_type: migration_boundary
- condition_status: active
- scope: migration
- trigger: before_server_migration
- confirmation_required: no
- source: storage_adapter_policy / migration_preflight_check
- evidence_status: direct
- notes: 迁移前必须完成阶段收口、成果清单、READONLY、DOCS_INDEX、smoke test、boundary_state、敏感信息排除与回滚说明。

### 3. GLM 5.1 候选模型

- title: GLM 5.1 model_adapter candidate
- condition_type: candidate
- condition_status: candidate
- scope: model_adapter
- trigger: future_api_stage
- confirmation_required: before_execute
- source: apple_ecosystem_api_entry
- evidence_status: summarized
- notes: 倩倩偏好 GLM 5.1，但当前未接入，不是当前事实。

### 4. 安卓 API 试验机候选

- title: Android API experiment device candidate
- condition_type: candidate
- condition_status: candidate
- scope: device_adapter
- trigger: after_hippocampus_upgrade_and_server_migration
- confirmation_required: before_execute
- source: user_message
- evidence_status: direct
- notes: 倩倩考虑云服务器迁移后购买安卓手机，用于更多可接 API 的 App 试验。

### 5. 2026-04-25 阶段总收口补写

- title: 2026-04-25 stage closeout backfill
- condition_type: stage_bound
- condition_status: active for historical closeout record
- scope: stage
- trigger: restore_previous_stage_record
- confirmation_required: no
- source: memory_temporal_triple_schema
- evidence_status: direct
- notes: 事件发生在 2026-04-25，记录补写在 2026-04-26，标 backfilled，不误判为冲突。

## 十、读取规则

读取持久条件时必须判断：

1. condition_status 是否 active
2. condition_type 是长期、阶段、条件、候选还是临时
3. scope 是否匹配当前场景
4. trigger 是否满足
5. 是否需要确认
6. 是否有隐私边界
7. 是否被新条件替代
8. 是否只是 candidate

## 十一、写入规则

写入持久条件时必须判断：

- 是否真的长期有效
- 是否只是阶段规则
- 是否只是候选
- 是否需要时间字段
- 是否需要来源证据
- 是否需要 confirmation_required
- 是否涉及隐私边界
- 是否会覆盖旧规则

禁止：

- 把一次性事件写成长期条件
- 把候选路线写成当前事实
- 把外部材料写成已采用
- 把旧条件压过当前命令输出
- 未确认时自动共享

## 十二、与现有设计的关系

- memory_temporal_triple_schema：记录条件的时间状态
- memory_provenance_schema：记录条件来源与证据
- contradiction_detection_policy：处理条件冲突
- public_scope_check：处理私密与共享边界
- gateway_boundary_state_schema：记录施工技术边界
- migration_preflight_check：处理迁移前条件
- storage_truth_source_map：判断条件冲突时谁说了算
- foreshadow_tracking_schema：未来记录延后事项与触发条件

## 十三、当前边界

当前阶段只写设计文档。

不做：

- 不实现规则引擎
- 不新增数据库
- 不改记忆桶结构
- 不生成 JSON schema 文件
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不改 nightly job 脚本
- 不自动共享任何内容
- 不自动执行条件
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十四、当前结论

persistent_condition_schema v0.1 定义了 OmbreBrain 未来持久条件的结构。

它确认：长期规则、阶段规则、条件触发、候选计划、私密边界和迁移边界必须分开记录，不能把“以后可能”写成“现在已经”。

事件会过去，
门规要留牌。
