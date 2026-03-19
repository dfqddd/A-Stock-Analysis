#!/bin/bash
# 恢复本地配置文件（用于本地开发，不上传到 GitHub）
# 使用方法: bash config/use-local-config.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 检查备份文件是否存在
if [ -f "$SCRIPT_DIR/config.yaml.backup" ]; then
    cp "$SCRIPT_DIR/config.yaml.backup" "$SCRIPT_DIR/config.yaml"
    echo "✅ 已恢复本地配置文件"
    echo "⚠️  注意: config.yaml 包含敏感信息，请勿提交到 GitHub"
    echo "   该文件已被添加到 .gitignore"
else
    echo "❌ 未找到备份文件 config.yaml.backup"
    echo "请手动配置 config.yaml"
fi

# 设置环境变量提示
echo ""
echo "💡 建议设置环境变量以避免敏感信息泄露:"
echo "   export DINGTALK_WEBHOOK='你的钉钉webhook地址'"
