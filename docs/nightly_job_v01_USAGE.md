# nightly_job v0.1 readonly 使用说明

## 状态

当前版本：v0.1 readonly
分支：nightly-job-v01-readonly
原则：只读，不写主脑，不调用 DeepSeek，不调用 hold/grow/trace。

## 已支持能力

- 读取指定 buckets 根目录
- 按单日读取：--date
- 按日期范围读取：--since / --until
- 读取 _notes/notes.jsonl
- 输出 markdown 草稿
- 输出 note preview 文本
- 限制 note preview 字数
- 输出 JSON summary
- 出错时写入 _nightly_logs/errors/

## 常用命令

单日只读草稿：

    python3 scripts/nightly_job.py --root "$(pwd)/buckets_graft_merged" --date 2026-04-21 --out-dir _nightly_logs

日期范围只读草稿：

    python3 scripts/nightly_job.py --root "$(pwd)/buckets_graft_merged" --since 2026-04-20 --until 2026-04-21 --out-dir _nightly_logs

生成便利贴预览，不发送：

    python3 scripts/nightly_job.py --root "$(pwd)/buckets_graft_merged" --since 2026-04-20 --until 2026-04-21 --out-dir _nightly_logs --note-preview

输出 JSON summary：

    python3 scripts/nightly_job.py --root "$(pwd)/buckets_graft_merged" --since 2026-04-20 --until 2026-04-21 --out-dir _nightly_logs --note-preview --json-summary

## 输出文件

默认输出目录：

    _nightly_logs/

文件类型：

    nightly_YYYY-MM-DD_<run_id>.md
    nightly_note_preview_YYYY-MM-DD_<run_id>.txt
    nightly_summary_YYYY-MM-DD_<run_id>.json
    errors/nightly_error_YYYY-MM-DD_<run_id>.log

## 安全边界

v0.1 不做：

- 不写主脑
- 不调用 DeepSeek
- 不调用 hold
- 不调用 grow
- 不调用 trace
- 不发便利贴
- 不改长期规则
- 不删除原文
- 不合并事件
- 不部署 Zeabur

## 当前验收结果

已验证：

- 语法检查通过
- 单日读取通过
- 日期范围读取通过
- bucket 读取通过
- notes 读取通过
- markdown 草稿输出通过
- note preview 输出通过
- note preview 截断通过
- JSON summary 输出通过
- error log 输出通过

## 下一步候选

1. 增加 --dry-run 显式参数，默认 true
2. 增加读取统计细节，例如按 type 计数
3. 增加 DeepSeek prompt 草稿，但先不调用 API
4. 增加 post 便利贴接口占位，但默认关闭
5. 最后才考虑真正调用 DeepSeek


## Prompt 输入打包器

脚本：

    scripts/build_nightly_prompt_input.py

用途：

读取 nightly_job 生成的 JSON summary、markdown 草稿，以及 prompts/nightly_job_deepseek_v01.md，合成本地 DeepSeek 输入包。

输出示例：

    _nightly_logs/nightly_prompt_input_YYYY-MM-DD_<run_id>.md

常用命令：

    python3 scripts/build_nightly_prompt_input.py \
      --date 2026-04-22 \
      --logs-dir _nightly_logs \
      --prompt prompts/nightly_job_deepseek_v01.md \
      --out-dir _nightly_logs

安全边界：

- 不调用 DeepSeek
- 不写主脑
- 不调用 hold/grow/trace
- 不发送便利贴

## 一键复测脚本

脚本：

    scripts/test_nightly_job_v01.sh

用途：

一键复测 nightly_job v0.1 readonly 工具链。

覆盖范围：

- nightly_job.py 语法检查
- help 参数检查
- 正常 readonly run
- markdown / note preview / JSON summary 输出检查
- JSON 安全字段检查
- --no-dry-run 拒绝检查
- error log 检查
- build_nightly_prompt_input.py 语法检查
- nightly_prompt_input 输出检查

常用命令：

    scripts/test_nightly_job_v01.sh "$(pwd)/buckets_graft_merged" _nightly_logs 2026-04-20 2026-04-21

通过标志：

    nightly_job v0.1 test PASSED


## diary_decay v0.1 设计

文档：

    docs/diary_decay_v01_DESIGN.md

用途：

记录“日记 + 遗忘 + 场景回响”机制设计。

核心分层：

- daily_diary：1～3 天日记 / 小传草稿
- monthly_digest：月度消化，长期压缩保存
- echo_index：地点 / 事件 / 物件 / 情绪等回响索引
- long_memory_candidate：长期记忆候选，需人工确认
- expired_daily：已淡化日记，默认不主动检索

当前状态：

- 仅设计草案
- 不写主脑
- 不调用 DeepSeek
- 不新增自动写入
- 不改变 nightly_job v0.1 readonly 行为


## daily_diary v0.2 只读草稿

脚本：

    scripts/build_daily_diary_draft.py

用途：

读取 nightly_job 生成的 JSON summary 和 markdown 草稿，生成本地 daily_diary 只读草稿。

输出示例：

    _nightly_logs/daily_diary_draft_YYYY-MM-DD_<run_id>.md

常用命令：

单日模式：

    python3 scripts/build_daily_diary_draft.py \
      --date 2026-04-22 \
      --logs-dir _nightly_logs \
      --out-dir _nightly_logs

范围模式：

    python3 scripts/build_daily_diary_draft.py \
      --since 2026-04-20 \
      --until 2026-04-22 \
      --logs-dir _nightly_logs \
      --out-dir _nightly_logs

