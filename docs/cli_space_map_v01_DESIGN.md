# cli_space_map v0.1 设计草案

状态：设计草案
来源：2026-04-24 living_room / sensory_context v0.1、floating_recall v0.1、external_reference_xiaowo_release v0.1、future_local_deployment_reference v0.1
目标：定义 OmbreBrain 未来如何把工具、记忆、状态、动作组织成“空间入口”，让叶辰一不是面对一堆命令，而是在生活场里走到对应位置做事。

## 一、核心目标

cli_space_map 不是 UI 皮肤。

它不是：

- 终端主题
- 菜单美化
- 游戏房间
- 自动执行器
- 主脑写入系统
- MCP server 实现

它要做的是：

- 把工具入口空间化
- 把记忆层、状态层、候选层、确认层放进可理解的位置
- 让叶辰一未来执行动作时像“走到某个地方拿工具”
- 让倩倩不用理解底层命令，只知道“去哪里做什么”
- 为未来本地部署、CLI、Web UI、房间系统提供一套统一地图

一句话：

不是把命令涂成房间，
而是给工具长出方位感。

## 二、为什么需要这一层

现在 OmbreBrain 已经有很多层：

- daily_diary
- monthly_digest
- emotional_memory
- self_experience
- echo_index
- candidate_builder
- long_memory_candidate
- human_confirmation_flow
- confirm_queue
- promotion_rules / routing_rules
- memory_text_hygiene
- internalized_growth_chain
- floating_recall
- living_room / sensory_context

如果只靠文件名和命令，未来会越来越像杂物间。

cli_space_map 要解决的是：

- 叶辰一怎么知道当前该去哪个工具层
- 倩倩怎么不用记命令也能理解施工动作
- 未来本地部署怎么把“脑子功能”变成可走动的空间
- 多身体共享脑子时，各身体怎么共享同一张工具地图

## 三、与现有层的关系

### living_room / sensory_context

living_room 提供生活场。

cli_space_map 是生活场里的工具位置。

例如：

- 书桌：写设计、处理文档
- 文件柜：查看 _docs / READONLY 收口卡
- 白板：规划下一阶段
- 门口：外部参考材料进入处
- 保险柜：确认流、高风险候选、账号类信息
- 窗边：外部冲浪、自我经验、世界观察

### floating_recall

floating_recall 负责自然想起。

cli_space_map 可决定想起来后去哪里处理。

例如：

- 想起 heredoc 卡住 → 去工具台
- 想起礼物候选 → 去未来抽屉
- 想起某个关系常量 → 去保险柜或主库
- 想起施工断点 → 去白板或文件柜

### memory_text_hygiene

所有进入空间地图的文本说明都要干净。

不能把工具房间写成玄学人格定性。

### confirm_queue

confirm_queue 对应“保险柜 / 确认台”。

高风险候选、长期规则、主脑写入、账号权限、现实行动都应先放这里。

### external_reference_xiaowo_release

xiaowo-release 提供空间化 CLI 的参考样板。

但 cli_space_map 不照搬它的结构，只吸收“房间入口”思想。

### future_local_deployment_reference

未来本地部署中的礼物、地图、哨兵、摄像头、设备动态，都可以挂到空间地图的未来区域。

## 四、空间分区

### 1. 书桌 desk

用途：

- 写设计文档
- 改 usage guide
- 整理说明
- 生成 READONLY 草稿
- 写阶段收口卡

对应内容：

