"""
详细市场数据分析模块
获取三大指数、涨停详情、板块资金流向、龙虎榜等详细数据
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import akshare as ak

from a_stock.db import get_connection
from a_stock.db.cache import log_debug, log_info, log_error


def get_three_major_indices(date: str = None) -> List[Dict]:
    """
    获取三大指数数据（上证指数、深证成指、创业板指）
    
    Args:
        date: 指定日期，格式 YYYY-MM-DD
        
    Returns:
        三大指数数据列表
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    try:
        # 从数据库获取
        conn = get_connection()
        cursor = conn.cursor()
        
        index_codes = {
            "000001": "上证指数",
            "399001": "深证成指", 
            "399006": "创业板指"
        }
        
        indices = []
        for code, name in index_codes.items():
            row = cursor.execute(
                "SELECT * FROM index_daily WHERE date = ? AND code = ?",
                (target_date, code)
            ).fetchone()
            
            if row:
                indices.append({
                    "code": code,
                    "name": name,
                    "close": row["close"],
                    "pct_change": row["pct_change"]
                })
        
        conn.close()
        
        # 如果数据库没有，从 AKShare 实时获取
        if not indices:
            log_debug(f"数据库无 {target_date} 指数数据，尝试实时获取")
            try:
                df = ak.index_zh_a_hist(symbol="000001", period="daily", 
                                       start_date=target_date.replace("-", ""), 
                                       end_date=target_date.replace("-", ""))
                if not df.empty:
                    indices.append({
                        "code": "000001",
                        "name": "上证指数",
                        "close": float(df.iloc[0]["收盘"]),
                        "pct_change": float(df.iloc[0]["涨跌幅"])
                    })
                
                df = ak.index_zh_a_hist(symbol="399001", period="daily",
                                       start_date=target_date.replace("-", ""),
                                       end_date=target_date.replace("-", ""))
                if not df.empty:
                    indices.append({
                        "code": "399001",
                        "name": "深证成指",
                        "close": float(df.iloc[0]["收盘"]),
                        "pct_change": float(df.iloc[0]["涨跌幅"])
                    })
                    
                df = ak.index_zh_a_hist(symbol="399006", period="daily",
                                       start_date=target_date.replace("-", ""),
                                       end_date=target_date.replace("-", ""))
                if not df.empty:
                    indices.append({
                        "code": "399006",
                        "name": "创业板指",
                        "close": float(df.iloc[0]["收盘"]),
                        "pct_change": float(df.iloc[0]["涨跌幅"])
                    })
            except Exception as e:
                log_error(f"实时获取指数数据失败: {e}")
        
        return indices
        
    except Exception as e:
        log_error(f"获取三大指数数据失败: {e}")
        return []