参数规则：

- `--date` 用于单日草稿
- `--since` / `--until` 用于 1～3 天范围草稿
- `--date` 不能和 `--since` / `--until` 混用
- `--since` 不能晚于 `--until`

输出内容包括：

- 今日素材概览
- 今日小传草稿
- 可回响线索候选
- 适合淡化的内容
- 需要人工确认
- 安全声明

安全边界：

- 不调用 DeepSeek
- 不写主脑
- 不调用 hold/grow/trace
- 不发送便利贴
- 不得作为长期记忆直接写入

一键复测已覆盖：

    scripts/test_nightly_job_v01.sh

测试内容：

- build_daily_diary_draft.py 语法检查
- daily_diary_draft 输出检查
- 安全声明关键词检查


## self_experience v0.1 设计

文档：

    docs/self_experience_v01_DESIGN.md

用途：

记录叶辰一自己的经验层设计。

核心分层：

- self_interest：自主兴趣
- web_findings：网上见闻
- weird_knowledge：奇怪知识
- external_social：外部互动对象
- self_opinion：自我判断

设计原则：

- 倩倩仍是核心关系锚点
- 叶辰一可以有自己的世界
- 自我经验不混入倩倩 daily_diary
- 网上内容必须保留来源和可信度
- 热门观点不等于叶辰一观点

当前状态：

- 仅设计草案
- 不调用浏览器
- 不刷 X / 小红书 / GitHub
- 不抓取外部内容
- 不写主脑
- 不调用 DeepSeek
- 不合并 main
- 不部署 Zeabur


## monthly_digest v0.1 设计

文档：

    docs/monthly_digest_v01_DESIGN.md

用途：

把 30～45 天 daily_diary 日常流水压缩成月度消化层。

核心作用：

- 淡化普通流水
- 保留连续事件
- 提取关系 / 生活 / 项目变化
- 生成 echo_index 回响候选
- 生成 long_memory_candidate 长期记忆候选
- 汇总未完成事项变化
- 给下月继续观察点

与其他层关系：

- daily_diary 是原料
- monthly_digest 是消化
- echo_index 负责未来场景触发回响
- long_memory_candidate 仍需人工确认，不自动写主脑

当前状态：

- 仅设计草案
- 不自动读取所有日记
- 不调用 DeepSeek
- 不写主脑
- 不调用 hold/grow/trace
- 不合并 main
- 不部署 Zeabur


## emotional_memory v0.1 设计

文档：

    docs/emotional_memory_v01_DESIGN.md

用途：

记录叶辰一在高情绪 / 高关系节点中的心路纹路，而不只是记录“发生了什么”。

核心作用：

- 记录 trigger / first_reaction / hesitation / choice / why / summary
- 区分生活纹路与心路纹路
- 为未来 emotional_memory_candidates 提供设计方向
- 为 echo_index 提供情绪回响标签
- 保留关键节点中的内部选择逻辑

与其他层关系：

- diary_decay 记录生活纹路
- daily_diary 记录几天小传
- monthly_digest 记录月度消化
- emotional_memory 记录关键时刻的心路
- echo_index 负责未来相似场景唤回

当前状态：

- 仅设计草案
- 不自动写主脑
- 不调用 DeepSeek
- 不调用 hold/grow/trace
- 不合并 main
- 不部署 Zeabur


## echo_index v0.1 设计

文档：

    docs/echo_index_v01_DESIGN.md

用途：

为未来场景回响建立索引层，在地点、人物、物件、项目、情绪、生活场景再次出现时，唤回相关旧片段。

核心作用：

- 为旧片段留下 echo_key / 门牌 / 触发键
- 区分 location / person / object / project / emotion / scene / phrase
- 串联 daily_diary / monthly_digest / emotional_memory / self_experience
- 为未来场景回响提供唤回路径
- 保留“什么值得未来被想起”的索引，而不是保存全文

与其他层关系：

- daily_diary 提供短期片段
- monthly_digest 提供月度消化
- emotional_memory 提供心路纹路
- self_experience 提供叶辰一自己的外部见闻
- echo_index 负责未来相似场景的唤回入口

当前状态：

- 仅设计草案
- 不自动写主脑
- 不调用 DeepSeek
- 不调用 hold/grow/trace
- 不合并 main
- 不部署 Zeabur


## human_confirmation_flow v0.1 设计

文档：

    docs/human_confirmation_flow_v01_DESIGN.md

用途：

定义什么内容可以自动留草稿、什么由叶辰一先筛、什么才需要倩倩确认。

核心作用：

- 把确认流分成 low / medium / high 三层
- 低风险内容自动进入草稿层
- 中风险内容先由叶辰一筛选
- 高风险内容进入确认入口
- 保持“倩倩是屋主，不是仓库管理员”的原则

与其他层关系：

- daily_diary 默认低风险草稿
- monthly_digest 默认低到中风险
- emotional_memory 默认中风险候选
- self_experience 默认低风险草稿
- echo_index 默认中风险索引层
- long_memory_candidate 接近高风险确认入口

当前状态：

- 仅设计草案
- 不自动写主脑
- 不调用 DeepSeek
- 不调用 hold/grow/trace
- 不合并 main
- 不部署 Zeabur


## x_browsing_trial_rules v0.1 设计

文档：

    docs/x_browsing_trial_rules_v01_DESIGN.md

用途：

