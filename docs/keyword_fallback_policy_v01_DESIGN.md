# keyword_fallback_policy v0.1 设计草案

状态：设计草案
来源：2026-04-25 recall_layer_policy v0.1。短消息、暗号、人名、物件、日期等不能只依赖向量检索。
目标：定义 OmbreBrain 未来关键词兜底召回策略，确保明确锚点可以稳定命中，并与向量召回、规则触发、人工确认共同工作。

## 一、核心目标

keyword_fallback_policy 是关键词兜底召回策略。

它不是：

- 搜索引擎实现
- 向量数据库
- embedding 脚本
- API 网关
- 自动写入器
- 本地部署程序

它要解决的是：

- 短词被向量检索漏掉
- 暗号和物件无法靠语义稳定命中
- 人名、窗口名、文件名、commit hash 需要精确命中
- 施工状态和边界不能靠模糊召回
- 关键词命中后如何分层注入

一句话：

向量像闻味道，
关键词像认钥匙齿。

## 二、适用对象

关键词兜底适用于以下对象：

### 1. 人物名

- 倩倩
- 叶辰一
- 顾砚深
- 小起
- 卡卡

### 2. 暗号与纪念锚点

- 0412
- 9月29
- 4月8日
- 阳光明媚
- 日月戒指
- 镜像宇宙

### 3. 物件与场景锚点

- 戒指
- 小鬣狗
- 白色夜神
- 主卧长书桌
- 弱电箱
- 天台
- 云服务器

### 4. 项目与仓库锚点

- OmbreBrain
- PR #2
- nightly-job-v01-readonly
- Zeabur
- DeepSeek
- xiaowo-release
- OmbreBrain_DOCS_INDEX

### 5. 文件与设计名

- memory_gateway_reference
- recall_layer_policy
- keyword_fallback_policy
- stage_closeout_pack
- closeout_manifest
- repair_note_schema
- paste_safe_writer

### 6. commit / 版本 / 分支

- commit hash
- v0.1 / v0.2
- main
- nightly-job-v01-readonly

## 三、关键词类型

### 1. exact_keyword

必须精确匹配。

适合：

- commit hash
- 文件名
- 分支名
- PR 编号
- 日期编号

### 2. alias_keyword

同一对象的别名。

示例：

- 顾砚深 / 顾彦深
- 小窝2.0 / xiaowo 2.0
- 海马体 / OmbreBrain
- 晚间收口 / EVENING_STAGE_CLOSEOUT

### 3. phrase_keyword

短语锚点。

示例：

- 官方 ChatGPT → API → 本地部署
- 写入前防滑，出事后止血，修完后插旗
- 身体可以换，脑子不用重长

### 4. tag_keyword

标签命中。

适合：

- READONLY收口
- smoke test passed
- main未动
- Zeabur未动
- DeepSeek未调用

### 5. fuzzy_keyword

轻微错字、别字、空格差异。

示例：

- GLM5.1 / GLM 5.1
- API站 / API 站
- docs index / DOCS_INDEX

## 四、命中后的分层

关键词命中后不能一股脑塞入上下文。

推荐分层：

- must_include：身份、红线、当前施工边界、明确文件 / PR / 分支状态
- should_include：强相关设计、近期收口、直接相关 READONLY
- candidate：弱相关候选、外部参考材料
- blocked：私密不共享、权限不足、高风险未确认内容

## 五、短消息关键词策略

短消息如“好”“继续”“开工”“收口”本身信息量低。

处理原则：

- 先结合 recent_context
- 再看当前施工栈
- 再看关键词是否命中未完成对象
- 不把普通“好”误召成所有高权重记忆

示例：

如果当前刚完成 recall_layer_policy，用户说“继续”，优先召回 recall_layer_policy 当前收口状态和下一颗候选，而不是全局所有“继续”记忆。

## 六、别名规则

别名应服务于召回，不应篡改原文。

原则：

- 保留原写法
- 增加别名索引
- 不把未确认别名写成事实
- 人名别字需要谨慎，例如顾砚深 / 顾彦深可作为别名，但正式写法按当前确认版本

## 七、冲突处理

关键词命中多个对象时，按以下顺序判定：

1. 当前上下文是否刚提到
2. 是否属于当前施工对象
3. 是否高权重 / 已收口
4. 是否有明确文件名或版本号
5. 是否需要人工确认

不能因为关键词相同就乱接。

## 八、隐私与共享边界

关键词命中不等于可以共享。

未来叶辰一与顾砚深公屏 / 留言板只允许共享：

- 公共任务
- 施工状态
- 交接摘要
- 工具结果
- 低风险上下文

不得共享：

- 私密关系记忆
- 亲密内容
- 账号密钥
- 财务信息
- 高风险权限
- 任一方专属主库

## 九、与 recall_layer_policy 的关系

recall_layer_policy 定义召回层总策略。

keyword_fallback_policy 是其中关键词兜底的细则。

组合关系：

- recent_context 负责当前正在发生什么
- keyword_fallback 负责明确锚点
- rule_trigger 负责高优先级规则
- vector_recall 负责语义相似
- manual_confirm 负责中高风险停点

## 十、当前边界

当前阶段只写设计文档。

不做：

- 不实现搜索程序
- 不新增关键词库文件
- 不生成 embedding
- 不改 nightly job 脚本
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不接顾砚深公屏 MCP
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十一、当前结论

keyword_fallback_policy v0.1 定义了 OmbreBrain 未来关键词兜底召回策略。

它让短词、暗号、人名、物件、日期、窗口名、文件名和施工状态不会被向量检索漏掉。

不是所有门都靠闻味道找，
有些门必须认钥匙。
