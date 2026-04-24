# readonly_card_schema v0.1 设计草案

状态：设计草案
来源：2026-04-24 closeout_router v0.1，以及当日多张 READONLY 收口卡实践
目标：定义 OmbreBrain 本地 READONLY 收口卡的统一结构、必填字段、检查项与使用边界。

## 一、核心目标

readonly_card_schema 是本地收口卡模板层。

它不是：

- 自动写卡程序
- 主脑写入格式
- GitHub PR 模板
- 线上功能文档
- 对外公开文档标准

它要做的是：

- 统一本地 READONLY 收口卡结构
- 让每颗设计完成状态可快速回看
- 固定关键提交、验证命令、边界状态
- 防止漏写 PR / main / Zeabur / DeepSeek / xiaowo-release 状态
- 防止 heredoc 脏尾巴残留
- 让未来阶段总收口能直接读取这些卡

一句话：

READONLY 卡不是作文，
是每颗脑部零件的入柜标签。

## 二、为什么需要这一层

2026-04-24 已经形成多张本地 READONLY 卡：

- OmbreBrain_memory_text_hygiene_v01_READONLY.md
- OmbreBrain_internalized_growth_chain_v01_READONLY.md
- OmbreBrain_external_reference_xiaowo_release_v01_READONLY.md
- OmbreBrain_floating_recall_v01_READONLY.md
- OmbreBrain_living_room_sensory_context_v01_READONLY.md
- OmbreBrain_future_local_deployment_reference_v01_READONLY.md
- OmbreBrain_cli_space_map_v01_READONLY.md
- OmbreBrain_room_action_router_v01_READONLY.md
- OmbreBrain_external_material_intake_v01_READONLY.md
- OmbreBrain_closeout_router_v01_READONLY.md

这些卡已经稳定包含：

- 当前状态
- 核心文件
- 关键提交
- 已验证命令
- 设计意义
- 下次候选
- 当前结论
- 边界说明
- DOCS_INDEX 挂载状态
- 无脏尾巴检查

readonly_card_schema 负责把这些结构固化。

## 三、适用对象

### 1. repo_design READONLY

适用于仓库设计文档收口。

例如：

- docs/cli_space_map_v01_DESIGN.md
- docs/room_action_router_v01_DESIGN.md

必须包含：

- 设计文档路径
- usage guide 引用情况
- 关键提交
- smoke test 结果
- 仓库边界
- 本地索引状态

### 2. local_reference READONLY

适用于本地参考材料卡。

例如：

- future_local_deployment_reference

必须包含：

- 来源
- 为什么只作参考
- 不进仓库原因
- 未来可拆候选
- 当前不做什么

### 3. stage_closeout READONLY

适用于阶段总收口。

必须包含：

- 当日完成项
- 所有关键提交
- 所有本地 READONLY 卡
- PR / main / Zeabur / DeepSeek 状态
- 未完成事项
- 下一步候选

### 4. repair_note READONLY

适用于重要修复说明。

必须包含：

- 出了什么问题
- 怎么修
- 是否影响仓库
- 是否影响未来施工流程
- 是否需要写入 closeout_router 或 dirty_tail_guard

## 四、统一文件命名

推荐格式：

```text
OmbreBrain_<topic>_v01_READONLY.md

```

规则：

- 文件名必须包含 OmbreBrain
- topic 使用小写 snake_case
- 版本号使用 v01 / v02
- READONLY 大写
- 不使用空格
- 不使用中文文件名
- 不覆盖旧版本，除非明确是修正同一张卡

## 五、必填结构

### 1. 标题

格式：

```markdown
# OmbreBrain <topic> v0.1 READONLY 收口说明
```

### 2. 元数据

必须包含：

- 更新时间
- 所属分支
- 所属 PR
- 状态

### 3. 当前状态

必须说明：

- 这颗是否完成
- 是否新增仓库设计文档
- 是否写入 usage guide
- 是否挂入本地 _docs 索引
- 是否通过 smoke test

### 4. 当前边界

必须说明不做什么。

常见边界：

- 不自动合并 main
- 不自动部署 Zeabur
- 不自动改主脑
- 不自动运行外部项目
- 不自动接入 MCP server
- 不自动调用 DeepSeek
- 不把设计写成真实执行程序

### 5. 核心文件

必须列出：

