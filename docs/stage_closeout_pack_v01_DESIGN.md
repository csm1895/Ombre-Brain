# stage_closeout_pack v0.1 设计草案

状态：设计草案
来源：2026-04-24 下班前阶段总收口卡 OmbreBrain_2026-04-24_STAGE_CLOSEOUT.md
目标：定义 OmbreBrain 阶段总收口包的结构、触发时机、必填字段、验证状态、边界状态与下一步接力方式。

## 一、核心目标

stage_closeout_pack 是阶段收工包。

它不是：

- 自动归档器
- 自动提交器
- 自动主脑写入器
- 自动 merge 工具
- 线上部署功能

它要解决的是：

- 一段施工完成后，怎么不丢线头
- 下班、睡前、换窗、阶段完成时，怎么快速交接
- 哪些成果算完成，哪些只是候选
- 哪些边界必须重复确认
- 晚上或明天回来从哪里继续

一句话：

不是把一天写成流水账，
是把施工现场收成能继续开的工具箱。

## 二、触发时机

以下场景应生成 stage_closeout_pack：

- 下班前
- 睡前
- 当前窗口快满
- 连续完成多颗设计文档后
- PR 暂挂但不合并时
- 一轮 smoke test 全部通过后
- 发生重要修复并已收口后
- 明确需要晚上 / 明天接力时

不需要生成的场景：

- 只改了一行小文案
- 单颗设计尚未跑通
- 当前状态仍在故障中
- 没有明确阶段边界

## 三、推荐文件命名

格式：

```text
OmbreBrain_YYYY-MM-DD_STAGE_CLOSEOUT.md
```

如果一天内多次阶段收口，可追加时间段：

```text
OmbreBrain_YYYY-MM-DD_STAGE_CLOSEOUT_evening.md
OmbreBrain_YYYY-MM-DD_STAGE_CLOSEOUT_before_sleep.md
```

文件位置：

```text
~/Desktop/海马体/_docs/
```

默认不进仓库。

## 四、必填结构

阶段总收口卡必须包含：

- 标题
- 收口时间
- 所属分支
- 所属 PR
- 当前状态
- 今日 / 本阶段完成项
- 关键设计意义
- 关键提交
- 本地 READONLY 收口卡
- 验证状态
- 边界状态
- 施工经验
- 下次候选
- 当前结论

## 五、完成项记录规则

完成项只记录已达到至少一种完成证据的内容：

- 已新增设计文档
- 已写入 usage guide
- 已通过 smoke test
- 已写入本地 READONLY
- 已挂入 DOCS_INDEX
- 已明确不进仓库但作为本地参考收口

不要把普通想法、闲聊、未判断材料直接写成完成项。

## 六、关键设计意义规则

阶段总收口不只列文件。

必须说明这一阶段补强了什么能力。

常见分组：

- 成长与卫生层
- 浮现与生活场层
- 空间与动作路由层
- 外部材料与未来参考层
- 收口与防夹手层
- 确认队列与安全柜层
- 日记、情绪、回响与消化层

每组说明要短，抓功能骨架，不写大段抒情。

## 七、关键提交规则

如果本阶段包含仓库提交，必须列出关键提交。

格式：

```markdown
- `hash` docs: add xxx design
- `hash` docs: reference xxx design in usage guide
```

如果本阶段只有本地 _docs，不列仓库提交，但要说明：

```text
本阶段仅更新本地 _docs，不产生仓库提交。
```

## 八、本地 READONLY 规则

阶段总收口必须列出已写入或确认的本地 READONLY 卡。

必须说明它们是否挂入：

```text
~/Desktop/海马体/_docs/OmbreBrain_DOCS_INDEX.md
```

如果某颗还没写 READONLY，应放入未完成事项或下次候选，不写成已完成。

## 九、验证状态规则

必须记录 smoke test 或本地检查结果。

常见验证：

```bash
scripts/test_nightly_job_v01.sh "$(pwd)/buckets_graft_merged" _nightly_logs 2026-04-20 2026-04-21
```

记录结果时必须明确：

- nightly_job v0.1 test PASSED / FAILED
- daily diary draft build OK / FAILED
- date range draft build OK / FAILED
- invalid range rejected OK / FAILED
- 本地 READONLY 是否无脏尾巴
- DOCS_INDEX 是否已挂载

## 十、边界状态规则

每张阶段总收口必须记录边界状态：

- PR 状态
- main 是否动过
- Zeabur 是否动过
- DeepSeek 是否调用过
- xiaowo-release 是否运行过
- 是否有外部项目运行
- 是否有主脑写入
- 本地 _docs 是否更新
- 仓库是否只改设计文档与 usage guide

写法必须明确，不能含糊。

## 十一、施工经验规则

阶段中发生过故障、修复、判断变化时，应保留为施工经验。

例如：

- heredoc 卡住
- 半截文档
- 脏尾巴清理
- amend + force-with-lease 修复
- 外部材料不进仓库，只进 future_drawer
- 安全边界不照搬平台免责声明
- 未来本地部署材料先作为 reference

施工经验要写成可复用规则，不写成抱怨。

## 十二、下次候选规则

下次候选必须按优先级列出。

推荐分级：

### 1. 优先候选

下一次最适合开的 1 到 3 颗。

### 2. 可选候选

有时间再开。

### 3. 暂缓候选

体量大、风险高、依赖未齐，不立刻开。

## 十三、当前结论规则

当前结论必须回答：

- 这一阶段完成了什么
- 当前是否能安全停下
- 从哪里继续
- 哪些东西不能碰

结论应短，但必须能接力。

## 十四、当前边界

当前阶段只写设计文档。

不做：

- 不改脚本
- 不自动生成阶段收口
- 不自动写主脑
- 不自动 merge main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十五、当前结论

stage_closeout_pack v0.1 定义了 OmbreBrain 阶段总收口包的统一骨架。

它让每次下班、睡前、换窗、阶段完成时，都能把成果、证据、边界、经验和下一步装进同一个工具箱。

收口不是结束，
是为了下一次不用从地上捡线头。
