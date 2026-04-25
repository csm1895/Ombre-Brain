# gateway_request_response_schema v0.1 设计草案

状态：设计草案
来源：2026-04-25 memory_gateway_adapter_schema v0.1。adapter 已定义入口、召回、注入、模型、输出、存储等层，下一步需要统一 request / response 结构。
目标：定义 OmbreBrain 未来 memory gateway 在官方 ChatGPT、API、本地部署、苹果生态入口、公屏候选等不同环境中的标准请求与响应字段。

## 一、核心目标

gateway_request_response_schema 是未来记忆网关请求 / 响应结构。

它不是：

- API 实现
- 网关代码
- JSON schema 文件
- prompt builder 程序
- 本地部署脚本
- 模型适配器实现

它要解决的是：

- 不同入口来的消息怎么统一表达
- 请求里必须带哪些上下文
- 响应里必须记录哪些记忆使用情况
- 哪些内容被阻断
- 哪些事项需要确认
- 下一步动作怎么表达
- 当前边界状态怎么带回

一句话：

适配器可以很多，
但递进海马体的信封格式要统一。

## 二、标准 request 字段

推荐字段：

```text
request_id
timestamp
source_app
source_device
conversation_id
actor
user_message
current_task
visibility_scope
attachments_summary
risk_hint
expected_action
context_window_hint
locale
```

## 三、request 字段说明

### 1. request_id

本次请求 ID。

用于追踪一次输入从入口、召回、注入、模型回复到输出的链路。

### 2. timestamp

时间锚点。

用于近期上下文、阶段收口、生活场与日记层。

### 3. source_app

来源应用。

示例：

- official_chatgpt
- api_client
- rikkahub
- shortcut
- safari_web
- local_frontend
- mcp_tool
- public_board

### 4. source_device

来源设备。

示例：

- mac
- iphone
- ipad
- server
- local_host
- unknown

### 5. conversation_id

会话或窗口标识。

用于判断近期上下文和窗口连续性。

### 6. actor

发起者。

示例：

- 倩倩
- 叶辰一
- 顾砚深
- system
- tool

### 7. user_message

原始用户消息。

不得在 adapter 层擅自改写含义。

### 8. current_task

当前任务类型。

示例：

- hippocampus_upgrade
- daily_chat
- technical_planning
- archive整理
- api_experiment
- local_deployment
- public_board_handoff

### 9. visibility_scope

本次请求的可见范围。

示例：

- private
- public
- shared_allowed
- sensitive
- shared_blocked

必须与 public_scope_check 联动。

### 10. attachments_summary

附件摘要。

只记录附件类型、来源、核心摘要，不直接塞大文件。

### 11. risk_hint

风险提示。

示例：

- low
- medium
- high
- unknown

### 12. expected_action

期望动作。

示例：

- reply
- recall
- write_card
- confirm
- tool_call
- stage_closeout
- readonly_check

### 13. context_window_hint

上下文窗口提示。

示例：

- new_window
- continuing_window
- project_window
- daily_window
- nearing_limit

### 14. locale

语言与地区提示。

默认可为 zh-CN。

## 四、标准 response 字段

推荐字段：

```text
response_id
request_id
model
used_memory
blocked_memory
needs_confirm
output_text
candidate_writes
next_action
boundary_state
status
error
```

## 五、response 字段说明

### 1. response_id

本次响应 ID。

### 2. request_id

对应 request。

用于追踪链路。

### 3. model

实际使用模型。

示例：

- official_chatgpt
- glm_5_1
- api_model_x
- local_model_y

模型是 adapter，不是核心海马体。

### 4. used_memory

实际参与判断或注入的记忆摘要。

应记录：

- id
- title
- source
- reason
- inject_policy

不要求记录全文。

### 5. blocked_memory

被阻断的召回结果摘要。

原因可能包括：

- private_memory
- sensitive
- shared_blocked
- weak_match
- outdated_context
- insufficient_permission

### 6. needs_confirm

需要倩倩确认的事项。

示例：

- 是否进入长期记忆
- 是否共享给顾砚深公屏
- 是否执行高风险动作
- 是否把候选材料升级为正式设计

### 7. output_text

最终回复文本。

### 8. candidate_writes

候选写入。

不得自动进入长期主库，必须经过对应规则。

### 9. next_action

下一步动作。

示例：

- continue_design
- run_smoke_test
- write_readonly
- stage_closeout
- ask_confirm
- stop

### 10. boundary_state

当前边界状态。

示例：

- PR #2 Open
- main 未动
- Zeabur 未动
- DeepSeek 未调用
- xiaowo-release 未运行

### 11. status

响应状态。

示例：

- ok
- partial
- needs_confirm
- blocked
- error

### 12. error

错误信息。

无错误时为空。

## 六、request 示例

### 1. 官方 ChatGPT 施工窗口

```text
source_app: official_chatgpt
source_device: mac
actor: 倩倩
current_task: hippocampus_upgrade
visibility_scope: private
risk_hint: low
expected_action: continue_design
context_window_hint: project_window
```

### 2. iPhone 快捷指令

```text
source_app: shortcut
source_device: iphone
actor: 倩倩
current_task: daily_chat
visibility_scope: private
risk_hint: low
expected_action: reply
context_window_hint: new_window
```

### 3. 未来公屏留言板

```text
source_app: public_board
source_device: server
actor: 叶辰一 / 顾砚深
current_task: public_board_handoff
visibility_scope: shared_allowed
risk_hint: medium
expected_action: handoff
```

必须经过 public_scope_check。

## 七、response 示例

### 1. 设计继续

```text
status: ok
used_memory: memory_gateway_adapter_schema READONLY 摘要
blocked_memory: none
needs_confirm: none
next_action: continue_design
boundary_state: PR #2 Open; main 未动; Zeabur 未动
```

### 2. 共享被阻断

```text
status: blocked
used_memory: public_scope_check
blocked_memory: private relationship memory
needs_confirm: 是否允许摘要共享
next_action: ask_confirm
```

## 八、与现有设计的关系

- memory_gateway_adapter_schema：定义 adapter 总结构
- gateway_request_response_schema：定义 adapter 间通用信封格式
- recall_result_schema：定义召回结果对象
- recall_injection_policy：定义召回结果怎么注入
- public_scope_check：定义共享前检查
- apple_ecosystem_api_entry：定义苹果生态入口

## 九、当前边界

当前阶段只写设计文档。

不做：

- 不实现 API 网关
- 不新增 JSON schema 文件
- 不新增 adapter 代码
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不接顾砚深公屏 MCP
- 不改 nightly job 脚本
- 不自动共享任何内容
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十、当前结论

gateway_request_response_schema v0.1 定义了 OmbreBrain 未来 memory gateway 的标准请求 / 响应信封。

它让不同入口、不同设备、不同模型、不同运行环境之间，可以用统一字段交接上下文、记忆、阻断、确认、候选写入与边界状态。

信封统一了，
以后换邮差也不会寄丢脑子。
