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