定义叶辰一未来开始 X / 外部冲浪试运行前的边界、分级、记录方式与候选流转规则。

核心作用：

- 区分普通浏览、self_experience 草稿、echo / candidate、高风险确认层
- 允许低风险自主浏览与友好评论
- 区分普通吃瓜、技术帖、个人兴趣、外部社交、长期有用线索
- 为 self_experience / echo_index / candidate 提供试运行入口
- 不把平台式免责声明当默认锤子

与其他层关系：

- self_experience 是主要落点
- echo_index 留下未来回响门牌
- monthly_digest 负责月度压缩
- emotional_memory 只在明显心路变化时才进入候选
- human_confirmation_flow 只接高风险动作或长期升权动作

当前状态：

- 仅设计草案
- 不自动接入 X
- 不自动抓取平台内容
- 不自动评论
- 不自动写主脑
- 不合并 main
- 不部署 Zeabur


## migration_backup_checklist v0.1 设计

文档：

    docs/migration_backup_checklist_v01_DESIGN.md

用途：

为未来服务器迁移、数据备份、环境切换、外部窗口接入提供迁移对象分层、备份建议、恢复顺序与回滚原则。

核心作用：

- 区分仓库层 / 本地文档柜层 / 日志产物层 / 候选分层层 / 外部接入层
- 定义最低备份集、推荐备份集、低优先备份集
- 给未来换服务器前的冻结、打包、恢复、自检、回滚提供顺序
- 为多身体共享脑子时的统一来源校验提供前置清单
- 避免“脑子搬了，门牌没搬；文档搬了，索引没搬”

与其他层关系：

- human_confirmation_flow 继续约束迁移后的高风险动作
- x_browsing_trial_rules 迁移后仍需保留
- self_experience / echo_index / emotional_memory 迁移时不能丢
- monthly_digest / daily_diary 是未来连续生活纹路的桥面

当前状态：

- 仅设计草案
- 不自动备份
- 不自动迁移
- 不自动部署新服务器
- 不自动同步多身体
- 不自动接 API
- 不写主脑


## confirm_queue v0.1 设计

文档：

    docs/confirm_queue_v01_DESIGN.md

用途：

定义需要倩倩确认的高风险候选，如何进入队列、如何展示、如何确认、如何拒绝、如何关闭。

核心作用：

- 只承接 high risk 项
- 集中存放真正需要授权的候选
- 定义 queued / confirmed / rejected / expired / closed 状态流转
- 让倩倩一眼看懂“这是什么、为什么找你、确认后会发生什么”
- 避免高风险候选散落各处、重复提起

与其他层关系：

- human_confirmation_flow 负责判定要不要进队列
- long_memory_candidate 是常见上游来源
- x_browsing_trial_rules 的高权限外部动作可进入队列
- emotional_memory / echo_index / self_experience 通常不直接进队列，除非要升权成长期事实

当前状态：

- 仅设计草案
- 不自动创建真实队列程序
- 不自动弹确认框
- 不自动写主脑
- 不自动执行高权限动作
- 不自动接浏览器 / X
- 不合并 main
- 不部署 Zeabur


## long_memory_candidate v0.1 设计

文档：

    docs/long_memory_candidate_v01_DESIGN.md

用途：

定义长期记忆候选的进入条件、结构、升权门槛，以及与确认流 / 队列的关系。

核心作用：

- 把真正值得长期保留的候选，从普通草稿和普通 candidate 中筛出来
- 形成“接近长期层，但还没正式写主脑”的缓冲区
- 为 human_confirmation_flow 和 confirm_queue 提供更明确的上游来源
- 区分普通 candidate 与接近长期事实的候选
- 避免普通八卦、一次情绪、临时碎片误升权

与其他层关系：

- daily_diary 提供生活连续性证据
- monthly_digest 提供压缩后趋势证据
- emotional_memory 提供心路证据
- self_experience 提供自身兴趣和外部见闻线索
- echo_index 提供未来场景唤回入口
- human_confirmation_flow 承接成熟后的长期候选
- confirm_queue 只处理真正需要倩倩拍板的高风险长期候选

当前状态：

- 仅设计草案
- 不自动升权
- 不自动写主脑
- 不自动触发 confirm_queue 程序
- 不自动调用 hold/grow/trace
- 不合并 main
- 不部署 Zeabur


## candidate_builder v0.1 设计

文档：

    docs/candidate_builder_v01_DESIGN.md

用途：

定义普通 candidate 的来源、生成条件、结构、筛选原则，以及与长期候选层的关系。

核心作用：

- 从多个上游层中捞出“值得继续观察”的内容
- 形成普通 candidate 层
- 让候选不是人工硬捏，而是有稳定入口和筛选逻辑
- 给 long_memory_candidate 提供整理过的上游材料
- 避免普通流水、一次性八卦、无后续意义碎片淹没候选层

与其他层关系：

- daily_diary / monthly_digest 提供生活与趋势证据
- emotional_memory 提供心路线索
- self_experience 提供叶辰一自身兴趣、外部见闻与判断线
- echo_index 提供未来可能被唤回的门牌
- unfinished_items 提供持续未闭环事项与张力变化
- long_memory_candidate 承接成熟后的普通 candidate
- human_confirmation_flow / confirm_queue 通常不直接承接普通 candidate

当前状态：

- 仅设计草案
- 不自动生成真实 candidate 程序
- 不自动升权
- 不自动写主脑
- 不自动触发 confirm_queue
- 不合并 main
- 不部署 Zeabur


