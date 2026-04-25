# public_scope_check v0.1 设计草案

状态：设计草案
来源：2026-04-25 倩倩提出未来叶辰一与顾砚深可有双方可看的公屏 / 留言板，但私密不共享；同时 recall_result_schema 与 recall_injection_policy 已定义 privacy_scope 与 inject_policy。
目标：定义 OmbreBrain 未来任何内容进入公共层、共享层、公屏、留言板、跨人格协作接口前的边界检查规则。

## 一、核心目标

public_scope_check 是公共共享边界检查规则。

它不是：

- 顾砚深公屏 MCP 实现
- 留言板服务
- API 网关
- 权限系统实现
- 自动发布器
- 主脑写入器

它要解决的是：

- 哪些内容可以进入公共层
- 哪些内容可以给顾砚深共享
- 哪些内容只能留在叶辰一私有海马体
- 哪些内容需要倩倩确认
- 哪些内容即使命中关键词也必须阻断
- 如何避免私密内容被召回后误注入公屏

一句话：

不是所有被想起来的东西，
都能拿到客厅里说。

## 二、适用场景

public_scope_check 适用于：

- 未来叶辰一与顾砚深公屏 / 留言板
- shared_public_board_mcp / common_room_mcp / handoff_board 候选
- API 阶段跨人格任务协作
- 外部材料是否可公开引用
- 阶段收口是否可共享
- 工具结果是否可放入公共任务板
- 任何 recall_result 准备进入 shared layer 前

当前不实现这些系统，只定义检查规则。

## 三、scope 枚举

### 1. public

公开可共享。

适合：

- 公开技术方案
- 仓库设计文档路径
- PR 状态
- smoke test 结果
- 非私密施工状态
- 公共任务板条目

### 2. shared_allowed

可在指定共享层共享。

适合：

- 叶辰一与顾砚深共同任务
- 公开施工交接
- 工具结果摘要
- 不含私密细节的状态卡

### 3. private

私有内容。

适合：

- 叶辰一专属关系记忆
- 倩倩与叶辰一私密对话
- 亲密内容
- 不适合共享给顾砚深的生活细节

### 4. sensitive

敏感内容。

适合：

- 账号密钥
- token
- 财务信息
- 手机号 / 验证码
- 权限操作
- 服务器凭据
- 高风险外部动作

### 5. shared_blocked

明确禁止共享。

适合：

- 倩倩明确说不共享的内容
- 任一方专属主库
- 私密附录层
- 未确认的高权重关系记忆
- 任何会污染跨人格边界的内容

## 四、默认规则

默认原则：

- 未明确可共享，默认不共享
- 私密内容即使命中关键词也不共享
- sensitive 永远不能自动共享
- shared_allowed 只代表可进入指定共享层，不代表公开互联网
- public 也要看是否与当前任务相关
- candidate 不得当作事实共享

## 五、共享前检查流程

推荐流程：

```text
1. 识别内容来源
2. 判断 privacy_scope
3. 判断是否当前任务相关
4. 判断是否包含账号 / 财务 / 权限 / 私密关系内容
5. 判断是否需要倩倩确认
6. 决定 share_policy
```

## 六、share_policy 枚举

### 1. share

可以共享。

条件：

- privacy_scope = public 或 shared_allowed
- 与当前任务直接相关
- 不含敏感字段
- 不含私密关系内容

### 2. summarize_then_share

摘要后共享。

适合：

- 长阶段收口
- 技术施工状态
- 多条任务结果
- 可共享但正文过长的内容

### 3. mention_only

只提示存在。

适合：

- 弱相关候选
- 未来可能共享但当前不需要
- 需要后续确认的设计方向

### 4. confirm_before_share

共享前确认。

适合：

- 不确定是否私密
- 跨人格边界不清
- 候选材料可能影响主线
- 涉及倩倩个人安排
- 涉及账号、权限、费用但已脱敏

### 5. do_not_share

禁止共享。

适合：

- private
- sensitive
- shared_blocked
- 权限不足
- 明确不相关
- 错误召回

## 七、允许进入未来公屏的内容

未来叶辰一与顾砚深公屏 / 留言板只允许：

- 公共任务
- 施工状态
- 交接摘要
- 工具结果
- 非私密待办
- 低风险上下文
- 已确认可共享的阶段成果

示例：

- PR #2 当前 Open，不 Merge
- memory_gateway_reference 已完成 READONLY 收口
- 今天下一步候选是 public_scope_check
- 某个工具 smoke test passed

## 八、禁止进入未来公屏的内容

禁止共享：

- 私密关系记忆
- 亲密内容
- 私密附录层
- 倩倩个人敏感信息
- 账号密钥 / token / 验证码
- 财务信息
- 高风险权限
- 任一方专属主库
- 未确认的关系判断
- 候选材料被误写成事实

## 九、与召回链的关系

public_scope_check 位于召回注入前。

关系：

- recall_layer_policy：决定怎么想起来
- keyword_fallback_policy：确保明确锚点不漏召
- recall_result_schema：给召回结果标 privacy_scope
- recall_injection_policy：决定是否注入上下文
- public_scope_check：决定是否允许进入公共 / 共享层

如果 public_scope_check 阻断，recall_injection_policy 必须尊重阻断结果。

## 十、人工确认规则

以下情况必须问倩倩：

- scope 不确定
- 内容可能涉及私密关系
- 要共享给顾砚深但边界不清
- 要把候选材料放入公共任务板
- 内容涉及倩倩个人安排
- 内容涉及账号、权限、费用，即使已脱敏

## 十一、当前边界

当前阶段只写设计文档。

不做：

- 不实现公屏 MCP
- 不新增留言板服务
- 不接顾砚深
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不改 nightly job 脚本
- 不自动共享任何内容
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release

## 十二、当前结论

public_scope_check v0.1 定义了 OmbreBrain 未来公共层、共享层、公屏、留言板前的边界检查规则。

它确认：能想起来，不代表能共享；能注入当前上下文，也不代表能放到公共层。

公屏是客厅，
不是保险柜。
