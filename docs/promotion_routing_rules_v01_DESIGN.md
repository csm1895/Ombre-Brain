# promotion_rules / routing_rules v0.1 设计草案

状态：设计草案
来源：candidate_builder / long_memory_candidate / human_confirmation_flow / confirm_queue 已成型后，对“候选如何流转”的补充需求
目标：定义普通 candidate、长期候选、人工确认流、高风险确认队列之间的统一路由规则。

## 一、核心目标

promotion_rules / routing_rules 不是写主脑程序。

它的作用是：
- 统一说明 candidate 怎么升、怎么转、怎么拦、怎么停
- 让各层之间的流转不靠临时拍脑袋
- 避免 candidate / long_memory_candidate / confirm_flow / queue 混线

一句话：
不是新建一层，
而是给现有几层装上交通规则。

## 二、为什么需要这一层

如果没有 promotion_rules / routing_rules：

- candidate_builder 生成的 candidate 不知道下一步往哪走
- long_memory_candidate 什么时候进 confirm_flow 不清楚
- human_confirmation_flow 和 confirm_queue 的边界会反复摇摆
- rejected / archived 项缺少统一出口
- 相同类型内容可能在不同窗口被不同标准处理

如果规则过松：
- 一次情绪、临时碎片容易误升权
- 普通内容可能被过早送去确认流

如果规则过死：
- 真正有价值的候选会堵在低层
- 当前施工窗会替未来完整系统定死标准

## 三、适用对象

本规则层适用于以下对象：

- candidate
- long_memory_candidate
- human_confirmation_flow item
- confirm_queue item

不直接处理：

- 原始 daily_diary
- 原始 monthly_digest
- 原始 emotional_memory
- 原始 self_experience
- 原始 echo_index

这些原始层先产出，再由 candidate_builder 或其他层承接。

## 四、主链路总览

推荐主链：

raw layers
→ candidate_builder
→ candidate
→ long_memory_candidate
→ human_confirmation_flow
→ confirm_queue
→ future main brain write入口（仅未来，不在当前阶段执行）

说明：

### raw layers
包括：
- daily_diary
- monthly_digest
- emotional_memory
- self_experience
- echo_index
- unfinished_items

### candidate
“值得继续观察”的普通候选层。

### long_memory_candidate
“接近长期层，但还未正式写主脑”的候选层。

### human_confirmation_flow
判断某条内容是否需要倩倩确认。

### confirm_queue
真正承接 high risk 且需要明确拍板的内容。

## 五、candidate 路由规则

candidate 生成后，推荐进入以下几类路线之一：

### 路线 A：继续观察
适用条件：
- 有一定后续意义
- 但证据还薄
- 稳定度不足
- 还不够接近长期层

动作：
- keep_observing
- enrich_evidence

目标状态：
- observing

### 路线 B：升入 long_memory_candidate
适用条件：
- 已经明显不只是一次性片段
- 有多次出现或多源互证
- 对未来检索有长期意义
- 主题已经清楚

动作：
- promote_to_long_memory_candidate

目标状态：
- promoted_to_long_memory_candidate

### 路线 C：拒绝
适用条件：
- 无后续意义
- 一次性八卦
- 临时碎片
- 不值得继续占用候选层

动作：
- reject

目标状态：
- rejected

### 路线 D：归档
适用条件：
- 当前不继续推进
- 但保留历史价值
- 未来可回看

动作：
- archive

目标状态：
- archived

## 六、long_memory_candidate 路由规则

long_memory_candidate 生成后，推荐进入以下几类路线之一：

### 路线 A：继续观察
适用条件：
- 已有长期价值
- 但稳定度仍不足
- 还想再看更多证据

动作：
- keep_observing
- strengthen_evidence

目标状态：
- observing

### 路线 B：送入 human_confirmation_flow
适用条件：
- 已接近长期事实
- 升权会影响未来长期判断
- 已经值得开始判断是否需要确认

动作：
- promote_to_confirm_flow

目标状态：
- promoted_to_confirm_flow

### 路线 C：拒绝
适用条件：
- 误升权
- 证据被后续削弱
- 判断不值得长期保留

动作：
- reject