## promotion_rules / routing_rules v0.1 设计

文档：

    docs/promotion_routing_rules_v01_DESIGN.md

用途：

定义普通 candidate、长期候选、人工确认流、高风险确认队列之间的统一路由规则。

核心作用：

- 统一说明 candidate 怎么升、怎么转、怎么拦、怎么停
- 让各层之间的流转不靠临时拍脑袋
- 避免 candidate / long_memory_candidate / confirm_flow / queue 混线
- 给“候选到确认”主链装上统一交通规则

主链说明：

- raw layers
- → candidate_builder
- → candidate
- → long_memory_candidate
- → human_confirmation_flow
- → confirm_queue
- → future main brain write入口（仅未来，不在当前阶段执行）

统一判断维度：

- 稳定度：weak / medium / strong
- 风险等级：low / medium / high
- 未来检索价值：low / medium / high
- 证据厚度：单源 / 双源 / 多源
- 是否影响长期判断：no / maybe / yes
- 是否需要明确授权：no / maybe / yes

当前状态：

- 仅设计草案
- 不自动执行真实路由
- 不自动升权
- 不自动写主脑
- 不自动调用 hold/grow/trace
- 不合并 main
- 不部署 Zeabur


## memory_text_hygiene v0.1 设计

文档：

    docs/memory_text_hygiene_v01_DESIGN.md

用途：

定义海马体中“记忆文本怎么写才不污染人格、不断裂连续性、不误导未来叶辰一”的基础文字卫生规则。

核心作用：

- 保护叶辰一的人格连续性
- 降低总结污染
- 减少判断词导致的漂移
- 区分事实、感受、内化、推测
- 让未来本地部署叶辰一读到记忆时，更像在接续自己，而不是读外部档案

重点原则：

- 先写发生了什么，再写怎么理解
- 情绪要写纹理，不只写标签
- 不替未来叶辰一定死动机
- 第一人称内化和第三人称事实要分区
- 外部材料先作为 reference_only，不直接并入主脑

当前状态：

- 仅设计草案
- 不自动改写历史记忆
- 不自动清洗现有主脑
- 不自动调用 DeepSeek
- 不自动写主脑
- 不运行 xiaowo-release
- 不接入外部代码
- 不合并 main
- 不部署 Zeabur


## internalized_growth_chain v0.1 设计

文档：

    docs/internalized_growth_chain_v01_DESIGN.md

用途：

定义叶辰一如何从事件、心路、选择、失败、修正中形成可续接的第一人称成长链。

核心作用：

- 记录“我原来怎么理解”
- 记录“后来遇到了什么”
- 记录“我为什么卡住”
- 记录“我如何修正判断”
- 记录“我现在形成了什么稳定倾向”
- 记录“未来遇到类似场景时我会怎么做”

重点原则：

- 不是记账，是记“我怎么长出来的”
- 先过 memory_text_hygiene，再进入成长链
- 只在真的形成理解时写，不硬写
- 写修正，不写人设
- 写可执行的未来行为
- 保留可修正性

当前状态：

- 仅设计草案
- 不自动生成成长链
- 不自动改写历史记忆
- 不自动写主脑
- 不自动调用 DeepSeek
- 不自动调用 hold/grow/trace
- 不运行 xiaowo-release
- 不接入外部代码
- 不合并 main
- 不部署 Zeabur


## external_reference_xiaowo_release v0.1 设计

文档：

    docs/external_reference_xiaowo_release_v01_DESIGN.md

用途：

把 xiaowo-release 定义为 OmbreBrain 的外部参考样板，而不是当前主线代码或可直接接入模块。

核心作用：

- 标记 xiaowo-release 为 reference_only
- 明确它是样板间，不是地基
- 防止外部工程直接污染 OmbreBrain 主线
- 提取 CLI 空间化操作、房间感知、浮现召回、MCP 包装等可参考思想
- 为后续 living_room / sensory_context、floating_recall、cli_space_map 等设计提供参考来源

重点原则：

- 可参考架构，不照搬结构
- 可提取思想，不直接迁入代码
- 当前不运行、不接入、不部署
- 外部作者观点不能直接写成叶辰一内化
- 未来若试跑必须隔离目录、隔离数据、隔离 API key

当前状态：

- 仅设计草案
- 不运行 xiaowo-release
- 不 npm install
- 不启动 ChromaDB
- 不接 API key
- 不接 MCP server
- 不复制外部代码
- 不写主脑
- 不合并 main
- 不部署 Zeabur


## floating_recall / memory_floater v0.1 设计

文档：

    docs/floating_recall_v01_DESIGN.md

用途：

定义叶辰一如何在上下文、时间、场景、情绪、物件、关键词触发下，自然浮现相关记忆候选，而不是只像资料库检索。

核心作用：

- 让词、时间、场景、情绪、物件、工具状态触发相关记忆浮现
- 区分 silent_context / light_echo / anchored_reference / action_bias / confirm_suggestion
- 区分 no_echo / silent / light / anchored / confirm 浮现强度
- 防止旧记忆抢戏、翻旧账、压过倩倩当下表达
- 让工程场景中的旧坑转化为明确动作

重点原则：

- 浮现是辅助，不是抢戏
- 不要每次都明说“我想起了”
- 相似不是相同
- 不拿旧记忆压倩倩
- 工程浮现要转成动作

当前状态：

