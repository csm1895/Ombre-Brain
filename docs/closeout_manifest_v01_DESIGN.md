# closeout_manifest v0.1 设计草案

状态：设计草案
来源：2026-04-24 多颗设计文档与本地 READONLY 收口后，需要统一盘点成果状态。
目标：定义 OmbreBrain 阶段成果清单 manifest 的结构、对象类型、状态字段、检查项与接力方式。

## 一、核心目标

closeout_manifest 是阶段成果清单。

它不是：

- 自动扫描脚本
- 自动归档器
- 自动提交器
- 自动主脑写入器
- 自动 merge 工具

它要解决的是：

- 当前阶段到底完成了哪些颗粒
- 哪些只有设计文档，哪些已经挂 usage guide
- 哪些已有本地 READONLY 收口卡
- 哪些已通过 smoke test
- 哪些只在本地 _docs，不进仓库
- 哪些是候选，不能误写成完成
- 下次接力时从哪里继续

一句话：

stage_closeout_pack 管“怎么收工”，
closeout_manifest 管“收工时清点了哪些东西”。

## 二、适用场景

以下情况适合生成 closeout_manifest：

- 一天内完成多颗设计文档
- 一个 PR 中积累多个设计层提交
- 本地 READONLY 卡超过 5 张
- 当前窗口快满，需要交接
- 准备写阶段总收口卡
- 准备判断下一颗优先级
- 需要确认哪些内容已完成、哪些待补

不适用场景：

- 单颗设计刚开始
- 当前故障未修复
- 没有明确成果对象
- 只是普通聊天或临时想法

## 三、推荐文件命名

阶段 manifest 推荐命名：

```text
OmbreBrain_YYYY-MM-DD_CLOSEOUT_MANIFEST.md
```

如果一天内分多段，可追加时段：

```text
OmbreBrain_YYYY-MM-DD_CLOSEOUT_MANIFEST_evening.md
OmbreBrain_YYYY-MM-DD_CLOSEOUT_MANIFEST_before_sleep.md
```

默认位置：

```text
~/Desktop/海马体/_docs/
```

默认不进仓库。

## 四、manifest 对象类型

### 1. repo_design

仓库设计文档。

必须记录：

- 主题名
- 设计文档路径
- add design 提交
- usage guide 引用提交
- smoke test 状态
- READONLY 状态
- DOCS_INDEX 状态
- 当前边界

### 2. local_reference

本地参考材料卡。

必须记录：

- 主题名
- 本地文件路径
- 来源
- 为什么只作参考
- 不进仓库原因
- 未来可拆候选
- DOCS_INDEX 状态

### 3. stage_closeout

阶段总收口卡。

必须记录：

- 收口时间
- 覆盖范围
- 关键完成项
- 边界状态
- 下一步候选
- DOCS_INDEX 状态

### 4. candidate

候选项。

必须记录：

- 候选名
- 来源
- 为什么还没开
- 依赖项
- 建议优先级

### 5. repair_note

修复说明。

必须记录：

- 问题
- 修复方式
- 是否影响仓库
- 是否影响未来施工流程
- 是否需要沉淀为 guard / schema / router

## 五、状态字段

每个对象建议使用统一状态字段：

- topic
- type
- repo_doc
- usage_guide
- readonly_card
- docs_index
- smoke_test
- commits
- local_only
- boundary
- next_action
- status

## 六、状态枚举

### 1. status

- done
- partial
- candidate
- blocked
- local_reference
- superseded

### 2. smoke_test

- passed
- failed
- not_required
- not_run

### 3. readonly_card

- exists
- missing
- not_required
- needs_update

### 4. docs_index

- mounted
- missing
- duplicate
- needs_cleanup

### 5. boundary

- main_untouched
- zeabur_untouched
- deepseek_not_called
- xiaowo_not_run
- local_only
- repo_design_only

## 七、推荐表格结构

manifest 可使用 Markdown 表格。

推荐字段：

```markdown
| topic | type | repo_doc | usage | readonly | index | smoke | status | next |
|---|---|---|---|---|---|---|---|---|
```

如果内容复杂，可按类型分段，不强行塞进一张大表。

## 八、检查规则

生成 manifest 前应检查：

- git log 是否包含关键提交
- usage guide 是否包含设计引用
- 本地 READONLY 是否存在
- DOCS_INDEX 是否挂载
- smoke test 是否通过
- 是否有脏尾巴
- 是否有未完成事项被误写成完成

推荐命令：

```bash
git log --oneline --decorate -20
grep -n "<topic>" docs/nightly_job_v01_USAGE.md
ls -lh ~/Desktop/海马体/_docs | grep "<topic>"
grep -n "OmbreBrain_<topic>_v01_READONLY" ~/Desktop/海马体/_docs/OmbreBrain_DOCS_INDEX.md
grep -n "^EOF$\\|^PY$\\|^MARKER$" ~/Desktop/海马体/_docs/OmbreBrain_<topic>_v01_READONLY.md || echo "无脏尾巴"
```

## 九、与其他设计的关系

### 1. 与 closeout_router

closeout_router 决定一颗设计完成后走哪条路。
closeout_manifest 记录最终走到了哪一步。

### 2. 与 readonly_card_schema

readonly_card_schema 定义单张 READONLY 怎么写。
closeout_manifest 记录哪些 READONLY 已经存在。

### 3. 与 stage_closeout_pack

stage_closeout_pack 定义阶段总收口怎么写。
closeout_manifest 是阶段总收口里的成果清单来源。

### 4. 与 dirty_tail_guard

dirty_tail_guard 负责防止半截文档和脏尾巴。
closeout_manifest 只记录检查结果，不负责自动修复。

## 十、当前边界

当前阶段只写设计文档。

不做：

- 不新增 manifest 自动生成脚本
- 不扫描全仓库
- 不自动改 DOCS_INDEX
- 不自动修复 READONLY
- 不自动提交
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十一、当前结论

closeout_manifest v0.1 定义了 OmbreBrain 阶段成果清单的结构。

它让一轮施工完成后，可以清楚看到：

- 哪些完成
- 哪些只完成一半
- 哪些只是候选
- 哪些在仓库
- 哪些只在本地
- 下一步该补哪里

阶段收口负责关灯，
manifest 负责数钥匙。
