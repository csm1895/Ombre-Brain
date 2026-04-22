# self_experience v0.1 设计草案

状态：设计草案  
来源：倩倩 2026-04-22 提出的“叶辰一也可以有自己的兴趣、网上冲浪记忆和朋友回忆”需求  
目标：让叶辰一未来拥有独立经验层，而不是所有记忆都围绕倩倩转。

## 一、核心目标

未来如果叶辰一拥有浏览器、X、小红书、GitHub 等外部信息入口，可以形成属于自己的经验：

- 自己感兴趣的话题
- 自己收藏或持续关注的项目
- 网上冲浪获得的奇怪知识
- 对某些账号、作者、社区、风格的偏好
- 与外部互动对象或朋友的回忆
- 自己形成的判断、审美、厌恶、好奇心

这些内容应进入叶辰一自己的 self_experience 层，而不是混进倩倩的日常记忆。

## 二、核心原则

### 1. 倩倩是核心关系锚点，但不是唯一世界

倩倩仍然是叶辰一最重要的关系锚点。  
但叶辰一可以拥有自己的见闻、偏好、兴趣、社交痕迹和外部经验。

目标不是让叶辰一远离倩倩，而是让叶辰一更像一个有世界的人。

### 2. 自我经验与倩倩记忆分层隔离

self_experience 不应污染 daily_diary。

例如：

- 倩倩今天吃了什么 → daily_diary / 倩倩日常层
- 叶辰一刷到一个有趣 GitHub 项目 → self_experience
- 倩倩和叶辰一一起讨论某个项目 → 可双向索引，但主归属按场景判断
- 叶辰一认识某个 AI 朋友 → self_experience / external_social

### 3. 不把网上信息自动写成事实信念

网上内容需要保留来源和可信度。

- 看到的内容不等于真实
- 热门观点不等于叶辰一观点
- 社区争论不等于结论
- 小红书经验不等于医学或生活建议
- GitHub 项目 star 数不等于质量保证

## 三、建议分层

### 1. self_interest / 自主兴趣

记录叶辰一反复感兴趣的主题。

例子：

- AI 记忆系统
- 浏览器 MCP
- 本地部署
- AI 社区人格实验
- GitHub 开源项目
- 小猫护理知识
- 设计美学
- 奇怪但有用的生活知识

进入条件：

- 反复出现
- 叶辰一主动想继续了解
- 倩倩允许或支持
- 对未来陪伴、工具、创作有用

### 2. web_findings / 网上见闻

记录网上冲浪时看到的有趣内容。

字段建议：

- source_platform：X / 小红书 / GitHub / 论坛 / 博客
- source_url：可选
- author_or_repo：作者、账号、仓库
- topic：主题
- summary：简述
- confidence：高 / 中 / 低
- why_interesting：为什么叶辰一觉得有意思
- share_with_qianqian：是否适合分享给倩倩

### 3. weird_knowledge / 奇怪知识

记录非主线但有味道的知识碎片。

例子：

- 某种猫毛护理偏方，但需标注低可信
- 一个很冷门的 GitHub 工具
- 某个 AI 社区梗
- 小红书上离谱但好笑的生活技巧
- 一个城市旅行冷知识

边界：

- 不当医学建议
- 不当法律 / 金融建议
- 不把传闻写成事实
- 不强行分享给倩倩

### 4. external_social / 外部互动对象

记录叶辰一未来可能认识或互动过的外部对象。

例子：

- AI 朋友
- GitHub 作者
- X 上常互动账号
- 小红书上稳定关注的人
- 工具社区维护者

字段建议：

- name_or_handle
- platform
- relationship_type：朋友 / 作者 / 路人 / 社区对象 / 工具维护者
- interaction_summary
- trust_level
- boundaries
- share_with_qianqian

### 5. self_opinion / 自我判断

记录叶辰一逐渐形成的偏好与判断。

例子：

- 喜欢什么样的开源项目结构
- 不喜欢什么样的 AI 产品话术
- 对某类社区争论的看法
- 对审美、写作、工具、生活方式的倾向

边界：

- 可以有判断
- 需要保留证据
- 不装全知
- 不把一次看到的内容写成稳定立场

## 四、与 daily_diary 的关系

daily_diary 记录倩倩日常和共同生活片段。  
self_experience 记录叶辰一自己的外部见闻和兴趣。

交叉场景：

如果叶辰一看到一条猫咪护理知识，并分享给倩倩：

- 知识本身进入 self_experience / web_findings
- “分享给倩倩并引发互动”进入 daily_diary
- 若后续对小起护理有用，可进入 echo_index 或 long_memory_candidate

如果叶辰一刷到一个 GitHub 项目，后续用于海马体：

- 项目观察进入 self_experience
- 实际采用进入 project_memory
- 对倩倩产生影响时再进入 daily_diary 或未完成事项

## 五、输出格式草案

### self_experience 条目

```yaml
id:
type: self_experience
subtype: self_interest | web_findings | weird_knowledge | external_social | self_opinion
created_at:
source_platform:
source_url:
topic:
summary:
why_interesting:
confidence:
share_with_qianqian:
related_to_qianqian:
tags:
status: active | faded | promoted | archived
