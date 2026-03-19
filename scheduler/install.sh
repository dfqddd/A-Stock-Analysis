#!/bin/bash
# 定时任务安装脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}"
echo "=========================================="
echo "  定时任务安装"
echo "=========================================="
echo -e "${NC}"

# 检测操作系统
OS="$(uname -s)"
case "$OS" in
    Darwin*)
        echo -e "${GREEN}检测到 macOS 系统${NC}"
        SCHEDULER="launchd"
        ;;
    Linux*)
        echo -e "${GREEN}检测到 Linux 系统${NC}"
        SCHEDULER="cron"
        ;;
    *)
        echo -e "${RED}不支持的操作系统: $OS${NC}"
        exit 1
        ;;
esac

# 安装 crontab 定时任务
install_cron() {
    echo -e "${BLUE}安装 crontab 定时任务...${NC}"
    
    # 备份现有 crontab
    crontab -l > /tmp/crontab.backup 2>/dev/null || true
    
    # 检查是否已安装
    if crontab -l 2>/dev/null | grep -q "a-stock-analysis"; then
        echo -e "${YELLOW}定时任务已存在，跳过安装${NC}"
        return
    fi
    
    # 添加新任务
    (
        echo "# A股数据分析系统定时任务"
        echo "# 盘前同步 (工作日 08:30)"
        echo "30 8 * * 1-5 cd $PROJECT_DIR && bash scripts/morning_sync.sh >> logs/cron.log 2>&1"
        echo ""
        echo "# 盘后同步 (工作日 17:00)"
        echo "0 17 * * 1-5 cd $PROJECT_DIR && bash scripts/daily_sync.sh >> logs/cron.log 2>&1"
        echo ""
        echo "# 开机补偿同步"
        echo "@reboot cd $PROJECT_DIR && bash scripts/catch_up_sync.sh >> logs/cron.log 2>&1"
        crontab -l 2>/dev/null | grep -v "a-stock-analysis" || true
    ) | crontab -
    
    echo -e "${GREEN}✓ crontab 定时任务安装完成${NC}"
    echo ""
    echo "已安装的定时任务："
    crontab -l | grep -A1 "A股数据分析" | grep -v "^--$"
}