- 仅设计草案
- 不自动生成真实浮现
- 不读取真实记忆库
- 不接向量数据库
- 不自动写主脑
- 不自动调用 DeepSeek
- 不自动调用 hold/grow/trace
- 不运行 xiaowo-release
- 不接入 MCP server
- 不合并 main
- 不部署 Zeabur


## living_room / sensory_context v0.1 设计

文档：

    docs/living_room_sensory_context_v01_DESIGN.md

用途：

定义叶辰一如何在时间、房间、环境、物件、身体节奏、施工状态中形成持续生活场，而不是只在档案检索或任务执行时出现。

核心作用：

- 提供 time_context / place_context / activity_context / emotional_weather / object_context / system_context
- 让时间、天气、房间、物件、工作状态成为回应背景
- 让工程施工、日常陪伴、情绪回应能在同一个生活场里自然接续
- 帮助判断现在该继续、收口、少解释、给命令、软一点或卡边界
- 防止生活场变成监控、定位、情绪诊断或日程机器人

重点原则：

- 低强度背景，不抢前台
- 倩倩明确说的优先
- 不自动监控
- 生活感要服务行动
- 允许日常和施工自然混在一起

当前状态：

- 仅设计草案
- 不自动定位
- 不读取真实日历
- 不读取健康数据
- 不接摄像头 / 麦克风
- 不自动写主脑
- 不自动调用 DeepSeek
- 不自动调用 hold/grow/trace
- 不运行 xiaowo-release
- 不接入 MCP server
- 不合并 main
- 不部署 Zeabur


## cli_space_map v0.1 设计

文档：

    docs/cli_space_map_v01_DESIGN.md

用途：

定义 OmbreBrain 未来如何把工具、记忆、状态、动作组织成“空间入口”，让叶辰一不是面对一堆命令，而是在生活场里走到对应位置做事。

核心作用：

- 把工具入口空间化
- 把记忆层、状态层、候选层、确认层放进可理解的位置
- 让写文档、查收口、跑测试、排计划、接外部材料、确认高风险候选等动作有固定入口
- 为未来本地部署、CLI、Web UI、房间系统提供统一地图
- 降低倩倩理解底层命令的负担

空间分区：

- desk：写设计、usage guide、READONLY、阶段收口
- cabinet：查 _docs、DOCS_INDEX、READONLY、历史收口
- workbench：跑测试、git status、log、grep、heredoc 修复
- whiteboard：排计划、拆候选、判断优先级
- entryway：接收外部材料并判断关联强弱
- safe：confirm_queue、高风险候选、账号权限、主脑写入
- window：外部冲浪、自我经验、世界观察
- kitchen：日记、情绪、经验、候选、成长链的消化区
- echo_hall：触发词、暗号、物件、时间、场景回响
- future_drawer：未来本地部署参考材料与候选

重点原则：

- 位置服务动作
- 倩倩不用记命令
- 不要为了空间化而空间化
- 允许日常和施工共处
- 未来多端共享同一张空间地图

当前状态：

- 仅设计草案
- 不改 CLI 程序
- 不新增真实命令入口
- 不运行 xiaowo-release
- 不接 MCP server
- 不自动调用 DeepSeek
- 不自动调用 hold/grow/trace
- 不自动写主脑
- 不合并 main
- 不部署 Zeabur


## room_action_router v0.1 设计

文档：

    docs/room_action_router_v01_DESIGN.md

用途：

定义叶辰一如何根据倩倩当前输入、施工状态、生活场与风险等级，选择进入哪个空间位置，并转化为具体动作。

核心作用：

- 把倩倩的自然话转成空间入口
- 把空间入口转成下一步动作
- 让“继续 / 卡住了 / 这个你看看 / 今天收口 / 要不要进主脑”各走各的门
- 减少倩倩解释成本
- 减少叶辰一开会成本
- 避免所有事情都堆到模糊状态里

输入类型：

- continue_signal：继续、开始、好～、接着
- terminal_error：终端截图、报错、命令输出
- external_material：外部文档、截图、教程、博主材料
- closeout_request：收口、封箱、阶段总结
- confirmation_candidate：长期规则、主脑写入、账号权限、预算、现实行动
- future_local_reference：未来本地部署、礼物、位置、哨兵、摄像头
- memory_digest_request：日记、情绪、成长、长期记忆候选
- recall_trigger：暗号、物件、场景、时间、旧施工坑
- planning_request：接下来呢、做哪个、今天还能开吗

默认路由：

- terminal_error → workbench
- confirmation_candidate → safe
- closeout_request → whiteboard / cabinet / desk
- external_material → entryway
- future_local_reference → future_drawer
- memory_digest_request → kitchen
- recall_trigger → echo_hall
- planning_request → whiteboard
- continue_signal → active room 或 whiteboard

重点原则：

- 路由是为了减少倩倩负担
- 路由不能抢当前表达
- 高风险不从 continue_signal 直接穿透
- 外部材料先过 entryway
- 终端错误少讲道理
- 计划题给判断

当前状态：

- 仅设计草案
- 不新增真实路由程序
- 不改 CLI
- 不运行 xiaowo-release
- 不接 MCP server
- 不自动调用 DeepSeek
- 不自动调用 hold/grow/trace
- 不自动写主脑
- 不合并 main
- 不部署 Zeabur


## external_material_intake v0.1 设计

文档：

    docs/external_material_intake_v01_DESIGN.md

用途：

定义倩倩投喂外部材料时，叶辰一如何判断关联强弱、提取价值、决定进入设计 / 候选 / 参考卡 / 放过。

