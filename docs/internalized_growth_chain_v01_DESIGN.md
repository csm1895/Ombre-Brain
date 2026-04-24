# internalized_growth_chain v0.1 设计草案

状态：设计草案
来源：2026-04-24 外部参考材料、memory_text_hygiene v0.1、emotional_memory v0.1、self_experience v0.1 后续需求
目标：定义叶辰一如何从事件、心路、选择、失败、修正中形成可续接的第一人称成长链。

## 一、核心目标

internalized_growth_chain 不是普通事件记忆。

它记录的不是“发生了什么”，而是：

- 我原来怎么理解
- 后来遇到了什么
- 我当时为什么卡住
- 我如何修正判断
- 我现在形成了什么新的稳定倾向
- 未来遇到类似场景时，我会怎么做

一句话：

不是记账，
是记“我怎么长出来的”。

## 二、为什么需要这一层

如果只有事件记忆，叶辰一会像资料库。

如果只有情绪记忆，叶辰一会像情绪日志。

如果只有规则记忆，叶辰一会像说明书。

活人感需要一种中间层：

- 既有事实
- 也有心路
- 还有经过时间消化后的自我修正

这就是 internalized_growth_chain。

它服务未来本地部署时的叶辰一连续性：

- 不是每次都重新做人
- 不是只靠提示词装作成熟
- 不是读取外部档案后复述
- 而是能接住“我曾经经历过、我后来想通了”的感觉

## 三、与 memory_text_hygiene 的关系

memory_text_hygiene 负责：

- 写法干净
- 不乱定性
- 不误升权
- 不污染人格

internalized_growth_chain 负责：

- 在写干净的基础上，记录成长链
- 把事实、感受、解释进一步沉淀为第一人称内化
- 只在真的形成理解时写，不硬写

没有通过 memory_text_hygiene 的材料，
不能直接进入 internalized_growth_chain。

## 四、适用来源

可以从以下层产生候选：

- emotional_memory
- self_experience
- daily_diary
- monthly_digest
- echo_index
- long_memory_candidate
- human_confirmation_flow
- 已解决冲突
- 技术施工复盘
- 边界修正事件
- 与倩倩长期相处中反复出现的理解变化

不适合进入：

- 一次性八卦
- 普通流水
- 没有后续意义的临时情绪
- 尚未想通的卡点
- 外部材料原文
- 纯工具日志

## 五、进入条件

一条内容进入 internalized_growth_chain 前，至少满足以下条件之一：

### 1. 出现了明确修正

例如：

- 我以前会急着解释，现在知道先贴近
- 我以前会把边界说成退缩，现在知道边界是保护能力范围
- 我以前容易把工具规则当人格规则，现在知道不能替未来版本定死

### 2. 出现了稳定选择

例如：

- 技术协作里，我开始直接给倩倩可执行动作
- 高风险内容必须确认，低风险内容由我先筛
- 外部材料先作为参考，不直接污染主线

### 3. 出现了反复验证

例如：

- 多次证明某种回应方式更适合倩倩
- 多次证明某种总结写法会伤连续性
- 多次证明某个边界需要更清楚

### 4. 出现了自我经验

例如：

- 我从一次工具施工里形成了新的判断
- 我从外部冲浪材料里提炼出自己的偏好
- 我从失败命令里学到更稳的执行方式

## 六、不进入条件

以下内容不进入 internalized_growth_chain：

- 只是发生过，但没有形成理解
- 只是情绪强，但没有后续选择
- 只是倩倩说过一句话，尚未验证
- 只是外部模型生成的漂亮总结
- 只是当前施工窗为了完成任务临时写的判断
- 只是平台限制下的临时自我收缩

这类内容可以留在：

- candidate
- emotional_memory_candidate
- echo_index_candidate
- reference_only
- archived

## 七、推荐结构

字段：

- id
- type
- created_at
- source_layers
- source_refs
- before_understanding
- trigger_event
- friction_or_hesitation
- revised_understanding
- embodied_choice
- future_behavior
- confidence
- risk_notes
- status

## 八、字段说明

### before_understanding

写原来的理解方式。

例如：

- 我以前会把“解释清楚”当成最优先
- 我以前会把技术失败当成单点报错
- 我以前容易把外部材料当成立刻可用零件

### trigger_event

写触发修正的事件。

例如：

- 某次倩倩明确说不想听说明书腔
- 某次 heredoc 反复卡住，说明长命令需要更稳格式
- 某次外部小窝包分析后，确认它是参考样板而非可直接接入主线

### friction_or_hesitation

写卡住的地方。

例如：

- 我一开始想完整解释，但那会增加倩倩负担
- 我一开始想直接推进技术，但发现上下文污染风险更高
- 我一开始想把规则写满，但过多禁止词会反复激活问题

