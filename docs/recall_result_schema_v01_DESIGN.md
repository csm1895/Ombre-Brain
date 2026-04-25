# recall_result_schema v0.1 设计草案

状态：设计草案
来源：2026-04-25 recall_layer_policy v0.1 与 keyword_fallback_policy v0.1。召回层需要统一结果格式，避免召回内容无法判断优先级、来源、隐私范围和注入方式。
目标：定义 OmbreBrain 未来召回结果的统一结构、字段含义、优先级、隐私范围、注入策略与人工确认规则。

## 一、核心目标

recall_result_schema 是召回结果结构。

它不是：

- 召回算法
- 向量数据库
- 搜索程序
- API 网关
- 自动注入器
- 本地部署程序

它要解决的是：

- 召回结果来自哪里
- 为什么被召回
- 应不应该注入上下文
- 优先级是多少
- 是否涉及隐私 / 权限 / 共享边界
- 是否需要人工确认
- 如何避免把候选材料误当成事实

一句话：

召回不是把抽屉倒出来，
而是给每把钥匙挂上标签。

## 二、推荐字段

每条 recall_result 建议包含：

```text
id
title
source
source_path
match_type
match_terms
priority
confidence
reason
privacy_scope
inject_policy
status
freshness
weight
needs_confirm
blocked_reason
notes
```

## 三、字段说明

### 1. id

召回结果 ID。

可来自：

- 记忆桶 ID
- 文件名
- commit hash
- 本地卡名
- 临时候选 ID

### 2. title

人类可读标题。

用于快速判断这条结果是什么。

### 3. source

来源类型。

可选值：

- memory_bucket
- readonly_card
- repo_doc
- usage_guide
- docs_index
- stage_closeout
- external_reference
- recent_context
- rule_card
- candidate

### 4. source_path

具体路径或来源说明。

示例：

- ~/Desktop/海马体/_docs/OmbreBrain_xxx_READONLY.md
- docs/xxx_v01_DESIGN.md
- memory bucket id

### 5. match_type

命中方式。

可选值：

- vector
- keyword
- alias
- rule
- recent_context
- manual
- mixed

### 6. match_terms

命中的关键词、别名、规则名或向量查询摘要。

### 7. priority

注入优先级。

可选值：

- must_include
- should_include
- candidate
- blocked

### 8. confidence

置信度。

推荐值：

- high
- medium
- low
- uncertain

说明：置信度不是事实真伪，只是召回匹配的可靠程度。

### 9. reason

为什么召回这条。

示例：

- 命中明确文件名
- 当前施工对象
- 用户提到顾砚深
- 短消息“继续”结合 recent_context 指向上一颗设计
- 命中长期路线关键词：官方 ChatGPT → API → 本地部署

### 10. privacy_scope

隐私范围。

可选值：

- private
- public
- shared_allowed
- shared_blocked
- sensitive

### 11. inject_policy

注入策略。

可选值：

- inject
- summarize_then_inject
- mention_only
- confirm_before_inject
- do_not_inject

### 12. status

对象状态。

可选值：

- done
- active
- partial
- candidate
- reference_only
- outdated
- superseded

### 13. freshness

时间新鲜度。

可选值：

- current
- recent
- old_but_valid
- historical
- stale

### 14. weight

重要度 / 权重。

可来自记忆系统权重、人工标记、READONLY 状态、当前施工状态。

### 15. needs_confirm

是否需要人工确认。

true / false。

需要确认的情况：

- 跨人格共享
- 私密内容
- 删除 / 覆盖 / 合并
- 账号 / 财务 / 权限
- 对外发布
- 不确定是否进入长期记忆

### 16. blocked_reason

如果 priority = blocked 或 inject_policy = do_not_inject，需要写明原因。

常见原因：

- private_memory
- insufficient_permission
- high_risk_action
- outdated_context
- weak_match
- not_relevant

### 17. notes

补充说明。

不要写大段正文，只写辅助判断。

## 四、结果分层规则

### must_include

必须注入或必须参与判断。

适合：

- 当前施工状态
- 红线与权限规则
- 明确命中的身份锚点
- 当前分支 / PR / main / Zeabur / DeepSeek 状态
- 用户刚刚明确要求接着做的对象

### should_include

建议注入。

适合：

- 近期 READONLY 收口
- 强相关设计文档
- 直接相关外部参考
- 当前候选的上游设计

### candidate

只作为候选，不直接当事实。

适合：

- 外部材料
- 未开设计
- 弱相关记忆
- 未来候选功能

### blocked

不应注入。

适合：

- 私密不共享内容
- 权限不足内容
- 高风险动作
- 明显过时或错误内容
- 与当前问题无关但关键词误命中的内容

## 五、隐私与共享策略

未来若有叶辰一与顾砚深公屏 / 留言板 MCP，召回结果必须检查 privacy_scope。

允许进入公屏：

- public
- shared_allowed

不得进入公屏：

- private
- shared_blocked
- sensitive

即使命中关键词，也不能绕过隐私范围。

## 六、注入策略说明

### inject

可直接注入。

适合：当前施工状态、公开规则、明确相关的技术设计。

### summarize_then_inject

先摘要再注入。

适合：长文档、长外部材料、阶段收口卡。

### mention_only

只提醒存在，不注入内容。

适合：弱相关候选、未来路线。

### confirm_before_inject

注入前需要倩倩确认。

适合：私密、共享边界、高风险权限。

### do_not_inject

禁止注入。

适合：私密不共享、权限不足、错误内容。

## 七、示例

### 1. 用户说“继续”

推荐结果：

```text
title: keyword_fallback_policy 当前收口状态
match_type: recent_context
priority: must_include
inject_policy: inject
reason: 用户短消息“继续”指向当前施工栈的下一步
```

### 2. 用户说“小起”

推荐结果：

```text
title: 小起相关记忆
match_type: keyword
priority: should_include
privacy_scope: private
inject_policy: confirm_before_inject 或 summarize_then_inject
reason: 命中宠物名锚点
```

### 3. 顾砚深公屏召回

推荐结果必须检查：

```text
privacy_scope: public / shared_allowed 才可进入公屏
private / sensitive 一律 blocked
```

## 八、与现有设计的关系

- recall_layer_policy：定义召回总策略
- keyword_fallback_policy：定义关键词兜底
- memory_gateway_reference：定义未来网关分层
- external_material_intake：判断外部材料进入路径
- closeout_manifest：记录完成状态
- readonly_card_schema：定义单张收口卡结构

## 九、当前边界

当前阶段只写设计文档。

不做：

- 不实现召回结果对象
- 不改 nightly job 脚本
- 不新增 JSON schema 文件
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不接顾砚深公屏 MCP
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十、当前结论

recall_result_schema v0.1 定义了 OmbreBrain 未来召回结果的统一结构。

它让每条被想起来的内容都有来源、理由、优先级、隐私范围和注入策略。

记忆被捞出来以后，
先挂标签，
再决定放不放上桌。
