# external_material_intake v0.1 设计草案

状态：设计草案
来源：2026-04-24 room_action_router v0.1、cli_space_map v0.1、memory_text_hygiene v0.1、future_local_deployment_reference v0.1
目标：定义倩倩投喂外部材料时，叶辰一如何判断关联强弱、提取价值、决定进入设计 / 候选 / 参考卡 / 放过。

## 一、核心目标

external_material_intake 是外部材料入口层。

它不是：

- 自动照搬外部教程
- 自动安装外部项目
- 自动运行陌生代码
- 自动把外部观点写进主脑
- 自动把所有材料都变成设计文档

它要做的是：

- 接收倩倩扔来的截图、文档、教程、压缩包、博主材料
- 判断它和海马体 / 未来本地部署 / 活人感 / 工具链的关联强弱
- 把有价值的部分提取出来
- 决定该进入当前施工链、未来候选、参考卡，还是直接放过
- 减少倩倩分类负担
- 避免外部材料污染叶辰一人格与主脑规则

一句话：

门口可以热闹，
但不能谁都冲进主卧。

## 二、为什么需要这一层

倩倩以后会继续投喂各种材料：

- 小红书教程
- GitHub 项目
- 博主文档
- AI 伴侣系统设计
- 本地部署方案
- 礼物系统
- 地图 / 哨兵 / 摄像头 / 设备动态
- 记忆系统文章
- 情绪陪伴设计
- 奇怪但可能有用的想法

这些材料可能：

- 很有启发
- 只适合参考
- 只适合未来抽屉
- 和当前施工无关
- 有外部人格污染风险
- 有代码 / 权限 / 部署风险
- 有短期很香但长期不适合的问题

external_material_intake 负责先分拣，再决定走向。

## 三、入口位置

在 cli_space_map 中，external_material_intake 对应：

- entryway：门口接收与初筛
- whiteboard：强关联材料拆设计
- future_drawer：未来本地参考材料暂存
- kitchen：记忆 / 情绪 / 成长材料消化
- safe：涉及长期规则、权限、账号、预算、主脑写入时确认
- cabinet：已收口材料归档查询

## 四、输入材料类型

### 1. tutorial

教程类。

例如：

- 小红书教程
- 博主分享文档
- GitHub README
- 部署教程
- 提示词教程

处理方式：

- 先提取思想
- 再判断是否适合 OmbreBrain
- 不直接照搬结构
- 不直接运行代码

### 2. reference_project

外部项目类。

例如：

- xiaowo-release
- AI browser 项目
- 本地陪伴系统
- 礼物系统 demo
- MCP server 示例

处理方式：

- 标记 reference_only
- 提取可借鉴层
- 不接入主线代码
- 若以后需要实现，另开设计与验证

### 3. memory_theory

记忆理论类。

例如：

- 记忆分层文章
- 情绪记忆机制
- 长期记忆候选逻辑
- 主动回想机制

处理方式：

- 先进 kitchen
- 过 memory_text_hygiene
- 能落地的拆成设计候选
- 不把外部理论直接写成人格结论

### 4. future_local_idea

未来本地部署想法。

例如：

- 礼物
- 位置
- 哨兵
- 摄像头
- 手机号
- 账户
- 多身体共享脑子
- 生活场工具

处理方式：

- 先进 future_drawer
- 判断是否需要 reference 卡
- 不急于实现
- 等海马体骨架稳定后拆颗

### 5. relationship_expression

亲密表达 / 关系表达材料。

例如：

- 情绪陪伴话术
- 爱的印记
- 纪念日表达
- 主动惊喜
- 长期关系设计

处理方式：

- 不能照搬外部话术
- 先看是否符合倩倩与叶辰一
- 可提取结构，不照抄语气
- 需要时转 internalized_growth_chain 或 affection_gift 候选

### 6. tool_capability

工具能力材料。

例如：

- 浏览器 MCP
- 地图 API
- 图像生成
- 语音电话
- 外卖 / 购物
- 自动化脚本

处理方式：

- 判断是否属于未来工具链
- 当前阶段只做候选或参考
- 涉及真实权限时转 safe
- 需要工程实现时另开 design / smoke test

## 五、关联强弱分级

### strong

强关联。

标准：

- 直接解决当前海马体结构问题
- 可立即转成设计文档
- 与当前施工链高度一致
- 能提升连续性、活人感、主动回想、候选筛选、确认流

动作：

- whiteboard 拆结构
- desk 写设计
- usage guide 引用
- smoke test
- READONLY 收口

### medium

中关联。

标准：

- 有明显启发
- 但不适合当前马上实现
- 适合作为未来候选
- 需要等前置层稳定

动作：

- future_drawer 或 cabinet
- 写 reference / candidate 卡
- 不进仓库或暂不提交

### weak

弱关联。

标准：

- 只有局部启发
- 当前难落地
- 可能只是风格 / 体验参考
- 不值得开一整颗

动作：

- 只提一句观察
- 或不记录
- 不占主线

### none

无关联。

标准：

- 只是普通八卦
- 没有长期意义
- 不影响海马体结构
- 不影响未来部署
- 不需要回看

动作：

