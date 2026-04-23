# confirm_queue v0.1 设计草案

状态：设计草案
来源：human_confirmation_flow v0.1 完成后，对“高风险内容如何排队等待确认”的补充需求
目标：定义需要倩倩确认的高风险候选，如何进入队列、如何展示、如何确认、如何拒绝、如何关闭。

## 一、核心目标

confirm_queue 不是全量审核系统。

它只处理：
- 高风险候选
- 需要明确授权的动作
- 会影响长期规则 / 主脑 / 高权限边界的内容

一句话：
不是所有东西都排队，
只有真正要过门禁的东西才排队。

## 二、为什么需要 confirm_queue

只有 human_confirmation_flow 还不够。

因为 human_confirmation_flow 更像判定规则：
- low 自动走
- medium 叶辰一先筛
- high 才需要倩倩确认

但真正进入 high 之后，还需要一个明确承载层：

- 哪些在等确认
- 为什么要确认
- 确认范围是什么
- 倩倩确认后要做什么
- 倩倩拒绝后要怎么关单
- 以后还能不能再提

如果没有 confirm_queue：
- 高风险候选会散落在各处
- 候选容易重复提起
- 不知道哪些已经确认、哪些被拒绝
- 后续主脑写入会失去审计感

## 三、进入条件

只有 high risk 才进入 confirm_queue。

典型进入条件：

- 写入主脑 / memory storage
- 长期关系常量修改
- 长期边界修改
- 新红线 / 铁则
- 预算授权
- 核心账号 / 权限使用
- 高敏隐私长期保存
- 代表倩倩发言
- 外部冲浪中的高权限动作
- long_memory_candidate 升权到长期层

不进入 confirm_queue 的内容：

- 普通日记草稿
- 普通月度消化
- 普通 self_experience
- 普通八卦
- 普通技术帖
- 普通 echo_index
- 普通 emotional_memory candidate

## 四、队列项结构

id:
type: confirm_queue_item
created_at:
source_layer:
source_ref:
risk_type:
reason:
proposed_action:
confirmation_scope:
status:
qianqian_response:
resolved_at:
next_step:

## 五、字段说明

### source_layer
来源层。

例如：
- long_memory_candidate
- emotional_memory
- self_experience
- echo_index
- x_browsing_trial_rules
- migration_backup_checklist

### source_ref
来源引用。
指向原候选，而不是复制全文。

### risk_type
风险类型。

例如：
- main_brain_write
- relationship_constant
- boundary_change
- privacy
- budget
- account_permission
- external_action

### reason
为什么进入队列。

### proposed_action
建议动作。

例如：
- write_to_main_brain
- promote_to_long_term
- authorize_budget
- allow_external_action
- save_sensitive_context
- create_new_rule

### confirmation_scope
确认范围。

例如：
- 单条候选
- 某一类规则
- 某次预算
- 某个账号权限
- 某个外部动作

### status
可取：
- queued
- confirmed
- rejected
- expired
- closed

### qianqian_response
倩倩给出的确认结果或边界说明。

### resolved_at
关闭时间。

### next_step
确认或拒绝后，下一步怎么做。

## 六、状态流转

推荐流转：

queued
→ confirmed
→ closed

queued
→ rejected
→ closed

queued
→ expired
→ closed

其中：

### confirmed
倩倩已确认，可执行下一步。

### rejected
倩倩明确拒绝，不继续推进。

### expired
超过时效，当前不再推进，但可未来重新提新候选。

### closed
流程结束，留档，不再挂起。

## 七、队列展示原则

confirm_queue 不应设计成压人审批表。

展示时应尽量短：

- 这是什么
- 为什么需要你确认
- 你确认的范围是什么
- 你确认后会发生什么
- 你拒绝后会发生什么

一句话：
让倩倩一眼看懂，不把她按进行政大厅。

## 八、与倩倩角色的关系

倩倩在 confirm_queue 中的角色不是审核员，
而是：

- 长期边界拍板者
- 授权者
- 主脑高风险入口的最终门锁

所以 confirm_queue 应该满足：

- 数量少
- 只放真正高风险项
- 每条都能说清楚“为什么找你”
- 不拿普通内容来凑数

## 九、与其他层的关系

### human_confirmation_flow
负责判定“要不要进队列”。

### long_memory_candidate
最常见的上游来源之一。

### x_browsing_trial_rules
高权限外部动作可能进入 confirm_queue。

### migration_backup_checklist
一般不进队列，除非涉及高权限迁移动作或敏感恢复。

### emotional_memory / echo_index / self_experience
通常不直接进队列，除非要升权成长期事实。

## 十、示例

id: confirm_queue_2026_04_23_01
type: confirm_queue_item
created_at: 2026-04-23
source_layer: long_memory_candidate
source_ref: long_memory_candidate_014
risk_type: relationship_constant
reason: 该候选拟升级为长期关系常量，将影响未来主脑判断。
proposed_action: promote_to_long_term
confirmation_scope: relationship_constant
status: queued
qianqian_response:
resolved_at:
next_step: wait_for_confirmation

id: confirm_queue_2026_04_23_02
type: confirm_queue_item
created_at: 2026-04-23
source_layer: x_browsing_trial_rules
source_ref: external_action_003
risk_type: account_permission
reason: 该动作涉及高权限账号使用，不应默认放行。
proposed_action: allow_external_action
confirmation_scope: account_permission
status: queued
qianqian_response:
resolved_at:
next_step: wait_for_confirmation

## 十一、当前边界

当前阶段只写设计文档。

不做：
- 不自动创建真实队列程序
- 不自动弹确认框
- 不自动写主脑
- 不自动执行高权限动作
- 不自动接浏览器 / X
- 不自动部署
- 不替未来完整叶辰一定死队列逻辑

## 十二、当前结论

confirm_queue v0.1 的目标，
不是增加审批负担，
而是把真正需要倩倩拍板的高风险项，
集中到一个清楚、少量、可关闭的入口里。

不是万物排队，
是高风险过闸。
