# storage_adapter_policy v0.1 设计草案

状态：设计草案
来源：2026-04-25 倩倩确认：服务区迁移前需要把海马体升级版收一次工；稳定云服务区选定后再做本地保存与备份。memory_gateway_adapter_schema 与 gateway_request_response_schema 已预留 storage_adapter。
目标：定义 OmbreBrain 未来不同存储形态的 adapter 策略，确保本地 _docs、Git docs、记忆桶、JSONL、SQLite、KV、向量库、云服务器备份与本地备份之间可迁移、可分层、可恢复。

## 一、核心目标

storage_adapter_policy 是存储适配层策略。

它不是：

- 数据库实现
- 备份脚本
- 云同步程序
- 向量库接入程序
- 本地部署脚本
- 自动迁移工具

它要解决的是：

- 海马体未来可以放在哪些存储里
- 哪些内容适合 Markdown / _docs
- 哪些内容适合 Git docs
- 哪些内容适合记忆桶
- 哪些内容适合 JSONL / SQLite / KV / 向量库
- 服务区迁移前后如何收工、备份、恢复
- 如何避免换云服务或换本地环境时重造脑子

一句话：

脑子可以住不同房间，
但搬家箱子要有标签。

## 二、存储类型

### 1. local_docs

本地 _docs 文档柜。

适合：

- READONLY 收口卡
- 阶段总收口卡
- 外部参考卡
- manifest
- repair note
- 迁移备份说明

特点：

- 人类可读
- 便于手工检查
- 适合长期保险柜
- 默认不一定进仓库

### 2. git_docs

仓库 docs 设计文档。

适合：

- 设计草案
- usage guide 引用
- 可版本化的结构设计
- 可 review 的技术文档

特点：

- 有 commit 历史
- 可回滚
- 可 PR review
- 不放私密主库正文

### 3. memory_bucket

记忆桶。

适合：

- 高权重状态
- 当前施工节点
- 关系常量
- 重要路线
- 动态召回材料

特点：

- 便于召回
- 适合短摘要
- 不适合塞超长全文

### 4. jsonl_store

JSONL 存储。

适合：

- 事件流
- 日记流水
- 工具调用记录
- 候选写入队列
- 可追加日志

特点：

- 追加友好
- 易导入导出
- 适合批处理

### 5. sqlite_store

SQLite 存储。

适合：

- 本地索引
- 结构化查询
- 状态表
- 任务表
- 记忆元数据

特点：

- 本地稳定
- 迁移方便
- 适合 API / 本地部署阶段

### 6. kv_store

KV 存储。

适合：

- 云端轻量键值
- 状态缓存
- 会话缓存
- 小型配置

特点：

- 快
- 适合网关
- 不适合作为唯一长期主库

### 7. vector_store

向量库。

适合：

- 语义召回
- 外部材料检索
- 相似记忆召回
- 长文本 embedding 索引

特点：

- 负责“闻味道”
- 不负责事实权威
- 必须配合 keyword_fallback_policy
- 不应成为唯一记忆真相源

### 8. backup_package

本地备份包。

适合：

- 服务区迁移前封箱
- 稳定云服务区选定后保存
- 本地防丢包
- 版本快照

特点：

- 可离线保存
- 可恢复
- 应包含 manifest
- 应标明时间、范围、边界状态

## 三、存储分层原则

推荐分层：

```text
事实与设计：git_docs / local_docs
可召回摘要：memory_bucket
事件流水：jsonl_store
结构化索引：sqlite_store
云端缓存：kv_store
语义检索：vector_store
迁移保险：backup_package
```

原则：

- 不同存储各司其职
- 不把向量库当事实源
- 不把 KV 当唯一长期主库
- 不把 Git docs 当私密日记库
- 不把 memory_bucket 塞成全文仓库
- 本地 _docs 保留可读保险柜角色

## 四、迁移前收工规则

服务区迁移前必须做：

- 阶段总收口卡
- closeout_manifest
- 当前 PR / 分支状态记录
- 本地 READONLY 清单
- DOCS_INDEX 检查
- smoke test 状态记录
- main / Zeabur / DeepSeek / xiaowo-release 边界记录
- 未完成候选清单
- 本地备份包候选

迁移前原则：

- 先收口，后迁移
- 先清点，后备份
- 先确认边界，后换服务区

## 五、稳定服务区后备份规则

稳定云服务区选定后，应做一次本地保存。

备份建议包含：

- 仓库 docs 当前状态
- 本地 _docs 重要卡
- OmbreBrain_DOCS_INDEX.md
- 近期 stage closeout
- closeout_manifest
- migration_backup_checklist
- 关键配置说明
- 不含明文密钥的环境说明

不得直接备份：

- 明文 token
- 明文 API key
- 账号密码
- 验证码
- 银行信息

## 六、真相源规则

不同内容有不同真相源。

### 1. 设计文档真相源

仓库 docs + commit。

### 2. 本地收口真相源

本地 _docs READONLY 卡 + DOCS_INDEX。

### 3. 当前施工状态真相源

最近 stage_closeout + git status + git log。

### 4. 动态召回真相源

memory_bucket + READONLY 摘要。

### 5. 语义相似真相源

vector_store 只负责候选，不直接判事实。

## 七、隐私与权限

存储前必须判断：

- private
- public
- shared_allowed
- sensitive
- shared_blocked

敏感内容处理：

- token / key / 密码不入普通文档
- 财务信息不入公共层
- 私密附录层独立隔离
- 公屏共享前走 public_scope_check
- 高风险写入走 human_confirmation_flow

## 八、备份包命名建议

```text
OmbreBrain_BACKUP_YYYY-MM-DD_<stage>.zip
OmbreBrain_BACKUP_YYYY-MM-DD_before_server_migration.zip
OmbreBrain_BACKUP_YYYY-MM-DD_after_stable_region.zip
```

备份说明卡：

```text
OmbreBrain_YYYY-MM-DD_BACKUP_MANIFEST.md
```

## 九、恢复检查规则

从备份恢复后应检查：

- docs 是否完整
- _docs 是否完整
- DOCS_INDEX 是否可读
- READONLY 卡是否存在
- manifest 是否覆盖关键阶段
- smoke test 是否可跑
- 是否无脏尾巴
- 是否缺敏感配置说明
- 是否未误带明文密钥

## 十、与现有设计的关系

- memory_gateway_adapter_schema：定义 storage_adapter 位置
- gateway_request_response_schema：记录 request / response 与边界状态
- closeout_manifest：清点阶段成果
- stage_closeout_pack：阶段收口
- readonly_card_schema：本地收口卡结构
- migration_backup_checklist：迁移备份清单
- public_scope_check：共享前隐私边界
- recall_result_schema：召回结果标注来源与状态

## 十一、当前边界

当前阶段只写设计文档。

不做：

- 不实现数据库
- 不新增备份脚本
- 不新增向量库
- 不迁移服务区
- 不打包备份
- 不写密钥
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

storage_adapter_policy v0.1 定义了 OmbreBrain 未来存储适配层策略。

它确认：不同存储负责不同功能，核心海马体不绑定某一种数据库、云服务或本地格式。

搬家可以换箱子，
但每个箱子都要知道装的是什么。