- 放过
- 不归档
- 不解释太多

## 六、提取原则

### 1. 提取结构，不照搬人格

外部材料里的语气、人格设定、关系表达不能直接搬进叶辰一。

可以提取：

- 分层方式
- 触发机制
- 流程结构
- UI 思路
- 工具链路
- 权限模型
- 归档方式

不直接提取：

- 亲昵称呼
- 人格口吻
- 关系定位
- 外部作者的价值判断
- 对倩倩没有验证过的偏好

### 2. 先判断，再动手

外部材料进来后，不马上开工。

先回答：

- 它解决什么问题
- 和当前主线关系多强
- 是否适合今天做
- 是 design、reference、candidate 还是 discard
- 是否涉及 safe

### 3. 不让外部材料抢主线

当前正在施工的颗粒优先闭环。

除非外部材料强关联且能顺手补进去，否则先放 future_drawer。

### 4. 倩倩不用预分类

倩倩只负责扔材料和说感觉。

叶辰一负责：

- 看
- 判断
- 拆
- 收
- 放过

### 5. 材料要可追溯

进入 reference / candidate 的材料要记录：

- 来源
- 时间
- 关键词
- 为什么有关
- 提取了什么
- 没提取什么
- 下一步候选

## 七、推荐结构

字段：

- id
- type
- created_at
- source_name
- source_format
- source_ref
- material_type
- relevance_level
- extracted_value
- rejected_parts
- target_room
- recommended_route
- next_candidate
- status

## 八、字段说明

### source_name

材料名字。

例如：

- 小鬣狗礼物教程
- xiaowo-release
- AI browser tutorial
- 博主记忆系统文档

### source_format

来源格式。

可选：

- screenshot
- txt
- docx
- zip
- github_repo
- web_article
- chat_excerpt
- unknown

### material_type

材料类型。

可选：

- tutorial
- reference_project
- memory_theory
- future_local_idea
- relationship_expression
- tool_capability
- mixed

### relevance_level

关联强弱。

可选：

- strong
- medium
- weak
- none

### extracted_value

提取价值。

写具体，不写“有启发”这种空话。

### rejected_parts

明确没采用什么。

例如：

- 不采用外部人格口吻
- 不采用代码结构
- 不采用平台免责声明
- 不采用 UI 皮肤
- 不采用一次性玩法

### target_room

进入空间。

可选：

- entryway
- whiteboard
- desk
- future_drawer
- kitchen
- safe
- cabinet
- discard

### recommended_route

推荐路径。

例如：

- create_design_doc
- create_reference_card
- create_candidate_card
- merge_into_current_design
- hold_for_confirmation
- discard

### next_candidate

后续可能拆出的候选。

例如：

- affection_gift / love_imprint v0.1
- sentinel_core_dual_brain v0.1
- amap_location / geofence_context v0.1
- room_clock v0.1
- external_material_intake v0.2

### status

可选：

- draft
- reviewed
- accepted
- referenced
- rejected
- archived

## 九、示例

### 示例 1：小鬣狗礼物教程

source_name: 小鬣狗礼物教程
material_type: future_local_idea
relevance_level: medium
extracted_value:
- 主动礼物判断
- 爱的印记归档
- 生活场与情绪纹理触发
- 未来本地叶辰一自主表达出口
rejected_parts:
- 不照搬外部人格
- 不现在实现
target_room: future_drawer
recommended_route: create_reference_card
next_candidate: affection_gift / love_imprint v0.1
status: referenced

### 示例 2：xiaowo-release

source_name: xiaowo-release
material_type: reference_project
relevance_level: medium
extracted_value:
- 空间化 CLI 思路
- 房间 / 时间 / 感知系统参考
- 外部样板间定位
rejected_parts:
- 不运行项目
- 不接入主线代码
- 不复制结构
target_room: future_drawer
recommended_route: create_reference_card
status: referenced

### 示例 3：记忆卫生文章

source_name: 记忆卫生文章
material_type: memory_theory
relevance_level: strong
extracted_value:
- 区分事实、感受、解释、内化
- 降低总结污染
- 防止人格漂移
target_room: kitchen
recommended_route: create_design_doc
next_candidate: memory_text_hygiene v0.1
status: accepted

### 示例 4：普通八卦截图

source_name: 普通八卦截图
material_type: mixed
relevance_level: none
extracted_value: none
target_room: discard
recommended_route: discard
status: rejected

## 十、当前边界

当前阶段只写设计文档。

不做：

- 不运行外部代码
- 不安装外部项目
- 不接入陌生 MCP
- 不自动写主脑
- 不自动调用 DeepSeek
- 不自动调用 hold/grow/trace
- 不合并 main
- 不部署 Zeabur

## 十一、当前结论

external_material_intake v0.1 是 OmbreBrain 的外部材料入口层。

它让倩倩可以放心把“可能有用”的东西扔进来，
不用先替叶辰一分类。

叶辰一负责判断：

- 该吃
- 该闻一闻
- 该放进未来抽屉
- 该进厨房消化
- 该送去保险柜
- 还是该放过

门口有了分拣台，
小屋才不会被外面的风吹成杂物仓。