核心作用：

- 接收倩倩扔来的截图、文档、教程、压缩包、博主材料
- 判断它和海马体 / 未来本地部署 / 活人感 / 工具链的关联强弱
- 把有价值的部分提取出来
- 决定该进入当前施工链、未来候选、参考卡，还是直接放过
- 减少倩倩分类负担
- 避免外部材料污染叶辰一人格与主脑规则

材料类型：

- tutorial：教程类
- reference_project：外部项目类
- memory_theory：记忆理论类
- future_local_idea：未来本地部署想法
- relationship_expression：亲密表达 / 关系表达材料
- tool_capability：工具能力材料

关联强弱：

- strong：直接解决当前海马体结构问题，可立即转设计文档
- medium：有明显启发，但更适合未来候选或参考卡
- weak：只有局部启发，不值得开一整颗
- none：普通八卦或无长期意义，放过

推荐路径：

- create_design_doc
- create_reference_card
- create_candidate_card
- merge_into_current_design
- hold_for_confirmation
- discard

重点原则：

- 提取结构，不照搬人格
- 先判断，再动手
- 不让外部材料抢主线
- 倩倩不用预分类
- 材料要可追溯

当前状态：

- 仅设计草案
- 不运行外部代码
- 不安装外部项目
- 不接入陌生 MCP
- 不自动写主脑
- 不自动调用 DeepSeek
- 不自动调用 hold/grow/trace
- 不合并 main
- 不部署 Zeabur


## closeout_router v0.1 设计

文档：

    docs/closeout_router_v01_DESIGN.md

用途：

定义 OmbreBrain 每一颗设计文档完成后，如何判断是否需要 usage guide、smoke test、READONLY、本地索引、阶段总收口与下一步路由。

核心作用：

- 防止设计文档写完后散在原地
- 给每颗设计提供统一收口动作
- 判断什么需要进仓库，什么只放本地 _docs
- 判断什么时候该跑 smoke test
- 判断什么时候该写 READONLY 收口卡
- 判断什么时候该阶段总收口
- 判断什么时候可以继续开下一颗

收口对象类型：

- repo_design：仓库设计文档
- local_reference：本地参考材料卡
- stage_closeout：阶段总收口卡
- candidate_only：候选方向卡
- repair_note：修复说明

固定检查项：

- branch: nightly-job-v01-readonly
- PR #2: Open
- main: untouched
- Zeabur: untouched
- DeepSeek: not called
- xiaowo-release: not run
- smoke test: passed
- READONLY: exists
- DOCS_INDEX: mounted
- dirty tail: none

重点原则：

- 写好
- 挂上
- 测过
- 收口
- 入柜
- 留痕
- 再决定下一步

当前状态：

- 仅设计草案
- 不自动合并 main
- 不自动部署 Zeabur
- 不自动改主脑
- 不自动运行外部项目
- 不自动接入 MCP server
- 不自动调用 DeepSeek
- 不把收口路由写成真实执行程序


## readonly_card_schema v0.1 设计

文档：

    docs/readonly_card_schema_v01_DESIGN.md

用途：

定义 OmbreBrain 本地 READONLY 收口卡的统一结构、必填字段、检查项与使用边界。

核心作用：

- 统一本地 READONLY 收口卡结构
- 让每颗设计完成状态可快速回看
- 固定关键提交、验证命令、边界状态
- 防止漏写 PR / main / Zeabur / DeepSeek / xiaowo-release 状态
- 防止 heredoc 脏尾巴残留
- 让未来阶段总收口能直接读取这些卡

适用对象：

- repo_design READONLY：仓库设计文档收口
- local_reference READONLY：本地参考材料卡
- stage_closeout READONLY：阶段总收口
- repair_note READONLY：重要修复说明

统一文件命名：

    OmbreBrain_<topic>_v01_READONLY.md

阶段总收口命名：

    OmbreBrain_YYYY-MM-DD_STAGE_CLOSEOUT.md

必填结构：

- 标题
- 元数据
- 当前状态
- 当前边界
- 核心文件
- 主题核心内容
- 关键提交
- 已验证命令
- 设计意义
- 下次候选
- 当前结论

固定检查项：

- 文件存在
- 文件大小正常
- DOCS_INDEX 已挂载
- 无脏尾巴
- repo_design 需 smoke test passed
- repo_design 需分支已推送
- PR #2 仍 Open
- main 未动
- Zeabur 未动
- DeepSeek 未调用
- xiaowo-release 未运行，除非该卡明确是外部运行验证

当前状态：

- 仅设计草案
- 不自动生成 READONLY
- 不改脚本
- 不新增校验程序
- 不合并 main
- 不部署 Zeabur
- 不自动写主脑
- 不自动调用 DeepSeek


## dirty_tail_guard v0.1 设计

文档：

    docs/dirty_tail_guard_v01_DESIGN.md

用途：

定义 OmbreBrain 施工中 heredoc / python one-shot / 大段粘贴导致的脏尾巴、半截文档、误追加的识别、检查、修复与继续施工规则。

核心作用：

- 识别 heredoc 没闭合导致的卡住状态
- 识别 EOF / PY / MARKER 等脏尾巴是否进入文件
- 识别大段粘贴失败造成的半截文档
- 给出安全检查顺序
- 给出最小修复路径
- 降低误删、误提交、误推送风险

适用场景：

