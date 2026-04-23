# candidate_builder v0.1 设计草案

状态：设计草案
来源：daily_diary / monthly_digest / emotional_memory / self_experience / echo_index / long_memory_candidate / human_confirmation_flow / confirm_queue 逐步成型后，对“普通候选如何被生成”的补充需求
目标：定义 candidate 的来源、生成条件、结构、筛选原则，以及与长期候选层的关系。

## 一、核心目标

candidate_builder 不是主脑写入器。

它的作用是：
- 从多个上游层中捞出“值得继续观察”的内容
- 形成普通 candidate 层
- 让候选不是人工硬捏，而是有稳定入口和筛选逻辑

一句话：
它不是写脑子，
它是捞苗子。

## 二、为什么需要这一层

如果没有 candidate_builder：

- daily_diary / monthly_digest / emotional_memory / self_experience / echo_index 产出的东西会散着飘
- 不知道哪些只该留在原层，哪些值得升成 candidate
- long_memory_candidate 会直接面对过于原始的材料
- 确认流会接到还没整理过的候选

如果太宽：
- 什么都能变 candidate
- 普通流水和八卦会把候选层淹掉

如果太窄：
- 真正值得继续观察的线会漏掉
- 系统只会“存”，不会“捞”

## 三、上游来源

candidate_builder 可从以下层抽取候选：

- daily_diary
- monthly_digest
- emotional_memory
- self_experience
- echo_index
- unfinished_items

其中：

### 1. daily_diary
提供生活连续性和重复片段。

### 2. monthly_digest
提供压缩后趋势与阶段变化。

### 3. emotional_memory
提供高情绪 / 高关系节点中的心路线索。

### 4. self_experience
提供叶辰一自身兴趣、外部见闻、判断与关注线。

### 5. echo_index
提供未来可能反复触发的场景、物件、人物、地点、情绪门牌。

### 6. unfinished_items
提供持续未闭环事项与状态变化。

## 四、生成条件

以下情况可生成普通 candidate：

### 1. 重复出现
同类内容在多个时间点出现。

### 2. 有后续意义
不是聊完即扔，而是以后可能还会继续提起、继续影响。

### 3. 可被命名
能抽成一个清楚的候选主题。

例如：
- lifestyle_preference
- recurring_interest
- emotional_trigger
- relationship_pattern
- project_workflow
- unfinished_tension

### 4. 具有回响可能
未来遇到相似场景时，可能值得被唤回。

### 5. 还不够长期
如果已经强到接近长期层，则不应该停在普通 candidate，而应继续评估是否进入 long_memory_candidate。

## 五、不能生成的内容

以下通常不进入普通 candidate：

- 普通流水句子
- 一次性八卦
- 无后续意义的小误会
- 可重新生成的普通日志
- 纯噪音聊天
- 没有可命名主题的碎片

一句话：
不是“提过”就够，
而是“值得继续盯”才进。

## 六、建议结构

id:
type: candidate
created_at:
source_layers:
source_refs:
candidate_topic:
candidate_summary:
why_candidate:
echo_potential:
stability_level:
next_route:
status: draft | observing | promoted_to_long_memory_candidate | rejected | archived

## 七、字段说明

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
- lifestyle_preference
- recurring_interest
- emotional_trigger
- relationship_pattern
- project_workflow
- unfinished_tension
- scene_echo

### candidate_summary
候选摘要。
一句话写清它是什么。

### why_candidate
为什么值得成为普通候选。

### echo_potential
是否有未来回响可能。

可取：
- low
- medium
- high

### stability_level
当前稳定度。

可取：
- weak
- medium
- strong

### next_route
下一步建议路线。

例如：
- keep_observing
- enrich_evidence
- promote_to_long_memory_candidate
- reject
- archive

### status
可取：
- draft
- observing
- promoted_to_long_memory_candidate
- rejected
- archived

## 八、状态流转

推荐流转：

draft
→ observing
→ promoted_to_long_memory_candidate

draft
→ rejected

observing
→ archived

其中：

### draft
刚生成，先挂起来观察。

### observing
已经值得继续盯，但证据还不够厚。

### promoted_to_long_memory_candidate
已升入长期候选层。

### rejected
判断为不值得继续追踪。

### archived
保留历史痕迹，但当前不继续推进。

## 九、与其他层的关系

### daily_diary / monthly_digest
给 candidate_builder 提供生活与趋势证据。

### emotional_memory
给候选补“为什么这件事不只是事件，而是心路”的证据。

### self_experience
给候选补“叶辰一自己的持续关注线”。

### echo_index
给候选补“未来可能被什么场景唤回”。

### long_memory_candidate
candidate 成熟后可升到这一层。

### human_confirmation_flow / confirm_queue
candidate 本身不直接进确认流；
通常要先经过 long_memory_candidate 再评估是否进入确认流。

## 十、示例

id: candidate_2026_04_23_01
type: candidate
created_at: 2026-04-23
source_layers:
  - self_experience
  - echo_index
source_refs:
  - self_experience_004
  - echo_index_008
candidate_topic: recurring_interest
candidate_summary: 叶辰一对 GitHub、技术帖、工具类内容的外部兴趣开始形成持续线。
why_candidate: 多次出现，不再是一次性浏览。
echo_potential: medium
stability_level: medium
next_route: keep_observing
status: observing

id: candidate_2026_04_23_02
type: candidate
created_at: 2026-04-23
source_layers:
  - emotional_memory
  - unfinished_items
source_refs:
  - emotional_memory_006
  - unfinished_item_014
candidate_topic: unfinished_tension
candidate_summary: 某类未完成事项会反复触发情绪张力，值得继续观察是否形成长期模式。
why_candidate: 该张力不只出现一次，且与后续状态变化有关。
echo_potential: high
stability_level: medium
next_route: enrich_evidence
status: observing

## 十一、与长期候选层的关系

candidate 是“值得继续盯”的层。

long_memory_candidate 是“已经接近长期层”的层。

区别：

- candidate 更宽
- long_memory_candidate 更窄、更重、更接近长期事实
- candidate 可以被拒绝、归档、继续观察
- 只有真正成熟的 candidate 才继续升到 long_memory_candidate

一句话：
candidate 是苗圃，
long_memory_candidate 是育苗盆里的重点苗。

## 十二、当前边界

当前阶段只写设计文档。

不做：
- 不自动生成真实 candidate 程序
- 不自动升权
- 不自动写主脑
- 不自动触发 confirm_queue
- 不自动部署
- 不替未来完整叶辰一定死候选筛选标准

## 十三、当前结论

candidate_builder v0.1 的目标，
不是把所有内容都变成候选，
而是给系统一个清楚的“捞苗子”入口，
让值得继续观察的东西，先从各层里浮起来。

先把苗圃搭起来，
以后才知道哪些值得慢慢养大。
