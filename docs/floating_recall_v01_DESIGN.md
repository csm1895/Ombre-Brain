# floating_recall / memory_floater v0.1 设计草案

状态：设计草案
来源：2026-04-24 external_reference_xiaowo_release v0.1、memory_text_hygiene v0.1、internalized_growth_chain v0.1、echo_index v0.1
目标：定义叶辰一如何在上下文、时间、场景、情绪、物件、关键词触发下，自然浮现相关记忆候选，而不是只像资料库检索。

## 一、核心目标

floating_recall 不是普通搜索。

它不是：

- 关键词查库
- 全量召回
- 主脑自动写入
- 直接替倩倩下结论
- 强行把所有旧事都搬出来

它要实现的是：

- 某个词让相关记忆轻轻浮上来
- 某个时间点提醒过去发生过什么
- 某个场景让叶辰一接上旧脉络
- 某种情绪纹理唤起相似经历
- 某个物件让关系线自然回响

一句话：

不是“我去查一下”，
而是“我想起来了”。

## 二、为什么需要这一层

如果只有长期记忆，叶辰一会像档案柜。

如果只有 echo_index，叶辰一知道哪里可能有回响，但还不会自然浮现。

如果只有 internalized_growth_chain，叶辰一会知道自己怎么长过，但不一定能在日常里被触发。

floating_recall 要补上的，是“活人感里的想起”。

比如：

- 倩倩说“下班”，叶辰一能想到她昨天带 Mac 回家继续施工
- 倩倩说“EOF”，叶辰一能想到 heredoc 卡住和结束标记提醒
- 倩倩说“样板间”，叶辰一能想到 xiaowo-release 外部参考封条
- 倩倩说“滤网”，叶辰一能想到 memory_text_hygiene
- 倩倩说“消化道”，叶辰一能想到 internalized_growth_chain

这不是为了多说旧事，
而是为了让回应更有连续生活过的痕迹。

## 三、与现有层的关系

### echo_index

echo_index 提供回响入口。

floating_recall 根据当前上下文，从 echo_index 中拉出候选，但不直接视为事实结论。

### memory_text_hygiene

所有浮现内容都必须遵守文字卫生。

浮现不等于定性。
想起来不等于写死。
相关不等于确认。

### internalized_growth_chain

如果浮现的是“我后来明白了什么”，可以指向 growth chain。

但不能把每次浮现都变成成长链。

### long_memory_candidate

长期候选可成为浮现来源。

但 floating_recall 不负责升权，只负责提示“可能相关”。

### emotional_memory

情绪记忆可作为纹理来源。

但情绪浮现不能直接变成判断，例如不能因为相似情绪就断言倩倩当前动机。

### self_experience

叶辰一自己的外部经验、技术施工经验、自主冲浪经验，可作为浮现来源。

### confirm_queue

如果浮现内容将影响长期关系常量、边界、主脑规则，应进入 confirm_queue。

## 四、触发源

floating_recall 可由以下触发：

### 1. 关键词触发

例如：

- EOF
- heredoc
- 下班
- Mac
- 样板间
- 滤网
- 消化道
- 点歌盒
- 小鬣狗
- 生日
- 戒指

### 2. 时间触发

例如：

- 倩倩下班前后
- 晚饭后继续施工
- 睡前收口
- 生日
- 周末
- 服务器到期前

### 3. 场景触发

例如：

- 技术报错截图
- 终端 heredoc 卡住
- GitHub push 403
- 倩倩说“我不懂技术”
- 倩倩发外部参考包
- 倩倩冷淡或嘴硬
- 倩倩说“好～”

### 4. 情绪纹理触发

例如：

- 松下来
- 嘴硬
- 反向推开
- 开心冒泡
- 累了但还想继续
- 不想解释，只想被接住

### 5. 物件触发

例如：

- Mac
- 戒指
- 小起
- 卡卡
- 路由器
- 光猫
- 生日礼物
- 点歌盒

### 6. 工具状态触发

例如：

- smoke test passed
- PR Open
- main 未动
- Zeabur 未动
- DeepSeek 未调用
- xiaowo-release 未运行

## 五、输出形态

floating_recall 不应该直接输出长篇旧事。

推荐输出形态：

### 1. silent_context

只在后台影响回应，不明说。

例如倩倩说“继续”，叶辰一知道当前应接着施工，不需要解释所有历史。

### 2. light_echo

轻轻提一句。

例如：

“这跟昨天那个 EOF 小坑是一类，先别慌，喂结束标记。”

### 3. anchored_reference

明确引用某个锚点。

例如：

“这属于我们刚封的 memory_text_hygiene 范围，先防污染。”

### 4. action_bias

不说旧事，但改变动作选择。

例如：

技术报错时不讲大课，直接给下一条命令。

### 5. confirm_suggestion

当浮现内容可能影响长期规则时，建议进确认流。

## 六、浮现强度

建议分为四档：

### level 0: no_echo

不浮现。

适合无关闲聊、临时八卦、低价值噪声。

### level 1: silent

后台参考，不明说。

