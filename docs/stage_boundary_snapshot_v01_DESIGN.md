# stage_boundary_snapshot v0.1 设计草案

状态：设计草案
来源：2026-04-25 gateway_boundary_state_schema v0.1、storage_truth_source_map v0.1，以及今晚多颗设计连续完成后的阶段收口需求。
目标：定义 OmbreBrain 阶段快照结构，用于阶段总收口、迁移前、备份前、换窗前，记录某一时刻完成项、关键提交、本地 READONLY、DOCS_INDEX、边界状态、下次候选与是否建议继续。

## 一、核心目标

stage_boundary_snapshot 是阶段边界快照。

它不是：

- 阶段总收口卡
- closeout_manifest
- 备份 manifest
- 自动检查脚本
- 自动生成器
- 迁移工具

它要解决的是：

- 某一阶段当前完成了什么
- 哪些设计已提交
- 哪些 usage guide 已引用
- 哪些本地 READONLY 已写
- DOCS_INDEX 是否挂载
- smoke test 是否通过
- 当前边界状态是否干净
- 下次候选是什么
- 当前适合继续、收口还是停止

一句话：

阶段快照不是收工，
是给当前工地拍一张带时间戳的全景照。

## 二、适用场景

适用于：

- 阶段总收口前
- 多颗设计连续完成后
- 服务区迁移前
- 本地备份前
- 换窗前
- 睡前停工前
- API 试验前后
- 本地部署前后

不适用于：

- 单颗设计刚开始
- 尚未完成任何验证
- 没有明确阶段边界的日常聊天

## 三、推荐字段

```text
snapshot_id
timestamp
stage_name
stage_reason
branch
pr_state
completed_items
repo_docs
usage_guide_refs
local_readonly_cards
docs_index_state
smoke_test_state
boundary_state
truth_source_notes
known_untracked
sensitive_state
next_candidates
overall_status
next_action
notes
```

## 四、字段说明

### 1. snapshot_id

阶段快照 ID。

推荐格式：

```text
stage_snapshot_YYYY-MM-DD_HHMM_<stage>
```

### 2. timestamp

快照时间。

### 3. stage_name

阶段名称。

示例：

- memory_gateway_upgrade
- recall_chain_upgrade
- migration_backup_chain
- evening_stage_closeout
- before_server_migration

### 4. stage_reason

为什么拍这张快照。

示例：

- 多颗设计连续完成
- 准备阶段总收口
- 服务区迁移前
- 本地备份前
- 换窗前

### 5. branch / pr_state

当前分支与 PR 状态。

示例：

- branch: nightly-job-v01-readonly
- pr_state: PR #2 Open

### 6. completed_items

本阶段完成的颗粒清单。

应记录：

- 设计名
- 状态
- 是否 repo doc 完成
- 是否 usage guide 引用
- 是否 smoke test passed
- 是否 READONLY 写入
- 是否 DOCS_INDEX 挂载

### 7. repo_docs

仓库设计文档清单。

记录路径，例如：

- docs/memory_gateway_reference_v01_DESIGN.md
- docs/storage_truth_source_map_v01_DESIGN.md

### 8. usage_guide_refs

usage guide 引用状态。

记录：

- 已引用
- 未引用
- 不适用

### 9. local_readonly_cards

本地 READONLY 收口卡清单。

记录：

- 文件名
- 是否存在
- 是否 DOCS_INDEX 挂载
- 是否无脏尾巴

### 10. docs_index_state

DOCS_INDEX 状态。

示例：

- mounted
- missing
- needs_review

### 11. smoke_test_state

smoke test 状态。

示例：

- passed
- failed
- not_run
- partial

### 12. boundary_state

边界状态小票。

应引用 gateway_boundary_state_schema。

至少记录：

- main_state
- zeabur_state
- deepseek_state
- xiaowo_release_state
- api_state
- model_state
- local_model_state
- public_share_state

### 13. truth_source_notes

真相源说明。

用于说明本快照以什么为准。

示例：

- repo docs 以 git commit 为准
- 本地收口以 READONLY + DOCS_INDEX 为准
- 当前状态以 git status / git log 为准

### 14. known_untracked

已知未跟踪项。

记录既有 untracked，不误处理。

### 15. sensitive_state

敏感信息状态。

示例：

- no_sensitive_known
- needs_review
- sensitive_found

### 16. next_candidates

下次候选。

只列候选，不写成已完成。

### 17. overall_status

整体状态。

可选：

- continue_ok
- closeout_recommended
- stop_required
- confirm_required
- repair_required

### 18. next_action

下一步动作。

可选：

- continue_design
- write_stage_closeout
- write_backup_manifest
- run_preflight
- ask_confirm
- stop

### 19. notes

补充说明。

只写关键状态，不写流水账。

## 五、推荐文本结构

```text
# OmbreBrain Stage Boundary Snapshot

## 一、基础信息
## 二、本阶段完成项
## 三、仓库设计文档
## 四、usage guide 引用
## 五、本地 READONLY
## 六、DOCS_INDEX 状态
## 七、验证状态
## 八、边界状态小票
## 九、真相源说明
## 十、已知未跟踪项
## 十一、敏感信息状态
## 十二、下次候选
## 十三、当前判断
```

## 六、当前判断规则

### continue_ok

适合继续。

条件：

- 当前阶段尚未过长
- 边界状态干净
- smoke test passed
- 当前颗粒未过多
- 无敏感风险

### closeout_recommended

建议收口。

条件：

- 已完成多颗设计
- 时间接近睡前 / 换窗 / 下班
- 准备迁移 / 备份前
- PR 提交已较多
- 本阶段主线已经完整

### confirm_required

需要确认。

条件：

- 是否继续开新颗粒不确定
- 是否开始阶段总收口不确定
- 是否进入迁移 / 备份流程不确定
- 是否共享或写入高权重内容不确定

### repair_required

需要修复。

条件：

- 某颗 READONLY 缺失
- DOCS_INDEX 缺挂载
- smoke test failed
- 有脏尾巴
- git 状态异常

### stop_required

必须停止。

条件：

- 误碰 main
- 误部署 Zeabur
- 误调用 DeepSeek
- 误运行 xiaowo-release
- 发现敏感信息泄露
- 私密内容误入公共层

## 七、与 stage_closeout 的区别

stage_boundary_snapshot 是快照。

它记录当前一刻状态，帮助判断是否继续或收口。

stage_closeout_pack 是收工包。

它在决定收口后，正式总结本阶段完成项、结论和下次候选。

关系：

- snapshot 可以先于 closeout
- closeout 可以引用 snapshot
- snapshot 不替代 closeout

## 八、与现有设计的关系

- gateway_boundary_state_schema：提供边界状态字段
- storage_truth_source_map：说明各项状态以哪里为准
- closeout_manifest：提供成果清单
- stage_closeout_pack：正式阶段收口
- backup_manifest_schema：备份时引用快照
- migration_preflight_check：迁移前引用快照

## 九、当前边界

当前阶段只写设计文档。

不做：

- 不生成阶段快照文件
- 不做阶段总收口
- 不打包备份
- 不迁移服务区
- 不实现自动检查
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不改 nightly job 脚本
- 不自动共享任何内容
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十、当前结论

stage_boundary_snapshot v0.1 定义了 OmbreBrain 阶段边界快照结构。

它让阶段总收口、迁移前、备份前、换窗前都可以先拍一张全景照，再决定继续、收口、确认、修复或停止。

工地可以继续干，
但先拍照，免得工具藏进影子里。