- docs/*_DESIGN.md
- docs/nightly_job_v01_USAGE.md
- ~/Desktop/海马体/_docs/OmbreBrain_DOCS_INDEX.md

本地参考卡可不列仓库设计文档，但要说明不进仓库。

### 6. 主题核心内容

不同卡可自定义章节。

例如：

- 材料类型
- 空间分区
- 输入类型与默认路由
- 收口对象类型
- 固定检查项
- 关联强弱
- 推荐路径

### 7. 关键提交

repo_design 必须列出：

- 设计文档提交
- usage guide 引用提交

格式：

```markdown
- `hash` docs: add xxx design
- `hash` docs: reference xxx design in usage guide
```

local_reference 不需要关键提交，除非有相关仓库引用。

### 8. 已验证命令

必须列出 smoke test 或检查命令。

repo_design 推荐：

```bash
scripts/test_nightly_job_v01.sh "$(pwd)/buckets_graft_merged" _nightly_logs 2026-04-20 2026-04-21
```

local_reference 推荐：

```bash
ls -lh ~/Desktop/海马体/_docs | grep -E "<topic>|DOCS_INDEX"
grep -n "OmbreBrain_<topic>_v01_READONLY" ~/Desktop/海马体/_docs/OmbreBrain_DOCS_INDEX.md
grep -n "^MARKER$|^EOF$|^PY$" ~/Desktop/海马体/_docs/OmbreBrain_<topic>_v01_READONLY.md || echo "无脏尾巴"
```

### 9. 设计意义

必须说明：

- 它解决什么问题
- 为什么对海马体有长期意义
- 和活人感 / 连续性 / 施工稳定性有什么关系

### 10. 下次候选

列出未来可能拆出的候选。

如果没有，写：

```text
暂无明确候选。
```

### 11. 当前结论

必须明确：

- 这是设计文档还是本地参考
- 不是线上功能
- 不是主脑写入
- 当前状态是否完成

## 六、固定检查项

READONLY 收口完成前必须检查：

- 文件存在
- 文件大小正常
- DOCS_INDEX 已挂载
- 无脏尾巴
- 如果是 repo_design，smoke test passed
- 如果是 repo_design，分支已推送
- PR #2 仍 Open
- main 未动
- Zeabur 未动
- DeepSeek 未调用
- xiaowo-release 未运行，除非该卡明确是外部运行验证

## 七、脏尾巴规则

脏尾巴指 heredoc 或 python one-shot 的结束标记意外进入文件。

常见脏尾巴：

- EOF
- PY
- 该卡专用 marker

检查命令：

```bash
grep -n "^MARKER$|^EOF$|^PY$" file || echo "无脏尾巴"
```

处理原则：

- 发现就清理
- 清理后重新检查
- 如果已经影响索引，重写索引
- 如果频繁发生，后续可开 dirty_tail_guard v0.1

## 八、DOCS_INDEX 挂载规则

每张 READONLY 卡必须挂载到：

```text
~/Desktop/海马体/_docs/OmbreBrain_DOCS_INDEX.md
```

挂载内容应包括：

- 文件名
- 用途
- 内容包括
- 当前状态

不要把整张 READONLY 内容复制进索引。

## 九、使用原则

### 1. READONLY 是回看入口

未来不一定先读完整设计文档。
先读 READONLY，知道这颗是什么、完成到哪、边界是什么。

### 2. 本地卡不等于主脑记忆

READONLY 是文档柜标签。
是否进入长期记忆、规则卡、成长链，要走相应路由。

### 3. 不要写成情绪总结

可以有生活感，但不能把收口卡写成纯聊天记录。

### 4. 不要漏边界

每张卡必须写清楚当前不做什么。

### 5. 不要为了统一牺牲重点

模板是骨架，具体章节可以按主题调整。

## 十、当前边界

当前阶段只写设计文档。

不做：

- 不自动生成 READONLY
- 不改脚本
- 不新增校验程序
- 不合并 main
- 不部署 Zeabur
- 不自动写主脑
- 不自动调用 DeepSeek

## 十一、当前结论

readonly_card_schema v0.1 是 OmbreBrain 本地 READONLY 收口卡的统一骨架。

它让每张收口卡都能回答：

- 这是什么
- 做完了吗
- 证据在哪
- 边界在哪
- 未来怎么接

卡片有骨架，
文档柜才不会越收越乱。
