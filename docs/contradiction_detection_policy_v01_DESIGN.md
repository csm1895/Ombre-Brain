cd ~/Desktop/海马体/Ombre-Brain-graft-test

pbpaste > docs/contradiction_detection_policy_v01_DESIGN.md

echo ""
echo "=== 检查 contradiction_detection_policy 文档 ==="
ls -lh docs/contradiction_detection_policy_v01_DESIGN.md
grep -n "## 十、当前结论" docs/contradiction_detection_policy_v01_DESIGN.md
grep -n "^READONLYONLY$\|^EOF$\|^PY$\|^MARKER$" docs/contradiction_detection_policy_v01_DESIGN.md || echo "无脏尾巴"

echo ""
echo "=== 看文档尾部 ==="
tail -40 docs/contradiction_detection_policy_v01_DESIGN.md

echo ""
echo "=== 提交 contradiction_detection_policy 设计文档 ==="
git add docs/contradiction_detection_policy_v01_DESIGN.md
git commit -m "docs: add contradiction detection policy design"

echo ""
echo "=== 推送分支 ==="
git push

echo ""
echo "=== 状态确认 ==="
git status
git log --oneline --decorate -10