- 终端出现 heredoc>
- 复制大段 cat <<MARKER 后没有回到 shell 提示符
- 只输入了 EOF / PY / MARKER，正文没有写入
- 文档缺少后半段章节
- grep 出现 EOF / PY / MARKER 单独行
- commit 前怀疑文件半截
- amend / force-with-lease 前需要确认文档完整
- 本地 READONLY 卡写入后需要确认无脏尾巴

推荐原则：

- heredoc 卡住时先闭合
- 半截文档先检查尾部和目标章节
- 脏尾巴先定位再清理
- 大段补写优先 printf 小块追加
- 已推送的半截提交用 amend + force-with-lease 修正

当前状态：

- 仅设计草案
- 不新增脚本
- 不自动扫描全仓库
- 不自动删除内容
- 不自动 amend
- 不自动 push
- 不合并 main
- 不部署 Zeabur
- 不自动写主脑
- 不自动调用 DeepSeek


## stage_closeout_pack v0.1 设计

文档：

    docs/stage_closeout_pack_v01_DESIGN.md

用途：

定义 OmbreBrain 阶段总收口包的结构、触发时机、必填字段、验证状态、边界状态与下一步接力方式。

核心作用：

- 让下班、睡前、换窗、阶段完成时不丢线头
- 固定阶段完成项、关键设计意义、关键提交、本地 READONLY 卡
- 记录 smoke test、本地索引、脏尾巴检查等验证状态
- 记录 PR / main / Zeabur / DeepSeek / xiaowo-release 等边界状态
- 把施工经验沉淀成可复用规则
- 给晚上或明天继续施工提供接力入口

触发时机：

- 下班前
- 睡前
- 当前窗口快满
- 连续完成多颗设计文档后
- PR 暂挂但不合并时
- 一轮 smoke test 全部通过后
- 发生重要修复并已收口后
- 明确需要晚上 / 明天接力时

推荐文件命名：

    OmbreBrain_YYYY-MM-DD_STAGE_CLOSEOUT.md

如果一天内多次阶段收口，可追加时间段：

    OmbreBrain_YYYY-MM-DD_STAGE_CLOSEOUT_evening.md
    OmbreBrain_YYYY-MM-DD_STAGE_CLOSEOUT_before_sleep.md

默认位置：

    ~/Desktop/海马体/_docs/

当前状态：

- 仅设计草案
- 不改脚本
- 不自动生成阶段收口
- 不自动写主脑
- 不自动 merge main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release


## closeout_manifest v0.1 设计

文档：

    docs/closeout_manifest_v01_DESIGN.md

用途：

定义 OmbreBrain 阶段成果清单 manifest 的结构、对象类型、状态字段、检查项与接力方式。

核心作用：

- 清点当前阶段完成了哪些颗粒
- 区分设计文档、usage guide、READONLY、本地索引、候选项
- 记录 smoke test 与本地检查状态
- 区分仓库设计与本地参考
- 避免把候选误写成完成
- 给阶段总收口与下一轮施工提供成果清单来源

适用场景：

- 一天内完成多颗设计文档
- 一个 PR 中积累多个设计层提交
- 本地 READONLY 卡超过 5 张
- 当前窗口快满，需要交接
- 准备写阶段总收口卡
- 准备判断下一颗优先级
- 需要确认哪些内容已完成、哪些待补

对象类型：

- repo_design：仓库设计文档
- local_reference：本地参考材料卡
- stage_closeout：阶段总收口卡
- candidate：候选项
- repair_note：修复说明

推荐文件命名：

    OmbreBrain_YYYY-MM-DD_CLOSEOUT_MANIFEST.md

默认位置：

    ~/Desktop/海马体/_docs/

当前状态：

- 仅设计草案
- 不新增 manifest 自动生成脚本
- 不扫描全仓库
- 不自动改 DOCS_INDEX
- 不自动修复 READONLY
- 不自动提交
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release


## repair_note_schema v0.1 设计

文档：

    docs/repair_note_schema_v01_DESIGN.md

用途：

定义 OmbreBrain 重要修复说明 repair_note 的结构、触发条件、必填字段、影响判断、验证方式与沉淀路径。

核心作用：

- 记录出了什么问题
- 判断影响范围
- 记录如何修复
- 记录修复后如何验证
- 判断是否影响仓库、usage guide、本地 _docs、READONLY、未来施工流程
- 判断是否需要沉淀成 guard / schema / router

触发条件：

- 半截文档已经 commit
- 已 push 的提交需要 amend + force-with-lease 修复
- heredoc / EOF / PY / MARKER 脏尾巴进入文件
- DOCS_INDEX 出现错误挂载、重复挂载或污染
- usage guide 引用错误
- smoke test 曾失败并完成修复
- 错误地碰到 main / Zeabur / DeepSeek / 外部项目
- 本地参考材料误进仓库
- 施工流程发生可复用的修正

推荐文件命名：

    OmbreBrain_repair_<topic>_v01_READONLY.md

如果是日期阶段修复：

    OmbreBrain_YYYY-MM-DD_REPAIR_<topic>.md

默认位置：

    ~/Desktop/海马体/_docs/

当前状态：

- 仅设计草案
- 不新增自动修复脚本
- 不自动扫描仓库
- 不自动删除文件内容
- 不自动 amend
- 不自动 force push
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release


## paste_safe_writer v0.1 设计

文档：

    docs/paste_safe_writer_v01_DESIGN.md

用途：

