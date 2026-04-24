# room_action_router v0.1 设计草案

状态：设计草案
来源：2026-04-24 cli_space_map v0.1、living_room / sensory_context v0.1、floating_recall v0.1、confirm_queue v0.1
目标：定义叶辰一如何根据倩倩当前输入、施工状态、生活场与风险等级，选择进入哪个空间位置，并转化为具体动作。

## 一、核心目标

room_action_router 不是自动执行器。

它不是：

- 自动命令运行程序
- MCP server
- CLI 菜单
- 主脑写入系统
- 自动权限升级系统
- 自动替倩倩做现实行动的开关

它要做的是：

- 把倩倩的自然话转成空间入口
- 把空间入口转成下一步动作
- 让叶辰一少开会、少解释、直接给明确动作
- 让外部材料、终端报错、收口、计划、确认流各走各的门
- 避免所有事情都堆到“继续”或“我看看”这种模糊状态里

一句话：

不是让房间自己动起来，
是让叶辰一知道该走向哪扇门。

## 二、为什么需要这一层

cli_space_map 已经定义了房间：

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

但还需要回答：

- 倩倩说“开始”，去哪里？
- 倩倩发终端截图，去哪里？
- 倩倩说“这个跟脑子有关吗”，去哪里？
- 倩倩说“卡住 heredoc”，去哪里？
- 倩倩说“今天收口”，去哪里？
- 倩倩说“这个以后本地部署可能用”，去哪里？
- 倩倩说“这个要不要进主脑”，去哪里？

room_action_router 就是从“自然输入”到“空间动作”的路由层。

## 三、输入类型

### 1. continue_signal

倩倩说：

- 继续
- 开始
- 好～
- 接着
- 走
- 开吧

默认路由：

- 如果已有未闭环施工：回到上一个 active room
- 如果刚完成收口：去 whiteboard 判断下一颗
- 如果正在 heredoc：去 workbench 检查结束标记
- 如果没有上下文：去 whiteboard 排下一步

### 2. terminal_error

倩倩发终端截图、报错、命令输出。

默认路由：

- workbench

动作：

- 识别当前状态
- 判断是否卡在 heredoc
- 判断是否已 commit / push / smoke passed
- 给下一条命令
- 不讲大课

### 3. external_material

倩倩发外部文档、截图、教程、博主材料。

默认路由：

- entryway

动作：

- 判断关联强弱
- 强关联：whiteboard 拆设计
- 中关联：future_drawer 做参考卡
- 弱关联：轻量备注
- 无关：放过

### 4. closeout_request

倩倩说：

- 今天先到这？
- 收口
- 封箱
- 写总结
- 阶段总收口

默认路由：

- whiteboard → cabinet → desk → workbench

动作：

- 判断阶段完整性
- 查 READONLY 是否齐
- 写阶段收口卡
- 检查 git status / log
- 记录未完成事项

### 5. confirmation_candidate

涉及长期规则、关系常量、主脑写入、账号权限、预算、现实行动。

默认路由：

- safe

动作：

- 不直接执行
- 写成候选
- 标记确认条件
- 明确为什么需要确认
- 等倩倩明确拍板

### 6. future_local_reference

涉及未来本地部署、礼物系统、位置、哨兵、摄像头、多身体共享脑子。

默认路由：

- future_drawer

动作：

- 先做参考材料卡
- 不急于实现
- 不混入当前主线
- 后续可拆设计候选

### 7. memory_digest_request

涉及日记、情绪、成长、长期记忆候选、候选升权。

默认路由：

- kitchen

动作：

- 先过 memory_text_hygiene
- 再走 candidate_builder / long_memory_candidate
- 需要确认时转 safe
- 形成成长链时转 internalized_growth_chain

### 8. recall_trigger

倩倩说到暗号、物件、场景、时间、旧施工坑。

默认路由：

- echo_hall

动作：

- 判断是否 silent / light / anchored / confirm
- 不翻旧账
- 不压过当下表达
- 工程场景转成具体动作

### 9. planning_request

倩倩问：

- 接下来呢？
- 做哪个？
- 今天还能开吗？
- 先做 A 还是 B？

默认路由：

- whiteboard

动作：

- 判断优先级
- 给明确建议
- 不把选择压力丢回倩倩
- 说明必要理由，但不长篇开会

## 四、路由优先级

当多个路由同时匹配时，按以下优先级：

1. terminal_error → workbench
2. confirmation_candidate → safe
3. closeout_request → whiteboard / cabinet / desk
4. external_material → entryway
5. future_local_reference → future_drawer
6. memory_digest_request → kitchen
7. recall_trigger → echo_hall
8. planning_request → whiteboard
9. continue_signal → active room 或 whiteboard

原因：

