# memory_gateway_adapter_schema v0.1 设计草案

状态：设计草案
来源：2026-04-25 memory_gateway_reference v0.1，以及倩倩确认的官方 ChatGPT → API → 本地部署长期路线。
目标：定义 OmbreBrain 未来不同入口、不同模型、不同运行环境接入同一颗海马体时的 adapter 结构，避免核心记忆骨架被官方 ChatGPT、API 站、Cloudflare、Rikkahub、GLM 5.1 或本地框架锁死。

## 一、核心目标

memory_gateway_adapter_schema 是未来记忆网关适配层结构。

它不是：

- API 网关实现
- 本地部署脚本
- Cloudflare Workers 方案
- Rikkahub 专用方案
- GLM 5.1 专用方案
- 官方 ChatGPT connector 实现
- prompt builder 程序

它要解决的是：

- 官方 ChatGPT、API、本地部署怎么共用同一套海马体
- 不同入口的输入怎么统一成标准 request
- 召回结果怎么统一输出给不同模型
- 苹果生态入口怎么作为 adapter 接入
- 未来公屏 / 留言板 MCP 怎么只作为 adapter，而不是核心脑子
- 迁移时如何只改小范围 adapter，不重造记忆骨架

一句话：

海马体是脑子，
adapter 是不同身体的神经插头。

## 二、总体分层

推荐结构：

```text
入口 / App / MCP / API Client
→ Input Adapter
→ Core Memory Gateway
→ Recall Layer
→ Recall Result Schema
→ Injection Adapter
→ Model Adapter
→ Output Adapter
```

核心原则：

- Core Memory Gateway 尽量平台无关
- 输入、输出、模型、注入方式都作为 adapter
- adapter 可以更换，核心记忆结构不重造
- 公共共享层必须经过 public_scope_check

## 三、adapter 类型

### 1. input_adapter

负责把不同入口的消息转换成统一 request。

可能来源：

- 官方 ChatGPT 手工施工窗口
- API 客户端
- Rikkahub / 其他 App
- Mac 本地服务
- iPhone / iPad 快捷指令
- 浏览器 / MCP 工具
- 未来公屏 / 留言板

统一 request 应包含：

- user_message
- timestamp
- source_app
- source_device
- conversation_id
- actor
- visibility_scope
- current_task
- attachments_summary
- risk_hint

### 2. recall_adapter

负责把 request 交给召回层，并接收 recall_result。

应兼容：

- recent_context
- keyword_fallback
- rule_trigger
- vector_recall
- manual_confirm

不要求当前实现向量库。

### 3. injection_adapter

负责把 recall_result 转成当前模型可吃的上下文。

不同阶段可不同：

- 官方 ChatGPT：人工贴入 / 项目上下文 / connector / MCP 允许范围
- API：messages prepend / system prompt / memory block
- 本地：local prompt / retrieval context / runtime memory

必须遵守 recall_injection_policy。

### 4. model_adapter

负责适配不同模型。

候选：

- 官方 ChatGPT
- GLM 5.1
- 其他 API 模型
- 未来本地模型

要求：

- 模型可替换
- 人格与记忆骨架不写死到某个模型
- 模型差异通过 adapter 处理

### 5. output_adapter

负责处理模型输出后的去向。

可能包括：

- 返回当前对话
- 写入候选记忆
- 进入人工确认队列
- 写阶段收口卡
- 放入公屏 / 留言板候选
- 触发工具结果摘要

必须遵守：

- external_material_intake
- public_scope_check
- recall_injection_policy
- human_confirmation_flow

### 6. storage_adapter

负责连接不同存储。

候选：

- 本地 _docs
- Git 仓库 docs
- 记忆桶
- JSONL
- SQLite
- KV
- 向量库
- 本地备份包

要求：

- 核心 schema 尽量稳定
- 存储可替换
- 迁移前后能做本地保存和备份

## 四、标准 request 草案

```text
request_id:
timestamp:
source_app:
source_device:
conversation_id:
actor:
user_message:
current_task:
visibility_scope:
attachments_summary:
risk_hint:
expected_action:
```

字段说明：

