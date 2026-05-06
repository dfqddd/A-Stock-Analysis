"""
调度任务模块
定义各种同步和分析任务
"""

import os
import sys
from datetime import datetime
from typing import Optional, Callable, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from a_stock.db.cache import log_info, log_debug, log_error
from a_stock.sync import (
    sync_stock_info,
    sync_stock_daily,
    sync_limit_up,
    sync_stock_hot_ranking,
    sync_stock_news,
    sync_stock_events,
)
from a_stock.sync.stock_daily_tushare import sync_stock_daily_tushare
from a_stock.sync.index_sync import sync_index_daily
from a_stock.sync import (
    sync_sentiment,
    sync_sector_ranking,
    sync_market_stats,
)
from a_stock.analysis import (
    generate_daily_review,
)
from a_stock.notify import send_daily_report


def run_sync_task(
    task_func: Callable,
    task_name: str,
    date: str = None,
    **kwargs
) -> bool:
    """
    执行同步任务并记录日志
    
    Args:
        task_func: 任务函数
        task_name: 任务名称
        date: 指定日期
        **kwargs: 传递给任务函数的参数
        
    Returns:
        是否成功
    """
    log_info(f"开始执行: {task_name}")
    start_time = datetime.now()
    
    try:
        if date:
            task_func(date=date, **kwargs)
        else:
            task_func(**kwargs)
            
        elapsed = (datetime.now() - start_time).total_seconds()
        log_info(f"完成: {task_name} (耗时 {elapsed:.1f}s)")
        return True
        
    except Exception as e:
        log_error(f"失败: {task_name} - {e}")
        return False


def daily_sync(date: str = None, notify: bool = False):
    """
    每日数据同步
    
    执行所有数据同步任务，生成复盘报告并可选发送通知
    使用并发执行提高效率
    
    Args:
        date: 指定日期（可选）
        notify: 是否发送通知
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"=" * 50)
    log_info(f"每日数据同步 - {target_date}")
    log_info(f"=" * 50)
    
    # Step 1: 同步股票基础信息（必须先执行，其他任务依赖股票代码列表）
    run_sync_task(sync_stock_info, "股票基础信息", skip_details=True)
    
    # Step 2: 先执行涨停数据同步（market_stats 依赖此数据）
    log_info("先执行涨停数据同步（其他任务依赖此数据）...")
    run_sync_task(sync_limit_up, "涨停数据", date=target_date)
    
    # Step 3: 并发执行轻量同步任务
    log_info("开始并发执行其他数据同步任务...")
    
    # 定义并发任务列表（不含日K数据，避免多线程下连接池冲突）
    concurrent_tasks = [
        (sync_market_stats, "市场统计", {"date": target_date}),
        (sync_index_daily, "三大指数", {"date": target_date}),
        (sync_sector_ranking, "板块排名", {"date": target_date}),
        (sync_sentiment, "市场情绪", {"date": target_date}),
        (sync_stock_hot_ranking, "热门股票榜单", {"date": target_date}),
    ]
    
    # 使用线程池并发执行
    with ThreadPoolExecutor(max_workers=5) as executor:
        # 提交所有任务
        futures = {}
        for task_func, task_name, task_kwargs in concurrent_tasks:
            future = executor.submit(run_sync_task, task_func, task_name, **task_kwargs)
            futures[future] = task_name
        
        # 等待所有任务完成
        completed = 0
        failed = 0
        for future in as_completed(futures):
            task_name = futures[future]
            try:
                result = future.result()
                if result:
                    completed += 1
                else:
                    failed += 1
            except Exception as e:
                log_error(f"任务 {task_name} 异常: {e}")
                failed += 1
    
    log_info(f"并发任务完成: 成功 {completed}/{len(concurrent_tasks)}, 失败 {failed}")
    
    # 生成复盘报告
    log_info("生成复盘报告...")
    report = generate_daily_review(date=target_date, sync=False)
    
    # 发送通知
    if notify:
        send_daily_report(report)
    
    log_info(f"=" * 50)
    log_info(f"每日数据同步完成 - {target_date}")
    log_info(f"=" * 50)
    
    return report


def morning_sync(date: str = None):
    """
    早盘数据同步
    
    在开盘前执行，更新股票基础信息、新闻、热门排名和事件
    
    Args:
        date: 指定日期（可选）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info(f"=" * 50)
    log_info(f"早盘数据同步 - {target_date}")
    log_info(f"=" * 50)
    
    # Step 1: 同步股票基础信息（必须先执行）
    run_sync_task(sync_stock_info, "股票基础信息")
    
    # Step 2: 并发执行其他早盘任务
    log_info("开始并发执行早盘数据同步...")
    
    morning_tasks = [
        (sync_stock_hot_ranking, "热门股票排名", {"date": target_date}),
        (sync_stock_news, "股票新闻", {"date": target_date}),
        (sync_stock_events, "股票事件", {"date": target_date}),
    ]
    
    # 使用线程池并发执行
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for task_func, task_name, task_kwargs in morning_tasks:
            future = executor.submit(run_sync_task, task_func, task_name, **task_kwargs)
            futures[future] = task_name
        
        # 等待所有任务完成
        completed = 0
        failed = 0
        for future in as_completed(futures):
            task_name = futures[future]
            try:
                result = future.result()
                if result:
                    completed += 1
                else:
                    failed += 1
            except Exception as e:
                log_error(f"任务 {task_name} 异常: {e}")
                failed += 1
    
    log_info(f"早盘任务完成: 成功 {completed}/{len(morning_tasks)}, 失败 {failed}")
    log_info(f"=" * 50)
    log_info(f"早盘数据同步完成 - {target_date}")
    log_info(f"=" * 50)


