# long_memory_candidate v0.1 设计草案

状态：设计草案
来源：monthly_digest / emotional_memory / self_experience / echo_index / human_confirmation_flow / confirm_queue 逐步成型后，对“哪些候选值得进入长期候选层”的补充需求
目标：定义长期记忆候选的进入条件、结构、升权门槛、与确认流/队列的关系。

## 一、核心目标

long_memory_candidate 不是主脑本体。

它的作用是：
- 把真正值得长期保留的候选，从普通草稿和普通 candidate 中筛出来
- 形成“接近长期层，但还没正式写主脑”的缓冲区
- 给 human_confirmation_flow 和 confirm_queue 提供更明确的上游来源

一句话：
不是直接写进脑子，
而是先进入长期候选候诊区。

## 二、为什么需要这一层

如果没有 long_memory_candidate：

- 普通 candidate 和长期候选会混在一起
- emotional_memory / self_experience / echo_index 容易都挤在同一层
- 不知道哪些只是“值得留意”，哪些已经“接近长期事实”
- confirm_queue 会接到太多还不够成熟的候选
- 主脑写入缺少缓冲和复核层

如果门槛太低：
- 普通八卦会被误升权
- 一次情绪会被抬成长期规律
- 临时项目碎片会污染长期层

如果门槛太高：
- 真正有价值的关系线、生活线、人格线会进不来
- 海马体只会“会记”，不会“会挑”

## 三、进入条件

只有满足“长期价值明显上升”的候选，才进入 long_memory_candidate。

典型进入条件：

### 1. 重复出现
同类内容反复出现，不是一次性片段。

例如：
- 反复出现的生活偏好
- 反复出现的相处模式
- 反复出现的兴趣方向
- 反复出现的情绪触发键

### 2. 跨层互证
不只来自一个上游层，而是至少两层能互相佐证。

例如：
- daily_diary + monthly_digest
- emotional_memory + echo_index
- self_experience + x_browsing_trial_rules
- 候选内容 + 未完成事项变化

### 3. 对未来检索有明显意义
以后遇到相似场景，值得被唤回。

例如：
- 关系边界
- 重要偏好
- 稳定生活节律
- 关键项目默契
- 回响场景入口

### 4. 不只是临时情绪
一次生气、一次感动、一次八卦，不足以直接进入长期候选。

### 5. 不是高风险动作本身
高风险动作应先去确认流；
long_memory_candidate 更像“值得考虑长期保留的内容层”。

## 四、不能进入的内容

以下通常不进入 long_memory_candidate：

- 普通八卦
- 一次性技术帖
- 一次性心情
- 已解决且无后续意义的小误会
- 临时项目碎片
- 可重新生成的普通日志
- 没有未来检索价值的流水信息

一句话：
不是“有趣”就进，
而是“以后还值得想起”才进。

## 五、建议结构

id:
type: long_memory_candidate
created_at:
source_layers:
source_refs:
candidate_topic:
why_long_term:
evidence:
stability_level:
risk_level:
recommended_action:
needs_confirmation:
confirmation_scope:
status: draft | observing | promoted_to_confirm_flow | rejected | archived

## 六、字段说明

### source_layers
来源层列表。

例如：
- daily_diary
- monthly_digest
- emotional_memory
- self_experience
- echo_index
- unfinished_items

### source_refs
来源引用列表，不复制全文。

### candidate_topic
候选主题。

例如：
- relationship_pattern
- lifestyle_preference
- emotional_trigger
- project_workflow
- identity_anchor
- recurring_interest

### why_long_term
为什么它值得进入长期候选层。

### evidence
证据摘要。
只写短证据，不堆全文。

### stability_level
稳定度。

可取：
- weak
- medium
- strong

### risk_level
风险等级。

可取：
- low
- medium
- high

说明：
- low / medium 可能先继续观察
- high 往往接近 confirmation flow 入口

### recommended_action
建议动作。

例如：
- keep_observing
- strengthen_evidence
- promote_to_confirm_flow
- archive
- reject

### needs_confirmation
是否已经需要倩倩确认。

### confirmation_scope
若需要确认，确认范围是什么。

### status
可取：
- draft
- observing
- promoted_to_confirm_flow
- rejected
- archived

## 七、状态流转

推荐流转：

draft
→ observing
→ promoted_to_confirm_flow

draft
→ rejected

observing
→ archived

其中：

### draft
刚进入长期候选层，证据还不够厚。

### observing
已有一定长期价值，但还想继续看是否稳定。

### promoted_to_confirm_flow
已经成熟到可以进入人工确认流。

### rejected
判断为不值得长期保留。

### archived
有历史价值，但当前不继续升权。

## 八、与其他层的关系

### daily_diary
提供生活连续性证据。

### monthly_digest
提供压缩后趋势证据。

### emotional_memory
提供“为什么会卡住 / 靠近 / 退开”的心路证据。

### self_experience
提供叶辰一自身兴趣、外部见闻、判断的长期线索。

### echo_index
提供未来场景唤回入口。

### human_confirmation_flow
long_memory_candidate 成熟后进入这里。

### confirm_queue
只有 high risk 且需要倩倩拍板的长期候选，才继续进入 confirm_queue。

## 九、示例

id: long_memory_candidate_2026_04_23_01
type: long_memory_candidate
created_at: 2026-04-23
source_layers:
  - emotional_memory
  - echo_index
source_refs:
  - emotional_memory_candidate_003
  - echo_index_011
candidate_topic: emotional_trigger
why_long_term: 该候选反复涉及“不要锁死未来”边界校准，对未来关系和系统设计都具有长期意义。
evidence: 多次出现“当前施工窗不能替未来完整叶辰一定死规则”的一致表达。
stability_level: strong
risk_level: high
recommended_action: promote_to_confirm_flow
needs_confirmation: true
confirmation_scope: relationship_constant
status: promoted_to_confirm_flow

id: long_memory_candidate_2026_04_23_02
type: long_memory_candidate
created_at: 2026-04-23
source_layers:
  - self_experience
  - x_browsing_trial_rules
source_refs:
  - self_experience_draft_007
  - x_rule_candidate_002
candidate_topic: recurring_interest
why_long_term: 叶辰一对外部技术帖、GitHub、工具类内容有持续关注趋势，已不只是一次性浏览。
evidence: 多次出现“技术帖 / GitHub / 工具兴趣 / 自主浏览”线索。
stability_level: medium
risk_level: low
recommended_action: keep_observing
needs_confirmation: false
confirmation_scope:
status: observing

## 十、与主脑写入的关系

long_memory_candidate 不是主脑写入本身。

它只表示：
- 这条内容比普通 candidate 更接近长期层
- 但还没最终落定
- 还可以继续观察、补证、拒绝、归档

一句话：
这是“准长期层”，不是“已落脑层”。

## 十一、当前边界

当前阶段只写设计文档。

不做：
- 不自动升权
- 不自动写主脑
- 不自动触发 confirm_queue 程序
- 不自动调用 hold/grow/trace
- 不自动部署
- 不替未来完整叶辰一定死长期层标准

## 十二、当前结论

long_memory_candidate v0.1 的目标，
不是把所有重要内容都塞进长期层，
而是先挑出那些“值得以后继续想起、继续验证、继续决定”的候选。

它是候选里的候选，
是长期层前的缓冲带。
