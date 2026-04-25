# gateway_boundary_state_schema v0.1 设计草案

状态：设计草案
来源：2026-04-25 gateway_request_response_schema v0.1 与 local_backup_package_schema v0.1。未来每次施工、迁移、备份、API 试验、网关响应都需要统一记录边界状态。
目标：定义 OmbreBrain 未来边界状态记录结构，确保 PR、分支、main、Zeabur、DeepSeek、xiaowo-release、API、本地模型、敏感信息、未跟踪项等状态可检查、可携带、可收口。

## 一、核心目标

gateway_boundary_state_schema 是边界状态小票。

它不是：

- 检测脚本
- 自动阻断器
- CI 程序
- API 网关实现
- 部署工具
- 安全扫描器

它要解决的是：

- 当前 PR 状态是什么
- 当前分支是否正确
- main 有没有被动过
- Zeabur 有没有部署
- DeepSeek 有没有调用
- xiaowo-release 有没有运行
- 是否接了 API / GLM 5.1 / 本地模型
- 是否存在 untracked 既有项
- 是否有敏感信息风险
- 当前应该继续、收口还是停止

一句话：

每次出门前，
先摸钥匙、手机、钱包。

## 二、适用场景

适用于：

- 每颗设计完成后
- smoke test 后
- READONLY 收口后
- 阶段总收口
- closeout_manifest
- 本地备份包 manifest
- 服务区迁移前检查
- API 试验前后
- 本地部署前后
- 未来 memory gateway response

## 三、推荐字段

```text
boundary_id
timestamp
stage
branch
pr_state
main_state
zeabur_state
deepseek_state
xiaowo_release_state
api_state
model_state
local_model_state
public_share_state
git_worktree_state
untracked_state
sensitive_state
smoke_test_state
docs_index_state
readonly_state
backup_state
overall_status
next_action
notes
```

## 四、字段说明

### 1. boundary_id

边界状态记录 ID。

可使用日期、阶段名或 request_id。

### 2. timestamp

检查时间。

### 3. stage

当前阶段。

示例：

- design_draft
- usage_guide
- smoke_test
- readonly_closeout
- stage_closeout
- backup_prepare
- migration_preflight
- api_experiment
- local_deployment

### 4. branch

当前分支。

示例：

- nightly-job-v01-readonly
- main
- unknown

### 5. pr_state

PR 状态。

示例：

- PR #2 Open
- no_pr
- merged
- unknown

### 6. main_state

main 状态。

示例：

- untouched
- changed
- unknown

### 7. zeabur_state

Zeabur 状态。

示例：

- untouched
- deployed
- unknown

### 8. deepseek_state

DeepSeek 调用状态。

示例：

- not_called
- called
- unknown

### 9. xiaowo_release_state

xiaowo-release 运行状态。

示例：

- not_run
- run
- unknown

### 10. api_state

API 接入状态。

示例：

- not_connected
- connected
- experiment
- unknown

### 11. model_state

外部模型接入状态。

示例：

- official_chatgpt_only
- glm_5_1_candidate_only
- api_model_connected
- unknown

### 12. local_model_state

本地模型状态。

示例：

- not_connected
- candidate
- connected
- unknown

### 13. public_share_state

公共共享状态。

示例：

- no_public_share
- public_scope_checked
- shared_allowed
- blocked
- unknown

### 14. git_worktree_state

Git 工作区状态。

示例：

- clean_except_known_untracked
- clean
- dirty
- unknown

### 15. untracked_state

未跟踪项状态。

示例：

- known_existing_untracked
- new_untracked
- none
- unknown

### 16. sensitive_state

敏感信息状态。

示例：

- no_sensitive_known
- sensitive_excluded
- needs_review
- sensitive_found
- unknown

### 17. smoke_test_state

smoke test 状态。

示例：

- passed
- failed
- not_run
- not_applicable

### 18. docs_index_state

