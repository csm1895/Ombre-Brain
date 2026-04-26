# backup_restore_readme_schema v0.1 设计草案

状态：设计草案
来源：2026-04-25 local_backup_package_schema、backup_manifest_schema、migration_preflight_check，以及 2026-04-26 开工复位时补写阶段总收口卡。
目标：定义 OmbreBrain 本地备份包中的 README_RESTORE.md 写法，让未来恢复备份时能清楚知道怎么解包、怎么检查、怎么确认 docs / _docs / manifest / boundary_state 都在，以及如何避免把缺少密钥或配置误判为海马体丢失。

## 一、核心目标

backup_restore_readme_schema 是备份包恢复说明结构。

它不是：

- 恢复脚本
- 自动解包工具
- 数据库导入器
- 云迁移程序
- 密钥恢复工具
- 本地部署程序

它要解决的是：

- 备份包拿到后先看什么
- 如何确认备份包结构完整
- 如何确认 repo_docs / local_docs / manifest / verification 存在
- 如何确认 DOCS_INDEX 可读
- 如何确认 READONLY 卡存在
- 如何确认 boundary_state 与 backup_manifest
- 如何区分“配置缺失”和“海马体丢失”
- 如何避免恢复时误带明文密钥

一句话：

保险箱不只要有清单，
还要有开箱说明。

## 二、推荐文件名

备份包内推荐文件名：

```text
README_RESTORE.md
```

可选阶段文件名：

```text
README_RESTORE_before_server_migration.md
README_RESTORE_after_stable_region.md
README_RESTORE_before_local_deployment.md
```

## 三、推荐位置

位于备份包根目录：

```text
OmbreBrain_BACKUP_YYYY-MM-DD_<stage>/
  MANIFEST.md
  README_RESTORE.md
  repo_docs/
  local_docs/
  stage_closeout/
  manifests/
  verification/
  migration_notes/
```

## 四、推荐结构

README_RESTORE.md 推荐包含：

```text
# OmbreBrain Restore README

## 一、先读这个
## 二、本备份包适用场景
## 三、恢复前不要做什么
## 四、目录结构说明
## 五、基础完整性检查
## 六、repo_docs 检查
## 七、local_docs 检查
## 八、manifest 检查
## 九、verification 检查
## 十、boundary_state 检查
## 十一、敏感配置说明
## 十二、常见误判
## 十三、恢复后下一步
## 十四、当前结论
```

## 五、先读这个

必须说明：

- 这是恢复说明，不是自动恢复工具
- 先检查，再复制
- 先看 manifest，再判断缺什么
- 缺少 API key / token / .env 不等于海马体丢失
- 不要把旧备份直接覆盖当前工作目录
- 不要把未知文件直接加入 Git

推荐原文：

```text
先不要覆盖当前目录。
先按本文件检查备份包结构、MANIFEST、DOCS_INDEX、READONLY 与 boundary_state。
缺少密钥或 .env 是正常的，普通备份包不保存明文敏感配置。
```

## 六、适用场景

适用于：

- 服务区迁移前备份恢复检查
- 稳定云服务区后本地保存恢复检查
- 本地部署前备份验证
- 换机器后确认海马体资料是否齐全
- PR 大阶段收口后离线检查

不适用于：

- 自动部署
- 自动恢复数据库
- 自动恢复密钥
- 自动合并 Git 分支
- 自动覆盖当前海马体目录

## 七、恢复前不要做什么

禁止：

- 不要直接覆盖当前工作目录
- 不要把备份包里的文件全部 git add
- 不要把旧 READONLY 覆盖新 READONLY
- 不要把旧 DOCS_INDEX 覆盖新 DOCS_INDEX
- 不要把缺密钥误判成系统坏了
- 不要从备份包恢复明文密钥
- 不要把 private / sensitive 内容放入公共层

## 八、基础完整性检查

推荐检查命令：

```bash
ls -lh
find . -maxdepth 3 -type f | sort | head -200
```

必须确认存在：

- MANIFEST.md
- README_RESTORE.md
- repo_docs/
- local_docs/
- verification/

阶段备份还应确认：

- stage_closeout/
- manifests/
- migration_notes/

## 九、repo_docs 检查

检查目的：确认仓库设计文档快照存在。

推荐命令：

```bash
find repo_docs -type f | sort | head -100
grep -R "memory_gateway\\|backup_manifest\\|migration_preflight" repo_docs 2>/dev/null | head -40
```

