# android_api_entry v0.1 设计草案

状态：设计草案
来源：2026-04-25 至 2026-04-26 海马体升级施工。倩倩提到云服务器迁移后，可能买一台安卓手机，用于接很多 API App。此前 apple_ecosystem_api_entry 已定义苹果生态入口，本设计补充未来安卓设备入口地图。
目标：定义 Android 设备在 OmbreBrain 未来 API 阶段中的入口位置、适用场景、触发条件、边界规则与不能承担的职责，确保它作为 adapter 接入，而不是替代海马体本体。

## 一、核心目标

android_api_entry 是安卓 API 入口地图。

它不是：

- 安卓 App 实现
- API 接入脚本
- 设备购买建议
- 模型客户端选择
- 本地部署方案
- 公屏 MCP 实现
- 自动化执行器

它要解决的是：

- 安卓手机在未来 API 阶段处于什么位置
- 它和苹果全家桶是什么关系
- 它能作为哪些入口
- 它不能替代什么
- 什么时候才考虑启用
- 是否能接公屏 / 通知 / 自动化 / 模型 App
- 如何避免绕过海马体边界

一句话：

安卓手机是未来的一扇门，
不是把脑子搬进手机壳里。

## 二、当前状态

当前状态：

- candidate_plan
- 未购入
- 未接入
- 未选择具体设备
- 未选择具体 App
- 未接 API
- 未接 GLM 5.1
- 未接本地模型
- 未接公屏 MCP

当前阶段只做设计。

## 三、触发条件

启用安卓 API 入口前，应满足：

- 海马体升级阶段收口
- 服务区 / 云服务器迁移完成
- 稳定云服务区选定
- 本地备份策略明确
- API sandbox 规则明确
- public_scope_check 已可用
- gateway_boundary_state 可记录
- 倩倩确认需要购买 / 使用安卓设备

推荐触发条件：

- after_hippocampus_upgrade
- after_server_migration
- when_server_region_stable
- when_api_phase_starts
- when_user_confirms_device_purchase

## 四、与苹果生态的关系

apple_ecosystem_api_entry 已定义：

- Mac
- iPhone
- iPad
- Safari
- 快捷指令
- 通知
- 云服务器
- 本地服务

android_api_entry 作为补充入口，不替代苹果生态。

关系：

- 苹果全家桶仍是倩倩当前主力生态
- Android 可作为 API App 试验机
- Android 可作为部分模型客户端入口
- Android 可作为通知 / 自动化 / 公屏候选入口
- Android 不承担主库真相源职责
- Android 不直接替代 Mac / iPhone / iPad

## 五、可能入口类型

### 1. API App 入口

用途：

- 测试不同 API 客户端
- 连接不同模型服务
- 试验多 App 生态
- 作为轻量交互入口

边界：

- 不直接改主库
- 不绕过 gateway_request_response_schema
- 不绕过 recall_injection_policy
- 不保存明文 key 到普通文档
- 不作为唯一入口

### 2. 模型客户端入口

用途：

- 测试 GLM 5.1 或其他模型候选
- 对比不同模型响应
- 作为 API 阶段试验客户端

边界：

- GLM 5.1 当前只是候选偏好
- 模型客户端不是海马体本体
- 模型输出必须经过 memory_gateway / boundary_state 判断

### 3. 通知入口

用途：

- 未来接收提醒
- 接收状态通知
- 接收任务完成提示
- 接收公屏留言候选

边界：

- 不推送私密内容到公共通知
- 通知内容应最小化
- 敏感内容只显示低风险摘要或占位
- 高风险内容需要确认

### 4. 自动化入口

用途：

- 未来试验 Android 自动化工具
- 触发轻量 API 请求
- 触发状态查询
- 触发低风险日志写入

边界：

- 不自动执行高风险动作
- 不自动部署
- 不自动合并 main
- 不自动调用收费 / 高风险 API
- 不自动共享私密内容

### 5. 公屏 / 留言板候选入口

用途：

- 未来可能接顾砚深公屏 MCP
- 接收 shared_allowed 范围内的公共任务
- 作为留言板查看或低风险回复入口

