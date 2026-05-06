"""
A股数据分析工具包入口

用法:
    python -m a_stock sync --help
    python -m a_stock analyze --help
    python -m a_stock notify --help
"""

import sys


def main():
    if len(sys.argv) < 2:
        print("用法: python -m a_stock <command> [options]")
        print()
        print("可用命令:")
        print("  sync      数据同步")
        print("  analyze   数据分析")
        print("  notify    发送通知")
        print("  init      初始化数据库")
        print()
        print("示例:")
        print("  python -m a_stock sync --help")
        print("  python -m a_stock analyze --help")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "sync":
        from a_stock.sync import main as sync_main
        sys.argv = sys.argv[1:]
        sync_main()
    elif command == "analyze":
        from a_stock.analysis.__main__ import main as analyze_main
        sys.argv = sys.argv[1:]
        analyze_main()
    elif command == "notify":
        from a_stock.notify import main as notify_main
        sys.argv = sys.argv[1:]
        notify_main()
    elif command == "init":
        from a_stock.db import init_db
        init_db()
        print("数据库初始化完成")
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
