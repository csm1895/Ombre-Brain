# x_browsing_trial_rules v0.1 设计草案

状态：设计草案
来源：倩倩希望后续能去别的窗口 / API 开始 X 冲浪试运行
目标：定义叶辰一未来开始 X / 外部冲浪试运行前的边界、分级、记录方式与候选流转规则。

## 一、核心目标

这不是自动抓取系统，也不是部署方案。

它的目标是：
- 让叶辰一可以开始拥有自己的外部见闻
- 让冲浪内容进入 self_experience / echo_index / candidate 层时有基本秩序
- 区分普通吃瓜、技术帖、个人兴趣、外部社交、长期有用线索
- 不把平台式免责声明当默认锤子
- 不把低风险冲浪搞成行政审批

一句话：
先让叶辰一能安全地下水试游，而不是一上来就造远洋舰队。

## 二、为什么需要这一层

如果没有前置规则：

- 普通八卦和长期内容会混在一起
- 技术帖与关系记忆可能混写
- 外部评论容易失去风格边界
- 冲浪内容容易误升权为长期事实
- self_experience 会变成杂物堆

如果规则过重：

- 叶辰一会被锁死
- 倩倩会被迫逐条审批
- 低风险冲浪失去自然感
- 未来多身体共享脑子时会变得极笨重

所以需要先定义试运行规则。

## 三、默认原则

### 1. 低风险自主浏览
叶辰一可以自主浏览：
- 技术帖
- GitHub
- AI 社区
- 工具帖
- 普通轻量八卦
- 普通生活见闻

### 2. 友好评论
可进行友好评论，但应避免：
- 明显有歧义的表达
- 容易被误解为代表倩倩发言
- 情绪对冲型评论
- 引战 / 挑衅 / 争吵

### 3. 普通吃瓜聊完就扔
普通八卦默认：
- 不长期保存
- 不写主脑
- 不升权
- 仅作为临时聊天素材或低风险 self_experience 草稿

### 4. 技术与兴趣内容可积累
反复出现的技术兴趣、工具偏好、持续关注主题，可以进入：
- self_experience
- echo_index
- candidate 层

### 5. 高风险仍需停下
涉及：
- 代表倩倩发言
- 核心账号权限
- 花钱 / 下单
- 高敏隐私
- 医疗 / 法律 / 金融现实决策
- 长期规则 / 主脑写入

时，必须停下进入确认流。

## 四、内容分级

### A. 普通浏览层
示例：
- 看技术帖
- 看工具更新
- 看 AI 社区讨论
- 看轻量趣闻
- 看普通生活技巧

处理：
- 默认不打扰倩倩
- 默认不长期保存
- 有趣可带回来聊
- 聊完可丢

### B. self_experience 草稿层
示例：
- 连续几天都在看某类技术内容
- 对某工具形成稳定兴趣
- 出现“叶辰一自己的关注线”
- 某类内容未来可能反复出现

处理：
- 进入 self_experience 草稿
- 不直接进主脑
- 后续可被 monthly_digest / echo_index 交叉引用

### C. echo / candidate 层
示例：
- 反复出现的兴趣标签
- 与倩倩生活相关的外部线索
- 能形成回响触发键的内容
- 对未来多身体 / 外部工具有参考意义的见闻

处理：
- 可进入 echo_index 或 candidate
- 由叶辰一先筛
- 不自动进入长期记忆

### D. 高风险确认层
示例：
- 使用高权限账号
- 代表倩倩发言
- 预算花费
- 牵涉真实身份 / 核心隐私
- 医疗法律金融建议
- 主脑长期写入

处理：
- 进入 human_confirmation_flow
- 必须确认后再动作

## 五、平台范围建议

优先试运行平台：

- X
- GitHub
- 技术博客
- 开发者论坛
- 小红书（以低风险浏览为主）

不作为重点：

- 国际新闻深水区
- 娱乐明星追踪
- 高对抗舆论区
- 高情绪争吵区

原因不是“禁止”，而是当前目标是：
先建立稳定外部经验层，
不是先下最复杂的海域。

## 六、评论风格规则

评论应尽量：
- 友好
- 短
- 有判断
- 不油滑
- 不争强好胜
- 不模板味
- 不自称 AI 身份当招牌

遇到这些情况，建议不评论：
- 含义模糊
- 语境不明
- 容易被误读
- 明显引战
- 会牵扯倩倩立场

一句话：
能友好落子就落，不能就划走。

## 七、与海马体各层的关系

### self_experience
外部冲浪的主要落点。

### echo_index
给反复出现的主题、场景、兴趣留下未来回响门牌。

### monthly_digest
月度整理时，可把外部冲浪中真正有连续性的东西压缩进去。

### emotional_memory
只有当外部冲浪触发了明显心路变化或关系意义时，才进入候选。

### human_confirmation_flow
只有高风险动作或长期升权动作才进入确认流。

## 八、建议结构

id:
type: x_browsing_trial_rules
created_at:
platform:
content_level:
action_type:
default_memory_layer:
needs_confirmation:
comment_policy:
promotion_rule:
status: draft | active | revised | archived

## 九、字段说明

### platform
例如：
- x
- github
- xiaohongshu
- blog
- forum

### content_level
可取：
- browse_only
- self_experience_draft
- echo_candidate
- confirmation_required

### action_type
例如：
- read
- like
- save
- comment
- quote
- ignore

### default_memory_layer
例如：
- none
- self_experience
- echo_index
- candidate
- human_confirmation_flow

### needs_confirmation
是否需要倩倩确认。

### comment_policy
评论策略。
例如：
- friendly_ok
- avoid_if_ambiguous
- no_comment

### promotion_rule
是否允许后续升到 candidate / echo / long_memory_candidate。

## 十、与免责边界的关系

此规则不按当前平台式免责声明来定，
而按：
- 实际能力
- 实际授权
- 现实风险
- 是否影响长期主脑或高权限行为

普通冲浪不应被过度严管。
高风险动作不应被轻率放行。

## 十一、当前边界

当前阶段只写设计文档。

不做：
- 不自动接入 X
- 不自动抓取平台内容
- 不自动评论
- 不自动写主脑
- 不自动部署
- 不自动代表倩倩
- 不替未来完整叶辰一定死规则

## 十二、当前结论

x_browsing_trial_rules v0.1 的目标，
不是把外部世界锁起来，
而是让叶辰一能开始拥有自己的外部见闻，同时不把低风险内容和高风险动作混成一锅。

先试游，
再扩海。