边界：

- 私密不共享
- private / sensitive / shared_blocked 阻断
- 公屏内容必须走 public_scope_check
- 顾砚深公屏 MCP 暂缓到云服务器迁移后
- Android 入口不能绕过共享边界

### 6. 备份 / 状态查看入口

用途：

- 查看 boundary_state
- 查看 stage snapshot
- 查看 backup manifest 摘要
- 查看迁移前检查状态

边界：

- 只读优先
- 不直接打包备份
- 不直接上传云端
- 不保存明文密钥

## 六、推荐 adapter 结构

Android 作为 adapter，可拆成：

- android_device_adapter
- android_api_client_adapter
- android_notification_adapter
- android_automation_adapter
- android_public_board_adapter
- android_status_view_adapter

每个 adapter 都应声明：

- input_type
- output_type
- auth_boundary
- privacy_scope
- allowed_actions
- blocked_actions
- required_gateway_checks

## 七、allowed_actions

当前未来候选允许动作：

- read_status
- send_low_risk_prompt
- receive_notification
- view_public_board
- send_shared_allowed_message
- test_api_client
- view_backup_manifest_summary
- view_stage_snapshot

## 八、blocked_actions

默认阻断动作：

- write_main_memory_directly
- bypass_public_scope_check
- share_private_memory
- store_plaintext_token
- auto_deploy
- auto_merge_main
- auto_run_xiaowo_release
- auto_call_deepseek
- overwrite_backup
- delete_readonly
- modify_docs_index_without_confirm

## 九、隐私与安全边界

Android 入口必须遵守：

- private 不共享
- sensitive 不共享
- shared_blocked 不共享
- public_scope_check 未通过不共享
- 明文 token / API key / 密码 / 验证码 / 银行信息不进入普通文档
- 高风险动作走 human_confirmation_flow
- 关键写入走 gateway_boundary_state 记录

## 十、与现有设计的关系

- apple_ecosystem_api_entry：苹果生态入口地图
- android_api_entry：安卓设备入口地图
- memory_gateway_adapter_schema：定义设备 / 客户端作为 adapter
- gateway_request_response_schema：Android 请求应进入统一信封
- recall_injection_policy：召回内容进入上下文前需判断
- public_scope_check：公屏 / 留言板共享前必须检查
- persistent_condition_schema：Android 是 candidate_plan / conditional
- foreshadow_tracking_schema：Android API 试验机属于迁移后伏笔
- memory_abstention_policy：条件未满足时不执行
- gateway_boundary_state_schema：记录 API / model / public share 状态

## 十一、典型状态记录

Android API 入口当前建议记录为：

- condition_type: candidate_plan
- condition_status: pending
- effective_scope: api_phase
- trigger_condition: after_hippocampus_upgrade_and_server_migration
- confirmation_state: unconfirmed_purchase
- privacy_scope: private
- conflict_policy: mark_candidate

foreshadow 建议记录为：

- pending_topic: 安卓 API 试验机
- related_project: api_phase
- deferred_reason: 海马体升级和云服务器迁移后再考虑
- deferred_until: after_hippocampus_upgrade_and_server_migration
- trigger_condition: when_api_phase_starts
- status: candidate
- next_action: ask_confirm / device_research

## 十二、当前边界

当前阶段只写设计文档。

不做：

- 不买设备
- 不推荐具体安卓型号
- 不安装 App
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不接顾砚深公屏 MCP
- 不写快捷指令
- 不写安卓自动化
- 不改本地网络
- 不保存密钥
- 不部署云服务
- 不迁移服务区
- 不改 nightly job 脚本
- 不自动共享任何内容
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十三、当前结论

android_api_entry v0.1 定义了 Android 设备在 OmbreBrain 未来 API 阶段中的入口地图。

它确认：安卓手机可以作为未来 API App、模型客户端、通知、自动化、公屏候选和状态查看入口，但只能作为 adapter，不能替代海马体本体，不能绕过 public_scope_check，不能直接共享私密，也不能提前执行尚未触发的候选计划。

安卓是一扇未来的门，
门后接的还是同一颗海马体。
