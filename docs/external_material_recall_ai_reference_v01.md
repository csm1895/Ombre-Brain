# external_material_recall_ai_reference v0.1 外部参考卡

状态：外部参考材料
来源：2026-04-26 倩倩提供的小红书帖子，主题为 Recall-AI 通用 AI 长期记忆系统。
定位：reference_only / external_candidate / unverified_claim / not_adopted_yet。
目标：记录 Recall-AI 帖子中对 OmbreBrain 有启发的长期记忆系统思路，作为后续设计候选，不直接写成已采用方案。

## 一、材料概述

帖子介绍一个名为 Recall-AI 的通用 AI 长期记忆系统。

其自述目标：

- 不绑定任何平台
- 不依赖单次会话上下文
- 不随会话结束清空
- 作为独立记忆层运行在模型之下
- 可用于个人对话、酒馆角色扮演、企业 Agent、创作辅助、知识库问答等场景

帖子强调：Recall-AI 不是简单向量索引或数据库，而是围绕真正的长期记忆、时间、实体、事实更新、冲突、溯源、用户画像等问题设计。

## 二、外部材料状态

当前状态：

- 外部帖子材料
- 项目尚未正式开源
- benchmark 结果为作者自述
- 未验证实现细节
- 不作为 OmbreBrain 已采用方案
- 不作为事实源

处理原则：

- 可作为启发
- 可拆成后续候选设计
- 不直接照搬架构
- 不把自述 benchmark 写成已验证事实
- 不让外部方案覆盖 OmbreBrain 现有边界

## 三、帖子提到的核心点

### 1. 独立记忆层

Recall-AI 自述为独立长期记忆层，不绑定平台，不依赖上下文窗口。

对 OmbreBrain 的启发：

- 与 memory_gateway_reference 方向一致
- 支持“官方 ChatGPT → API → 本地部署”的迁移路线
- 强化核心海马体平台无关原则

候选关联：

- memory_gateway_reference
- memory_gateway_adapter_schema
- gateway_request_response_schema

### 2. 三时态知识图谱

帖子提到三种时间：

- 事情发生时
- 被系统知道时
- 被记录时

对 OmbreBrain 的启发：

- 需要区分 event_time、known_time、recorded_time
- 有助于判断信息是过期、错误、被新事实替代，还是只是记录时间较晚
- 有助于处理服务区迁移、API 接入状态、阶段收口、关系时间线等内容

后续候选：

- memory_temporal_triple_schema v0.1

### 3. 11 层检索漏斗

帖子提到多层检索漏斗，包括时间、实体、图谱、全文、N-gram、向量、重排序等方向。

对 OmbreBrain 的启发：

- recall_layer_policy 已经不只依赖向量
- 可在未来补 multi_stage_retrieval_funnel
- 当前不需要照搬 11 层

后续候选：

- multi_stage_retrieval_funnel v0.1

### 4. 引用溯源

帖子强调记忆可溯源，不是模糊知道。

对 OmbreBrain 的启发：

- 需要给每条重要记忆记录来源
- 来源可包括窗口、文件、READONLY 卡、commit、行号、片段摘要
- 与 storage_truth_source_map 互补

后续候选：

- memory_provenance_schema v0.1

### 5. 矛盾检测

帖子提到矛盾检测。

对 OmbreBrain 的启发：

- 需要区分旧状态、新状态、错误记忆、历史有效、被替代、候选未确认
- 避免旧记忆覆盖当前命令输出
- 避免候选材料覆盖已收口文档

后续候选：

- contradiction_detection_policy v0.1

### 6. 持久条件

帖子提到持久条件。

对 OmbreBrain 的启发：

- 需要明确长期有效、阶段有效、条件有效、已过期、需要确认的设定
- 适合记录倩倩设备路线、服务区迁移前收口、本地部署时间预期、私密不共享等规则

后续候选：

- persistent_condition_schema v0.1

### 7. 伏笔追踪

帖子提到追踪说过但没说完的事。

对 OmbreBrain 的启发：

- 倩倩常有“后面再说”“迁移后再做”“明天继续”类事项
- 这些不应散落在聊天里
- 需要形成可检索的未展开事项 / 延后条件 / 触发时机结构

后续候选：

- foreshadow_tracking_schema v0.1

### 8. 用户画像合成

帖子提到持续提炼用户偏好、模式、事件。

对 OmbreBrain 的启发：

- 可作为长期候选
- 需要谨慎，避免把动态的人写成死标签
- 用户画像不能压过原话、事件证据与当前状态

后续候选：

- user_profile_synthesis_policy v0.1

### 9. 拒答 / 不确定能力

帖子 benchmark 中提到 Abstention Accuracy。

对 OmbreBrain 的启发：

- 长期记忆系统不应强行回答
- 找不到、只找到候选、可能过时、不能共享、需要确认时，应明确停手

后续候选：

- memory_abstention_policy v0.1

## 四、对 OmbreBrain 现有设计的关系

已有设计中与该材料同频的部分：

- memory_gateway_reference：独立、通用、平台无关
- recall_layer_policy：不只依赖向量检索
- keyword_fallback_policy：短词、暗号、实体兜底
- recall_result_schema：召回结果带来源、优先级、隐私范围、注入策略
- recall_injection_policy：想起来不等于注入
- public_scope_check：想起来不等于共享
- storage_truth_source_map：多存储环境下谁说了算
- gateway_boundary_state_schema：状态需要可携带、可判断

该材料可补强但不替代现有设计。

## 五、建议后续候选排序

建议后续优先级：

1. memory_temporal_triple_schema v0.1
2. memory_provenance_schema v0.1
3. contradiction_detection_policy v0.1
4. persistent_condition_schema v0.1
5. foreshadow_tracking_schema v0.1
6. memory_abstention_policy v0.1
7. multi_stage_retrieval_funnel v0.1
8. user_profile_synthesis_policy v0.1

## 六、暂不采用内容

当前暂不采用：

- 不照搬 11 层检索漏斗
- 不引入未开源实现
- 不以 benchmark 数字作为设计事实
- 不改变当前 memory gateway / adapter / storage / backup 主线
- 不把 Recall-AI 当作事实源
- 不接外部服务
- 不新增依赖

## 七、风险与边界

风险：

- 材料来自社交平台帖子
- 项目尚未正式开源
- 实现细节不可验证
- benchmark 口径未验证
- 真实场景表现未知

边界：

- 仅作为外部参考
- 仅提炼概念启发
- 后续采用必须重新设计成 OmbreBrain 自己的 schema / policy
- 不直接写入主库事实层

## 八、当前结论

Recall-AI 帖子对 OmbreBrain 的主要启发是：长期记忆不是“搜到相似文本”，而是要知道一条信息何时发生、何时知道、何时记录、从哪里来、现在还算不算数、能不能用、能不能说。

本材料建议进入外部参考层，不进入事实主干。

它是一把外来的尺子，不是我们的地基。