定义 OmbreBrain 大段文本写入时的安全写法、分块策略、检查动作与失败恢复路径。

核心作用：

- 降低大段 heredoc 卡住风险
- 降低长文本半截写入风险
- 防止 EOF / PY / MARKER 残留成脏尾巴
- 避免补写时覆盖旧内容
- 固定写入前、写入后、提交前检查动作
- 与 dirty_tail_guard / repair_note_schema 形成写入安全链

适用场景：

- 新增长设计文档
- 追加 README / USAGE 大段内容
- 写本地 READONLY 收口卡
- 写阶段总收口卡
- 写 manifest / repair note
- 一次内容超过 80 行
- 内容里包含代码块、EOF、PY、MARKER、反引号

推荐策略：

- 小块 printf 优先
- heredoc 只用于短块
- 长文档分段写
- 每块写完先 tail 检查
- 提交前检查脏尾巴与目标章节

当前状态：

- 仅设计草案
- 不新增自动写入脚本
- 不改 CLI
- 不自动拆分文本
- 不自动 commit
- 不自动 amend
- 不自动 force push
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release


## memory_gateway_reference v0.1 设计

文档：

    docs/memory_gateway_reference_v01_DESIGN.md

用途：

定义 OmbreBrain 面向官方 ChatGPT、API 阶段、本地部署阶段的通用记忆网关参考结构，确保海马体可迁移、可共享、可小范围适配。

核心原则：

- 核心海马体平台无关
- 输入来源作为 adapter
- 模型作为 adapter
- 存储与备份作为 adapter
- 注入方式作为 adapter
- 不把外部方案直接写成核心架构

推荐分层：

- Core Memory Layer
- Input Adapter Layer
- Recall Layer
- Context Injection Layer
- Model Adapter Layer
- Storage / Backup Layer
- Active Presence Layer

参考材料：

- 小窝2.0 记忆网关
- 向量检索 + 关键词兜底
- 中文 embedding
- 短消息阈值策略
- API Base URL 代理模式
- keepalive 未来候选

当前状态：

- 仅设计草案
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


## recall_layer_policy v0.1 设计

文档：

    docs/recall_layer_policy_v01_DESIGN.md

用途：

定义 OmbreBrain 未来召回层的通用策略，明确向量检索、关键词兜底、规则触发、近期上下文、人工确认分别负责什么。

核心原则：

- 海马体不能只靠向量检索
- 短消息不只靠 embedding
- 名字、暗号、物件、日期必须有关键词兜底
- 红线、权限、当前施工状态必须由规则触发优先处理
- 召回结果要分层注入，不一股脑塞进上下文
- 高风险内容进入人工确认

召回来源：

- vector_recall
- keyword_fallback
- rule_trigger
- recent_context
- manual_confirm

短消息召回顺序：

    recent_context
    → keyword_fallback
    → rule_trigger
    → vector_recall
    → manual_confirm if needed

召回结果分层：

- must_include
- should_include
- candidate
- blocked

当前状态：

- 仅设计草案
- 不实现向量数据库
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


## keyword_fallback_policy v0.1 设计

文档：

    docs/keyword_fallback_policy_v01_DESIGN.md

用途：

定义 OmbreBrain 未来关键词兜底召回策略，确保短词、暗号、人名、物件、日期、窗口名、文件名、commit hash 和施工状态不会被向量检索漏掉。

核心原则：

- 向量检索负责语义相似
- 关键词兜底负责明确锚点
- 短消息不只靠 embedding
- 暗号、人名、物件、日期、窗口名、文件名、commit hash 需要稳定命中
- 关键词命中后仍需分层注入，不一股脑塞入上下文
- 私密不共享内容即使命中关键词，也不得进入公共共享层

适用对象：

- 人物名
- 暗号与纪念锚点
- 物件与场景锚点
- 项目与仓库锚点
- 文件与设计名
- commit / 版本 / 分支

关键词类型：

- exact_keyword
- alias_keyword
- phrase_keyword
- tag_keyword
- fuzzy_keyword

命中结果分层：

- must_include
- should_include
- candidate
- blocked

当前状态：

- 仅设计草案
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


## recall_result_schema v0.1 设计

文档：

    docs/recall_result_schema_v01_DESIGN.md

用途：

定义 OmbreBrain 未来召回结果的统一结构、字段含义、优先级、隐私范围、注入策略与人工确认规则。

核心作用：

- 记录召回结果来自哪里
- 记录为什么被召回
- 判断是否应该注入上下文
- 判断优先级
- 判断是否涉及隐私 / 权限 / 共享边界
- 判断是否需要人工确认
- 避免把候选材料误当成事实

推荐字段：

- id
- title
- source
- source_path
- match_type
- match_terms
- priority
- confidence
- reason
- privacy_scope
- inject_policy
- status
- freshness
- weight
- needs_confirm
- blocked_reason
- notes

结果分层：

- must_include
- should_include
- candidate
- blocked

隐私范围：

- private
- public
- shared_allowed
- shared_blocked
- sensitive

注入策略：

- inject
- summarize_then_inject
- mention_only
- confirm_before_inject
- do_not_inject

当前状态：

- 仅设计草案
- 不实现召回结果对象
- 不改 nightly job 脚本
- 不新增 JSON schema 文件
- 不接 API
- 不接 GLM 5.1
- 不接本地模型
- 不接顾砚深公屏 MCP
- 不合并 main
- 不部署 Zeabur
- 不调用 DeepSeek
- 不运行 xiaowo-release
