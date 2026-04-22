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