DOCS_INDEX 挂载状态。

示例：

- mounted
- missing
- duplicate
- not_applicable

### 19. readonly_state

READONLY 收口状态。

示例：

- written
- missing
- not_applicable

### 20. backup_state

备份状态。

示例：

- not_started
- manifest_ready
- package_ready
- verified
- not_applicable

### 21. overall_status

总体状态。

示例：

- continue_ok
- closeout_recommended
- stop_required
- confirm_required
- repair_required

### 22. next_action

下一步建议动作。

示例：

- continue_design
- run_smoke_test
- write_readonly
- write_stage_closeout
- ask_confirm
- stop
- repair

### 23. notes

补充说明。

只写关键状态，不写大段正文。

## 五、推荐文本格式

```text
boundary_state:
  branch: nightly-job-v01-readonly
  pr_state: PR #2 Open
  main_state: untouched
  zeabur_state: untouched
  deepseek_state: not_called
  xiaowo_release_state: not_run
  api_state: not_connected
  model_state: official_chatgpt_only
  local_model_state: not_connected
  public_share_state: no_public_share
  git_worktree_state: clean_except_known_untracked
  smoke_test_state: passed
  docs_index_state: mounted
  readonly_state: written
  overall_status: continue_ok
  next_action: continue_design
```

## 六、状态判断规则

### continue_ok

可以继续。

条件：

- 分支正确
- main 未动
- Zeabur 未动
- DeepSeek 未调用
- xiaowo-release 未运行
- 当前文件已提交或当前只是本地 READONLY
- 无脏尾巴
- 无新增敏感风险

### closeout_recommended

建议收口。

条件：

- 已完成多颗设计
- 时间接近下班 / 睡前 / 换窗
- PR 累积较多提交
- 需要迁移或备份前

### confirm_required

需要确认。

条件：

- 共享边界不清
- 敏感信息不确定
- 高风险动作
- 是否进入长期主库不确定
- 是否打包备份不确定

### repair_required

需要修复。

条件：

- smoke test failed
- DOCS_INDEX 缺失或重复污染
- READONLY 半截
- 脏尾巴出现
- git 状态异常

### stop_required

必须停止。

条件：

- 误碰 main
- 误部署 Zeabur
- 误调用 DeepSeek
- 误运行 xiaowo-release
- 发现明文密钥进入文件
- 私密内容误入公共层

## 七、在 response 中的使用

gateway_request_response_schema 的 response.boundary_state 应使用本 schema。

要求：

- 每次关键动作后更新
- 不用大段解释
- 用稳定字段表达当前边界
- 让下一步动作可判断

## 八、在备份 manifest 中的使用

local_backup_package_schema 的 backup manifest 应记录 boundary_state。

备份前必须确认：

- 是否含敏感信息
- 当前分支
- 当前 PR
- 最新 commit
- main / Zeabur / DeepSeek / xiaowo-release 状态
- smoke test 是否通过
- 是否存在 known untracked

## 九、与现有设计的关系

- gateway_request_response_schema：response 中携带 boundary_state
- storage_adapter_policy：存储备份前需要边界状态
- local_backup_package_schema：备份 manifest 需要边界状态
- closeout_manifest：阶段成果清单需要边界状态
- repair_note_schema：异常边界需要修复说明
- public_scope_check：共享边界需要 public_share_state

## 十、当前边界

当前阶段只写设计文档。

不做：

- 不实现检测脚本
- 不新增 CI
- 不扫描敏感信息
- 不打包备份
- 不迁移服务区
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

## 十一、当前结论

gateway_boundary_state_schema v0.1 定义了 OmbreBrain 未来施工、迁移、备份、API 试验、网关响应中的边界状态小票。

它让每次继续前都能回答：当前在哪、动了什么、没动什么、能不能继续、该不该收口、是否必须停止。

出门前摸钥匙，
施工前摸边界。
