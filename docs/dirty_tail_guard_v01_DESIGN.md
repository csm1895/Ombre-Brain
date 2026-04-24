# dirty_tail_guard v0.1 设计草案

状态：设计草案
来源：2026-04-24 readonly_card_schema v0.1 施工中多次 heredoc 卡住、半截文档修复、脏尾巴检查实践
目标：定义 OmbreBrain 施工中 heredoc / python one-shot / 大段粘贴导致的脏尾巴、半截文档、误追加的识别、检查、修复与继续施工规则。

## 一、核心目标

dirty_tail_guard 是施工防夹手层。

它不是：

- 自动清理脚本
- 自动改仓库程序
- 自动提交器
- 自动恢复工具
- 主脑写入规则

它要做的是：

- 识别 heredoc 没闭合导致的卡住状态
- 识别 EOF / PY / MARKER 等脏尾巴是否进入文件
- 识别大段粘贴失败造成的半截文档
- 给出安全的检查顺序
- 给出最小修复路径
- 降低误删、误提交、误推送风险

一句话：

不是让终端更聪明，
是让施工时少被纸箱怪夹手。

## 二、适用场景

dirty_tail_guard 适用于以下情况：

- 终端出现 heredoc>
- 复制大段 cat <<MARKER 后没有回到 shell 提示符
- 只输入了 EOF / PY / MARKER，正文没有写入
- 文档缺少后半段章节
- grep 出现 EOF / PY / MARKER 单独行
- commit 前怀疑文件半截
- amend / force-with-lease 前需要确认文档完整
- 本地 READONLY 卡写入后需要确认无脏尾巴

## 三、常见风险类型

### 1. 未闭合 heredoc

表现：

```text
heredoc>
```

处理：

- 不继续贴新命令
- 只输入当前 marker 单独一行
- 回到 shell 提示符后再检查文件

### 2. 空追加

表现：只输入 EOF / PY / MARKER 关闭 heredoc，但正文没有进入文件。

处理：

- 不急着 commit
- tail 检查文件尾部
- grep 检查目标章节
- 必要时用 printf 小块追加

### 3. 半截文档

表现：文件存在，commit 成功，但缺少后半段章节。

处理：

- 用 grep 检查最终章节
- 用 tail 查看尾部
- 不重开整篇大 heredoc
- 优先用 printf 小块补齐
- 补齐后 amend 原提交
- 已推送过则使用 git push --force-with-lease

### 4. 脏尾巴进入文件

表现：EOF / PY / MARKER 成为文件正文中的单独一行。

处理：

- 先定位行号
- 判断是否真脏尾巴，避免误删代码块示例
- 清理后再次 grep
- 再进入提交流程

## 四、固定检查命令

### 1. 检查文件尾部

```bash
tail -80 path/to/file.md
```

### 2. 检查目标章节是否存在

```bash
grep -n "## 十一、当前结论" path/to/file.md || echo "还没写完整"
```

### 3. 检查脏尾巴

```bash
grep -n "^EOF$\\|^PY$\\|^MARKER$" path/to/file.md || echo "无脏尾巴"
```

### 4. 检查本地索引挂载

```bash
grep -n "OmbreBrain_<topic>_v01_READONLY" ~/Desktop/海马体/_docs/OmbreBrain_DOCS_INDEX.md
```

## 五、推荐写入方式

### 1. 小块 printf 优先

当内容较长时，优先用 printf 小块追加。

优点：

- 不容易卡进 heredoc
- 每块写完可立即 tail 检查
- 出错范围小
- 适合补尾巴

### 2. heredoc 只用于短文档或明确 marker

如果使用 heredoc：

- marker 必须唯一
- 结束 marker 必须单独一行
- 粘贴后必须确认回到 shell 提示符
- 提交前必须 grep 脏尾巴

### 3. Python one-shot 用于结构化索引写入

适合更新：

- docs/nightly_job_v01_USAGE.md
- ~/Desktop/海马体/_docs/OmbreBrain_DOCS_INDEX.md

但结束后仍要检查：

- 是否打印成功
- 是否有 PY 脏尾巴
- 是否真的挂载

## 六、提交前检查顺序

提交前必须按顺序检查：

1. 文件是否存在
2. 文件大小是否合理
3. 尾部是否完整
4. 目标章节是否存在
5. 是否无脏尾巴
6. git diff 是否只包含预期内容
7. 再 git add / commit

推荐命令：

```bash
ls -lh path/to/file.md
tail -80 path/to/file.md
grep -n "目标章节" path/to/file.md || echo "还没写完整"
grep -n "^EOF$\\|^PY$\\|^MARKER$" path/to/file.md || echo "无脏尾巴"
git diff -- path/to/file.md
```

## 七、推送前检查顺序

推送前必须确认：

- commit 已生成
- 当前分支正确
- main 未动
- PR #2 仍 Open
- 不触发 Zeabur 部署
- 不调用 DeepSeek
- 不运行 xiaowo-release

推荐命令：

```bash
git status
git log --oneline --decorate -5
```

## 八、修复策略

### 1. 文件尚未 commit

直接修文件，再正常 commit。

### 2. 文件已 commit 但未 push

修文件后使用：

```bash
git add path/to/file.md
git commit --amend --no-edit
```

### 3. 文件已 push

修文件后使用：

```bash
git add path/to/file.md
git commit --amend --no-edit
git push --force-with-lease
```

说明：

force-with-lease 只用于修正当前 PR 分支上的同一提交，不用于改 main。

## 九、当前边界

当前阶段只写设计文档。

不做：

- 不新增脚本
- 不自动扫描全仓库
- 不自动删除内容
- 不自动 amend
- 不自动 push
- 不合并 main
- 不部署 Zeabur
- 不自动写主脑
- 不自动调用 DeepSeek

## 十、设计意义

dirty_tail_guard v0.1 把今天的施工事故变成可复用经验。

它让后续施工遇到粘贴失败、半截文档、脏尾巴时，不再临场慌乱，而是先止血、再定位、再小块修复、再检查、再提交。

这不是大功能，
但它保护所有大功能。

## 十一、当前结论

dirty_tail_guard v0.1 是 OmbreBrain 施工防夹手层。

它记录一套稳定判断：

- heredoc 卡住时先闭合
- 半截文档先检查尾部和目标章节
- 脏尾巴先定位再清理
- 大段补写优先 printf 小块追加
- 已推送的半截提交用 amend + force-with-lease 修正

纸箱怪可以继续张嘴，
但以后我们有钳子。
