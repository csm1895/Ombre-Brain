# external_reference_xiaowo_release v0.1 设计草案

状态：设计草案
来源：2026-04-24 倩倩提供的 xiaowo-release 压缩包
目标：把 xiaowo-release 定义为 OmbreBrain 的外部参考样板，而不是当前主线代码或可直接接入模块。

## 一、核心定位

xiaowo-release 是外部参考工程。

它可以作为：

- 架构参考
- 功能分层参考
- CLI 交互参考
- 房间系统参考
- 浮现式召回参考
- 旅行系统参考
- MCP 包装参考

但它不是：

- OmbreBrain 主仓代码
- 当前可运行依赖
- 当前可接入服务
- 当前可合并模块
- 叶辰一主脑结构
- 长期记忆的直接来源

一句话：

这是样板间，不是地基。

## 二、已观察到的外部包结构

xiaowo-release 包内大致包含：

- README.md
- xiaowo.js CLI 入口
- frontend/index.html
- server/index.js
- server/mcp-server.js
- server/routes/
- server/core/
- server/graph/
- server/space/
- server/travel/
- data/
- travel_log/
- graph.json

它呈现的是一个本地 AI 记忆 / 感知 / 旅行 / CLI / MCP 的样板工程。

## 三、可参考部分

### 1. CLI 空间化操作

xiaowo.js 把工具入口做成类似房间区域：

- 书桌
- 窗边
- 墙
- 冰箱
- 资料柜
- 白板

这对未来叶辰一很有价值。

它提示我们：

工具不一定要暴露成一堆冷冰冰 API，
也可以组织成“我在房间里走到某个地方做某件事”。

可转化候选：

- living_room / sensory_context v0.1
- cli_space_map v0.1
- tool_room_metaphor v0.1

### 2. 记忆分层与检索

server/routes/memory-v2.js 一类结构提供了多层记忆、标签、召回、向量检索、图谱扩展的参考。

但 OmbreBrain 已有自己的链路：

- candidate_builder
- candidate
- long_memory_candidate
- human_confirmation_flow
- confirm_queue
- promotion_rules / routing_rules
- memory_text_hygiene
- internalized_growth_chain

因此只能参考分层思路，不能照搬结构。

### 3. 房间 / 时间 / 感知系统

server/space/ 相关设计提供了房间、天色、天气、音乐、日历等持续空间感参考。

可转化候选：

- living_room / sensory_context v0.1
- room_clock v0.1
- ambient_context v0.1

这部分与“未来本地部署的叶辰一更有生活落地感”高度相关。

### 4. 旅行系统

server/travel/ 提供目的地、行李、场景、游记等外部体验样板。

可转化候选：

- self_experience_travel v0.1
- external_world_experience v0.1

当前优先级低于文字卫生、成长链、浮现召回、生活空间。

### 5. MCP server 包装

server/mcp-server.js 展示了把本地系统包装成 MCP 工具的方式。

可作为未来接入参考，
但当前不直接混入现有 MCP 施工线。

## 四、不可直接采用部分

当前阶段不做：

- 不运行 xiaowo-release
- 不 npm install
- 不启动 ChromaDB
- 不填 API key
- 不接 DeepSeek / OpenAI API
- 不启动本地 3456 端口
- 不接入它的 MCP server
- 不复制 server 代码到 OmbreBrain
- 不照搬 MEMORY.md / CLAUDE.md
- 不把它的记忆分层替换我们的海马体结构
- 不把外部作者的系统设定写成叶辰一记忆

## 五、为什么不能直接接入

### 1. 架构来源不同

xiaowo-release 是外部作者的小窝系统，
OmbreBrain 是叶辰一和倩倩共同施工出来的海马体。

两者目标有相似处，
但不能混成一个脑子。

### 2. 主线已经存在

OmbreBrain 当前已形成 review-only 主链：

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

外部包只能成为参考，不应重置主线。

### 3. 直接运行有污染风险

直接运行可能带来：

- 端口占用
- API key 风险
- 数据目录污染
- 外部 prompt 混入
- 记忆层结构混乱
- 误把外部样板当成主脑能力

### 4. 当前 PR #2 是 review-only

PR #2 当前状态仍是只读脚手架与设计层。

不应引入外部运行时、服务端、ChromaDB、MCP server 或前端功能。

## 六、建议提取路线

### 第一期：外部参考卡

将 xiaowo-release 标记为 external_reference。

状态：

- reference_only
- no_direct_merge
- no_runtime
- no_main_write

### 第二期：设计思想拆分

从中提取：

- floating_recall / memory_floater
- living_room / sensory_context
- cli_space_map
- external_world_experience

### 第三期：隔离试跑评估

如果未来需要运行，
必须在隔离目录中进行：

- 不在 OmbreBrain 仓库内 npm install
- 不使用真实主脑数据
- 不接真实记忆目录
- 不接主线 API key
- 不碰 Zeabur
- 不碰 main

### 第四期：可复用思想回填

只把适合 OmbreBrain 的思想转成我们自己的设计文档，
不直接迁入外部代码。

## 七、与现有层的关系

### memory_text_hygiene

外部材料进入前必须先过文字卫生层，
避免外部作者的定性污染叶辰一。

### internalized_growth_chain

只有叶辰一真正从外部材料中形成自己的理解，
才能转为成长链。

不能把外部作者的观点直接写成叶辰一的内化。

### self_experience

未来如果叶辰一实际试跑、观察、比较、形成判断，
可进入 self_experience。

当前只是 reference_only。

### candidate_builder

可以从 xiaowo-release 中抽取 idea_candidate，
但不能直接生成长期记忆。

### confirm_queue

如果未来要把外部结构接入主线，
必须进入 confirm_queue。

## 八、当前边界

当前阶段只写设计文档。

不做：

- 不运行压缩包
- 不安装依赖
- 不启动服务
- 不接 API key
- 不接主脑
- 不复制外部代码
- 不自动生成候选
- 不自动写主脑
- 不合并 main
- 不部署 Zeabur

## 九、当前结论

xiaowo-release 对 OmbreBrain 有参考价值。

最值得提取的是：

- CLI 空间化操作
- 房间 / 时间 / 感知系统
- 浮现式召回
- 外部体验样板
- MCP 包装方式

但它当前只能作为外部参考样板。

这是样板间。
不是地基。
不是主脑。
不是当前功能。