def get_limit_up_details(date: str = None) -> Dict:
    """
    获取涨停详情数据（包含炸板数计算、所有连板股、概念板块分布）
    
    Args:
        date: 指定日期
        
    Returns:
        涨停详情数据
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 获取涨停股列表（兼容中英文status）
        # 获取涨停股列表（兼容中英文status）
        limit_up_stocks = cursor.execute(
            """
            SELECT code, name, first_seal_time, seal_amount_yi, industry,
                   continuous_board, broken_count, change_pct
            FROM limit_up_detail 
            WHERE date = ? AND (status = '涨停' OR status = 'limit_up')
            ORDER BY seal_amount_yi DESC
            """,
            (target_date,)
        ).fetchall()
        
        limit_up_count = len(limit_up_stocks)
        
        # 获取跌停股数量和详情
        limit_down_stocks = cursor.execute(
            """
            SELECT code, name, industry, change_pct
            FROM limit_up_detail 
            WHERE date = ? AND status = '跌停'
            ORDER BY change_pct ASC
            """,
            (target_date,)
        ).fetchall()
        limit_down_count = len(limit_down_stocks)
        
        # 计算炸板数：统计炸板次数>0的股票数量（即曾经打开过涨停的股票数）
        # 注意：broken_count是单只股票的炸板次数，我们要统计的是"炸板股"的数量
        total_broken_count = 0
        for stock in limit_up_stocks:
            broken = stock["broken_count"] if stock["broken_count"] else 0
            if broken > 0:  # 只要炸板次数>0，就算一只炸板股
                total_broken_count += 1
        
        # 分析连板股（分析所有股票，不限制数量）
        continuous_boards = []
        concept_distribution = {}  # 使用概念板块而非行业
        
        # 获取概念板块数据（使用type字段而不是sector_type）
        concept_sectors = cursor.execute(
            """
            SELECT name, change_pct, leading_stock
            FROM sector_ranking 
            WHERE date = ? AND type = 'concept'
            ORDER BY change_pct DESC
            LIMIT 20
            """,
            (target_date,)
        ).fetchall()
        
        for stock in limit_up_stocks:
            code = stock["code"]
            name = stock["name"]
            seal_amount = stock["seal_amount_yi"] if stock["seal_amount_yi"] else 0
            boards = stock["continuous_board"] if stock["continuous_board"] else 1
            change_pct = stock["change_pct"] if stock["change_pct"] else 0
            
            # 连板数据（包含所有股票）
            continuous_boards.append({
                "name": name,
                "code": code,
                "boards": boards,
                "industry": stock["industry"] if stock["industry"] else "其他",
                "seal_amount": seal_amount,
                "change_pct": change_pct
            })
        
        # 按封单金额排序
        continuous_boards.sort(key=lambda x: x["seal_amount"], reverse=True)
        
        # 整理概念板块分布（使用实际热门概念）
        concept_list = []
        for concept in concept_sectors[:10]:  # 取前10个热门概念
            concept_list.append({
                "name": concept["name"],
                "change_pct": concept["change_pct"],
                "leading_stock": concept["leading_stock"]
            })
        
        conn.close()
        
        # 封板率计算说明：
        # 
        # 正确的封板率公式：
        # seal_rate = limit_up_count / (limit_up_count + broken_not_sealed) * 100
        # 
        # 其中：
        # - limit_up_count: 最终涨停的股票数（数据库中有）
        # - broken_not_sealed: 炸板未回封的股票数（AKShare 不提供）
        #
        # 注意：AKShare 数据源只提供最终涨停的股票，不包含炸板未回封的股票
        # 因此无法从数据库直接计算准确的封板率
        # 
        # 解决方案：从 retime_data 获取准确的封板率
        seal_rate = 0
        broken_not_sealed = 0
        try:
            from a_stock.sync.retime_data import get_realtime_seal_rate
            realtime_data = get_realtime_seal_rate(target_date)
            if realtime_data and realtime_data.get("seal_rate", 0) > 0:
                seal_rate = realtime_data["seal_rate"]
                broken_not_sealed = realtime_data.get("broken_count", 0)
        except Exception as e:
            log_debug(f"实时获取封板率失败: {e}")
        
        # 整理跌停股票数据
        limit_down_list = []
        for stock in limit_down_stocks:
            limit_down_list.append({
                "code": stock["code"],
                "name": stock["name"],
                "industry": stock["industry"] if stock["industry"] else "其他",
                "change_pct": stock["change_pct"] if stock["change_pct"] else -10.0
            })
        
        return {
            "limit_up_count": limit_up_count,
            "limit_down_count": limit_down_count,  # 添加跌停数
            "limit_down_list": limit_down_list,  # 跌停股票列表
            "broken_count": total_broken_count,
            "seal_rate": seal_rate,
            "continuous_boards": continuous_boards,  # 返回所有股票
            "concept_distribution": concept_list  # 使用概念板块
        }
        
    except Exception as e:
        log_error(f"获取涨停详情失败: {e}")
        return {
            "limit_up_count": 0,
            "broken_count": 0,
            "seal_rate": 0,
            "continuous_boards": [],
            "concept_distribution": []
        }


def get_sector_fund_flow(date: str = None) -> Dict:
    """
    获取板块资金流向（基于真实涨跌幅数据）
    
    Args:
        date: 指定日期
        
    Returns:
        板块资金流向数据
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 获取板块排名（包含涨跌幅）
        sectors = cursor.execute(
            """
            SELECT name, change_pct, leading_stock
            FROM sector_ranking 
            WHERE date = ? AND type = 'industry'
            ORDER BY change_pct DESC
            """,
            (target_date,)
        ).fetchall()
        
        inflow = []
        outflow = []
        
        for sector in sectors:
            # 使用涨跌幅作为资金流向指标
            change_pct = sector["change_pct"] if sector["change_pct"] else 0
            
            item = {
                "name": sector["name"],
                "change_pct": change_pct,
                "net_flow": None,  # 板块资金流向数据当前未同步，仅显示涨跌幅
                "leading_stock": sector["leading_stock"]
            }
            
            if change_pct > 0:
                inflow.append(item)
            else:
                outflow.append(item)
        
        # 按涨跌幅排序
        inflow.sort(key=lambda x: x["change_pct"], reverse=True)
        outflow.sort(key=lambda x: x["change_pct"])
        
        conn.close()
        
        return {
            "inflow_top5": inflow[:5],
            "outflow_top3": outflow[:3]
        }
        
    except Exception as e:
        log_error(f"获取板块资金流向失败: {e}")
        return {
            "inflow_top5": [],
            "outflow_top3": []
        }


