#!/bin/bash
# A股数据分析系统一键安装脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}"
echo "=========================================="
echo "  A股数据分析系统 安装向导"
echo "=========================================="
echo -e "${NC}"

# 1. 检查 Python 版本
echo -e "${BLUE}[1/6] 检查环境...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
        echo -e "${RED}✗ Python 版本过低，需要 3.9+${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ 未检测到 Python3，请先安装 Python 3.9+${NC}"
    exit 1
fi

# 检查 pip
if command -v pip3 &> /dev/null; then
    echo -e "${GREEN}✓ pip3 已安装${NC}"
else
    echo -e "${RED}✗ 未检测到 pip3${NC}"
    exit 1
fi



# 2. 创建目录结构
echo -e "${BLUE}[2/6] 创建目录结构...${NC}"
mkdir -p data logs config
echo -e "${GREEN}✓ 目录创建完成${NC}"

# 3. 安装 Python 依赖
echo -e "${BLUE}[3/6] 安装 Python 依赖...${NC}"

# 尝试安装，优先使用 --user 避免权限问题
if pip3 install --user -r requirements.txt 2>/dev/null; then
    echo -e "${GREEN}✓ Python 依赖安装完成 (用户模式)${NC}"
elif pip3 install -r requirements.txt 2>/dev/null; then
    echo -e "${GREEN}✓ Python 依赖安装完成 (系统模式)${NC}"
else
    echo -e "${RED}✗ Python 依赖安装失败${NC}"
    echo -e "${YELLOW}提示: 尝试手动运行: pip3 install --user -r requirements.txt${NC}"
    exit 1
fi

# 验证关键依赖
echo -e "${BLUE}[4/6] 验证依赖安装...${NC}"
if python3 -c "import akshare, pandas, numpy, requests, yaml, loguru" 2>/dev/null; then
    echo -e "${GREEN}✓ 关键依赖验证通过${NC}"
else
    echo -e "${RED}✗ 依赖验证失败，请检查安装日志${NC}"
    exit 1
fi



# 5. 创建配置文件
echo -e "${BLUE}[5/6] 创建配置文件...${NC}"
if [ ! -f config/config.yaml ]; then
    cp config/config.example.yaml config/config.yaml
    echo -e "${GREEN}✓ 配置文件已创建: config/config.yaml${NC}"
else
    echo -e "${YELLOW}! 配置文件已存在，跳过${NC}"
fi

# 6. 初始化数据库
echo -e "${BLUE}[6/6] 初始化数据库...${NC}"
if python3 -m a_stock init 2>/dev/null; then
    echo -e "${GREEN}✓ 数据库初始化完成${NC}"
else
    echo -e "${YELLOW}! 数据库初始化跳过 (可能已存在)${NC}"
fi

echo ""
echo -e "${GREEN}"
echo "=========================================="
echo "  ✓ 安装完成！"
echo "=========================================="
echo -e "${NC}"
echo ""
echo -e "${YELLOW}下一步操作：${NC}"
echo ""
echo "  1. 编辑配置文件："
echo -e "     ${BLUE}vim config/config.yaml${NC}"
echo ""
echo "  2. 填写必要配置："
echo "     - 钉钉 Webhook URL（如需推送功能）"
echo "     - 自选股列表"
echo ""
echo "  3. 同步历史数据："
echo -e "     ${BLUE}python -m a_stock sync --help${NC}"
echo ""
echo "  4. 查看分析报告："
echo -e "     ${BLUE}python -m a_stock analyze --help${NC}"
echo ""
echo "  5. 安装定时任务（可选）："
echo -e "     ${BLUE}bash scheduler/install.sh${NC}"
echo ""
