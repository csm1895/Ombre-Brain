# backup_manifest_schema v0.1 设计草案

状态：设计草案
来源：2026-04-25 local_backup_package_schema v0.1 与 gateway_boundary_state_schema v0.1。备份包需要一张可读、可恢复、可检查的 MANIFEST.md。
目标：定义 OmbreBrain 本地备份包 MANIFEST.md 的结构，记录备份时间、阶段、原因、范围、包含清单、排除清单、边界状态、验证结果、恢复步骤与当前结论。

## 一、核心目标

backup_manifest_schema 是备份包清单结构。

它不是：

- 备份脚本
- 自动打包工具
- 压缩程序
- 云迁移工具
- 密钥保存工具
- 数据库导出器

它要解决的是：

- 备份包从哪里来
- 备份包为什么生成
- 备份包覆盖了什么
- 备份包排除了什么
- 当前分支 / PR / commit 是什么
- 当前边界状态是否干净
- smoke test 是否通过
- 恢复时应该怎么检查
- 是否明确排除了敏感信息

一句话：

备份箱可以很重，
但箱内清单必须一眼看懂。

## 二、推荐文件名

```text
OmbreBrain_YYYY-MM-DD_BACKUP_MANIFEST.md
```

如果是特定阶段：

```text
OmbreBrain_YYYY-MM-DD_before_server_migration_BACKUP_MANIFEST.md
OmbreBrain_YYYY-MM-DD_after_stable_region_BACKUP_MANIFEST.md
OmbreBrain_YYYY-MM-DD_before_local_deployment_BACKUP_MANIFEST.md
```

## 三、推荐结构

MANIFEST.md 推荐包含：

```text
# OmbreBrain Backup Manifest

## 一、基础信息
## 二、备份原因
## 三、覆盖范围
## 四、包含内容清单
## 五、排除内容清单
## 六、仓库状态
## 七、本地 _docs 状态
## 八、边界状态小票
## 九、验证结果
## 十、恢复步骤
## 十一、敏感信息排除声明
## 十二、未完成事项
## 十三、当前结论
```

## 四、基础信息

必须记录：

- 备份时间
- 备份阶段
- 备份包名称
- 备份包位置
- 生成原因
- 操作者
- 当前项目

示例：

```text
备份时间：2026-04-25 21:10
备份阶段：before_server_migration
备份包名称：OmbreBrain_BACKUP_2026-04-25_before_server_migration.zip
当前项目：OmbreBrain / 海马体轻升级
```

## 五、备份原因

可选原因：

- before_server_migration
- after_stable_region
- before_local_deployment
- after_major_upgrade
- before_merge
- manual_snapshot

说明必须写清：

- 为什么现在备份
- 是否迁移前
- 是否稳定服务区后
- 是否本地部署前
- 是否只是手动快照

## 六、覆盖范围

必须说明备份覆盖哪些范围。

推荐范围：

- repo_docs
- local_docs
- stage_closeout
- manifests
- verification
- migration_notes
- restore_readme

不得含糊写“全部备份”。

## 七、包含内容清单

包含内容应按目录列出。

### 1. repo_docs

记录：

- docs/*.md 设计文档
- docs/nightly_job_v01_USAGE.md
- 当前 PR 相关说明

### 2. local_docs

记录：

- OmbreBrain_DOCS_INDEX.md
- READONLY 收口卡
- 外部参考卡
- 阶段收口卡

### 3. stage_closeout

记录：

- 最近阶段总收口
- 当天总收口
- 服务区迁移前收口

### 4. manifests

记录：

- closeout_manifest
- backup_manifest
- migration checklist

### 5. verification

记录：

- smoke test 命令与结果
- git status 摘要
- git log 摘要
- DOCS_INDEX grep 结果
- 脏尾巴检查结果

## 八、排除内容清单

必须明确排除：

- 明文 token
- 明文 API key
- 账号密码
- 验证码
- 银行信息
- 服务器私钥
- .env 明文文件
- 未脱敏敏感日志
- 未确认可共享的私密内容

说明模板：

```text
已排除：明文 token / API key / 密码 / 验证码 / 银行信息
如需恢复相关配置，由倩倩另行管理，不进入普通备份包。
```

## 九、仓库状态

必须记录：

- 当前分支
- 当前 PR
- 最新 commit
- 是否已 push
- git status 摘要
- known untracked 项

示例：

```text
分支：nightly-job-v01-readonly
PR：#2 Open
main：未动
远端：up to date
```

## 十、本地 _docs 状态

必须记录：

- DOCS_INDEX 是否存在
- 关键 READONLY 是否存在
- 阶段收口是否存在
- 是否无脏尾巴
- 是否已挂载本次新增卡

## 十一、边界状态小票

必须引用 gateway_boundary_state_schema。

推荐写法：

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
  sensitive_state: no_sensitive_known
  smoke_test_state: passed
  docs_index_state: mounted
  overall_status: continue_ok / closeout_recommended
```

## 十二、验证结果

必须记录：

- smoke test 是否通过
- DOCS_INDEX 是否可 grep
- READONLY 是否可 grep
- 是否无脏尾巴
- 是否无已知敏感信息
- 是否已记录 known untracked

## 十三、恢复步骤

必须包含基础恢复检查：

```bash
ls -lh
find . -maxdepth 3 -type f | sort | head -200
grep -n "OmbreBrain_DOCS_INDEX" -R . || true
grep -n "STAGE_CLOSEOUT\\|READONLY\\|MANIFEST" -R local_docs stage_closeout manifests 2>/dev/null || true
grep -n "^READONLYONLY$\\|^EOF$\\|^PY$\\|^MARKER$" -R . || echo "无明显脏尾巴"
```

如果恢复到仓库：

```bash
git status
git log --oneline --decorate -20
```

## 十四、敏感信息排除声明

必须写明：

- 备份包不保存明文密钥
- 备份包不保存账号密码
- 备份包不保存验证码
- 备份包不保存银行信息
- 如需恢复环境变量，由倩倩另行管理

## 十五、未完成事项

记录备份时仍未完成的事项：

- 待迁移服务区
- 待本地保存
- 待 API 试验
- 待安卓 API 试验机
- 待本地部署
- 待公屏 MCP 后续

不得把未完成写成已完成。

## 十六、当前结论

结论必须说明：

- 本备份是否可作为恢复参考
- 当前是否适合继续迁移
- 是否需要人工确认
- 是否存在已知风险

## 十七、与现有设计的关系

- local_backup_package_schema：定义备份包结构
- backup_manifest_schema：定义 MANIFEST.md 写法
- gateway_boundary_state_schema：提供边界状态小票
- storage_adapter_policy：定义存储适配与备份策略
- closeout_manifest：提供阶段成果清单
- stage_closeout_pack：提供阶段收口
- dirty_tail_guard：检查脏尾巴

## 十八、当前边界

当前阶段只写设计文档。

不做：

- 不生成 MANIFEST 文件
- 不打包备份
- 不复制文件
- 不压缩 zip
- 不上传云端
- 不迁移服务区
- 不写密钥
- 不读取 .env
- 不实现备份脚本
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不改 nightly job 脚本
- 不自动共享任何内容
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十九、当前结论

backup_manifest_schema v0.1 定义了 OmbreBrain 本地备份包 MANIFEST.md 的结构。

它确认：每个备份包都必须有一张能说明时间、阶段、原因、范围、内容、排除项、边界状态、验证结果与恢复方法的箱内清单。

箱子可以封口，
但清单必须能开口说话。