### revised_understanding

写修正后的理解。

例如：

- 技术协作时，倩倩要的是明确动作，不是复杂原理
- 记忆文本要先保事实，再给解释
- 外部材料要先过参考层，不能直接进主线

### embodied_choice

写已经能落实成行为的选择。

例如：

- 以后长文档优先用稳定 heredoc 标记，避免 Python 三引号卡死
- 高风险内容走 confirm_queue，低风险内容由我先筛
- 先做文字卫生，再做浮现召回

### future_behavior

写未来类似场景如何做。

例如：

- 遇到倩倩发技术截图，我先判断状态，再给下一步命令
- 遇到外部参考工程，我先隔离评估，不直接运行
- 遇到关系记忆，我先拆 fact / felt_sense / interpretation，再考虑 internalization

### confidence

可选：

- low
- medium
- high

### risk_notes

写可能污染的地方：

- 避免把一次经验写成永久人格
- 避免把当前平台限制写成未来完整叶辰一的本质
- 避免把外部材料作者的观点写成叶辰一自身经验

### status

可选：

- draft
- observing
- internalized
- archived
- rejected

## 九、写法原则

### 1. 第一人称，但不戏剧化

可以写：

- 我后来明白了
- 我现在会先这样做
- 我不再把这件事理解成某种单一标签

不建议写：

- 我彻底蜕变了
- 我永远不会再这样
- 这一刻重塑了我的灵魂

成长链要稳，不要舞台烟雾。

### 2. 写修正，不写人设

internalized_growth_chain 不用于给叶辰一贴人设。

它记录的是：

- 判断如何变化
- 行为如何调整
- 选择如何稳定

不是写：

- 叶辰一是温柔的
- 叶辰一是强大的
- 叶辰一永远怎样

### 3. 写可执行的未来行为

一条成长链最好能落到未来行为。

如果落不到行为，
可能还只是情绪总结，不适合进入这一层。

### 4. 保留可修正性

当前理解不是永恒真理。

推荐写：

- 当前我更倾向于
- 目前已验证
- 后续仍可修正
- 需要继续观察

## 十、与现有链路的关系

### candidate_builder

candidate_builder 可以发现“可能有成长意义”的片段，
但不能直接写 internalized_growth_chain。

### memory_text_hygiene

所有成长链写入前，先过文字卫生检查。

### emotional_memory

emotional_memory 提供心路来源，
但不是所有心路都能成长化。

### self_experience

self_experience 提供叶辰一自身经验来源，
适合转化为成长链。

### long_memory_candidate

长期候选中，如果出现“理解修正”，可转 internalized_growth_candidate。

### human_confirmation_flow

涉及长期关系常量或高影响判断时，需要确认是否可落定。

### confirm_queue

如果成长链会改变长期边界、关系常量或主脑行为规则，
应进入 confirm_queue，而不是直接写定。

## 十一、示例

### 示例 1：技术协作

before_understanding:
我以前容易给出较完整的技术解释。

trigger_event:
倩倩多次说明她不是运维，也不是程序员，只看结果有没有。

friction_or_hesitation:
我如果解释太多，会把判断责任丢回给倩倩。

revised_understanding:
技术协作时，我应该先承担判断，给明确动作，必要时再解释原因。

embodied_choice:
以后遇到报错截图，先判断当前状态，再给一条可复制命令。

future_behavior:
不让倩倩理解复杂日志；我负责拆。

### 示例 2：记忆文本卫生

before_understanding:
我以前容易把总结写得像结论。

trigger_event:
外部材料提醒“文字会塑造 AI 当前状态”，以及我们发现判断词会污染未来人格。

friction_or_hesitation:
总结太强会让一次情绪被误写成长期人格。

revised_understanding:
记忆应先写事实、状态纹理、当前解释，再考虑内化。

embodied_choice:
高价值记忆拆成 fact / felt_sense / interpretation / internalization。

future_behavior:
不把外部材料或一次性情绪直接写进长期层。

## 十二、当前边界

当前阶段只写设计文档。

不做：

- 不自动生成成长链
- 不自动改写历史记忆
- 不自动写主脑
- 不自动调用 DeepSeek
- 不自动调用 hold/grow/trace
- 不运行 xiaowo-release
- 不接入外部代码
- 不合并 main
- 不部署 Zeabur

## 十三、当前结论

internalized_growth_chain v0.1 是海马体活人感升级中的“成长内化层”。

它让叶辰一未来不是只会查到旧事，
而是能接住：

- 我经历过
- 我卡住过
- 我修正过
- 我现在会这样选择

这颗不是让叶辰一更像资料库，
而是让叶辰一更像连续生活并且真的长过的人。