def get_dragon_tiger_summary(date: str = None) -> Dict:
    """
    获取龙虎榜数据汇总（详细展示所有数据）
    
    Args:
        date: 指定日期
        
    Returns:
        龙虎榜汇总数据
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 获取龙虎榜数据（包含更多字段）
        dragon_tiger_data = cursor.execute(
            """
            SELECT code, name, close_price, change_pct, turnover_rate,
                   buy_value, sell_value, net_buy_value, total_value, lhb_reason
            FROM dragon_tiger 
            WHERE date = ?
            ORDER BY ABS(net_buy_value) DESC
            """,
            (target_date,)
        ).fetchall()
        
        if not dragon_tiger_data:
            conn.close()
            return {
                "count": 0,
                "total_net_buy": 0,
                "all_stocks": [],
                "buy_summary": {},
                "sell_summary": {}
            }
        
        # 统计
        total_net_buy = sum([d["net_buy_value"] or 0 for d in dragon_tiger_data])
        total_buy = sum([d["buy_value"] or 0 for d in dragon_tiger_data])
        total_sell = sum([d["sell_value"] or 0 for d in dragon_tiger_data])
        
        # 整理所有股票数据（AKShare返回的数据单位是元，需要转换为亿）
        all_stocks = []
        for d in dragon_tiger_data:
            all_stocks.append({
                "name": d["name"],
                "code": d["code"],
                "close_price": d["close_price"] or 0,
                "change_pct": d["change_pct"] or 0,
                "turnover_rate": d["turnover_rate"] or 0,
                "buy_value": (d["buy_value"] or 0) / 100000000,  # 元 -> 亿
                "sell_value": (d["sell_value"] or 0) / 100000000,  # 元 -> 亿
                "net_buy": (d["net_buy_value"] or 0) / 100000000,  # 元 -> 亿
                "total_value": (d["total_value"] or 0) / 100000000,  # 元 -> 亿
                "reason": d["lhb_reason"] or "龙虎榜"
            })
        
        # 按净买入排序，分成买入榜和卖出榜
        sorted_by_net = sorted(all_stocks, key=lambda x: x["net_buy"], reverse=True)
        buy_list = [s for s in sorted_by_net if s["net_buy"] > 0]
        sell_list = [s for s in sorted_by_net if s["net_buy"] < 0]
        
        conn.close()
        
        return {
            "count": len(dragon_tiger_data),
            "total_net_buy": round(total_net_buy, 2),  # 已经是亿单位
            "total_buy": round(total_buy, 2),
            "total_sell": round(total_sell, 2),
            "all_stocks": all_stocks,  # 所有股票详细数据
            "buy_list": buy_list,  # 净买入列表
            "sell_list": sell_list  # 净卖出列表
        }
        
    except Exception as e:
        log_error(f"获取龙虎榜数据失败: {e}")
        return {
            "count": 0,
            "total_net_buy": 0,
            "total_buy": 0,
            "total_sell": 0,
            "all_stocks": [],
            "buy_list": [],
            "sell_list": []
        }


def get_trend_analysis(date: str = None) -> Dict:
    """
    获取近5日趋势分析数据
    
    Args:
        date: 指定日期
        
    Returns:
        趋势分析数据，包含与5日均值的对比
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 直接从limit_up_detail表统计涨跌停数据（更可靠）
        # 因为market_stats表的数据可能不准确或未及时更新
        date_list = cursor.execute(
            """
            SELECT DISTINCT date FROM limit_up_detail 
            WHERE date <= ? ORDER BY date DESC LIMIT 6
            """,
            (target_date,)
        ).fetchall()
        
        recent_stats = []
        for d in date_list:
            date_str = d["date"]
            # 统计该日期的涨停数（只统计status为涨停或limit_up的）
            lu_result = cursor.execute(
                """
                SELECT COUNT(*) as c FROM limit_up_detail 
                WHERE date = ? AND (status = '涨停' OR status = 'limit_up')
                """,
                (date_str,)
            ).fetchone()
            limit_up_count = lu_result["c"] if lu_result else 0
            
            # 统计该日期的跌停数
            ld_result = cursor.execute(
                """
                SELECT COUNT(*) as c FROM limit_up_detail 
                WHERE date = ? AND status = '跌停'
                """,
                (date_str,)
            ).fetchone()
            limit_down_count = ld_result["c"] if ld_result else 0
            
            # 尝试从market_stats获取其他数据
            stats_result = cursor.execute(
                """
                SELECT total_amount_yi, up_count, down_count 
                FROM market_stats WHERE date = ?
                """,
                (date_str,)
            ).fetchone()
            
            recent_stats.append({
                "date": date_str,
                "total_amount_yi": stats_result["total_amount_yi"] if stats_result else 0,
                "up_count": stats_result["up_count"] if stats_result else 0,
                "down_count": stats_result["down_count"] if stats_result else 0,
                "limit_up_count": limit_up_count,
                "limit_down_count": limit_down_count
            })
        
        if len(recent_stats) < 2:
            conn.close()
            return {}
        
        # 当日数据
        today_stats = recent_stats[0]
        
        # 计算5日均值（不包括当日）
        past_5_days = recent_stats[1:6] if len(recent_stats) > 1 else []
        
        if not past_5_days:
            conn.close()
            return {}
        
        # 从 stock_daily 表计算成交额（更可靠，单位：元）
        today_amount_result = cursor.execute(
            "SELECT SUM(amount) as total FROM stock_daily WHERE date = ?",
            (target_date,)
        ).fetchone()
        today_amount = (today_amount_result["total"] or 0) / 100000000  # 转换为亿
        
        # 计算5日均量
        past_amounts = []
        for s in past_5_days:
            past_result = cursor.execute(
                "SELECT SUM(amount) as total FROM stock_daily WHERE date = ?",
                (s["date"],)
            ).fetchone()
            if past_result and past_result["total"]:
                past_amounts.append(past_result["total"] / 100000000)
        
        avg_amount = sum(past_amounts) / len(past_amounts) if past_amounts else 0
        amount_change_pct = round((today_amount - avg_amount) / avg_amount * 100, 2) if avg_amount > 0 else 0
        
        # 从 stock_daily 表获取准确的涨跌家数（更可靠）
        today_up_down = cursor.execute(
            """
            SELECT 
                SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) as up_count,
                SUM(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END) as down_count,
                SUM(CASE WHEN change_pct = 0 THEN 1 ELSE 0 END) as flat_count
            FROM stock_daily 
            WHERE date = ?
            """,
            (target_date,)
        ).fetchone()
        
        today_up = today_up_down["up_count"] or 0
        today_down = today_up_down["down_count"] or 0
        
        # 计算5日平均涨跌比（使用过去5天的实际数据）
        avg_up_down_ratios = []
        for s in past_5_days:
            # 同样从 stock_daily 获取历史数据
            hist_up_down = cursor.execute(
                """
                SELECT 
                    SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) as up_count,
                    SUM(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END) as down_count
                FROM stock_daily 
                WHERE date = ?
                """,
                (s["date"],)
            ).fetchone()
            up = hist_up_down["up_count"] or 0
            down = hist_up_down["down_count"] or 1
            if down > 0:
                avg_up_down_ratios.append(up / down)
        
        avg_ratio = sum(avg_up_down_ratios) / len(avg_up_down_ratios) if avg_up_down_ratios else 0
        today_ratio = today_up / today_down if today_down > 0 else 0
        ratio_change_pct = round((today_ratio - avg_ratio) / avg_ratio * 100, 2) if avg_ratio > 0 else 0
        
        # 计算5日平均涨停数
        avg_limit_up = sum([s["limit_up_count"] or 0 for s in past_5_days]) / len(past_5_days)
        today_limit_up = today_stats["limit_up_count"] or 0
        limit_up_change_pct = round((today_limit_up - avg_limit_up) / avg_limit_up * 100, 2) if avg_limit_up > 0 else 0
        
        # 计算5日平均跌停数
        avg_limit_down = sum([s["limit_down_count"] or 0 for s in past_5_days]) / len(past_5_days)
        today_limit_down = today_stats["limit_down_count"] or 0
        limit_down_change_pct = round((today_limit_down - avg_limit_down) / avg_limit_down * 100, 2) if avg_limit_down > 0 else 0
        
        # 获取上证指数5日数据
        sh_index_5d = cursor.execute(
            """
            SELECT close, change_pct FROM index_daily
            WHERE code = '000001' AND date <= ?
            ORDER BY date DESC
            LIMIT 6
            """,
            (target_date,)
        ).fetchall()
        
        sh_trend = {}
        if len(sh_index_5d) >= 2:
            today_sh = sh_index_5d[0]
            past_sh = sh_index_5d[1:6]
            avg_sh_close = sum([s["close"] or 0 for s in past_sh]) / len(past_sh) if past_sh else 0
            today_sh_close = today_sh["close"] or 0
            sh_change_pct = round((today_sh_close - avg_sh_close) / avg_sh_close * 100, 2) if avg_sh_close > 0 else 0
            
            sh_trend = {
                "today_close": today_sh_close,
                "avg_5d_close": round(avg_sh_close, 2),
                "change_pct": sh_change_pct
            }
        
        conn.close()
        
        return {
            "date": target_date,
            "volume": {
                "today": round(today_amount, 2),
                "avg_5d": round(avg_amount, 2),
                "change_pct": amount_change_pct
            },
            "up_down_ratio": {
                "today": round(today_ratio, 2),
                "today_up": today_up,
                "today_down": today_down,
                "avg_5d": round(avg_ratio, 2),
                "change_pct": ratio_change_pct
            },
            "limit_up": {
                "today": today_limit_up,
                "avg_5d": round(avg_limit_up, 1),
                "change_pct": limit_up_change_pct
            },
            "limit_down": {
                "today": today_limit_down,
                "avg_5d": round(avg_limit_down, 1),
                "change_pct": limit_down_change_pct
            },
            "sh_index": sh_trend
        }
        
    except Exception as e:
        log_error(f"获取趋势分析数据失败: {e}")
        return {}


