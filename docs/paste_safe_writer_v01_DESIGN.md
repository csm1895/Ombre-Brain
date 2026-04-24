# paste_safe_writer v0.1 设计草案

状态：设计草案
来源：2026-04-24 多次大段粘贴、heredoc 卡住、半截文档与脏尾巴修复经验。
目标：定义 OmbreBrain 大段文本写入时的安全写法、分块策略、检查动作与失败恢复路径。

## 一、核心目标

paste_safe_writer 是大段文本安全写入规则。

它不是：

- 自动写入脚本
- 自动修复程序
- 自动提交器
- 主脑写入器
- 线上功能

它要解决的是：

- 大段 heredoc 容易卡住
- 长文本容易半截写入
- EOF / PY / MARKER 容易残留成脏尾巴
- 补写时容易覆盖旧内容
- 提交前容易漏检查

一句话：

dirty_tail_guard 管出事后止血，
paste_safe_writer 管写入前防滑。

## 二、适用场景

适合使用 paste_safe_writer 的场景：

- 新增长设计文档
- 追加 README / USAGE 大段内容
- 写本地 READONLY 收口卡
- 写阶段总收口卡
- 写 manifest / repair note
- 一次内容超过 80 行
- 内容里包含代码块、EOF、PY、MARKER、反引号

不需要使用的场景：

- 一两行小修
- grep 检查
- git status / git log
- 不产生文件变化的命令

## 三、推荐写入方式

### 1. 小块 printf 优先

推荐：

```bash
printf "%s\n" \
  "line 1" \
  "line 2" \
  >> path/to/file.md
```

适合：

- 补写缺失章节
- 修复半截文档
- 追加 READONLY 尾部
- 小段内容 20 到 80 行

### 2. cat heredoc 只用于短块

heredoc 可以用，但只建议短块。

推荐：

```bash
cat > path/to/file.md <<'EOF'
content
EOF
```

限制：

- 不用于超长内容
- 不在疲劳时粘贴大段
- 不连续嵌套多个 heredoc
- marker 必须简单且唯一

### 3. 长文档分段写

超过 120 行时，优先拆成多块：

- header block
- core block
- check block
- conclusion block

每块写完先 tail 检查。

## 四、写入前检查

写入前先确认：

- 当前目录是否正确
- 目标文件是新建还是追加
- 使用 > 还是 >>
- 是否含有代码块
- 是否含有 EOF / PY / MARKER 字符
- 是否需要先备份

推荐：

```bash
pwd
ls -lh path/to/file.md 2>/dev/null || echo "new file"
```

## 五、写入后检查

每次写入后必须检查：

```bash
tail -80 path/to/file.md
grep -n "目标章节" path/to/file.md || echo "还没写完整"
grep -n "^EOF$\\|^PY$\\|^MARKER$" path/to/file.md || echo "无脏尾巴"
```

如果是仓库设计文档，还要检查：

```bash
git diff -- path/to/file.md
git status
```

## 六、失败恢复路径

### 1. 卡在 heredoc>

先输入 marker 闭合，不继续乱敲。

闭合后立刻检查：

```bash
tail -80 path/to/file.md
```

### 2. 文件半截

不要直接提交。

先判断缺哪段：

```bash
grep -n "## 当前结论" path/to/file.md || echo "还没写完整"
```

再用 printf 小块补齐。

### 3. 已提交半截

修好后使用：

```bash
git add path/to/file.md
git commit --amend --no-edit
```

### 4. 已推送半截

确认只修当前分支后：

```bash
git push --force-with-lease
```

## 七、与其他设计的关系

- dirty_tail_guard：负责发现和清理脏尾巴
- repair_note_schema：负责记录事故与修复
- readonly_card_schema：定义 READONLY 收口卡结构
- closeout_router：决定一颗完成后去哪
- stage_closeout_pack：负责阶段收工

## 八、当前边界

当前阶段只写设计文档。

不做：

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

## 九、当前结论

paste_safe_writer v0.1 定义了 OmbreBrain 大段文本写入时的安全规则。

它把今天的大段粘贴事故转成写入前、写入中、写入后的防滑流程。

不是为了写得慢，
是为了别让长文本在门口绊倒。
