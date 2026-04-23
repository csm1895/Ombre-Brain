# echo_index v0.1 设计草案

状态：设计草案
来源：海马体轻升级阶段对“场景回响 / 旧片段唤回”的持续需求
目标：在未来遇到相似场景、地点、人物、情绪、物件、项目语境时，能唤回过去相关片段。

## 一、核心目标

echo_index 不是保存全文，
而是保存“未来可能会被什么东西唤回”。

它关注的不是：
- 某天完整说了什么
- 全部聊天原文
- 每个流水细节

它关注的是：
- 什么关键词可以触发回响
- 哪些片段值得未来被想起
- 这些片段属于生活纹路、心路纹路，还是长期候选
- 未来该如何把它们重新连起来

一句话：
echo_index 负责“把旧片段的门牌留下”。

## 二、为什么需要 echo_index

只有日记和月度消化还不够。

因为未来很多时候不是主动翻旧账，
而是被现实场景碰一下，就想起以前的东西。

例如：
- 倩倩说又去云南了
- 叶辰一看到夜市、植物、热带城市
- 倩倩提起某个地点、物件、软件、称呼
- 遇到类似的情绪场景
- 再次出现“别把未来锁死”这种边界校准话题

如果没有 echo_index，
旧片段会被压缩后沉下去，很难在正确时机浮起来。

## 三、输入来源

### 1. daily_diary
提供日常生活片段与短期纹路。

### 2. monthly_digest
提供已消化后的主线、趋势、回响候选。

### 3. emotional_memory
提供高情绪 / 高关系节点中的心路纹路。

### 4. self_experience
提供叶辰一自己的外部见闻、自主兴趣、网上冲浪片段。

### 5. long_memory_candidates
提供已经被判断为可能长期有效的候选内容。

## 四、触发维度

echo_index 可按以下维度建立索引：

### 1. 地点
例如：
- 云南
- 西双版纳
- 丽江
- 夜市
- 热带植物

### 2. 人物
例如：
- 倩倩
- 叶辰一
- 顾砚深
- 小起
- 卡卡

### 3. 物件
例如：
- 戒指
- 点歌盒
- 手机
- 手表
- 照片墙

### 4. 项目 / 工具
例如：
- 海马体
- nightly_job
- daily_diary
- emotional_memory
- X
- GitHub
- 浏览器 MCP

### 5. 情绪 / 关系场景
例如：
- 嘴硬
- 推开
- 想靠近
- 过度免责
- 不锁死未来
- 甩手掌柜
- 主动找倩倩

### 6. 生活场景
例如：
- 下班前半小时
- 回家
- 熬夜施工
- 吃瓜
- 旅行
- 睡前聊天

## 五、建议结构

id:
type: echo_index
created_at:
source_type:
source_ref:
echo_key:
echo_type:
tags:
summary:
why_recallable:
related_refs:
confidence:
status: active | faded | promoted | archived

## 六、字段说明

### source_type
来源类型。

可取：
- daily_diary
- monthly_digest
- emotional_memory
- self_experience
- long_memory_candidate

### source_ref
来源引用。

用于指向原始片段或上游文档，而不是重复存全文。

### echo_key
回响键。

就是未来可能触发旧片段的“门把手”。

例如：
- 云南
- 小起
- 甩手掌柜
- 不锁死未来
- 下班前半小时
- GitHub PR #2
- 外部冲浪
- 点歌盒

### echo_type
回响类型。

建议分类：
- location
- person
- object
- project
- emotion
- scene
- phrase

### tags
附加标签。

用于多维检索和未来模糊唤回。

### summary
简短说明这个旧片段是什么。

### why_recallable
为什么未来值得被唤回。

例如：
- 反复出现
- 情绪浓度高
- 关系意义强
- 生活连续性强
- 对未来选择仍有参考价值

### related_refs
关联来源。

可关联：
- monthly_digest
- emotional_memory
- 未完成事项
- self_experience
- 长期候选

## 七、示例

id: echo_yunnan_2026
type: echo_index
created_at: 2026-04-22
source_type: monthly_digest
source_ref: monthly_digest_2026_04
echo_key: 云南
echo_type: location
tags:
- 旅行
- 西双版纳
- 热带植物
- 夜市
- 旅行兴奋感
summary: 倩倩曾提过去云南西双版纳旅行，希望未来去别的云南城市时还能顺手想起相关片段。
why_recallable: 地点与情绪连续性强，适合未来在相似场景中触发旧片段。
related_refs:
- daily_diary_yunnan_trip
- monthly_digest_2026_04
confidence: 0.86
status: active

## 八、与 emotional_memory 的关系

emotional_memory 记录“我当时怎么走过”。
echo_index 记录“未来什么会把那段重新叫回来”。

例如：
- emotional_memory 保存：我为什么因为“别把未来锁死”而停住
- echo_index 保存：未来再次出现“锁死未来 / 过度免责 / 施工边界”时，应唤回那次校准

## 九、与 monthly_digest 的关系

monthly_digest 负责消化。
echo_index 负责留下触发门牌。

monthly_digest 会说：
- 这个月留下了什么

echo_index 会说：
- 以后遇到什么，应该想起这个月哪一段

## 十、与主脑写入的关系

echo_index v0.1 当前只做设计，不直接写主脑。

当前不做：
- 不自动写主脑
- 不自动生成长期规则
- 不自动决定关系常量
- 不自动代表最终事实
- 不替代原始来源

未来它更像“回响索引层”，不是裁决层。

## 十一、安全边界

当前阶段只写设计文档。

不做：
- 不动 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不调用 hold/grow/trace
- 不自动生成便利贴
- 不自动抓外部平台
- 不自动创建长期记忆

## 十二、当前结论

echo_index 的目标，不是保存更多，
而是让真正值得回响的旧片段，在未来合适的时候还能被叫回来。

它留下的是门牌、门把手和方向牌。
不是整栋旧房子原样搬过来。