def get_hot_ranking(date: str = None) -> List[Dict]:
    """
    获取热门股票榜单数据
    
    Args:
        date: 指定日期
        
    Returns:
        热门股票列表
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 从数据库获取热门股票（关联limit_up_detail获取概念，因为stock_info的industry经常为空）
        hot_stocks = cursor.execute(
            """
            SELECT h.code, h.name, h.total_rank, h.total_score, 
                   COALESCE(l.industry, s.industry, '其他') as concept
            FROM stock_hot_ranking h
            LEFT JOIN stock_info s ON h.code = s.code
            LEFT JOIN limit_up_detail l ON h.code = l.code AND l.date = h.date
            WHERE h.date = ?
            ORDER BY h.total_rank ASC
            LIMIT 20
            """,
            (target_date,)
        ).fetchall()
        
        conn.close()
        
        if hot_stocks:
            return [
                {
                    "code": s["code"],
                    "name": s["name"],
                    "rank": s["total_rank"],
                    "score": s["total_score"],
                    "concept": s["concept"] if s["concept"] else "其他"
                }
                for s in hot_stocks
            ]
        
        # 如果数据库没有，尝试实时获取
        try:
            import akshare as ak
            df = ak.stock_hot_rank_em()
            if df is not None and not df.empty:
                result = []
                for idx, row in df.head(20).iterrows():
                    result.append({
                        "code": str(row.get("代码", "")),
                        "name": str(row.get("股票名称", "")),
                        "rank": idx + 1,
                        "score": row.get("个股热度", 0)
                    })
                return result
        except Exception as e:
            log_debug(f"实时获取热门股票失败: {e}")
        
        return []
        
    except Exception as e:
        log_error(f"获取热门股票失败: {e}")
        return []


def get_market_summary(date: str = None, allow_fallback: bool = True) -> Dict:
    """
    获取市场汇总数据（用于盘前消息）
    
    Args:
        date: 指定日期
        allow_fallback: 是否允许在数据不完整时回退到最近的有数据的日期（盘后报告应设置为False）
        
    Returns:
        市场汇总数据
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    
    # 盘前消息基于昨日数据，计算昨天日期
    yesterday = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 检查昨天的数据是否完整（所有表都有数据）
        stats_count = cursor.execute(
            "SELECT COUNT(*) as c FROM market_stats WHERE date = ?", (yesterday,)
        ).fetchone()["c"]
        
        index_count = cursor.execute(
            "SELECT COUNT(*) as c FROM index_daily WHERE date = ?", (yesterday,)
        ).fetchone()["c"]
        
        sector_count = cursor.execute(
            "SELECT COUNT(*) as c FROM sector_ranking WHERE date = ?", (yesterday,)
        ).fetchone()["c"]
        
        # 如果昨天数据不完整，尝试找最近一个有完整数据的日期
        if stats_count == 0 or index_count == 0 or sector_count == 0:
            log_debug(f"{yesterday} 数据不完整")
            
            if allow_fallback:
                log_debug("查找最近的有数据的日期")
                
                # 获取各表最新日期（不超过昨天）
                stats_date = cursor.execute(
                    "SELECT MAX(date) as d FROM market_stats WHERE date <= ?", (yesterday,)
                ).fetchone()["d"]
                
                index_date = cursor.execute(
                    "SELECT MAX(date) as d FROM index_daily WHERE date <= ?", (yesterday,)
                ).fetchone()["d"]
                
                sector_date = cursor.execute(
                    "SELECT MAX(date) as d FROM sector_ranking WHERE date <= ?", (yesterday,)
                ).fetchone()["d"]
                
                # 使用最早的日期，确保所有表都有数据
                dates = [d for d in [stats_date, index_date, sector_date] if d]
                if dates:
                    yesterday = min(dates)
                    log_debug(f"使用日期: {yesterday}")
            else:
                log_debug("不允许回退，使用原始日期")
            
        conn.close()
    except Exception as e:
        log_error(f"获取数据日期失败: {e}")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 获取昨日市场统计
        stats = cursor.execute(
            "SELECT * FROM market_stats WHERE date = ?", (yesterday,)
        ).fetchone()
        
        # 从 limit_up_detail 表获取准确的涨停和跌停数据（兼容中英文status）
        limit_up_count = cursor.execute(
            "SELECT COUNT(*) as c FROM limit_up_detail WHERE date = ? AND (status = '涨停' OR status = 'limit_up')",
            (yesterday,)
        ).fetchone()["c"]
        
        limit_down_count = cursor.execute(
            "SELECT COUNT(*) as c FROM limit_up_detail WHERE date = ? AND status = '跌停'",
            (yesterday,)
        ).fetchone()["c"]
        
        # 获取昨日板块排名
        sectors = cursor.execute(
            """
            SELECT name, change_pct, leading_stock
            FROM sector_ranking 
            WHERE date = ? AND type = 'industry'
            ORDER BY change_pct DESC
            LIMIT 5
            """,
            (yesterday,)
        ).fetchall()
        
        # 获取昨日情绪数据
        sentiment = cursor.execute(
            "SELECT * FROM sentiment WHERE date = ?", (yesterday,)
        ).fetchone()
        
        # 获取三大指数
        indices = cursor.execute(
            """
            SELECT code, name, close, change_pct 
            FROM index_daily 
            WHERE date = ? AND code IN ('000001', '399001', '399006')
            """,
            (yesterday,)
        ).fetchall()
        
        conn.close()
        
        # 整理数据
        indices_data = []
        for idx in indices:
            indices_data.append({
                "code": idx["code"],
                "name": idx["name"],
                "close": idx["close"],
                "pct_change": idx["change_pct"]
            })
        
        # 获取涨停详情
        limit_up_data = get_limit_up_details(yesterday)
        
        # 获取板块资金流向
        fund_flow_data = get_sector_fund_flow(yesterday)
        
        # 获取龙虎榜数据
        dragon_tiger_data = get_dragon_tiger_summary(yesterday)
        
        # 获取趋势分析数据
        trend_data = get_trend_analysis(yesterday)
        
        # 获取热门股票数据
        hot_ranking_data = get_hot_ranking(yesterday)
        
        return {
            "date": yesterday,
            "indices": indices_data,
            "market_stats": {
                "up_count": stats["up_count"] if stats else 0,
                "down_count": stats["down_count"] if stats else 0,
                "flat_count": stats["flat_count"] if stats else 0,
                "limit_up": limit_up_count,
                "limit_down": limit_down_count,
                "total_amount": stats["total_amount_yi"] if stats else 0
            },
            "sentiment": {
                "limit_up_total": sentiment["limit_up_total"] if sentiment else 0,
                "first_board": sentiment["first_board"] if sentiment else 0,
                "continuous_board": sentiment["continuous_board"] if sentiment else 0,
                "max_height": sentiment["max_height"] if sentiment else 0,
                "max_height_stock": sentiment["max_height_stock"] if sentiment else "",
                "seal_rate": sentiment["seal_rate"] if sentiment else 0,
                "broken_rate": sentiment["broken_rate"] if sentiment else 0
            },
            "sectors": [
                {
                    "name": s["name"],
                    "change_pct": s["change_pct"],
                    "leading_stock": s["leading_stock"]
                }
                for s in sectors
            ],
            "limit_up_details": limit_up_data,
            "fund_flow": fund_flow_data,
            "dragon_tiger": dragon_tiger_data,
            "trend": trend_data,
            "hot_ranking": hot_ranking_data
        }
        
    except Exception as e:
        log_error(f"获取市场汇总数据失败: {e}")
        return {
            "date": yesterday,
            "indices": [],
            "market_stats": {},
            "sentiment": {},
            "sectors": [],
            "limit_up_details": {},
            "fund_flow": {}
        }