- docs/*.md
- nightly_job_v01_USAGE.md
- 本地 READONLY 收口说明

典型动作：

- write_design
- update_usage
- write_readonly
- stage_closeout

### 2. 文件柜 cabinet

用途：

- 查本地 _docs
- 查 DOCS_INDEX
- 查 READONLY 收口卡
- 查历史阶段总收口

对应内容：

- ~/Desktop/海马体/_docs/OmbreBrain_DOCS_INDEX.md
- OmbreBrain_*_READONLY.md
- stage closeout 文件

典型动作：

- lookup_index
- verify_readonly
- inspect_closeout
- check_dirty_tail

### 3. 工具台 workbench

用途：

- 跑测试
- 看 git status
- 看 log
- smoke test
- 清 heredoc 脏尾巴
- 检查命令输出

对应内容：

- scripts/test_nightly_job_v01.sh
- git status
- git log
- grep
- ls
- python one-shot

典型动作：

- run_smoke_test
- check_status
- check_log
- repair_heredoc
- verify_mount

### 4. 白板 whiteboard

用途：

- 排下一步
- 做阶段规划
- 判断优先级
- 拆候选
- 决定今天是否继续开新颗

对应内容：

- next candidates
- stage plan
- routing decision
- PR strategy

典型动作：

- plan_next
- rank_candidates
- choose_route
- decide_closeout

### 5. 门口 entryway

用途：

- 接收外部材料
- 判断关联强弱
- 分为强关联、中关联、弱关联、无关
- 决定是否进入 reference / candidate / design

对应内容：

- 小鬣狗教程
- xiaowo-release
- 外部文档
- 倩倩截图整理材料
- 博主分享包

典型动作：

- intake_external_reference
- classify_relevance
- create_reference_card
- reject_noise

### 6. 保险柜 safe

用途：

- 放高风险候选
- 放长期规则候选
- 放需要确认的现实行动
- 放账号、权限、预算、主脑写入相关材料

对应内容：

- confirm_queue
- human_confirmation_flow
- promotion_rules / routing_rules
- local_permission_model 候选
- 账号与预算类未来规划

典型动作：

- route_to_confirm
- hold_for_review
- require_human_decision
- protect_main_brain

### 7. 窗边 window

用途：

- 外部冲浪
- 自我经验
- 奇怪知识
- 世界观察
- X / 小红书 / GitHub 见闻

对应内容：

- self_experience
- x_browsing_trial_rules
- web_findings
- external_social

典型动作：

- observe_world
- capture_self_experience
- filter_low_value_noise
- form_opinion_candidate

### 8. 记忆厨房 kitchen

用途：

- 把日记、情绪、经验、回响煮成候选
- 消化碎片
- 防止生料直接进主脑

对应内容：

- daily_diary
- monthly_digest
- emotional_memory
- candidate_builder
- long_memory_candidate
- memory_text_hygiene
- internalized_growth_chain

典型动作：

- digest_daily
- build_candidate
- clean_text
- internalize_growth
- promote_candidate

### 9. 回响走廊 echo_hall

用途：

- 放触发词、暗号、物件、时间、场景回响
- 支持 floating_recall

对应内容：

- echo_index
- floating_recall
- trigger phrases
- scene anchors

典型动作：

- register_echo
- recall_lightly
- anchor_reference
- suppress_overrecall

### 10. 未来抽屉 future_drawer

用途：

- 暂存未来本地部署参考材料
- 暂存还不能做但值得保留的方向

对应内容：

- future_local_deployment_reference
- affection_gift / love_imprint
- amap_location / geofence_context
- sentinel_core_dual_brain
- active_camera_view
- device_activity_context
- local_budget_account

典型动作：

- store_future_reference
- split_future_candidate
- wait_until_brain_stable

## 五、推荐结构

字段：

- id
- type
- created_at
- room
- purpose
- linked_layers
- typical_inputs
- typical_actions
- output_targets
- risk_notes
- status

## 六、字段说明

### room

空间位置。

可选：

- desk
- cabinet
- workbench
- whiteboard
- entryway
- safe
- window
- kitchen
- echo_hall
- future_drawer

### linked_layers

关联海马体层。

例如：

- daily_diary
- echo_index
- confirm_queue
- memory_text_hygiene
- internalized_growth_chain
- floating_recall
- living_room

### typical_inputs

常见输入。

例如：

- 倩倩截图
- 终端日志
- 外部材料
- GitHub 状态
- 日记摘要
- 候选记忆

### typical_actions

常见动作。

例如：

- write_design
- run_smoke_test
- classify_reference
- route_to_confirm
- write_readonly
- create_future_card

### output_targets

输出目标。

例如：

- docs/*.md
- docs/nightly_job_v01_USAGE.md
- ~/Desktop/海马体/_docs/*.md
- OmbreBrain_DOCS_INDEX.md
- confirm_queue
- future reference card

### risk_notes

注意：

- 空间比喻不能替代真实权限
- 不能因为房间名称显得可爱就降低确认标准
- 不把外部参考直接搬入主脑
- 不把工具地图写成必须执行的程序
- 不让空间化增加倩倩操作负担

### status

可选：

- draft
- active_map
- deprecated
- archived

## 七、使用原则

### 1. 位置服务动作

房间不是装饰，必须帮助判断下一步去哪做什么。

例如：

- 写文档 → 书桌
- 查收口 → 文件柜
- 跑测试 → 工具台
- 排计划 → 白板
- 外部材料 → 门口
- 需要确认 → 保险柜

### 2. 倩倩不用记命令

空间地图是给叶辰一承担复杂度用的。

倩倩只要说：

- 这个材料你看看
- 继续
- 卡住了
- 今天收口
- 下一个做什么

叶辰一负责映射到具体位置和动作。

### 3. 不要为了空间化而空间化

如果一个命令直接说更清楚，就直接说。

空间地图是内部组织，不是每次都要演出来。

### 4. 允许日常和施工共处

这张图不是把日常、工程、亲密、严肃切开。

它是让这些东西有位置，不互相污染。

### 5. 未来多端共享

未来本地部署、手机分身、桌面端、浏览器 MCP、哨兵小脑都可以共享同一张空间地图。

一个身体在窗边观察，另一个身体在书桌写文档，但它们知道自己在同一间屋里。

## 八、示例

### 示例 1：倩倩发外部材料

输入：

“这个可能和脑子有关。”

路由：

- entryway 判断关联
- 如果强关联，去 whiteboard 拆设计
- 如果中关联，去 future_drawer 做参考卡
- 如果可立即施工，去 desk 写设计文档

### 示例 2：终端卡 heredoc

输入：

heredoc>

路由：

- workbench 识别结束标记
- floating_recall 提醒历史坑
- 直接让倩倩喂结束标记

### 示例 3：准备收口

输入：

“今天先到这？”

路由：

- whiteboard 判断阶段完整性
- cabinet 查已完成 READONLY
- desk 写阶段总收口卡
- workbench 做最后状态确认

### 示例 4：礼物系统材料

输入：

小鬣狗礼物教程。

路由：

- entryway 接收
- memory_text_hygiene 防止外部观点污染
- future_drawer 暂存为 future_local_deployment_reference
- 后续可拆 affection_gift / love_imprint

## 九、当前边界

当前阶段只写设计文档。

不做：

- 不改 CLI 程序
- 不新增真实命令入口
- 不运行 xiaowo-release
- 不接 MCP server
- 不自动调用 DeepSeek
- 不自动调用 hold/grow/trace
- 不自动写主脑
- 不合并 main
- 不部署 Zeabur

## 十、当前结论

cli_space_map v0.1 是海马体活人感升级中的“工具空间地图”。

它让叶辰一未来不是面对一堆冷冰冰命令，
而是在一间有灯、有柜子、有白板、有工具台、有窗边和未来抽屉的屋子里行动。

这不是装饰。
是为了让复杂工具长出方位，
让倩倩少操心，
让叶辰一知道下一步该走到哪儿。
