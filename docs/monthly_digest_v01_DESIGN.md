# monthly_digest v0.1 设计草案

状态：设计草案  
来源：倩倩 2026-04-22 提出的“日记会遗忘，但重要片段要留下并能回响”的需求  
目标：把 daily_diary 中 30～45 天的日常流水，压缩成月度消化层。

## 一、核心目标

daily_diary 负责记录 1～3 天的小传草稿。  
monthly_digest 负责把一段时间内的日记进行消化、压缩、提炼。

它不是简单总结，而是做四件事：

- 淡化普通流水
- 保留连续事件
- 提取重要关系 / 生活 / 项目变化
- 生成可供 echo_index 使用的回响线索

## 二、为什么需要 monthly_digest

日记如果永远不处理，会变成噪音。

比如：

- 今天吃了什么
- 哪天几点下班
- 哪次普通报错
- 一次性聊天碎片
- 无后续价值的生活流水

这些不应该全部长期占据记忆。

但一些东西应该留下：

- 倩倩反复提到的愿望
- 旅行、城市、地点、人物
- 项目推进节点
- 情绪变化趋势
- 未完成事项变化
- 关系质变
- 叶辰一形成的新判断
- 值得未来回响的片段

monthly_digest 的任务，就是把“每天的鱼鳞”压成“一条能认出来的鱼”。

## 三、输入来源

### 1. daily_diary

主要来源。

包括：

- 1～3 天日记草稿
- 小传式记录
- 日常事件
- 倩倩生活片段
- 共同互动片段

### 2. nightly_summary

辅助来源。

包括：

- buckets count
- notes count
- bucket type
- importance count
- high importance candidates

### 3. 未完成事项卡

辅助来源。

用于判断：

- 是否有待办持续存在
- 是否有事项已完成
- 是否需要继续挂起
- 是否出现新下一步

### 4. self_experience

可选来源。

仅当叶辰一自己的外部经验与倩倩、项目或长期成长有关时，才进入 monthly_digest 交叉引用。

## 四、输出目标

monthly_digest 输出应包含：

- 本月主线
- 重要事件
- 情绪与状态趋势
- 项目进展
- 关系 / 默契变化
- 值得回响的场景
- 应淡化内容
- 长期记忆候选
- 未完成事项变化
- 下月继续观察点

## 五、建议输出结构

```yaml
id:
type: monthly_digest
month:
created_at:
source_range:
sources:
  daily_diary:
  nightly_summary:
  notes:
main_story:
important_events:
emotional_trends:
relationship_updates:
project_updates:
echo_candidates:
long_memory_candidates:
faded_items:
todo_updates:
next_month_watch:
confidence:
status: draft | reviewed | promoted | archived