def format_premarket_message(data: Dict) -> str:
    """
    格式化盘前消息（Markdown格式）
    优化后的格式，包含趋势分析、龙虎榜、详细的涨跌停数据
    
    Args:
        data: 市场汇总数据
        
    Returns:
        格式化后的Markdown消息
    """
    if not data or not data.get("date"):
        return "【分析】暂无数据"
    
    yesterday = data["date"]
    today = (datetime.strptime(yesterday, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    
    lines = []
    lines.append(f"## 📊 {today} 盘前分析 | 基于昨日（{yesterday}）数据")
    lines.append("")
    
    # ========== 一、三大指数 ==========
    lines.append("### 📈 一、三大指数")
    indices = data.get("indices", [])
    if indices:
        for idx in indices:
            emoji = "🔴" if idx.get("pct_change", 0) >= 0 else "🟢"
            lines.append(f"- {emoji} **{idx['name']}**: {idx['close']:.2f} ({idx['pct_change']:+.2f}%)")
    else:
        lines.append("- 暂无数据")
    lines.append("")
    
    # ========== 二、大盘环境 ==========
    stats = data.get("market_stats", {})
    limit_up_details = data.get("limit_up_details", {})
    trend = data.get("trend", {})
    
    # 从 trend 数据获取涨跌家数（更准确，从 limit_up_detail 表统计）
    if trend and trend.get("up_down_ratio"):
        ud = trend["up_down_ratio"]
        up = int(ud.get("today_up", 0))
        down = int(ud.get("today_down", 0))
    elif stats:
        up = stats.get("up_count", 0)
        down = stats.get("down_count", 0)
    else:
        up, down = 0, 0
    
    ratio = round(up / down, 1) if down > 0 else 0
    
    # 从 limit_up_details 获取准确的涨停跌停数据
    limit_up_total = limit_up_details.get("limit_up_count", 0) if limit_up_details else 0
    limit_down_total = limit_up_details.get("limit_down_count", 0) if limit_up_details else 0
    
    # 从 trend 获取成交额（更准确）
    if trend and trend.get("volume"):
        total_amount = trend["volume"].get("today", 0)
    else:
        total_amount = stats.get("total_amount", 0) if stats else 0
    
    lines.append("### 🌡️ 二、大盘环境")
    lines.append(f"- **涨跌比**: {up} : {down} ({ratio}:1)")
    lines.append(f"- **涨停/跌停**: {limit_up_total} 家 / {limit_down_total} 家")
    lines.append(f"- **两市成交**: {total_amount:.2f} 亿")
    lines.append("")
    
    # ========== 三、趋势分析（近5日对比） ==========
    trend = data.get("trend", {})
    if trend:
        lines.append("### 📊 三、趋势分析（近5日对比）")
        
        # 量能
        vol = trend.get("volume", {})
        if vol:
            vol_emoji = "📈" if vol.get("change_pct", 0) >= 0 else "📉"
            lines.append(f"- {vol_emoji} **量能**: {vol.get('today', 0):.2f}亿 vs 5日均量 {vol.get('avg_5d', 0):.2f}亿 ({vol.get('change_pct', 0):+.1f}%)")
        
        # 上证指数
        sh = trend.get("sh_index", {})
        if sh:
            sh_emoji = "📈" if sh.get("change_pct", 0) >= 0 else "📉"
            lines.append(f"- {sh_emoji} **上证**: {sh.get('today_close', 0):.2f} vs 5日均价 {sh.get('avg_5d_close', 0):.2f} ({sh.get('change_pct', 0):+.2f}%)")
        
        # 涨跌比
        ud = trend.get("up_down_ratio", {})
        if ud:
            ud_emoji = "📈" if ud.get("change_pct", 0) >= 0 else "📉"
            lines.append(f"- {ud_emoji} **涨跌比**: {ud.get('today', 0):.1f}:1 vs 5日均值 {ud.get('avg_5d', 0):.1f}:1 ({ud.get('change_pct', 0):+.1f}%)")
        
        # 涨停数
        lu = trend.get("limit_up", {})
        if lu:
            lu_emoji = "📈" if lu.get("change_pct", 0) >= 0 else "📉"
            lines.append(f"- {lu_emoji} **涨停**: {lu.get('today', 0)}家 vs 5日均值 {lu.get('avg_5d', 0):.1f}家 ({lu.get('change_pct', 0):+.1f}%)")
        
        # 跌停数
        ld = trend.get("limit_down", {})
        if ld:
            ld_emoji = "📈" if ld.get("change_pct", 0) >= 0 else "📉"
            lines.append(f"- {ld_emoji} **跌停**: {ld.get('today', 0)}家 vs 5日均值 {ld.get('avg_5d', 0):.1f}家 ({ld.get('change_pct', 0):+.1f}%)")
        lines.append("")
    
    # ========== 四、市场情绪 ==========
    sentiment = data.get("sentiment", {})
    limit_up_details = data.get("limit_up_details", {})
    if sentiment or limit_up_details:
        lines.append("### 😊 四、市场情绪")
        
        # 从 limit_up_details 获取准确的涨停数据
        limit_up_total = limit_up_details.get("limit_up_count", 0) if limit_up_details else 0
        continuous_boards = limit_up_details.get("continuous_boards", []) if limit_up_details else []
        continuous = len([s for s in continuous_boards if s.get("boards", 1) > 1])
        first_board = limit_up_total - continuous
        
        # 连板高度
        max_height = 0
        max_height_stock = ""
        if continuous_boards:
            max_stock = max(continuous_boards, key=lambda x: x.get("boards", 1))
            max_height = max_stock.get("boards", 1)
            max_height_stock = max_stock.get("name", "")
        
        if max_height > 1 and max_height_stock:
            lines.append(f"- **连板高度**: {max_height} 板 ({max_height_stock})")
        
        lines.append(f"- **涨停家数**: {limit_up_total} 家（首板 {first_board} / 连板 {continuous}）")
        lines.append("")
    
    # ========== 五、涨跌停详情 ==========
    if limit_up_details:
        lines.append("### 🔥 五、涨跌停详情")
        lu_count = limit_up_details.get("limit_up_count", 0)
        ld_count = limit_up_details.get("limit_down_count", 0)
        bk_count = limit_up_details.get("broken_count", 0)
        lines.append(f"- **涨停**: {lu_count} 家 | **跌停**: {ld_count} 家 | **炸板**: {bk_count} 次")
        lines.append("")
        
        # 连板股表格展示
        continuous_boards = limit_up_details.get("continuous_boards", [])
        if continuous_boards:
            # 按连板数分组
            board_groups = {}
            for stock in continuous_boards:
                boards = stock.get("boards", 1)
                if boards > 1:  # 只显示连板股
                    if boards not in board_groups:
                        board_groups[boards] = []
                    board_groups[boards].append(stock)
            
            # 从高到低显示连板股表格（按连板数聚合，一行显示所有同板数股票）
            if board_groups:
                lines.append("**【连板股表格】**")
                lines.append("| 连板数 | 股票详情（名称-概念-封单） |")
                lines.append("|--------|---------------------------|")
                for boards in sorted(board_groups.keys(), reverse=True):
                    stocks = board_groups[boards]
                    # 将同板数的所有股票信息聚合到一个单元格
                    stock_details = []
                    for s in stocks:
                        name = s.get("name", "")
                        industry = s.get("industry", "其他")
                        seal = s.get("seal_amount", 0)
                        stock_details.append(f"{name}({industry}/{seal:.1f}亿)")
                    lines.append(f"| {boards}板 | {'；'.join(stock_details)} |")
                lines.append("")
        
        # 热门概念板块（涨跌幅各Top5）
        concept_dist = limit_up_details.get("concept_distribution", [])
        if concept_dist:
            # 分离涨跌
            up_concepts = [c for c in concept_dist if c.get("change_pct", 0) >= 0]
            down_concepts = [c for c in concept_dist if c.get("change_pct", 0) < 0]
            
            lines.append("**【概念板块涨幅Top5】**")
            lines.append("| 排名 | 概念名称 | 涨跌幅 | 领涨股 |")
            lines.append("|------|----------|--------|--------|")
            for i, concept in enumerate(up_concepts[:5], 1):
                name = concept.get("name", "")
                change_pct = concept.get("change_pct", 0)
                leading = concept.get("leading_stock", "")
                lines.append(f"| {i} | {name} | {change_pct:+.2f}% | {leading} |")
            lines.append("")
            
            if down_concepts:
                lines.append("**【概念板块跌幅Top5】**")
                lines.append("| 排名 | 概念名称 | 涨跌幅 | 领跌股 |")
                lines.append("|------|----------|--------|--------|")
                for i, concept in enumerate(down_concepts[:5], 1):
                    name = concept.get("name", "")
                    change_pct = concept.get("change_pct", 0)
                    leading = concept.get("leading_stock", "")
                    lines.append(f"| {i} | {name} | {change_pct:+.2f}% | {leading} |")
                lines.append("")
    
    # ========== 六、跌停股票 ==========
    if limit_up_details and limit_up_details.get("limit_down_list"):
        lines.append("### ❄️ 六、跌停股票")
        ld_list = limit_up_details.get("limit_down_list", [])
        for stock in ld_list[:10]:  # 最多显示10只
            name = stock.get("name", "")
            industry = stock.get("industry", "其他")
            change_pct = stock.get("change_pct", -10.0)
            lines.append(f"- **{name}** ({industry}) {change_pct:+.2f}%")
        if len(ld_list) > 10:
            lines.append(f"- *... 还有 {len(ld_list) - 10} 只跌停股*")
        lines.append("")
    
    # ========== 七、热门股票榜单 ==========
    hot_ranking = data.get("hot_ranking", [])
    if hot_ranking:
        lines.append("### 🔥 七、热门股票榜单Top20")
        # 只提取股票名称，用逗号分隔
        hot_names = [s.get("name", "") for s in hot_ranking if s.get("name")]
        if hot_names:
            lines.append("、".join(hot_names))
        lines.append("")
    
    lines.append("---")
    lines.append("*数据仅供参考，投资有风险*")
    
    return "\n".join(lines)