def catch_up_sync(date: str = None):
    """
    补数据同步（增强版）
    
    每天晚上 22:00 执行：
    1. 检查当天数据同步完整性
    2. 发送钉钉告警通知缺失数据
    3. 自动补偿缺失数据
    4. 同步个股异动等晚间披露的数据
    
    Args:
        date: 指定日期（可选，默认为最近交易日）
    """
    from a_stock.scheduler.sync_monitor import (
        run_sync_check_and_compensate,
        is_trading_day,
        get_last_trading_day,
    )
    
    # 确定目标日期
    target_date = date or get_last_trading_day()
    
    # 检查是否为交易日
    if not is_trading_day(target_date):
        log_info(f"{target_date} 不是交易日，跳过补数据同步")
        return
    
    log_info(f"=" * 50)
    log_info(f"补数据同步 - {target_date}")
    log_info(f"=" * 50)
    
    # Step 1: 执行数据完整性检查和自动补偿
    log_info("开始执行数据完整性检查和自动补偿...")
    run_sync_check_and_compensate(target_date)
    
    # Step 2: 同步个股异动数据（交易所晚间披露）- 暂时停用
    log_info("[暂停] 个股异动数据同步 - 数据源不稳定")
    
    log_info(f"=" * 50)
    log_info(f"补数据同步完成 - {target_date}")
    log_info(f"=" * 50)


def stock_daily_sync(date: str = None):
    """
    个股日K数据同步（独立任务，17:30 执行）

    使用 Tushare Pro 批量接口，一次请求获取所有股票当日数据。
    与 daily_sync 解耦，避免 15:10 时 Tushare 数据尚未就绪的问题。

    Args:
        date: 指定日期（可选，默认为今天）
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_info("=" * 50)
    log_info(f"个股日K数据同步 - {target_date}")
    log_info("=" * 50)

    try:
        result = sync_stock_daily_tushare(date=target_date)
        log_info(f"日K数据同步完成: 写入 {result.get('success', 0)} 条记录")
    except Exception as e:
        log_error(f"日K数据同步失败: {e}")

    log_info("=" * 50)
    log_info(f"个股日K数据同步完成 - {target_date}")
    log_info("=" * 50)


def dragon_tiger_sync(date: str = None):
    """
    龙虎榜数据同步
    
    交易所 17:00 后披露，建议 18:00 后执行
    
    Args:
        date: 指定日期（可选）
    """
    log_info("[暂停] 龙虎榜数据同步 - 东财数据源不稳定，暂时停用")
    return


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="调度任务")
    parser.add_argument("task", choices=["daily", "morning", "catchup", "stock-daily"], help="任务类型")
    parser.add_argument("--date", help="指定日期")
    parser.add_argument("--notify", action="store_true", help="发送通知")
    
    args = parser.parse_args()
    
    if args.task == "daily":
        daily_sync(date=args.date, notify=args.notify)
    elif args.task == "morning":
        morning_sync(date=args.date)
    elif args.task == "catchup":
        catch_up_sync(date=args.date)
    elif args.task == "stock-daily":
        stock_daily_sync(date=args.date)

if __name__ == "__main__":
    main()