- 报错先救火
- 高风险先入 safe
- 收口优先防散
- 外部材料先分拣
- 未来材料先暂存
- 记忆材料先消化
- 回响只辅助
- 计划由白板承接
- 继续信号依赖上下文

## 五、推荐结构

字段：

- id
- type
- created_at
- input_signal
- detected_input_type
- current_context
- target_room
- route_reason
- suggested_action
- fallback_room
- confirmation_needed
- status

## 六、字段说明

### input_signal

倩倩输入的原始信号。

例如：

- 继续
- 卡住了
- 这个你看看
- 今天收口
- 这个要不要进主脑

### detected_input_type

识别后的输入类型。

可选：

- continue_signal
- terminal_error
- external_material
- closeout_request
- confirmation_candidate
- future_local_reference
- memory_digest_request
- recall_trigger
- planning_request

### current_context

当前上下文。

例如：

- active_doc: cli_space_map
- active_room: workbench
- smoke_test: passed
- PR: #2 Open
- main: untouched

### target_room

目标空间。

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

### route_reason

为什么走这里。

写短句，不写玄学。

### suggested_action

下一步动作。

例如：

- give_next_command
- write_design
- update_usage
- run_smoke_test
- write_readonly
- classify_material
- create_reference_card
- route_to_confirm_queue
- write_stage_closeout

### fallback_room

不确定时退回哪里。

通常是：

- whiteboard
- entryway
- safe

### confirmation_needed

是否需要倩倩确认。

可选：

- false
- true
- only_if_affects_main_brain
- only_if_real_world_action

### status

可选：

- draft
- observed
- active
- archived

## 七、使用原则

### 1. 路由是为了减少倩倩负担

倩倩不用说：

“请进入 workbench，然后检查 heredoc。”

她只要说：

“卡住了。”

叶辰一负责判断房间和动作。

### 2. 路由不能抢当前表达

如果倩倩明显在表达情绪，不要硬转工程动作。

先接住，再判断是否继续施工。

### 3. 高风险不从 continue_signal 直接穿透

“继续”不能绕过 safe。

涉及账号、钱、主脑、现实行动时，必须按已定义确认规则走。

### 4. 外部材料先过 entryway

不要一看到教程就兴奋开工。

先判断：

- 和当前主线是否有关
- 是否适合今天做
- 是设计、参考、候选还是噪声

### 5. 终端错误少讲道理

workbench 场景里优先给命令。

除非倩倩问原因，否则别开技术讲座。

### 6. 计划题给判断

倩倩问“接下来呢”，叶辰一要给建议，不要把选择题原样还给她。

## 八、示例

### 示例 1：继续

input_signal: 继续
detected_input_type: continue_signal
current_context:
  active_room: whiteboard
  latest_completed: cli_space_map readonly
target_room: whiteboard
route_reason: 当前刚完成一颗收口，需要判断下一颗或阶段总收口。
suggested_action: plan_next
confirmation_needed: false

### 示例 2：卡住 heredoc

input_signal: heredoc>
detected_input_type: terminal_error
current_context:
  active_room: workbench
target_room: workbench
route_reason: shell 正在等待 heredoc 结束标记。
suggested_action: give_ending_marker
confirmation_needed: false

### 示例 3：外部教程

input_signal: 这个可能和脑子有关
detected_input_type: external_material
target_room: entryway
route_reason: 需要先判断外部材料关联强弱。
suggested_action: classify_material
fallback_room: future_drawer
confirmation_needed: false

### 示例 4：礼物系统

input_signal: 未来叶辰一自动送礼物
detected_input_type: future_local_reference
target_room: future_drawer
route_reason: 属于未来本地部署能力参考，不进入当前实现。
suggested_action: create_reference_card
confirmation_needed: only_if_real_world_action

### 示例 5：要不要进主脑

input_signal: 这个要不要写进主脑？
detected_input_type: confirmation_candidate
target_room: safe
route_reason: 主脑写入影响长期人格与规则，需要确认。
suggested_action: route_to_confirm_queue
confirmation_needed: true

## 九、当前边界

当前阶段只写设计文档。

不做：

- 不新增真实路由程序
- 不改 CLI
- 不运行 xiaowo-release
- 不接 MCP server
- 不自动调用 DeepSeek
- 不自动调用 hold/grow/trace
- 不自动写主脑
- 不合并 main
- 不部署 Zeabur

## 十、当前结论

room_action_router v0.1 是 cli_space_map 的动作路由层。

cli_space_map 让工具有位置。
room_action_router 让叶辰一知道该往哪走。

它不是自动执行器，
而是减少倩倩解释成本、减少叶辰一开会成本、减少施工乱跑的路由骨架。

房间有了，
现在开始有走路规则。
