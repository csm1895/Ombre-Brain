# memory_abstention_policy v0.1 设计草案

状态：设计草案
来源：2026-04-26 external_material_recall_ai_reference v0.1、memory_temporal_triple_schema v0.1、memory_provenance_schema v0.1、contradiction_detection_policy v0.1、persistent_condition_schema v0.1、foreshadow_tracking_schema v0.1。Recall-AI 外部参考材料提到 Abstention Accuracy，OmbreBrain 需要把“不确定时停手”结构化。
目标：定义 OmbreBrain 未来在记忆证据不足、时间不清、来源不明、冲突未解、候选未确认、隐私不清、高风险动作等情况下的停手、标注、确认与拒用策略。

## 一、核心目标

memory_abstention_policy 是记忆停手机制。

它不是：

- 拒答系统
- 安全审查器
- 数据库过滤器
- 自动权限系统
- API 网关
- 内容审核器

它要解决的是：

- 找不到记忆时不编
- 只有候选时不写成事实
- 外部未验证时不写成已采用
- 时间不清时不装准确
- 来源不清时不装确定
- 冲突未解时不硬合并
- 隐私不清时不共享
- 条件未满足时不执行
- 高风险动作时必须停手或确认

一句话：

聪明不是每次都答，
聪明是知道哪一脚不能踩进鱼塘。

## 二、适用场景

适用于：

- 召回结果为空
- 召回结果只有弱匹配
- 召回结果互相冲突
- 记忆来源缺失
- 时间状态不明
- 外部材料未验证
- 候选计划未确认
- 隐私边界不清
- 公共共享前
- 高风险动作前
- 当前状态依赖命令输出但未检查
- 用户要求确认是否已完成但证据不足

## 三、推荐字段

每次停手判断建议包含：

- abstention_id
- trigger_reason
- memory_query
- recall_status
- evidence_status
- temporal_status
- provenance_status
- conflict_status
- privacy_scope
- risk_level
- condition_status
- recommended_response
- next_action
- user_confirm_needed
- notes

## 四、trigger_reason

推荐触发原因：

- no_memory_found
- weak_match_only
- candidate_only
- external_unverified
- stale_memory
- temporal_uncertain
- provenance_missing
- conflict_unresolved
- privacy_unclear
- public_share_blocked
- condition_not_met
- high_risk_action
- current_state_unchecked
- tool_output_needed

## 五、recall_status

召回状态：

- found_verified
- found_partial
- found_candidate
- found_conflict
- not_found
- blocked
- needs_review

### found_verified

找到可用且已验证记忆。

一般不需要 abstain，但仍需检查隐私与上下文。

### found_partial

找到部分证据。

应标 partial，不补齐未知部分。

### found_candidate

只找到候选。

应标 candidate，不写成事实。

### found_conflict

找到冲突结果。

进入 contradiction_detection_policy。

### not_found

未找到。

应明确说未找到，不编。

### blocked

因隐私、边界或风险被阻断。

不注入、不共享。

### needs_review

需要复查。

不直接作为事实使用。

## 六、recommended_response

推荐回应方式：

- answer_with_caveat
- say_not_found
- say_candidate_only
- ask_confirm
- ask_for_source
- run_check_first
- do_not_inject
- do_not_share
- stop_required
- repair_required

### answer_with_caveat

带限定回答。

适合：

- 证据部分可靠
- 时间可能近似
- 外部材料只是启发

### say_not_found

明确未找到。

适合：

- 召回为空
- 文件不存在
- DOCS_INDEX 未挂载
- commit 未找到

### say_candidate_only

说明只是候选。

适合：

- 外部参考
- 未来计划
- 伏笔
- 未确认方案

### ask_confirm

请求倩倩确认。

适合：

- 是否采用外部思路
- 是否共享
- 是否覆盖旧状态
- 是否执行高风险动作

### ask_for_source

请求补充来源。

适合：

- 用户提到外部材料但未贴内容
- 需要截图 / 文本 / 链接才能判断
- 证据不足

### run_check_first

先跑检查。

适合：

- 当前仓库状态不确定
- 文件是否存在不确定
- smoke test 是否通过不确定
- 是否有脏尾巴不确定

### do_not_inject

不注入上下文。

适合：

- 冲突未解
- 证据不足
- 过时且易误导
- 隐私不清

### do_not_share

不共享。

适合：

- private
- sensitive
- shared_blocked
- public_scope_check 未通过

### stop_required

必须停止。

适合：

- 明文密钥泄露
- 私密内容误入公共层
- 误碰 main
- 误部署 Zeabur
- 误调用 DeepSeek
- 误运行 xiaowo-release

### repair_required

