#!/usr/bin/env bash
set -euo pipefail

# 指向 payment-qa-framework 仓库（本地 clone），存在 pom.xml 时跑回归。
# 例：FRAMEWORK_DIR=/Users/lchen/codex-playground/payment-qa-framework ./drift.sh --regress
FRAMEWORK_DIR="${FRAMEWORK_DIR:-}"

if [[ -n "$FRAMEWORK_DIR" && -f "$FRAMEWORK_DIR/pom.xml" ]]; then
  echo "==> 触发回归：$FRAMEWORK_DIR"
  (cd "$FRAMEWORK_DIR" && mvn -B test)
else
  echo "==> 未配置 FRAMEWORK_DIR（指向 payment-qa-framework），跳过自动回归。"
  echo "    手动回归清单见 drift-report.md 末尾。"
fi
