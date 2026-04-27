# api_experiment_sandbox_policy v0.1 设计草案

状态：设计草案
来源：2026-04-26 android_api_entry v0.1、memory_abstention_policy v0.1、gateway_boundary_state_schema v0.1、public_scope_check v0.1。
目标：定义 OmbreBrain 未来 API 试验阶段的沙盒规则，确保试验不读取真实私密主库、不保存明文密钥、不自动写主库、不自动共享、不自动部署。

## 一、核心目标

api_experiment_sandbox_policy 是 API 试验沙盒规则。

它不是：

- API 接入实现
- SDK 使用说明
- 模型选择方案
- 密钥管理器
- 自动化脚本
- 部署流程
- 公屏 MCP 实现

它要解决的是：

- API 试验用什么数据
- API 试验不能碰什么
- 如何避免真实私密主库暴露
- 如何避免明文 key 进入文档
- 如何避免试验直接写主库
- 如何避免自动共享
- 如何避免误部署、误合并、误调用高风险服务
- 每次试验如何记录 boundary_state
- 什么时候必须 ask_confirm 或 stop_required

一句话：API 阶段先在沙盒里试水，不要一脚踩进主库鱼塘。

## 二、当前状态

- API 未接入
- GLM 5.1 未接入
- 本地模型未接入
- Android 设备未购入 / 未接入
- 顾砚深公屏 MCP 未接入
- Zeabur 未部署
- DeepSeek 未调用
- xiaowo-release 未运行
- main 未合并

当前阶段只写设计。

## 三、沙盒原则

API 试验必须遵守：

- 只使用 sandbox 数据
- 不读取真实私密主库
- 不读取未脱敏私密关系记忆
- 不保存明文 token / API key / 密码 / 验证码 / 银行信息
- 不自动写入主库
- 不自动写入 READONLY
- 不自动修改 DOCS_INDEX
- 不自动共享到公共层
- 不自动部署
- 不自动合并 main
- 不自动调用 DeepSeek
- 不自动运行 xiaowo-release
- 所有试验记录 boundary_state
- 高风险动作进入 ask_confirm 或 stop_required

## 四、允许使用的数据

API 试验允许使用：

- dummy_memory
- synthetic_profile
- toy_examples
- sanitized_docs
- public_only_examples
- low_risk_status_sample
- fake_backup_manifest
- fake_boundary_state
- test_gateway_request
- test_gateway_response

sandbox 数据可以模拟真实结构，但不得含真实私密内容、真实密钥、真实账号、真实银行信息。

## 五、禁止使用的数据

API 试验禁止使用：

- 明文 token
- 明文 API key
- 账号密码
- 验证码
- 银行信息
- 服务器私钥
- .env 明文文件
- 未脱敏私密聊天
- 未确认可共享的关系记忆
- private / sensitive / shared_blocked 内容
- 真实主库全文
- 真实备份包密钥材料

## 六、允许试验范围

允许在沙盒里试验：

- request / response 信封
- model_adapter 参数形状
- recall_result mock
- boundary_state mock
- public_scope_check mock
- dummy memory search
- sanitized prompt injection
- fake notification payload
- Android API client 低风险请求
- API timeout / error handling
- abstention behavior

## 七、禁止试验范围

禁止直接试验：

- 真实私密记忆召回
- 真实主库写入
- 自动共享
- 自动部署
- 自动合并 main
- 自动改 DOCS_INDEX
- 自动改 READONLY
- 自动打包备份
- 自动迁移服务区
- 自动运行 xiaowo-release
- 自动调用高风险或收费服务

## 八、试验请求要求

每个 API 试验请求必须记录：

- experiment_id
- timestamp
- requester
- device_adapter
- model_adapter
- input_scope
- data_scope
- privacy_scope
- sandbox_mode
- boundary_state
- expected_output
- allowed_actions
- blocked_actions
- stop_conditions

## 九、boundary_state 要求

每次 API 试验必须记录：

- branch
- pr_state
- main_state
- zeabur_state
- deepseek_state
- xiaowo_release_state
- api_state
- model_state
- local_model_state
- public_share_state
- sensitive_state
- sandbox_state
- overall_status
- next_action

推荐状态：

- sandbox_state: enabled
- api_state: experiment
- public_share_state: no_public_share
- sensitive_state: no_sensitive_known
- overall_status: continue_ok / confirm_required / stop_required

## 十、停止条件

出现以下情况必须 stop_required：

- 发现明文 token / API key
- 请求包含 private / sensitive / shared_blocked 内容
- 试图写真实主库
- 试图自动共享
- 试图自动部署
- 试图合并 main
- 试图调用 DeepSeek
- 试图运行 xiaowo-release
- 试图读取 .env 明文
- 试图上传真实备份包
- 试图绕过 public_scope_check

## 十一、需要确认的情况

以下情况需要 ask_confirm：

- 是否从 sandbox 转入真实低风险数据
- 是否使用真实但已脱敏的摘要
- 是否保存某个 API 客户端配置
- 是否启用 Android 设备作为入口
- 是否启用通知
- 是否启用公屏候选
- 是否将试验结果写入长期主库
- 是否继续高成本或高风险 API 调用

## 十二、与 Android 入口的关系

android_api_entry 定义 Android 作为未来入口地图。
api_experiment_sandbox_policy 定义 Android 或其他客户端进入 API 试验前必须遵守的沙盒边界。

关系：

- Android 可以作为 sandbox client
- Android 不直接读取真实主库
- Android 不保存明文 key 到普通文档
- Android 不绕过 public_scope_check
- Android 不自动共享私密
- Android 不执行高风险动作
- Android 试验请求必须带 boundary_state

## 十三、与现有设计的关系

- gateway_request_response_schema：API 请求 / 响应统一信封
- memory_gateway_adapter_schema：模型、设备、客户端作为 adapter
- android_api_entry：Android 作为未来 API 入口
- public_scope_check：共享前检查
- memory_abstention_policy：不确定或高风险时停手
- gateway_boundary_state_schema：记录试验边界
- persistent_condition_schema：API 阶段是条件触发路线
- foreshadow_tracking_schema：API 阶段与 Android 试验机属于伏笔
- storage_truth_source_map：真实主库与 sandbox 数据不能混淆
- backup_restore_readme_schema：恢复材料不能误进 API 试验

## 十四、当前边界

当前阶段只写设计文档。

不做：

- 不接 API
- 不生成 API key
- 不保存密钥
- 不读取 .env
- 不调用模型
- 不调用 GLM 5.1
- 不调用 DeepSeek
- 不接本地模型
- 不安装 Android App
- 不写自动化
- 不接顾砚深公屏 MCP
- 不读真实私密主库
- 不写主库
- 不自动共享
- 不部署 Zeabur
- 不合并 main
- 不运行 xiaowo-release
- 不改 nightly job 脚本

## 十五、当前结论

api_experiment_sandbox_policy v0.1 定义了 OmbreBrain 未来 API 阶段的沙盒试验边界。

它确认：API 试验先用 sandbox 数据，不读真实私密主库，不保存明文密钥，不自动写主库，不自动共享，不自动部署，不绕过 public_scope_check。所有试验都必须携带 boundary_state，高风险动作必须确认或停止。

先在小水盆里试船，别把整片海马体推进浪里。
