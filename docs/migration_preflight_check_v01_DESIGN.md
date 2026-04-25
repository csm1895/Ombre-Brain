# migration_preflight_check v0.1 设计草案

状态：设计草案
来源：2026-04-25 storage_adapter_policy、local_backup_package_schema、gateway_boundary_state_schema、backup_manifest_schema。倩倩确认：服务区迁移前需要先把海马体升级版收一次工，稳定云服务区选定后再做本地保存与备份。
目标：定义 OmbreBrain 服务区 / 云服务器迁移前的预检清单，判断当前是否可以迁移、需要确认、需要修复或必须停止。

## 一、核心目标

migration_preflight_check 是迁移前预检规则。

它不是：

- 服务器迁移脚本
- 云服务部署程序
- 备份打包工具
- 回滚脚本
- API 网关实现
- 安全扫描器

它要解决的是：

- 迁移前海马体是否已收口
- 当前成果是否已清点
- 本地 READONLY 是否齐全
- DOCS_INDEX 是否挂好
- smoke test 是否通过
- 边界状态是否干净
- 备份包是否准备好
- 敏感信息是否排除
- 是否有回滚入口
- 当前能不能迁移

一句话：

搬家前先看门口清单，
猫、钥匙、煤气，一个都不能漏。

## 二、适用场景

适用于：

- 云服务器迁移前
- 服务区切换前
- 稳定云服务区落定前
- API 阶段正式试验前
- 本地部署前大备份前
- 重要 PR 大收口前

不适用于：

- 单颗设计普通收口
- 未完成阶段中途
- 没有迁移计划的日常施工

## 三、预检结论枚举

### 1. migrate_ready

可以迁移。

条件：

- 阶段收口完成
- closeout_manifest 完成
- 本地 READONLY 齐全
- DOCS_INDEX 齐全
- smoke test passed
- boundary_state 干净
- backup manifest 准备好
- 敏感信息已排除
- 回滚入口明确

### 2. confirm_required

需要倩倩确认。

条件：

- 是否迁移时机不确定
- 是否打包备份不确定
- 是否包含部分敏感配置说明不确定
- 是否有未完成事项需要带走不确定
- 是否需要暂停当前 PR 不确定

### 3. repair_required

需要修复后再迁移。

条件：

- DOCS_INDEX 缺项
- READONLY 半截
- smoke test failed
- 脏尾巴出现
- git 状态异常
- backup manifest 缺项

### 4. stop_required

必须停止迁移。

条件：

- 发现明文 token / API key / 密码 / 验证码
- 误碰 main
- 误部署 Zeabur
- 误调用 DeepSeek
- 误运行 xiaowo-release
- 私密内容误入公共层
- 回滚入口不明

### 5. not_applicable

当前不适用迁移预检。

条件：

- 只是普通设计施工
- 只是本地 READONLY 收口
- 没有服务区迁移动作

## 四、预检清单

### 1. 阶段收口检查

必须确认：

- 是否已有阶段总收口卡
- 是否记录本阶段完成项
- 是否记录下次候选
- 是否记录未完成事项
- 是否记录边界状态

### 2. closeout_manifest 检查

必须确认：

- 是否有阶段成果清单
- 是否列出 repo docs
- 是否列出 local docs
- 是否列出 smoke test 状态
- 是否列出 PR / 分支状态
- 是否列出不合并 / 不部署边界

### 3. 本地 READONLY 检查

必须确认：

- 关键 READONLY 是否都存在
- 是否挂入 DOCS_INDEX
- 是否无脏尾巴
- 是否没有半截文件

### 4. DOCS_INDEX 检查

必须确认：

- OmbreBrain_DOCS_INDEX.md 存在
- 本阶段新增设计已挂载
- 本阶段新增 READONLY 已挂载
- 没有明显重复污染

### 5. 仓库状态检查

必须确认：

- 当前分支正确
- 当前 PR 状态明确
- 最新提交已 push
- main 未动
- 已知 untracked 不误处理
- 没有未提交的关键修改

### 6. smoke test 检查

必须确认：

- smoke test 已通过
- 如果未跑，必须说明原因
- 如果失败，必须先 repair_note_schema 记录并修复

### 7. 边界状态检查

必须确认：

- Zeabur 未动
- DeepSeek 未调用
- xiaowo-release 未运行
- API 未接入，或 API 试验状态已标明
- GLM 5.1 未接入，或只是候选
- 本地模型未接入，或状态已标明
- 公共共享未开启，或 public_scope_check 已通过

### 8. 敏感信息排除检查

必须确认备份 / 迁移材料中不含：

- 明文 token
- 明文 API key
- 账号密码
- 验证码
- 银行信息
- 服务器私钥
- .env 明文文件
- 未脱敏敏感日志

### 9. 备份包准备检查

必须确认：

- 是否需要生成本地备份包
- backup manifest 是否准备好
- backup package 命名是否正确
- 包含内容是否清楚
- 排除内容是否清楚
- 恢复步骤是否写明

### 10. 回滚入口检查

必须确认：

- 当前仓库可回到最新提交
- 当前本地 _docs 有索引
- 关键收口卡可恢复
- 旧服务区是否仍可访问
- 新服务区失败时怎么暂停
- 不把迁移失败误判为海马体丢失

## 五、推荐输出格式

```text
migration_preflight:
  stage: before_server_migration
  branch: nightly-job-v01-readonly
  pr_state: PR #2 Open
  stage_closeout: ready / missing
  closeout_manifest: ready / missing
  readonly_cards: ready / missing
  docs_index: mounted / missing
  smoke_test: passed / failed / not_run
  boundary_state: clean / needs_review / dirty
  sensitive_state: excluded / needs_review / found
  backup_manifest: ready / missing
  rollback_entry: clear / unclear
  result: migrate_ready / confirm_required / repair_required / stop_required
  next_action: migrate / ask_confirm / repair / stop
```

## 六、迁移前最低门槛

最低门槛：

- 有阶段收口
- 有成果清单
- 有本地 READONLY
- 有 DOCS_INDEX
- 有 smoke test 结果
- 有 boundary_state
- 有敏感信息排除声明
- 有恢复 / 回滚说明

缺任一项，不建议迁移。

## 七、与现有设计的关系

- storage_adapter_policy：定义存储与迁移策略
- local_backup_package_schema：定义备份包结构
- backup_manifest_schema：定义备份 MANIFEST
- gateway_boundary_state_schema：提供边界状态小票
- stage_closeout_pack：提供阶段收口
- closeout_manifest：提供成果清单
- dirty_tail_guard：检查脏尾巴
- repair_note_schema：异常修复记录

## 八、当前边界

当前阶段只写设计文档。

不做：

- 不迁移服务区
- 不打包备份
- 不复制文件
- 不上传云端
- 不读取 .env
- 不扫描密钥
- 不实现检查脚本
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不改 nightly job 脚本
- 不自动共享任何内容
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 九、当前结论

migration_preflight_check v0.1 定义了 OmbreBrain 服务区 / 云服务器迁移前的预检清单。

它确认：迁移不是从一个地方跳到另一个地方，而是在确认收口、清点、备份、边界、敏感信息和回滚入口都清楚后，再换门牌。

猫抱好，钥匙拿好，煤气关好，
再搬家。