确认：

- 设计文档存在
- usage guide 存在
- 文件可读

注意：

repo_docs 是设计事实快照，不等于可直接覆盖仓库。

## 十、local_docs 检查

检查目的：确认本地 _docs 文档柜快照存在。

推荐命令：

```bash
find local_docs -type f | sort | head -200
grep -R "OmbreBrain_DOCS_INDEX" local_docs 2>/dev/null || true
grep -R "READONLY\\|STAGE_CLOSEOUT" local_docs 2>/dev/null | head -80
```

确认：

- OmbreBrain_DOCS_INDEX.md 存在
- READONLY 卡存在
- 阶段收口卡存在
- 文件可读

## 十一、manifest 检查

检查目的：确认箱内清单存在。

推荐命令：

```bash
find manifests -type f | sort
grep -R "boundary_state\\|包含内容\\|排除内容\\|恢复步骤" manifests MANIFEST.md 2>/dev/null | head -80
```

确认：

- 备份时间明确
- 备份阶段明确
- 覆盖范围明确
- 包含内容明确
- 排除内容明确
- 当前边界状态明确

## 十二、verification 检查

检查目的：确认备份前验证记录存在。

推荐命令：

```bash
find verification -type f | sort
grep -R "smoke test\\|nightly_job v0.1 test PASSED\\|无脏尾巴\\|git status" verification 2>/dev/null | head -80
```

确认：

- smoke test 结果存在
- 脏尾巴检查存在
- git status / git log 摘要存在
- DOCS_INDEX 检查存在

## 十三、boundary_state 检查

检查目的：确认恢复时知道当时边界是否干净。

应确认：

- PR 状态
- branch
- main_state
- zeabur_state
- deepseek_state
- xiaowo_release_state
- api_state
- model_state
- sensitive_state
- overall_status

如果 boundary_state 缺失，不建议直接迁移或覆盖。

## 十四、敏感配置说明

必须说明：

- 普通备份包不保存明文 token
- 普通备份包不保存 API key
- 普通备份包不保存账号密码
- 普通备份包不保存验证码
- 普通备份包不保存银行信息
- 普通备份包不保存 .env 明文文件

恢复时如果发现这些缺失：

- 这是预期行为
- 不代表海马体丢失
- 由倩倩另行从安全位置恢复

## 十五、常见误判

### 1. 缺 .env

结论：不等于坏了。

普通备份包应排除 .env 明文。

### 2. 缺 API key

结论：不等于 API 设计丢失。

API key 不进入普通备份包。

### 3. vector_store 不在包里

结论：不等于记忆丢失。

向量库只是候选检索层，事实源应回看 repo_docs、local_docs、READONLY、manifest。

### 4. Git untracked 存在

结论：不一定异常。

需要对照 known_untracked。

### 5. 旧备份与当前目录不同

结论：不应直接覆盖。

先比较 MANIFEST、commit、DOCS_INDEX 与 boundary_state。

## 十六、恢复后下一步

恢复检查完成后，下一步可选：

- 只读确认
- 对照当前仓库
- 补挂 DOCS_INDEX
- 写 repair_note
- 写 stage_boundary_snapshot
- 运行 migration_preflight_check
- 停止并等待确认

如果不确定，默认 ask_confirm。

## 十七、与现有设计的关系

- local_backup_package_schema：定义备份包结构
- backup_manifest_schema：定义 MANIFEST.md
- backup_restore_readme_schema：定义 README_RESTORE.md
- gateway_boundary_state_schema：定义边界状态小票
- storage_truth_source_map：定义恢复时谁说了算
- migration_preflight_check：定义迁移前检查
- repair_note_schema：定义异常修复记录

## 十八、当前边界

当前阶段只写设计文档。

不做：

- 不生成 README_RESTORE 文件
- 不打包备份
- 不复制文件
- 不覆盖目录
- 不上传云端
- 不迁移服务区
- 不读取 .env
- 不恢复密钥
- 不实现恢复脚本
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

backup_restore_readme_schema v0.1 定义了 OmbreBrain 本地备份包 README_RESTORE.md 的结构。

它确认：恢复时先读说明、先查 manifest、先验结构、先看边界，不把缺少密钥、缺少 .env、缺少向量库缓存误判为海马体丢失。

开箱之前先看说明，
别拿撬棍当钥匙。
