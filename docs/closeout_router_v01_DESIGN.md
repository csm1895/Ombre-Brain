# closeout_router v0.1 设计草案

状态：设计草案
来源：2026-04-24 room_action_router v0.1、cli_space_map v0.1、external_material_intake v0.1，以及当日多颗设计层收口经验
目标：定义 OmbreBrain 每一颗设计文档完成后，如何判断是否需要 usage guide、smoke test、READONLY、本地索引、阶段总收口与下一步路由。

## 一、核心目标

closeout_router 是收口路由层。

它不是自动发布器、自动合并器、自动部署器，也不是自动把所有设计都升级成功能。

它要做的是：

- 防止设计文档写完后散在原地
- 给每颗设计提供统一收口动作
- 判断什么需要进仓库，什么只放本地 _docs
- 判断什么时候该跑 smoke test
- 判断什么时候该写 READONLY 收口卡
- 判断什么时候该阶段总收口
- 判断什么时候可以继续开下一颗

一句话：

设计不是写完就完，
要封箱、贴签、入柜、验灯。

## 二、为什么需要这一层

2026-04-24 当天已经连续完成多颗设计层：

- memory_text_hygiene
- internalized_growth_chain
- external_reference_xiaowo_release
- floating_recall
- living_room / sensory_context
- future_local_deployment_reference
- cli_space_map
- room_action_router
- external_material_intake

实际施工中形成了一条稳定链路：

1. 写 docs/*_DESIGN.md
2. commit + push
3. 更新 docs/nightly_job_v01_USAGE.md
4. 更新本地 OmbreBrain_DOCS_INDEX.md
5. commit + push usage guide
6. 跑 smoke test
7. 写本地 READONLY 收口卡
8. 补本地 _docs 索引
9. 检查无脏尾巴
10. 记住关键状态
11. 决定下一步

closeout_router 就是把这条链路写成规则。

## 三、收口对象类型

### 1. repo_design

仓库设计文档。

默认收口：

- commit
- push
- usage guide 引用
- 本地 DOCS_INDEX 挂载
- smoke test
- 本地 READONLY
- 无脏尾巴检查

### 2. local_reference

本地参考材料卡。

默认收口：

- 写入 ~/Desktop/海马体/_docs
- 更新 OmbreBrain_DOCS_INDEX.md
- 检查无脏尾巴
- 不 commit
- 不 push
- 不进仓库

### 3. stage_closeout

阶段总收口卡。

默认收口：

- 总结当日完成项
- 记录关键提交
- 记录本地 READONLY 卡
- 记录 PR / main / Zeabur / DeepSeek 状态
- 记录未完成项
- 更新 OmbreBrain_DOCS_INDEX.md
- 不一定进仓库

### 4. candidate_only

候选方向卡。

默认收口：

- 写 candidate / reference 摘要
- 记录为什么现在不做
- 标记下一步触发条件
- 不直接开设计
- 不直接写主脑

### 5. repair_note

修复说明。

默认收口：

- 简短记录
- 若影响长期施工方法，进入 READONLY 或 stage closeout
- 若只是临时噪声，不归档

## 四、收口判定

### 1. 什么时候必须写 usage guide

满足以下任一条件：

- 新增 docs/*_DESIGN.md
- 影响 nightly_job 使用方式
- 影响后续施工判断
- 是未来经常需要被引用的设计层

动作：

- 更新 docs/nightly_job_v01_USAGE.md
- commit
- push

### 2. 什么时候必须跑 smoke test

满足以下任一条件：

- 更新了 usage guide
- 新增仓库设计文档后完成挂载
- 修改了脚本相关说明
- 当天连续施工多颗后需要确认流水线未受影响

动作：

- scripts/test_nightly_job_v01.sh "$(pwd)/buckets_graft_merged" _nightly_logs 2026-04-20 2026-04-21

### 3. 什么时候必须写 READONLY

满足以下任一条件：

- 新增一颗设计层
- 新增一张本地参考卡
- 完成一个阶段闭环
- 该内容未来需要快速回看
- 有关键提交、边界、验证状态需要固定

动作：

- 写入 ~/Desktop/海马体/_docs/OmbreBrain_*_READONLY.md
- 更新 OmbreBrain_DOCS_INDEX.md
- 检查无脏尾巴

### 4. 什么时候写阶段总收口

满足以下任一条件：

- 当天完成三颗以上设计层
- 即将下班 / 睡觉 / 换窗口
- 当前施工跨度较大
- PR 状态需要人工回看
- 未完成事项开始变多

动作：

- 写 OmbreBrain_YYYY-MM-DD_STAGE_CLOSEOUT.md
- 更新 DOCS_INDEX
- 记录下一步候选
- 记录 PR / main / Zeabur 状态

### 5. 什么时候可以继续开下一颗

满足以下全部条件：

- 上一颗设计已 commit + push
- usage guide 已引用
- smoke test passed
- READONLY 已写
- DOCS_INDEX 已挂载
- 无脏尾巴
- 当前还有明确下一颗
- 倩倩仍有精力
- 不会破坏阶段总线

动作：

- 去 whiteboard 判断下一颗
- 若下一颗强关联，继续
- 若下一颗偏远，先阶段收口

## 五、固定检查项

每颗收口必须确认：

- branch: nightly-job-v01-readonly
- PR #2: Open
- main: untouched
- Zeabur: untouched
- DeepSeek: not called
- xiaowo-release: not run
- MCP server: not connected unless explicitly stated
- smoke test: passed
- READONLY: exists
- DOCS_INDEX: mounted
- dirty tail: none

## 六、推荐结构

字段：

- id
- type
- created_at
- closeout_target
- target_type
- required_steps
- completed_steps
- verification_commands
- dirty_tail_check
- repo_status
- local_docs_status
- next_route
- status

## 七、示例

### 示例 1：repo_design 收口

target: external_material_intake v0.1
target_type: repo_design
required_steps:
- docs/external_material_intake_v01_DESIGN.md
- commit + push
- update usage guide
- commit + push
- smoke test
- local READONLY
- DOCS_INDEX
- dirty tail check
next_route: write_stage_closeout 或 continue_next_design

### 示例 2：local_reference 收口

target: future_local_deployment_reference v0.1
target_type: local_reference
required_steps:
- local READONLY
- DOCS_INDEX
- dirty tail check
not_required:
- commit
- push
- smoke test

### 示例 3：heredoc 修复

target: READONLY 脏尾巴
target_type: repair_note
required_steps:
- 识别结束标记
- 清理 EOF / PY / marker
- 重新检查
- 如果影响收口卡，记录到当前 READONLY

## 八、当前边界

当前阶段只写设计文档。

不做：

- 不自动合并 main
- 不自动部署 Zeabur
- 不自动改主脑
- 不自动运行外部项目
- 不自动接入 MCP server
- 不自动调用 DeepSeek
- 不把收口路由写成真实执行程序

## 九、当前结论

closeout_router v0.1 是 OmbreBrain 的收口路由层。

它保证每颗设计不是写完就散，
而是按统一顺序：

写好。
挂上。
测过。
收口。
入柜。
留痕。
再决定下一步。

这颗不是让施工慢下来，
是让晚上继续跑也不散架。
