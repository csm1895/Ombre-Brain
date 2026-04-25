# local_backup_package_schema v0.1 设计草案

状态：设计草案
来源：2026-04-25 storage_adapter_policy v0.1。倩倩确认：服务区迁移前需要先把海马体升级版收一次工；稳定云服务区选定后，再做一次本地保存与备份，以防万一。
目标：定义 OmbreBrain 本地备份包的命名、内容清单、排除项、manifest、恢复检查与边界记录规则。

## 一、核心目标

local_backup_package_schema 是本地备份包结构。

它不是：

- 备份脚本
- 自动打包工具
- 云迁移程序
- 数据库导出器
- 密钥保存工具
- 本地部署程序

它要解决的是：

- 服务区迁移前备份包里要装什么
- 稳定云服务区后本地保存要装什么
- 哪些内容必须排除
- 如何记录备份范围与时间
- 如何记录边界状态
- 恢复后如何检查是否完整
- 如何避免把明文 token / API key / 密码打进包里

一句话：

备份不是把抽屉倒进箱子，
而是给未来的自己留一只可打开的保险箱。

## 二、适用场景

适合生成本地备份包的场景：

- 云服务器 / 服务区迁移前
- 稳定云服务区选定后
- PR 阶段大收口后
- 海马体升级版阶段完成后
- 本地部署前准备迁移时
- 大量 READONLY 与设计文档已完成时

不适用场景：

- 单颗设计刚完成
- 当前状态未收口
- git 状态不清楚
- 尚未确认敏感信息排除
- smoke test 未跑且无原因记录

## 三、备份包命名

推荐命名：

```text
OmbreBrain_BACKUP_YYYY-MM-DD_<stage>.zip
```

迁移前：

```text
OmbreBrain_BACKUP_YYYY-MM-DD_before_server_migration.zip
```

稳定服务区后：

```text
OmbreBrain_BACKUP_YYYY-MM-DD_after_stable_region.zip
```

本地部署前：

```text
OmbreBrain_BACKUP_YYYY-MM-DD_before_local_deployment.zip
```

## 四、必须包含内容

### 1. 仓库设计文档

包含：

- docs/*.md 中已完成设计文档
- docs/nightly_job_v01_USAGE.md
- 与当前 PR 相关的说明文档

要求：

- 保留 git commit 信息
- 记录当前分支
- 记录 PR 状态

### 2. 本地 _docs 文档柜

包含：

- OmbreBrain_DOCS_INDEX.md
- 所有已完成 READONLY 收口卡
- 阶段总收口卡
- closeout_manifest
- migration / backup 相关说明
- 外部参考卡

要求：

- DOCS_INDEX 必须可读
- 关键卡必须能 grep 到
- 无脏尾巴

### 3. 阶段收口材料

包含：

- 最近一次 stage_closeout
- 最近一次 closeout_manifest
- 今日 / 本阶段完成项
- 下次候选
- 当前边界状态

### 4. 迁移状态说明

包含：

- 当前云服务区 / 服务器状态说明
- 是否迁移前 / 迁移后
- 当前不可动内容
- 回滚入口
- 未完成事项

### 5. 验证记录

包含：

- smoke test 命令
- smoke test 结果
- git status 摘要
- git log 摘要
- DOCS_INDEX 检查结果
- 脏尾巴检查结果

## 五、必须排除内容

不得进入普通备份包：

- 明文 token
- 明文 API key
- 账号密码
- 验证码
- 银行信息
- 未脱敏手机号敏感上下文
- 服务器私钥
- .env 明文文件
- 未确认可保存的敏感日志

如果必须记录配置存在，只写说明，不写值。

示例：

```text
需要 OPENAI_API_KEY：是
实际值：不进入备份包
保存位置：由倩倩另行管理
```

## 六、backup manifest

每个备份包建议配一张 manifest：

```text
OmbreBrain_YYYY-MM-DD_BACKUP_MANIFEST.md
```

manifest 必须包含：

- 备份时间
- 备份阶段
- 备份原因
- 覆盖范围
- 包含内容清单
- 排除内容清单
- 当前分支
- 当前 PR
- 最新 commit
- main / Zeabur / DeepSeek / xiaowo-release 状态
- smoke test 状态
- 恢复检查步骤
- 当前结论

## 七、推荐目录结构

备份包内部推荐结构：

```text
OmbreBrain_BACKUP_YYYY-MM-DD_<stage>/
  MANIFEST.md
  repo_docs/
  local_docs/
  stage_closeout/
  manifests/
  verification/
  migration_notes/
  README_RESTORE.md
```

说明：

- repo_docs 放仓库设计文档快照
- local_docs 放本地 _docs 关键卡
- stage_closeout 放阶段收口
- manifests 放成果清单
- verification 放检查记录
- migration_notes 放迁移说明
- README_RESTORE.md 放恢复步骤

## 八、恢复检查步骤

恢复后必须检查：

```bash
ls -lh
find . -maxdepth 3 -type f | sort | head -200
grep -n "OmbreBrain_DOCS_INDEX" -R . || true
grep -n "STAGE_CLOSEOUT\\|READONLY\\|MANIFEST" -R local_docs stage_closeout manifests 2>/dev/null || true
grep -n "^READONLYONLY$\\|^EOF$\\|^PY$\\|^MARKER$" -R . || echo "无明显脏尾巴"
```

如果恢复到仓库，还要检查：

```bash
git status
git log --oneline --decorate -20
```

## 九、边界状态记录

备份 manifest 必须记录：

- 当前 PR 是否 Open
- main 是否未动
- Zeabur 是否未动
- DeepSeek 是否调用
- xiaowo-release 是否运行
- 是否包含未提交文件
- 是否存在 untracked 既有项
- 是否包含敏感信息

## 十、与现有设计的关系

- storage_adapter_policy：定义存储与备份总策略
- migration_backup_checklist：定义迁移备份清单
- stage_closeout_pack：定义阶段收口
- closeout_manifest：定义成果清单
- readonly_card_schema：定义本地 READONLY 卡
- dirty_tail_guard：检查脏尾巴
- paste_safe_writer：安全写入备份说明

## 十一、当前边界

当前阶段只写设计文档。

不做：

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

## 十二、当前结论

local_backup_package_schema v0.1 定义了 OmbreBrain 本地备份包的结构。

它确认：备份包要能说明自己从哪里来、装了什么、没装什么、怎么恢复、当前边界是否干净。

真正可靠的备份，
不是一只塞满东西的袋子，
而是一只贴好标签、留有清单、知道怎么开箱的保险箱。
