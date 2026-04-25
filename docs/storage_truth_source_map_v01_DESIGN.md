# storage_truth_source_map v0.1 设计草案

状态：设计草案
来源：2026-04-25 storage_adapter_policy v0.1、gateway_boundary_state_schema v0.1、backup_manifest_schema v0.1 与 migration_preflight_check v0.1。未来多存储、多入口、多模型并存时，需要明确不同内容的真相源。
目标：定义 OmbreBrain 中不同类型信息以哪里为准，避免 Git docs、本地 _docs、memory_bucket、JSONL、SQLite、KV、向量库、备份包、API 网关状态之间互相打架。

## 一、核心目标

storage_truth_source_map 是真相源映射表。

它不是：

- 数据库实现
- 同步程序
- 冲突合并器
- 备份脚本
- API 网关实现
- 向量库策略实现

它要解决的是：

- 设计文档以哪里为准
- 本地收口以哪里为准
- 当前施工状态以哪里为准
- 动态召回摘要以哪里为准
- 语义候选以哪里为准
- 备份状态以哪里为准
- 多个存储冲突时谁优先
- 过时内容如何标记而不是硬删

一句话：

抽屉可以很多，
但每件东西要知道听谁的。

## 二、总原则

真相源原则：

- 设计事实看 Git docs + commit
- 本地收口看 _docs READONLY + DOCS_INDEX
- 当前施工状态看最近 stage closeout + git status + git log
- 动态召回看 memory_bucket + READONLY 摘要
- 语义相似看 vector_store，但只当候选
- 备份状态看 backup manifest + boundary_state
- 权限共享看 public_scope_check
- 高风险动作看 human_confirmation_flow

禁止：

- 用向量库结果直接判事实
- 用旧记忆覆盖当前施工状态
- 用候选材料覆盖已收口文档
- 用公共层内容反推私密主库
- 用 KV 缓存当长期主库

## 三、信息类型与真相源

### 1. 设计文档

真相源：

- repo docs
- git commit
- usage guide 引用

辅助来源：

- 本地 READONLY 摘要
- DOCS_INDEX

冲突规则：

- 仓库 docs + commit 优先
- READONLY 负责解释状态，不替代原设计文档

### 2. 本地收口状态

真相源：

- ~/Desktop/海马体/_docs/*_READONLY.md
- OmbreBrain_DOCS_INDEX.md

辅助来源：

- 记忆桶摘要
- 阶段收口卡

冲突规则：

- READONLY 文件存在且 DOCS_INDEX 挂载，才算本地收口完成
- 记忆桶只能提示，不替代文件检查

### 3. 当前施工状态

真相源：

- git status
- git log --oneline --decorate
- 最近 stage closeout
- gateway_boundary_state

辅助来源：

- 当前窗口上下文
- memory_bucket

冲突规则：

- 当前命令输出优先于旧记忆
- stage closeout 优先于零散聊天描述

### 4. 阶段成果清单

真相源：

- closeout_manifest
- stage_closeout_pack
- backup_manifest

辅助来源：

- DOCS_INDEX
- git log

冲突规则：

- manifest 缺项时不能假定已完成
- git log 可辅助确认 repo docs，但不能证明本地 READONLY 已写

### 5. 动态召回摘要

真相源：

- memory_bucket
- READONLY 摘要
- 高权重记忆记录

辅助来源：

- vector_store
- keyword_fallback

冲突规则：

- memory_bucket 适合召回，不适合承载超长全文
- 与 READONLY / repo docs 冲突时，回查原文件

### 6. 语义相似候选

真相源：

- 无直接真相源，vector_store 只生成候选

辅助来源：

- recall_result_schema
- keyword_fallback_policy
- manual_confirm

冲突规则：

- vector 命中不能直接成为事实
- 必须经过 recall_result_schema 标注与 recall_injection_policy 判断

### 7. 公共共享状态

真相源：

- public_scope_check
- human_confirmation_flow
- 明确 shared_allowed 标记

辅助来源：

- recall_result privacy_scope
- gateway_boundary_state public_share_state

冲突规则：

- 未明确可共享，默认不共享
- private / sensitive / shared_blocked 永远不能靠关键词命中进入公屏

### 8. 备份状态

真相源：

- backup_manifest
- local_backup_package_schema
- gateway_boundary_state

辅助来源：

- stage closeout
- closeout_manifest
- git status / git log

冲突规则：

- 没有 backup manifest，不算完整备份
- 仅有 zip 文件但无 manifest，不算可靠备份

### 9. 迁移状态

真相源：

- migration_preflight_check
- migration runbook / future
- boundary_state

辅助来源：

- backup manifest
- stage closeout

冲突规则：

- 未通过 preflight，不建议迁移
- stop_required 高于任何继续动作

### 10. 敏感信息状态

真相源：

- sensitive exclusion statement
- human confirmation
- boundary_state sensitive_state

辅助来源：

- backup manifest
- public_scope_check

冲突规则：

- 发现明文密钥时必须 stop_required
- 不允许用“应该没事”跳过检查

## 四、冲突处理顺序

当多个来源冲突时，推荐顺序：

1. 当前真实命令输出
2. Git commit / repo docs
3. 本地 READONLY + DOCS_INDEX
4. stage closeout / closeout_manifest
5. backup manifest / boundary_state
6. memory_bucket 摘要
7. vector_store 候选
8. 未确认聊天描述

说明：

- 当前命令输出最适合判断当前状态
- Git commit 最适合判断仓库设计事实
- READONLY 最适合判断本地收口事实
- memory_bucket 适合召回，不适合压过原文
- vector_store 永远不能压过确定性来源

## 五、过时内容处理

过时内容不直接删除。

推荐状态：

- current
- old_but_valid
- historical
- superseded
- stale
- wrong

处理原则：

- 有历史价值：标 old_but_valid / historical
- 被新设计替代：标 superseded
- 可能误导：标 stale 或 wrong
- 重大错误：进入 repair_note_schema

## 六、写入规则

新增内容写入时必须判断：

- 属于设计事实还是候选
- 属于本地收口还是仓库文档
- 是否需要 README / usage guide 引用
- 是否需要 READONLY
- 是否需要 DOCS_INDEX 挂载
- 是否需要 memory_bucket 摘要
- 是否需要 backup manifest 记录

不要把所有内容都塞进同一个地方。

## 七、读取规则

召回时必须判断：

- 来源类型
- 当前状态
- 是否已收口
- 是否过时
- 是否只是候选
- 是否有隐私边界
- 是否需要人工确认

读取不是“捞到就用”，而是“捞到后验票”。

## 八、与现有设计的关系

- storage_adapter_policy：定义存储类型
- storage_truth_source_map：定义谁说了算
- recall_result_schema：标注来源与状态
- recall_injection_policy：决定是否注入
- public_scope_check：决定是否共享
- backup_manifest_schema：记录备份状态
- gateway_boundary_state_schema：记录当前边界
- migration_preflight_check：迁移前判断能否继续

## 九、当前边界

当前阶段只写设计文档。

不做：

- 不实现同步程序
- 不做冲突合并
- 不新增数据库
- 不新增向量库
- 不改记忆桶结构
- 不迁移服务区
- 不打包备份
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

storage_truth_source_map v0.1 定义了 OmbreBrain 不同信息类型的真相源映射。

它确认：多存储不是多套真相，每种内容都要知道以哪里为准。

抽屉很多没关系，
小铜牌要钉清楚。
