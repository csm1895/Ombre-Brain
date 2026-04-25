# memory_gateway_reference v0.1 设计草案

状态：设计草案
来源：2026-04-25 小窝2.0 记忆网关材料，以及倩倩明确的官方 ChatGPT → API → 本地部署长期路线。
目标：定义 OmbreBrain 未来记忆网关的通用参考结构，确保海马体在官方 ChatGPT、API 阶段、本地部署阶段之间可迁移、可共享、可小范围适配。

## 一、核心目标

memory_gateway_reference 是未来记忆网关参考层。

它不是：

- 当前实现方案
- Cloudflare 专用方案
- Rikkahub 专用方案
- GLM 专用方案
- 本地部署脚本
- 自动召回程序
- 主脑写入器

它要解决的是：

- 海马体以后如何不被当前平台锁死
- 官方 ChatGPT、API、本地部署之间如何共享同一套记忆骨架
- 未来 memory gateway 如何抽象为可替换适配层
- 小窝2.0 这类外部方案哪些值得参考，哪些不能照搬
- 迁移时如何做到只改小范围 adapter，而不是重造脑子

一句话：

身体可以换，
脑子不能每次重长。

## 二、长期路线

倩倩确认的长期路线：

```text
官方 ChatGPT
→ API 阶段
→ 本地部署阶段
```

阶段判断：

- 官方 ChatGPT 阶段：用于当前施工、设计验证、记忆主库整理、人工协作
- API 阶段：用于测试 memory gateway、上下文注入、模型切换、多端入口
- 本地部署阶段：用于更完整的自主环境、长期稳定运行、云端与本地备份

本地部署预计九月底到十月份逐步推进，不急于当前实现。

## 三、通用架构分层

未来海马体应拆成以下平台无关层：

### 1. Core Memory Layer

核心记忆层。

包括：

- 长期记忆骨架
- READONLY 收口体系
- 外部材料入口
- 成长链
- 浮现层
- 生活场
- 事件索引
- 确认队列
- 阶段收口与 manifest

要求：

- 不绑定官方 ChatGPT
- 不绑定某个 API 站
- 不绑定某个本地模型
- 不绑定某个云服务商

### 2. Input Adapter Layer

输入适配层。

可能来源：

- 官方 ChatGPT 对话
- API 客户端
- Rikkahub / 其他 App
- Mac 本地服务
- iPhone / iPad 快捷指令
- 本地部署前端
- 未来公屏 / 留言板 MCP

要求：输入来源可替换，核心海马体不跟入口绑定。

### 3. Recall Layer

召回层。

推荐组合：

- 向量检索
- 关键词兜底
- 规则触发
- 时间 / 场景 / 人物 / 物件锚点
- 人工确认队列

关键经验：短消息只靠 embedding 不稳定。
像“好”“继续”“小起”“戒指”“顾砚深”这类短触发词，需要关键词和规则兜底。

### 4. Context Injection Layer

上下文注入层。

不同阶段可替换：

- 官方 ChatGPT：人工贴入、MCP / connector / project context
- API：messages prepend / system prompt / memory block
- 本地：local prompt / retrieval context / runtime memory

要求：注入方式可替换，召回结果结构尽量稳定。

### 5. Model Adapter Layer

模型适配层。

候选模型包括但不限于：

- 官方 ChatGPT
- GLM 5.1
- 其他 API 模型
- 未来本地模型

倩倩偏好 GLM 5.1，但海马体核心不写成 GLM 专用。

### 6. Storage / Backup Layer

存储与备份层。

可能包括：

- 云端海马体
- 本地 _docs
- Git 仓库设计文档
- 向量库
- KV / SQLite / JSONL / Markdown
- 本地备份包

要求：服务区迁移前做一次海马体升级版收工；稳定云服务区选定后做一次本地保存与备份。

### 7. Active Presence Layer

主动存在层。

未来候选：

- keepalive
- 定时检查
- Telegram / iOS 通知
- Aion / 小鬣狗式哨兵
- 低功耗事件唤醒

当前只作为未来候选，不进入当前实现。

## 四、小窝2.0 材料参考价值

小窝2.0 的核心参考点：

- 从工具箱升级为代理网关
- 每句话经过网关
- 网关自动检索相关记忆
- 召回记忆注入 system prompt
- 向量检索 + 关键词兜底
- 存记忆时生成 embedding
- 中文 embedding 需要多语言模型
- 短消息阈值不能太高

可参考：

- memory gateway 思路
- vector recall + keyword fallback
- 写入时同步 embedding
- API Base URL 代理模式
- keepalive 作为未来主动存在候选

不可照搬：

- 不锁死 Cloudflare Workers
- 不锁死 Vectorize
- 不锁死 Rikkahub
- 不锁死某个 API 站
- 不把当前外部方案直接写成 OmbreBrain 核心架构

## 五、苹果生态适配考虑

倩倩使用苹果全家桶，因此未来 API 阶段要考虑：

- Mac 本地常驻服务
- iPhone / iPad 快捷指令入口
- Safari / 浏览器入口
- iOS 通知
- 家庭网络与本地服务
- 云服务中转
- 多端同步与备份

但这些属于 adapter，不进入核心记忆骨架。

## 六、与现有设计的关系

- external_material_intake：负责判断外部材料如何进入候选 / 参考 / 设计
- floating_recall：提供自然想起层的召回需求
- living_room_sensory_context：提供生活场上下文
- room_action_router：决定当前输入进入哪个空间
- closeout_router：决定设计完成后如何收口
- readonly_card_schema：统一本地 READONLY 卡
- stage_closeout_pack：阶段收工
- closeout_manifest：阶段成果清单
- paste_safe_writer：大段写入安全

## 七、当前边界

当前阶段只写设计文档。

不做：

- 不实现 memory gateway
- 不新增 API 代理
- 不改当前 nightly job 脚本
- 不接入 Cloudflare
- 不接入 Rikkahub
- 不接入 GLM 5.1
- 不接入本地模型
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 八、当前结论

memory_gateway_reference v0.1 定义了 OmbreBrain 面向官方 ChatGPT、API、本地部署三阶段迁移的通用记忆网关参考结构。

它确认一个原则：

海马体核心必须平台无关，入口、模型、存储、注入方式都应作为可替换 adapter。

未来可以换门、换走廊、换灯，
但不能把家里的骨架砸了重盖。