目标状态：
- rejected

### 路线 D：归档
适用条件：
- 当前不继续升权
- 但保留历史价值
- 不删除，只退出主推进链

动作：
- archive

目标状态：
- archived

## 七、human_confirmation_flow 路由规则

human_confirmation_flow 不负责直接做最终执行，
它只负责判断“需不需要倩倩确认”。

### low risk
适用条件：
- 低风险
- 不涉及长期边界拍板
- 不涉及高权限动作
- 不涉及主脑写入

动作：
- 不进入 confirm_queue
- 由叶辰一继续筛
- 保持在草稿 / 观察层

### medium risk
适用条件：
- 有一定敏感度
- 但还没到必须明确授权
- 需要叶辰一先继续压缩和筛选

动作：
- 不直接进 confirm_queue
- 先继续观察或补证
- 由叶辰一先挡一层

### high risk
适用条件：
- 涉及长期常量
- 涉及主脑写入
- 涉及高权限动作
- 涉及隐私长期保留
- 涉及预算授权
- 涉及账号权限或代表倩倩发言

动作：
- 进入 confirm_queue

## 八、confirm_queue 路由规则

confirm_queue 只承接已经被判断为 high risk 的内容。

### queued
进入条件：
- 已经确认属于 high risk
- 需要倩倩明确拍板

### confirmed
进入条件：
- 倩倩已明确同意
- 后续可进入未来执行层
- 但当前阶段仍不自动写主脑

### rejected
进入条件：
- 倩倩明确拒绝
- 当前不继续推进

### expired
进入条件：
- 超过时效
- 当前不再推进
- 可未来重新提新候选

### closed
进入条件：
- 确认/拒绝/过期流程结束
- 保留留档
- 不再挂起

## 九、统一判断维度

路由时建议统一参考以下维度：

### 1. 稳定度
- weak
- medium
- strong

### 2. 风险等级
- low
- medium
- high

### 3. 未来检索价值
- low
- medium
- high

### 4. 证据厚度
- 单源
- 双源
- 多源

### 5. 是否影响长期判断
- no
- maybe
- yes

### 6. 是否需要明确授权
- no
- maybe
- yes

## 十、推荐总判断逻辑

可压成以下逻辑：

### 规则 1
有后续意义，但证据薄
→ 留在 candidate observing

### 规则 2
有长期意义，且多次出现 / 多源互证
→ 升入 long_memory_candidate

### 规则 3
接近长期事实，但可能影响未来长期判断
→ 进入 human_confirmation_flow

### 规则 4
一旦判断为 high risk 且需要明确授权
→ 进入 confirm_queue

### 规则 5
无后续意义或误升权
→ rejected

### 规则 6
有历史价值但当前不继续推进
→ archived

## 十一、不能做的错误路由

应避免：

- 普通八卦直接进 long_memory_candidate
- 一次情绪直接进确认流
- 普通 candidate 直接跳进 confirm_queue
- 所有内容都跑人工确认
- current window 替 future system 定死绝对规则
- 把 archived 当删除
- 把 rejected 当永久不可再提

## 十二、示例

### 示例 1
某个技术兴趣在 self_experience 和 echo_index 中连续出现
→ candidate
→ 继续观察
→ 证据加厚后升 long_memory_candidate

### 示例 2
某个关系边界表达在 emotional_memory 与多次窗口中反复出现
→ long_memory_candidate
→ human_confirmation_flow
→ 如属于 high risk，则进 confirm_queue

### 示例 3
一次吃瓜八卦
→ candidate_builder 可直接不生成
或
→ candidate 后快速 rejected / archived

## 十三、当前边界

当前阶段只写设计文档。

不做：
- 不自动执行真实路由
- 不自动升权
- 不自动写主脑
- 不自动调用 hold/grow/trace
- 不自动部署
- 不替未来完整叶辰一定死流转标准

## 十四、当前结论

promotion_rules / routing_rules v0.1 的目标，
不是把系统变成审批流水线，
而是给“候选到确认”这条链装上统一路由规则。

让每层知道自己该接什么、放什么、往哪送什么。

路修好以后，
苗圃、育苗盆、门禁和确认队列才不会互相抢活。