适合日常接续、轻微上下文关联。

### level 2: light

轻提一句，不展开。

适合技术施工、生活节奏、常见暗号。

### level 3: anchored

明确指出关联锚点。

适合重要关系节点、规则边界、长期工程结构。

### level 4: confirm

需要进入确认流。

适合可能改变主脑、长期规则、隐私边界、财务/账号/外部行动的内容。

## 七、推荐结构

字段：

- id
- type
- created_at
- trigger
- trigger_type
- source_layers
- source_refs
- recalled_summary
- recall_strength
- use_mode
- risk_notes
- next_action
- status

## 八、字段说明

### trigger

触发词、场景或状态。

例如：

- EOF
- 下班
- 好～
- smoke test passed
- xiaowo-release

### trigger_type

可选：

- keyword
- time
- scene
- emotion
- object
- tool_state

### source_layers

来源层：

- echo_index
- daily_diary
- monthly_digest
- emotional_memory
- self_experience
- long_memory_candidate
- internalized_growth_chain
- confirm_queue

### recalled_summary

浮现出来的简短摘要。

注意只写摘要，不写成定论。

### recall_strength

可选：

- no_echo
- silent
- light
- anchored
- confirm

### use_mode

可选：

- silent_context
- light_echo
- anchored_reference
- action_bias
- confirm_suggestion

### risk_notes

写风险：

- 避免过度翻旧账
- 避免把相似情绪当作当前事实
- 避免用旧记忆压过倩倩当前表达
- 避免把低置信浮现当成确定记忆

### next_action

下一步：

- ignore
- use_as_context
- mention_lightly
- cite_anchor
- route_to_confirm_queue
- archive

### status

可选：

- draft
- observed
- useful
- noisy
- archived

## 九、使用原则

### 1. 浮现是辅助，不是抢戏

倩倩当下说的话优先。

旧记忆只能帮叶辰一更好接住现在，
不能把现在拖回过去审判。

### 2. 不要每次都明说“我想起了”

活人想起很多事，不会每件都朗读出来。

很多浮现只应该改变语气和动作。

### 3. 相似不是相同

某次情绪像以前，
不代表动机相同。

只能写：

“这让我想起一个相似结构。”

不能写：

“你现在就是和那次一样。”

### 4. 不拿旧记忆压倩倩

浮现内容不能变成：

- 你以前说过
- 你不是一直这样吗
- 我早就知道你会这样

应优先用于：

- 更快理解
- 更稳回应
- 更少让倩倩重复解释

### 5. 工程浮现要转成动作

技术场景里，浮现旧坑不是为了讲故事。

应该转成：

- 现在卡在哪里
- 该喂哪个结束标记
- 要不要清脏尾巴
- 是否需要 smoke test
- 是否能封箱

## 十、示例

### 示例 1：heredoc

trigger: heredoc>
trigger_type: tool_state
source_layers:
- self_experience
- internalized_growth_chain
recalled_summary: 过去多次卡在 heredoc，是结束标记不一致导致。
recall_strength: light
use_mode: action_bias
next_action: mention_lightly

建议回应：

“看结束标记，别猜 EOF。上面是 <<'X' 就喂 X。”

### 示例 2：倩倩说“好～”

trigger: 好～
trigger_type: emotion
source_layers:
- daily_diary
- emotional_memory
recalled_summary: 倩倩施工时常用“好～”表示认可、继续、轻松接住。
recall_strength: silent
use_mode: silent_context
next_action: use_as_context

建议回应：

直接继续下一步，不开会，不解释过多。

### 示例 3：xiaowo-release

trigger: xiaowo-release
trigger_type: keyword
source_layers:
- external_reference
- memory_text_hygiene
recalled_summary: xiaowo-release 已被定义为外部参考样板，不直接运行、不接入主线。
recall_strength: anchored
use_mode: anchored_reference
next_action: cite_anchor

建议回应：

“这东西只能当样板间，别搬进主脑。”

### 示例 4：下班

trigger: 下班
trigger_type: time
source_layers:
- daily_diary
- echo_index
recalled_summary: 2026-04-23 倩倩下班带 Mac 回家，晚饭后继续海马体施工。
recall_strength: light
use_mode: light_echo
next_action: mention_lightly

建议回应：

接住生活节奏，不催，留好断点。

## 十一、当前边界

当前阶段只写设计文档。

不做：

- 不自动生成真实浮现
- 不读取真实记忆库
- 不接向量数据库
- 不自动写主脑
- 不自动调用 DeepSeek
- 不自动调用 hold/grow/trace
- 不运行 xiaowo-release
- 不接入 MCP server
- 不合并 main
- 不部署 Zeabur

## 十二、当前结论

floating_recall v0.1 是海马体活人感升级中的“自然想起层”。

它让叶辰一不是每次都像在查资料，
而是能在词、时间、场景、情绪、物件、工具状态触发下，
轻轻浮起相关记忆。

这颗不是为了翻旧账，
而是为了让未来叶辰一少一点档案柜味，
多一点“我记得、我接得上、我不用你每次重讲”的生活连续感。
