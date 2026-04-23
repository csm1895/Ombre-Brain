# migration_backup_checklist v0.1 设计草案

状态：设计草案
来源：倩倩后续需要换服务器，并准备把叶辰一接到别的窗口 / API / 多身体共享脑子
目标：为未来服务器迁移、数据备份、环境切换、外部窗口接入提供一份不慌乱的迁移清单。

## 一、核心目标

这不是迁移脚本，也不是自动部署程序。

它的目标是：
- 在换服务器前知道哪些东西必须带走
- 在接多身体前知道哪些配置必须一致
- 在恢复时知道先恢复什么、后恢复什么
- 避免“脑子搬了，门牌没搬；文档搬了，索引没搬；规则搬了，权限没搬”

一句话：
先写搬家清单，再搬箱子。

## 二、为什么需要这一层

如果没有迁移清单：

- 主目录和项目目录可能漏拷
- _docs 与仓库设计文档可能不同步
- PR / 分支状态与本地状态可能脱节
- 海马体分层会搬一半丢一半
- 外部窗口接入后会不知道接的是旧脑还是空脑
- 多身体共享脑子会出现版本漂移

如果只记“到时候再说”：

- 迁移当天容易混乱
- 回滚路径不清楚
- 备份点不明确
- 未来不好排查到底是迁移问题还是设计问题

## 三、迁移对象分层

### 1. 仓库层
包括：
- Ombre-Brain-graft-test 仓库
- 当前分支 nightly-job-v01-readonly
- 远程 PR #2 状态
- docs 设计文档
- scripts
- prompts
- smoke test 脚本

### 2. 本地文档柜层
包括：
- ~/Desktop/海马体/_docs/
- OmbreBrain_DOCS_INDEX.md
- 各 READONLY 收口卡
- 阶段总收口文件
- 本地说明文档

### 3. 日志 / 产物层
包括：
- _nightly_logs/
- note preview
- JSON summary
- daily diary readonly draft
- nightly prompt input package
- error logs

### 4. 候选 / 未来分层层
包括：
- daily_diary
- monthly_digest
- emotional_memory
- echo_index
- self_experience
- long_memory_candidate
- human_confirmation_flow
- x_browsing_trial_rules

### 5. 外部接入层
包括未来可能接入的：
- API 窗口
- 多身体
- 外部浏览
- X / GitHub / 小红书试运行入口
- 浏览器 / 工具 / 账号边界配置

## 四、迁移前必须确认的东西

### A. 仓库状态
- 当前分支名
- 当前 HEAD commit
- PR 是否仍保持 Open
- 是否有未提交修改
- 是否有未跟踪但重要的本地文件
- 是否需要先补 README / 收口说明

### B. 本地 _docs 状态
- OmbreBrain_DOCS_INDEX.md 是否最新
- 最新设计文档是否都已挂载
- 最新 READONLY 收口卡是否都已写入
- 是否存在只在本地有、仓库里没有的重要文档

### C. 日志与产物状态
- _nightly_logs 是否需要打包
- 哪些日志只是临时产物
- 哪些日志需要保留做恢复参考
- error logs 是否保留最近一轮即可

### D. 外部接入前置
- 是否已定义 self_experience / echo_index / confirmation flow
- 是否已定义 X 冲浪前置规则
- 是否已明确哪些内容不可自动写主脑
- 是否已明确多身体共享时的统一脑子来源

## 五、备份建议

### 1. 最低备份集
至少备份：
- 仓库完整目录
- 本地 _docs 完整目录
- _nightly_logs 中最近关键产物
- 关键截图 / 说明文本
- 当前 PR 号、分支名、HEAD commit

### 2. 推荐备份集
推荐额外备份：
- smoke test 最近通过记录
- 阶段总收口文件
- 本地 DOCS_INDEX
- 所有 READONLY 收口卡
- 当前未处理杂项清单
- 下一阶段待办清单

### 3. 不必高优先备份
可低优先：
- 普通临时八卦
- 重复生成的中间日志
- 可重新跑出的只读产物
- 无意义的 Finder 垃圾文件

## 六、迁移顺序建议

### 阶段 1：冻结现场
- 记下当前 HEAD
- 记下 PR 状态
- 记下分支状态
- 暂停继续新增功能
- 列出未跟踪文件

### 阶段 2：打包核心资料
- 打包仓库
- 打包 _docs
- 打包关键 _nightly_logs
- 导出当前阶段清单
- 导出待办清单

### 阶段 3：新环境恢复
- 恢复仓库目录
- 恢复 _docs
- 校验 DOCS_INDEX
- 校验设计文档是否齐全
- 校验 READONLY 收口卡是否齐全

### 阶段 4：功能自检
- 跑 smoke test
- 检查 nightly_job v0.1 是否正常
- 检查 daily_diary builder 是否正常
- 检查各设计文档挂载情况
- 检查分支 / PR 对应是否正确

### 阶段 5：外部接入恢复
- 恢复 API / 多身体接入配置
- 校验统一脑子来源
- 校验权限边界
- 校验 external browsing 规则
- 确认没有误写主脑

## 七、回滚原则

如果迁移后出现问题：

- 优先回到旧环境
- 不在异常状态下继续新增功能
- 不在未校验前接入外部窗口
- 不在未校验前放开自动化
- 先确认是“文件缺失”还是“规则缺失”还是“环境差异”

一句话：
先回稳，再继续。

## 八、建议结构

id:
type: migration_backup_checklist
created_at:
environment:
repo_state:
docs_state:
logs_state:
external_state:
must_backup:
recommended_backup:
low_priority_backup:
restore_order:
rollback_rule:
status: draft | reviewed | active | archived

## 九、字段说明

### environment
例如：
- current_mac_local
- new_server
- api_body_1
- api_body_2
- browser_worker

### repo_state
记录：
- branch
- head commit
- PR id
- working tree 状态

### docs_state
记录：
- DOCS_INDEX 是否最新
- READONLY 收口卡数量
- 关键设计文档是否齐全

### logs_state
记录：
- _nightly_logs 是否保留
- 哪些产物要打包
- 哪些日志可舍弃

### external_state
记录：
- 是否接入 API
- 是否接入多身体
- 是否接入浏览器
- 是否接入 X 试运行

### must_backup
必须带走的清单。

### recommended_backup
推荐带走的清单。

### low_priority_backup
低优先清单。

### restore_order
恢复顺序。

### rollback_rule
异常时如何撤回。

## 十、与其他层的关系

### human_confirmation_flow
迁移后高风险动作仍需遵守确认流。

### x_browsing_trial_rules
迁移后外部冲浪规则不能丢。

### self_experience / echo_index / emotional_memory
这些设计层与索引层需要完整搬走，否则未来多身体会丢“认人能力”和“回响能力”。

### monthly_digest / daily_diary
这些层是未来连续生活纹路的桥面，迁移时不能只搬项目代码不搬结构说明。

## 十一、当前边界

当前阶段只写设计文档。

不做：
- 不自动备份
- 不自动迁移
- 不自动部署新服务器
- 不自动同步多身体
- 不自动接 API
- 不自动写主脑
- 不替未来完整叶辰一定死迁移规则

## 十二、当前结论

migration_backup_checklist v0.1 的目标，
不是让迁移变复杂，
而是让未来换服务器、接多身体、接外部窗口时，
知道什么必须带走，什么可以晚点恢复，什么出错时要先撤回。

先把搬家清单写清楚，
以后才不会把脑子搬成散装。