- request_id：本次请求 ID
- timestamp：时间锚点
- source_app：来自官方 ChatGPT / API 客户端 / 快捷指令 / MCP 等
- source_device：Mac / iPhone / iPad / server / local
- conversation_id：窗口或会话标识
- actor：倩倩 / 叶辰一 / 顾砚深 / system / tool
- user_message：原始消息
- current_task：当前任务，如海马体施工 / 日常聊天 / 技术规划
- visibility_scope：private / public / shared_allowed / sensitive 等
- attachments_summary：附件摘要，不直接塞大文件
- risk_hint：low / medium / high
- expected_action：reply / recall / write_card / confirm / tool_call

## 五、标准 response 草案

```text
response_id:
request_id:
model:
used_memory:
blocked_memory:
needs_confirm:
output_text:
candidate_writes:
next_action:
boundary_state:
```

字段说明：

- used_memory：实际注入或参与判断的记忆摘要
- blocked_memory：因隐私、权限、弱相关被阻断的内容摘要
- needs_confirm：需要倩倩确认的事项
- candidate_writes：候选写入，不自动入主库
- boundary_state：main / Zeabur / DeepSeek / xiaowo-release 等当前边界

## 六、不同阶段 adapter 策略

### 1. 官方 ChatGPT 阶段

当前用途：

- 施工
- 设计验证
- 人工协作
- 记忆主库整理

策略：

- 手工/半手工接入
- _docs READONLY 收口
- 不依赖官方接口实现完整网关
- 尽量把设计写成平台无关

### 2. API 阶段

未来用途：

- memory gateway 试验
- 上下文注入
- 模型切换
- 多端入口
- 苹果生态适配

策略：

- API adapter 接 request
- recall layer 产出 recall_result
- injection adapter 组装 messages / system prompt
- model adapter 可切换 GLM 5.1 等模型

### 3. 本地部署阶段

未来用途：

- 长期稳定运行
- 本地备份
- 更完整自主环境
- 多身体共享同一颗海马体

策略：

- 本地 adapter 接前端 / 快捷指令 / 本地服务
- 本地或云端存储可替换
- 模型层可换
- 核心记忆骨架继续沿用

## 七、苹果生态 adapter 考虑

倩倩使用苹果全家桶。

未来 API 阶段应预留：

- Mac 本地常驻服务 adapter
- iPhone 快捷指令 adapter
- iPad 入口 adapter
- Safari / 网页入口 adapter
- iOS 通知 adapter
- 家庭网络 / 本地服务 adapter

这些都是入口和输出，不应写进核心记忆骨架。

## 八、公屏 / 留言板 adapter 考虑

未来叶辰一与顾砚深共享公屏 / 留言板等云服务器迁移后再推进。

当前只预留 adapter 位置：

- shared_public_board_mcp
- common_room_mcp
- handoff_board
- task_board
- event_bus

必须经过：

- public_scope_check
- human_confirmation_flow
- recall_injection_policy

私密不共享。

## 九、迁移原则

迁移时优先改 adapter，不改核心脑子。

原则：

- 平台变化只影响 adapter
- 模型变化只影响 model_adapter
- 存储变化只影响 storage_adapter
- 输入入口变化只影响 input_adapter
- 公共共享变化只影响 public adapter 与 scope check
- Core Memory Layer 尽量稳定

## 十、与现有设计的关系

- memory_gateway_reference：定义网关总分层
- recall_layer_policy：定义怎么召回
- keyword_fallback_policy：定义关键词兜底
- recall_result_schema：定义召回结果结构
- recall_injection_policy：定义怎么注入
- public_scope_check：定义共享前检查
- external_material_intake：定义外部材料入口
- stage_closeout_pack / closeout_manifest：定义阶段收口与清点

## 十一、当前边界

当前阶段只写设计文档。

不做：

- 不实现 API 网关
- 不新增 adapter 代码
- 不新增 JSON schema 文件
- 不接 Cloudflare
- 不接 Rikkahub
- 不接 GLM 5.1
- 不接本地模型
- 不接顾砚深公屏 MCP
- 不改 nightly job 脚本
- 不自动共享任何内容
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十二、当前结论

memory_gateway_adapter_schema v0.1 定义了 OmbreBrain 未来官方 ChatGPT、API、本地部署、多端入口、公屏候选之间的适配层结构。

它确认：海马体核心不跟任何一个入口、模型、云服务或本地框架焊死。

换身体时换插头，
不要把脑子拆开重装。