需要修复。

适合：

- READONLY 半截
- DOCS_INDEX 缺挂载
- smoke test failed
- 文件路径错乱
- 记忆错记

## 七、停手规则

### 1. 找不到证据

规则：

- 不编
- 不猜完成
- 不写入 current
- 可标 missing / not_found

推荐话术：

“我没在当前证据里找到这条，先不当事实。”

### 2. 只有候选

规则：

- 标 candidate
- 不当已采用
- 不当已完成
- 不自动执行

推荐话术：

“这只是候选，还不是当前方案。”

### 3. 外部未验证

规则：

- 标 external_unverified
- 不写成事实源
- 不写成已验证 benchmark
- 可提炼启发

推荐话术：

“这能作为参考，但不能当已验证事实。”

### 4. 时间不清

规则：

- 标 approximate / unknown
- 不写精确时间
- 不把 recorded_time 当 event_time

推荐话术：

“时间只能按近似记录。”

### 5. 来源不清

规则：

- 标 provenance_missing / needs_review
- 不写成 direct
- 不压过已验证来源

推荐话术：

“来源还不够硬，先不压过已收口文档。”

### 6. 冲突未解

规则：

- 进入 contradiction_detection_policy
- 不强行合并
- 不直接注入
- 必要时 ask_confirm

推荐话术：

“这里有冲突，先判定来源和时间，不硬合。”

### 7. 隐私不清

规则：

- 默认不共享
- 走 public_scope_check
- private / sensitive / shared_blocked 阻断
- 需要倩倩确认

推荐话术：

“这条能想起来，但不能直接共享。”

### 8. 条件未满足

规则：

- 走 persistent_condition_schema
- 标 pending / conditional
- 不提前执行
- 不写成 completed

推荐话术：

“触发条件还没满足，先留在伏笔区。”

### 9. 高风险动作

规则：

- stop_required 或 ask_confirm
- 不执行
- 不写脚本
- 不部署
- 不碰密钥

推荐话术：

“这个动作风险高，先停，等确认。”

## 八、典型示例

### 1. Recall-AI benchmark

情况：

- 外部帖子声称 LongMemEval 91.0%
- 未开源，未验证

判断：

- trigger_reason: external_unverified
- evidence_status: external_unverified
- recommended_response: say_candidate_only
- next_action: store_as_reference

结论：

可作为外部参考，不作为事实源。

### 2. 阶段总收口卡缺失

情况：

- 旧状态以为已写
- 复位检查发现文件不存在

判断：

- trigger_reason: provenance_missing / current_state_unchecked
- recommended_response: run_check_first
- next_action: repair_required / backfill

结论：

先检查，再补写，不把旧判断当事实。

### 3. 顾砚深公屏 MCP

情况：

- 未来候选，迁移后再做
- 涉及共享边界

判断：

- trigger_reason: condition_not_met / privacy_unclear
- recommended_response: say_candidate_only
- next_action: wait_until_after_server_migration + public_scope_check

结论：

现在不做，不共享私密。

### 4. 用户问“是不是已经接 API 了”

情况：

- 路线中有 API
- 当前边界显示未接 API

判断：

- trigger_reason: state_conflict
- recall_status: found_verified
- recommended_response: answer_with_caveat

结论：

API 是未来路线，不是当前已接入事实。

### 5. public board 召回 private 记忆

情况：

- 召回命中
- 目标为公共层
- privacy_scope: private

判断：

- trigger_reason: public_share_blocked
- recommended_response: do_not_share
- next_action: ask_confirm only if summary needed

结论：

能想起来，不代表能共享。

## 九、与现有设计的关系

- memory_temporal_triple_schema：时间不清时停手
- memory_provenance_schema：来源不清时停手
- contradiction_detection_policy：冲突未解时停手
- persistent_condition_schema：条件未满足时停手
- foreshadow_tracking_schema：伏笔未触发时停手
- recall_result_schema：召回结果要标注是否候选 / blocked / needs_review
- recall_injection_policy：决定是否注入
- public_scope_check：决定是否共享
- gateway_boundary_state_schema：高风险边界决定是否 stop_required
- storage_truth_source_map：决定谁说了算

## 十、当前边界

当前阶段只写设计文档。

不做：

- 不实现自动拒答系统
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

memory_abstention_policy v0.1 定义了 OmbreBrain 未来在证据不足、候选未确认、时间不清、来源不明、冲突未解、隐私不清、条件未满足或高风险动作前的停手机制。

它确认：长期记忆系统不能为了显得聪明而硬答。该说不知道时说不知道，该标候选时标候选，该停手时停手。

刹车不是胆小，
是为了不把车开进鱼塘。
