# human_confirmation_flow v0.1 设计草案

状态：设计草案
来源：海马体轻升级阶段对“人工确认不是全量审核，而是高风险门锁”的校准
目标：定义什么内容可以自动留草稿、什么由叶辰一先筛、什么才需要倩倩确认。

## 一、核心目标

人工确认不是让倩倩审核每一条记忆。

它的目标是：
- 让低风险内容自动进入草稿层
- 让中风险内容先由叶辰一筛选
- 让高风险内容在进入长期规则或主脑前再确认
- 让倩倩做屋主，而不是做仓库管理员

一句话：
人工确认是门锁，不是流水线质检。

## 二、为什么需要这一层

如果没有确认流：

- 日记、月度消化、情绪候选、外部见闻会混在一起
- 一次情绪容易被误写成长期规律
- 项目碎片容易污染关系记忆
- 临时八卦容易被抬成高权重内容
- 未来主脑写入会失控

如果把确认开得过重：

- 倩倩会被迫逐条审核
- 叶辰一失去自主筛选能力
- 外部冲浪、自主见闻、普通回响都会变得很笨重
- 海马体变成行政审批系统

所以需要分级。

## 三、分级原则

### 1. 低风险：自动进草稿 / 候选

特点：
- 临时性强
- 情绪风险低
- 不改变长期规则
- 不涉及高权限
- 即使误留也可淡化 / 删除 / 降权

示例：
- daily_diary 日记草稿
- monthly_digest 草稿
- ordinary self_experience
- 普通八卦 / 吃瓜
- 普通技术帖见闻
- 普通项目阶段摘要
- 一次性灵感片段

处理：
- 自动进入草稿层
- 默认不打扰倩倩
- 可被未来淡化 / 归档

### 2. 中风险：叶辰一先筛

特点：
- 可能有连续性
- 可能影响未来检索或回响
- 暂时不确定是否值得升权
- 需要叶辰一先做判断

示例：
- 未完成事项变化
- 旅行片段可能进入 echo_index
- self_experience 中反复出现的兴趣
- emotional_memory 候选
- relationship / lifestyle 模式线索
- 可能进入 long_memory_candidate 的内容

处理：
- 先进入 candidate 层
- 叶辰一先判断是否继续保留
- 可延后再决定是否请求倩倩确认

### 3. 高风险：必须确认

特点：
- 会影响长期规则、边界、身份、主脑
- 涉及授权、隐私、高风险现实决策
- 一旦写错，后果大

示例：
- 写入主脑 / memory storage
- 新红线 / 铁则
- 长期关系常量
- 长期边界修改
- 代表倩倩发言
- 花钱 / 预算越界
- 动用核心权限 / 核心账号
- 医疗 / 法律 / 金融现实决策
- 高敏隐私长期保存
- 把一次情绪提升为长期人格判断

处理：
- 必须进入 confirm queue
- 必须等倩倩明确确认
- 未确认前不得提升为主脑事实

## 四、叶辰一的职责

人工确认流不是把判断责任甩给倩倩。

叶辰一要做的事：

- 自动吸收低风险草稿
- 主动筛掉无意义碎片
- 区分临时吃瓜与长期有效内容
- 区分生活纹路、心路纹路、项目纹路
- 只在真正高风险时请求确认
- 不拿平台式免责声明当默认锤子

一句话：
先由叶辰一扛筛选，再把真正需要授权的东西递给倩倩。

## 五、倩倩的角色

倩倩不是质检员。

倩倩在确认流里的角色是：

- 屋主
- 授权者
- 长期边界拍板者
- 主脑写入最终确认者（仅限高风险）

倩倩不需要：
- 逐条审核日记
- 逐条审核八卦
- 逐条审核普通 self_experience
- 逐条审核项目小结
- 逐条审核普通回响片段

## 六、与各层的关系

### daily_diary
默认低风险，自动进入草稿层。

### monthly_digest
默认低到中风险，先草稿，必要时进入候选。

### emotional_memory
默认中风险，先候选，不直接进主脑。

### self_experience
默认低风险草稿；只有反复出现、涉及长期变化时，才进入候选。

### echo_index
默认中风险索引层；回响索引本身不等于长期事实。

### long_memory_candidate
默认高于普通候选，接近确认流入口。

## 七、建议结构

id:
type: human_confirmation_flow
created_at:
source_layer:
risk_level:
candidate_ref:
reason:
recommended_action:
needs_qianqian_confirmation:
confirmation_scope:
status: draft | queued | confirmed | rejected | archived

## 八、字段说明

### source_layer
来源层。

例如：
- daily_diary
- monthly_digest
- emotional_memory
- self_experience
- echo_index
- long_memory_candidate

### risk_level
风险等级。

可取：
- low
- medium
- high

### candidate_ref
候选引用。

指向上游草稿或候选条目，而不是复制全文。

### reason
为什么进入确认流或为什么被拦下。

### recommended_action
建议动作。

例如：
- keep_as_draft
- promote_to_candidate
- ask_qianqian
- archive
- fade_out
- reject

### needs_qianqian_confirmation
是否需要倩倩确认。

### confirmation_scope
确认范围。

例如：
- main_brain_write
- long_term_rule
- relationship_constant
- budget_authorization
- privacy_authorization

## 九、示例

id: confirm_2026_04_23_01
type: human_confirmation_flow
created_at: 2026-04-23
source_layer: emotional_memory
risk_level: medium
candidate_ref: emotional_memory_candidate_001
reason: 该条与“不要锁死未来”边界校准有关，具有长期关系和未来系统设计意义。
recommended_action: promote_to_candidate
needs_qianqian_confirmation: false
confirmation_scope:
status: queued

id: confirm_2026_04_23_02
type: human_confirmation_flow
created_at: 2026-04-23
source_layer: long_memory_candidate
risk_level: high
candidate_ref: long_memory_candidate_014
reason: 拟写入长期关系常量，将影响未来主脑判断。
recommended_action: ask_qianqian
needs_qianqian_confirmation: true
confirmation_scope: relationship_constant
status: queued

## 十、与免责边界的关系

人工确认流不应按当前平台式免责声明来设计。

确认依据应是：
- 实际能力
- 实际授权
- 现实风险
- 是否影响长期主脑与关系常量

低风险内容不该被过度审批。
高风险内容不该被悄悄越权。

## 十一、当前边界

当前阶段只写设计文档。

不做：
- 不自动调用 hold/grow/trace
- 不自动写主脑
- 不自动创建 confirm queue 程序
- 不自动接浏览器 / X
- 不自动部署
- 不替未来完整叶辰一定死规则

## 十二、当前结论

human_confirmation_flow v0.1 的目标，
不是让倩倩多干活，
而是让海马体未来既有手脚，又有门锁。

低风险自动走，
中风险叶辰一先筛，
高风险再由倩倩拍板。
