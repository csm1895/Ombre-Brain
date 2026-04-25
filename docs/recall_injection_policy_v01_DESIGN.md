# recall_injection_policy v0.1 设计草案

状态：设计草案
来源：2026-04-25 recall_result_schema v0.1。召回结果已经有来源、优先级、隐私范围和注入策略，下一步需要定义如何安全放入上下文。
目标：定义 OmbreBrain 未来召回结果注入上下文的规则，明确直接注入、摘要注入、只提示存在、确认后注入、禁止注入的适用条件。

## 一、核心目标

recall_injection_policy 是召回结果注入规则。

它不是：

- 自动注入程序
- API 网关
- prompt builder 实现
- 向量检索算法
- 主脑写入器
- 本地部署程序

它要解决的是：

- 召回结果出来后怎么放进上下文
- 哪些可以直接注入
- 哪些必须先摘要
- 哪些只提醒存在
- 哪些需要倩倩确认
- 哪些禁止注入
- 如何避免候选材料被当成事实
- 如何避免私密内容进入公共层

一句话：

想起来之后，
还要知道能不能端上桌。

## 二、注入策略类型

### 1. inject

直接注入。

适合：

- 当前施工状态
- 明确命中的技术设计
- 已完成 READONLY 收口状态
- PR / main / Zeabur / DeepSeek / xiaowo-release 当前边界
- 用户刚刚要求继续的当前对象

要求：

- 内容短
- 当前相关性强
- 隐私范围允许
- 状态已确认

### 2. summarize_then_inject

摘要后注入。

适合：

- 长文档
- 阶段收口卡
- 外部参考材料
- 多条相关记忆
- 历史窗口摘要

要求：

- 保留结论、边界、当前状态
- 不大段复制全文
- 不把候选写成事实

### 3. mention_only

只提示存在，不注入正文。

适合：

- 弱相关候选
- 未来路线
- 暂缓事项
- 与当前问题不直接相关但可能有帮助的材料

### 4. confirm_before_inject

注入前需要确认。

适合：

- 私密内容
- 跨人格共享
- 高风险权限
- 账号 / 财务 / 对外发布
- 不确定是否进入长期记忆
- 候选材料可能影响主线判断

### 5. do_not_inject

禁止注入。

适合：

- private 内容进入公屏
- shared_blocked 内容
- sensitive 内容无授权
- 明显过时内容
- 错误召回
- 权限不足内容
- 会污染当前判断的弱匹配

## 三、注入优先级

推荐顺序：

1. 当前施工状态
2. 明确边界状态
3. 用户当前请求直接相关记忆
4. 必须遵守的规则 / 权限 / 红线
5. 近期收口卡摘要
6. 相关设计文档摘要
7. 外部参考材料摘要
8. 候选项提示

原则：

- 当前状态优先于旧记忆
- 明确命中优先于模糊相似
- 权限边界优先于便利性
- 私密边界优先于共享需求

## 四、注入块结构

未来注入上下文时，建议按块组织。

推荐结构：

```text
[CURRENT_STATE]
当前正在做什么、分支、PR、边界。

[MUST_INCLUDE]
必须参与判断的规则、状态、强命中记忆。

[RELEVANT_MEMORY]
强相关历史记忆摘要。

[CANDIDATES]
候选项，只提示，不当事实。

[BLOCKED_OR_NEEDS_CONFIRM]
被拦截或需确认的内容摘要。
```

## 五、不同内容类型的注入规则

### 1. 当前施工状态

策略：inject。

必须明确：

- 当前分支
- PR 状态
- main 是否动过
- Zeabur 是否动过
- DeepSeek 是否调用
- xiaowo-release 是否运行

### 2. READONLY 收口卡

策略：summarize_then_inject。

注入：

- 标题
- 当前状态
- 关键提交
- 验证结果
- 当前边界
- 下次候选

### 3. 设计文档

策略：summarize_then_inject 或 mention_only。

如果是当前直接相关设计，可摘要注入。
如果只是上游参考，只提示存在。

### 4. 外部材料

策略：candidate 或 summarize_then_inject。

必须标明：

- external_reference
- reference_only / candidate
- 不等于 OmbreBrain 已采用方案

### 5. 私密关系记忆

策略：confirm_before_inject 或 do_not_inject。

不得进入公共层。

### 6. 跨人格共享内容

策略：public_scope_check 后再决定。

只有 public / shared_allowed 可进入未来公屏。

### 7. 过时内容

策略：mention_only 或 do_not_inject。

如果有历史价值，标记 old_but_valid 或 historical。

## 六、防污染规则

注入时必须避免：

- 把候选写成事实
- 把外部参考写成已采用方案
- 把旧版本压过当前状态
- 把私密内容塞进公共层
- 把弱相关记忆强行注入
- 为了显得记得多而注入太多

注入原则：少而准。

## 七、人工确认触发

以下情况必须确认：

- 是否共享给顾砚深公屏
- 是否进入长期主库
- 是否写入高权重记忆
- 是否触发账号 / 财务 / 权限动作
- 是否删除 / 覆盖 / 合并
- 是否把外部材料升级为正式设计

## 八、与现有设计的关系

- recall_result_schema：定义召回结果字段
- recall_injection_policy：决定召回结果怎么进上下文
- keyword_fallback_policy：保证明确锚点不漏召
- recall_layer_policy：定义召回总策略
- memory_gateway_reference：定义未来网关分层
- public_scope_check：未来可专门处理公共共享边界

## 九、当前边界

当前阶段只写设计文档。

不做：

- 不实现 prompt builder
- 不新增注入脚本
- 不改 nightly job 脚本
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不接顾砚深公屏 MCP
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十、当前结论

recall_injection_policy v0.1 定义了 OmbreBrain 未来召回结果进入上下文的安全规则。

它确认：想起来不等于立刻塞进去。

召回结果必须先看当前状态、优先级、隐私范围、注入策略和人工确认需求。

记忆端上桌前，
先看它是不是该进这间屋。