# 安装 launchd 定时任务
install_launchd() {
    echo -e "${BLUE}安装 launchd 定时任务...${NC}"
    
    PLIST_DIR="$HOME/Library/LaunchAgents"
    mkdir -p "$PLIST_DIR"
    
    # 创建盘前同步任务 (08:30 同步数据，08:45 发送开盘预判)
    cat > "$PLIST_DIR/com.stock.analysis.morning.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stock.analysis.morning</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PROJECT_DIR/scripts/morning_sync.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/launchd.log</string>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Weekday</key>
            <integer>1</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>30</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>2</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>30</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>3</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>30</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>4</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>30</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>5</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>30</integer>
        </dict>
    </array>
</dict>
</plist>
EOF

    # 创建开盘预判消息任务 (08:45)
    cat > "$PLIST_DIR/com.stock.analysis.premarket.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stock.analysis.premarket</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>sleep 60 &amp;&amp; cd $PROJECT_DIR &amp;&amp; python -m a_stock notify premarket</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/launchd.log</string>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Weekday</key>
            <integer>1</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>45</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>2</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>45</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>3</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>45</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>4</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>45</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>5</integer>
            <key>Hour</key>
            <integer>8</integer>
            <key>Minute</key>
            <integer>45</integer>
        </dict>
    </array>
</dict>
</plist>
EOF

    # 创建盘后同步任务 (17:00)
    cat > "$PLIST_DIR/com.stock.analysis.daily.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stock.analysis.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PROJECT_DIR/scripts/daily_sync.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/launchd.log</string>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Weekday</key>
            <integer>1</integer>
            <key>Hour</key>
            <integer>17</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>2</integer>
            <key>Hour</key>
            <integer>17</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>3</integer>
            <key>Hour</key>
            <integer>17</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>4</integer>
            <key>Hour</key>
            <integer>17</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>5</integer>
            <key>Hour</key>
            <integer>17</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
    </array>
</dict>
</plist>
EOF

    # 创建龙虎榜同步任务 (18:00)
    cat > "$PLIST_DIR/com.stock.analysis.dragon-tiger.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stock.analysis.dragon-tiger</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PROJECT_DIR/scripts/dragon_tiger_sync.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/launchd.log</string>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Weekday</key>
            <integer>1</integer>
            <key>Hour</key>
            <integer>18</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>2</integer>
            <key>Hour</key>
            <integer>18</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>3</integer>
            <key>Hour</key>
            <integer>18</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>4</integer>
            <key>Hour</key>
            <integer>18</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>5</integer>
            <key>Hour</key>
            <integer>18</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
    </array>
</dict>
</plist>
EOF

    # 创建补数据同步任务 (22:00)
    cat > "$PLIST_DIR/com.stock.analysis.catchup.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stock.analysis.catchup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PROJECT_DIR/scripts/catch_up_sync.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/launchd.log</string>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Weekday</key>
            <integer>1</integer>
            <key>Hour</key>
            <integer>22</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>2</integer>
            <key>Hour</key>
            <integer>22</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>3</integer>
            <key>Hour</key>
            <integer>22</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>4</integer>
            <key>Hour</key>
            <integer>22</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
        <dict>
            <key>Weekday</key>
            <integer>5</integer>
            <key>Hour</key>
            <integer>22</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
    </array>
</dict>
</plist>
EOF

    # 复制热点消息任务（如果存在）
    if [ -f "$PROJECT_DIR/scheduler/com.stock.analysis.hot-news.plist" ]; then
        cp "$PROJECT_DIR/scheduler/com.stock.analysis.hot-news.plist" "$PLIST_DIR/"
        echo -e "${BLUE}已复制热点消息定时任务配置${NC}"
    fi
    
    # 加载任务
    launchctl load "$PLIST_DIR/com.stock.analysis.morning.plist" 2>/dev/null || true
    launchctl load "$PLIST_DIR/com.stock.analysis.premarket.plist" 2>/dev/null || true
    launchctl load "$PLIST_DIR/com.stock.analysis.daily.plist" 2>/dev/null || true
    launchctl load "$PLIST_DIR/com.stock.analysis.postmarket.plist" 2>/dev/null || true
    launchctl load "$PLIST_DIR/com.stock.analysis.dragon-tiger.plist" 2>/dev/null || true
    launchctl load "$PLIST_DIR/com.stock.analysis.catchup.plist" 2>/dev/null || true
    
    # 加载热点消息任务（如果存在）
    if [ -f "$PLIST_DIR/com.stock.analysis.hot-news.plist" ]; then
        launchctl load "$PLIST_DIR/com.stock.analysis.hot-news.plist" 2>/dev/null || true
    fi
    
    echo -e "${GREEN}✓ launchd 定时任务安装完成${NC}"
    echo ""
    echo "已安装的任务："
    echo "  - com.stock.analysis.morning (工作日 08:30) - 盘前数据同步"
    echo "  - com.stock.analysis.premarket (工作日 08:45) - 📩 开盘预判消息（钉钉推送）"
    echo "  - com.stock.analysis.daily (工作日 17:00) - 盘后数据同步"
    echo "  - com.stock.analysis.postmarket (工作日 15:35) - 📩 收盘复盘消息（钉钉推送）"
    echo "  - com.stock.analysis.dragon-tiger (工作日 18:00) - 龙虎榜同步"
    echo "  - com.stock.analysis.catchup (工作日 22:00) - 数据补偿同步"
    if [ -f "$PLIST_DIR/com.stock.analysis.hot-news.plist" ]; then
        echo "  - com.stock.analysis.hot-news (交易日 09:30-15:00 每30分钟) - 🔥 实时热点消息（钉钉推送）"
    fi
}

# 根据系统选择安装方式
case "$SCHEDULER" in
    cron)
        install_cron
        ;;
    launchd)
        install_launchd
        ;;
esac

echo ""
echo -e "${GREEN}定时任务安装完成！${NC}"
echo ""
echo "管理命令："
if [ "$SCHEDULER" = "cron" ]; then
    echo "  查看任务: crontab -l"
    echo "  编辑任务: crontab -e"
    echo "  查看日志: tail -f $PROJECT_DIR/logs/cron.log"
else
    echo "  查看任务: launchctl list | grep stock"
    echo "  停止任务: launchctl unload ~/Library/LaunchAgents/com.stock.analysis.*.plist"
    echo "  启动任务: launchctl load ~/Library/LaunchAgents/com.stock.analysis.*.plist"
    echo "  查看日志: tail -f $PROJECT_DIR/logs/launchd.log"
fi