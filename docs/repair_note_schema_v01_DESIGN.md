# repair_note_schema v0.1 设计草案

状态：设计草案
来源：2026-04-24 readonly_card_schema 施工中出现半截文档、heredoc 卡住、amend + force-with-lease 修复经验。
目标：定义 OmbreBrain 重要修复说明 repair_note 的结构、触发条件、必填字段、影响判断、验证方式与沉淀路径。

## 一、核心目标

repair_note_schema 是修复说明卡骨架。

它不是：

- 自动修复程序
- 自动回滚工具
- 自动清理脚本
- 自动提交器
- 主脑写入器

它要解决的是：

- 出了什么问题
- 怎么判断影响范围
- 怎么修复
- 修复后怎么验证
- 是否影响仓库、usage guide、本地 _docs、READONLY、未来施工流程
- 是否需要沉淀成 guard / schema / router

一句话：

不是把事故藏起来，
是把事故炼成下次不摔的扶手。

## 二、触发条件

以下情况应写 repair_note：

- 半截文档已经 commit
- 已 push 的提交需要 amend + force-with-lease 修复
- heredoc / EOF / PY / MARKER 脏尾巴进入文件
- DOCS_INDEX 出现错误挂载、重复挂载或污染
- usage guide 引用错误
- smoke test 曾失败并完成修复
- 错误地碰到 main / Zeabur / DeepSeek / 外部项目
- 本地参考材料误进仓库
- 施工流程发生可复用的修正

不需要写 repair_note 的情况：

- 仅普通 typo，未提交，直接修正
- 单次命令输错但未影响文件
- 未产生状态变化的临时探索
- 普通设计迭代，无事故和边界变化

## 三、推荐文件命名

格式：

```text
OmbreBrain_repair_<topic>_v01_READONLY.md
```

如果是日期阶段修复：

```text
OmbreBrain_YYYY-MM-DD_REPAIR_<topic>.md
```

默认位置：

```text
~/Desktop/海马体/_docs/
```

默认不进仓库，除非修复说明本身需要进入仓库文档。

## 四、必填结构

repair_note 必须包含：

- 标题
- 修复时间
- 所属分支
- 所属 PR
- 问题摘要
- 触发场景
- 影响范围
- 修复动作
- 验证结果
- 是否影响仓库
- 是否影响本地 _docs
- 是否影响未来施工流程
- 是否需要沉淀为 guard / schema / router
- 当前边界
- 当前结论

## 五、影响范围判断

修复说明必须判断影响范围。

常见范围：

### 1. no_file_change

没有文件变化，只是终端卡住或命令输错。

### 2. local_file_only

只影响本地 _docs 文件。

### 3. repo_doc_only

只影响仓库设计文档。

### 4. usage_guide

影响 docs/nightly_job_v01_USAGE.md。

### 5. docs_index

影响 ~/Desktop/海马体/_docs/OmbreBrain_DOCS_INDEX.md。

### 6. pushed_commit

已经推送到远程分支，需要 amend + force-with-lease 修复。

### 7. forbidden_boundary

误触 main / Zeabur / DeepSeek / xiaowo-release / 外部项目。

## 六、修复动作类型

常见修复动作：

- close_heredoc：关闭卡住的 heredoc
- clean_dirty_tail：清理 EOF / PY / MARKER 脏尾巴
- append_missing_section：补齐半截文档
- rewrite_local_card：重写本地 READONLY 卡
- repair_docs_index：修复 DOCS_INDEX 挂载
- amend_commit：amend 当前提交
- force_with_lease：修复已推送提交
- add_guard_design：沉淀为 guard 设计
- add_schema_design：沉淀为 schema 设计
- add_router_design：沉淀为 router 设计

## 七、验证要求

修复完成后必须验证。

常见验证：

```bash
git status
git log --oneline --decorate -10
tail -80 path/to/file.md
grep -n "目标章节" path/to/file.md || echo "还没写完整"
grep -n "^EOF$\\|^PY$\\|^MARKER$" path/to/file.md || echo "无脏尾巴"
scripts/test_nightly_job_v01.sh "$(pwd)/buckets_graft_merged" _nightly_logs 2026-04-20 2026-04-21
```

验证结果必须写清：

- 是否回到 shell 提示符
- 文件是否完整
- 是否无脏尾巴
- smoke test 是否 passed
- 分支是否同步 origin
- main 是否未动
- Zeabur 是否未动
- DeepSeek 是否未调用
- xiaowo-release 是否未运行

## 八、沉淀路径判断

不是每次修复都要新增设计。

判断规则：

### 1. 一次性问题

写 repair_note 即可。

### 2. 重复出现的问题

应沉淀为 guard。

例如：dirty_tail_guard。

### 3. 结构不统一的问题

应沉淀为 schema。

例如：readonly_card_schema、repair_note_schema。

### 4. 路由判断混乱的问题

应沉淀为 router。

例如：closeout_router、room_action_router。

### 5. 阶段交接不清的问题

应沉淀为 pack / manifest。

例如：stage_closeout_pack、closeout_manifest。

## 九、示例：readonly_card_schema 半截文档修复

问题：

readonly_card_schema 初次补写时，大段 heredoc / 粘贴流程导致文档半截。

修复：

- 先关闭 heredoc
- 用 tail 与 grep 判断缺失章节
- 改用 printf 小块追加
- 补齐后 git commit --amend --no-edit
- 已推送后 git push --force-with-lease
- 重新 smoke test
- 写入 READONLY 收口卡

沉淀：

- dirty_tail_guard v0.1
- readonly_card_schema v0.1
- repair_note_schema v0.1

## 十、当前边界

当前阶段只写设计文档。

不做：

- 不新增自动修复脚本
- 不自动扫描仓库
- 不自动删除文件内容
- 不自动 amend
- 不自动 force push
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十一、当前结论

repair_note_schema v0.1 定义了 OmbreBrain 重要修复说明的统一骨架。

它让事故不只停留在“修好了”，而是能继续回答：

- 哪里坏了
- 怎么修的
- 影响了什么
- 验证过没有
- 下次怎么避免
- 是否应该沉淀成长期结构

修复不是擦掉脚印，
是把坑边插上小旗。
