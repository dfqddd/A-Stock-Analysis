"""
趋势股筛选器 - 四层过滤模型

第一层：硬性过滤（市值 > 150亿、排除 ST/北交所、排除停牌、流动性）
第二层：趋势确认（多头排列、价格在均线上方、涨幅适中、底部抬高）
第三层：量价健康（温和放量、涨时放量、非异常放量、换手率适中）
第四层：板块共振（所属行业强势、板块内有涨停）

数据源：本地 SQLite 数据库 + 实时市值接口（可选）
"""

import argparse
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

DB_PATH = "data/market.db"

# ─────────────────────────────────────────────
# 数据加载
# ─────────────────────────────────────────────

def get_latest_trade_date(conn: sqlite3.Connection) -> str:
    """获取最新交易日"""
    row = conn.execute("SELECT MAX(date) FROM stock_daily").fetchone()
    return row[0] if row else ""


def get_recent_trade_dates(conn: sqlite3.Connection, num_days: int = 25) -> List[str]:
    """获取最近 N 个交易日列表（降序）"""
    rows = conn.execute(
        "SELECT DISTINCT date FROM stock_daily ORDER BY date DESC LIMIT ?",
        (num_days,),
    ).fetchall()
    return [r[0] for r in rows]


def load_stock_info(conn: sqlite3.Connection) -> pd.DataFrame:
    """加载股票基础信息"""
    df = pd.read_sql_query(
        "SELECT code, name, market, board, industry, total_market_cap_yi FROM stock_info",
        conn,
    )
    return df


def load_stock_daily(conn: sqlite3.Connection, trade_dates: List[str]) -> pd.DataFrame:
    """加载最近 N 个交易日的日线数据"""
    placeholders = ",".join(["?"] * len(trade_dates))
    df = pd.read_sql_query(
        f"""
        SELECT date, code, name, open, close, high, low, volume, amount, change_pct
        FROM stock_daily
        WHERE date IN ({placeholders})
        ORDER BY code, date
        """,
        conn,
        params=trade_dates,
    )
    return df


def load_limit_up_detail(conn: sqlite3.Connection, trade_dates: List[str]) -> pd.DataFrame:
    """加载涨停明细"""
    placeholders = ",".join(["?"] * len(trade_dates))
    df = pd.read_sql_query(
        f"""
        SELECT date, code, name, status, industry
        FROM limit_up_detail
        WHERE date IN ({placeholders})
        """,
        conn,
        params=trade_dates,
    )
    return df


# ─────────────────────────────────────────────
# 市值获取（多数据源）
# ─────────────────────────────────────────────

def fetch_market_cap_from_eastmoney() -> Dict[str, float]:
    """从东财实时行情获取总市值（单位：亿元）"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        cap_map = {}
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).zfill(6)
            total_mv = float(row.get("总市值", 0) or 0)
            if total_mv > 0:
                cap_map[code] = total_mv / 1e8  # 转为亿
        print(f"  📡 东财实时市值: {len(cap_map)} 只")
        return cap_map
    except Exception as e:
        print(f"  ⚠️ 东财市值获取失败: {e}")
        return {}


def fetch_market_cap_from_tushare() -> Dict[str, float]:
    """从 Tushare daily_basic 获取总市值（单位：亿元）"""
    try:
        import yaml
        import tushare as ts
        with open("config/config.yaml") as f:
            cfg = yaml.safe_load(f)
        token = cfg.get("data_source", {}).get("tushare", {}).get("token", "")
        if not token:
            return {}
        pro = ts.pro_api(token)
        df = pro.daily_basic(
            trade_date=datetime.now().strftime("%Y%m%d"),
            fields="ts_code,total_mv,circ_mv,turnover_rate",
        )
        cap_map = {}
        for _, row in df.iterrows():
            code = row["ts_code"][:6]
            total_mv = float(row.get("total_mv", 0) or 0)
            if total_mv > 0:
                cap_map[code] = total_mv / 1e4  # Tushare 单位是万元，转为亿
        print(f"  📡 Tushare 市值: {len(cap_map)} 只")
        return cap_map
    except Exception as e:
        print(f"  ⚠️ Tushare 市值获取失败: {e}")
        return {}


def fetch_market_cap_from_baostock(date_str: str) -> Dict[str, float]:
    """从 baostock 获取总市值（单位：亿元）"""
    try:
        import baostock as bs
        lg = bs.login()
        if lg.error_code != "0":
            return {}

        # baostock 需要逐只股票查询，太慢
        # 改用从本地数据推算：市值 = close * volume / turnover_rate
        bs.logout()
        return {}
    except Exception:
        return {}


def get_market_cap(conn: sqlite3.Connection, latest_date: str) -> Dict[str, float]:
    """
    获取总市值映射（code -> 亿元）

    优先级：东财实时 > Tushare > 本地 stock_info
    """
    print("📊 获取市值数据...")

    # 1. 尝试东财实时
    cap_map = fetch_market_cap_from_eastmoney()
    if len(cap_map) > 3000:
        return cap_map

    # 2. 尝试 Tushare
    if len(cap_map) < 3000:
        tushare_map = fetch_market_cap_from_tushare()
        if len(tushare_map) > len(cap_map):
            cap_map = tushare_map

    # 3. 兜底：用本地 stock_info 已有数据
    if len(cap_map) < 3000:
        rows = conn.execute(
            "SELECT code, total_market_cap_yi FROM stock_info WHERE total_market_cap_yi > 0"
        ).fetchall()
        local_count = 0
        for code, cap in rows:
            if code not in cap_map:
                cap_map[code] = cap
                local_count += 1
        if local_count > 0:
            print(f"  📁 本地补充: {local_count} 只")

    print(f"  ✅ 总计获取市值: {len(cap_map)} 只")
    return cap_map


# ─────────────────────────────────────────────
# 第一层：硬性过滤
# ─────────────────────────────────────────────

def hard_filter(
    stock_info: pd.DataFrame,
    daily_df: pd.DataFrame,
    cap_map: Dict[str, float],
    recent_5_dates: List[str],
    min_market_cap: float = 150.0,
    min_avg_amount_yi: float = 5.0,
) -> pd.DataFrame:
    """
    硬性过滤：
    - 总市值 > min_market_cap 亿
    - 排除 ST/*ST
    - 排除北交所
    - 排除停牌（近5日无交易数据）
    - 近5日日均成交额 > min_avg_amount_yi 亿
    """
    # 添加市值列
    stock_info = stock_info.copy()
    stock_info["market_cap"] = stock_info["code"].map(cap_map)

    # 1. 排除 ST
    mask_not_st = ~stock_info["name"].str.contains("ST", case=False, na=False)

    # 2. 排除北交所（market=bj 或 board 含北交所 或 code 以 4/8/92 开头）
    mask_not_bj = ~(
        (stock_info["market"] == "bj")
        | stock_info["code"].str.startswith("4")
        | stock_info["code"].str.startswith("8")
        | stock_info["code"].str.startswith("92")
    )

    # 3. 市值过滤
    has_cap = stock_info["market_cap"].notna() & (stock_info["market_cap"] > 0)
    mask_cap = has_cap & (stock_info["market_cap"] >= min_market_cap)

    # 如果市值数据不足（覆盖率低于50%），放宽条件：有市值的必须 > 阈值，无市值的保留
    cap_coverage = has_cap.sum() / len(stock_info)
    if cap_coverage < 0.5:
        print(f"  ⚠️ 市值覆盖率仅 {cap_coverage:.0%}，放宽过滤：无市值的股票暂时保留")
        mask_cap = mask_cap | (~has_cap)

    # 组合基础过滤
    filtered = stock_info[mask_not_st & mask_not_bj & mask_cap].copy()

    # 4. 排除停牌 + 成交额过滤（需要用 daily 数据）
    recent_5 = daily_df[daily_df["date"].isin(recent_5_dates)]
    trade_stats = (
        recent_5.groupby("code")
        .agg(
            trade_days=("date", "nunique"),
            avg_amount=("amount", "mean"),
        )
        .reset_index()
    )

    # 近5日有至少3天交易（排除停牌）
    trade_stats = trade_stats[trade_stats["trade_days"] >= 3]

    # 日均成交额 > 阈值（amount 单位是元，转为亿）
    trade_stats["avg_amount_yi"] = trade_stats["avg_amount"] / 1e8
    trade_stats = trade_stats[trade_stats["avg_amount_yi"] >= min_avg_amount_yi]

    # 合并
    result = filtered.merge(
        trade_stats[["code", "avg_amount_yi"]], on="code", how="inner"
    )

    return result


# ─────────────────────────────────────────────
# 第二层：趋势确认
# ─────────────────────────────────────────────

def compute_ma_indicators(daily_df: pd.DataFrame, trade_dates: List[str]) -> pd.DataFrame:
    """
    计算均线和趋势指标：
    - MA5, MA10, MA20
    - 近20日涨幅
    - 近10日最低价, 近20日最低价
    - MA20斜率（MA20今日 - MA20 5日前）
    """
    latest_date = trade_dates[0]
    dates_5 = trade_dates[:5]
    dates_10 = trade_dates[:10]
    dates_20 = trade_dates[:20]

    results = []

    for code, group in daily_df.groupby("code"):
        group = group.sort_values("date")

        if len(group) < 20:
            continue

        # 最新一天数据
        latest = group[group["date"] == latest_date]
        if latest.empty:
            continue
        latest_row = latest.iloc[0]

        closes = group["close"].values
        current_close = latest_row["close"]

        # MA 计算
        ma5 = closes[-5:].mean() if len(closes) >= 5 else None
        ma10 = closes[-10:].mean() if len(closes) >= 10 else None
        ma20 = closes[-20:].mean() if len(closes) >= 20 else None

        if ma5 is None or ma10 is None or ma20 is None:
            continue

        # MA20 斜率：MA20今日 - MA20 5日前
        if len(closes) >= 25:
            ma20_5ago = closes[-25:-5].mean() if len(closes) >= 25 else closes[-20:].mean()
        else:
            ma20_5ago = ma20
        ma20_slope = round(ma20 - ma20_5ago, 3)

        # 近20日涨幅
        close_20_ago = group[group["date"].isin(dates_20)].iloc[0]["close"] if len(group[group["date"].isin(dates_20)]) > 0 else current_close
        pct_20d = round((current_close / close_20_ago - 1) * 100, 2) if close_20_ago > 0 else 0

        # 近10日最低价 vs 近20日最低价
        low_10d = group[group["date"].isin(dates_10)]["low"].min()
        low_20d = group[group["date"].isin(dates_20)]["low"].min()

        results.append({
            "code": code,
            "close": current_close,
            "change_pct": latest_row["change_pct"],
            "ma5": round(ma5, 2),
            "ma10": round(ma10, 2),
            "ma20": round(ma20, 2),
            "ma20_slope": ma20_slope,
            "pct_20d": pct_20d,
            "low_10d": low_10d,
            "low_20d": low_20d,
        })

    return pd.DataFrame(results)


def trend_filter(candidates: pd.DataFrame, ma_df: pd.DataFrame) -> pd.DataFrame:
    """
    趋势确认：
    - 多头排列：MA5 > MA10 > MA20
    - 价格在均线上方：close > MA20 且 close > MA10
    - 近20日涨幅 5%~30%
    - 底部抬高：近10日最低 > 近20日最低
    """
    merged = candidates.merge(ma_df, on="code", how="inner")

    mask = (
        # 多头排列
        (merged["ma5"] > merged["ma10"])
        & (merged["ma10"] > merged["ma20"])
        # 价格在均线上方
        & (merged["close"] > merged["ma20"])
        & (merged["close"] > merged["ma10"])
        # 近20日涨幅适中
        & (merged["pct_20d"] >= 5)
        & (merged["pct_20d"] <= 30)
        # 底部抬高
        & (merged["low_10d"] > merged["low_20d"])
    )

    return merged[mask].copy()


# ─────────────────────────────────────────────
# 第三层：量价健康
# ─────────────────────────────────────────────

def compute_volume_indicators(
    daily_df: pd.DataFrame, trade_dates: List[str], cap_map: Dict[str, float]
) -> pd.DataFrame:
    """
    计算量价指标：
    - 近5日平均成交量 vs 近20日平均成交量（量比）
    - 阳线成交量 vs 阴线成交量
    - 最近1日成交量 vs 近5日平均成交量
    - 换手率（从成交额和市值反推）
    """
    latest_date = trade_dates[0]
    dates_5 = trade_dates[:5]
    dates_20 = trade_dates[:20]

    results = []

    for code, group in daily_df.groupby("code"):
        group = group.sort_values("date")

        if len(group) < 20:
            continue

        latest = group[group["date"] == latest_date]
        if latest.empty:
            continue

        recent_5 = group[group["date"].isin(dates_5)]
        recent_20 = group[group["date"].isin(dates_20)]

        if len(recent_5) < 3 or len(recent_20) < 10:
            continue

        vol_avg_5 = recent_5["volume"].mean()
        vol_avg_20 = recent_20["volume"].mean()
        vol_latest = latest.iloc[0]["volume"]

        # 量比
        volume_ratio = round(vol_avg_5 / vol_avg_20, 2) if vol_avg_20 > 0 else 0

        # 阳线 vs 阴线成交量（近20日）
        bullish = recent_20[recent_20["change_pct"] > 0]
        bearish = recent_20[recent_20["change_pct"] < 0]
        bull_vol = bullish["volume"].mean() if len(bullish) > 0 else 0
        bear_vol = bearish["volume"].mean() if len(bearish) > 0 else 1

        # 最新量 / 近5日均量
        vol_spike = round(vol_latest / vol_avg_5, 2) if vol_avg_5 > 0 else 0

        # 换手率：近5日日均成交额 / 总市值
        amt_avg_5 = recent_5["amount"].mean()
        market_cap = cap_map.get(code, 0)
        if market_cap > 0:
            turnover_rate = round(amt_avg_5 / (market_cap * 1e8) * 100, 2)
        else:
            turnover_rate = None

        results.append({
            "code": code,
            "volume_ratio": volume_ratio,
            "bull_bear_vol_ratio": round(bull_vol / bear_vol, 2) if bear_vol > 0 else 999,
            "vol_spike": vol_spike,
            "turnover_rate_5d": turnover_rate,
        })

    return pd.DataFrame(results)


def volume_price_filter(candidates: pd.DataFrame, vol_df: pd.DataFrame) -> pd.DataFrame:
    """
    量价健康过滤：
    - 温和放量：近5日均量 > 近20日均量 * 1.2（volume_ratio > 1.2）
    - 涨时放量：阳线均量 > 阴线均量（bull_bear_vol_ratio > 1.0）
    - 非异常放量：最新量 < 近5日均量 * 3（vol_spike < 3）
    - 换手率适中：2%~8%
    """
    merged = candidates.merge(vol_df, on="code", how="inner")

    mask = (
        (merged["volume_ratio"] >= 1.2)
        & (merged["bull_bear_vol_ratio"] > 1.0)
        & (merged["vol_spike"] < 3.0)
    )

    # 换手率过滤（有值的才过滤）
    has_turnover = merged["turnover_rate_5d"].notna()
    turnover_ok = (merged["turnover_rate_5d"] >= 2) & (merged["turnover_rate_5d"] <= 8)
    mask = mask & (turnover_ok | ~has_turnover)

    return merged[mask].copy()


# ─────────────────────────────────────────────
# 第四层：板块共振
# ─────────────────────────────────────────────

def compute_sector_strength(
    daily_df: pd.DataFrame,
    stock_info: pd.DataFrame,
    limit_up_df: pd.DataFrame,
    trade_dates: List[str],
) -> Tuple[Dict[str, float], Dict[str, int]]:
    """
    计算板块强度：
    - 行业近5日平均涨幅
    - 行业近3日涨停数
    """
    dates_5 = trade_dates[:5]
    dates_3 = trade_dates[:3]

    # 构建 code -> industry 映射
    code_industry = dict(zip(stock_info["code"], stock_info["industry"]))

    # 计算行业近5日平均涨幅
    recent_5 = daily_df[daily_df["date"].isin(dates_5)].copy()
    recent_5["industry"] = recent_5["code"].map(code_industry)
    recent_5 = recent_5[recent_5["industry"].notna() & (recent_5["industry"] != "")]

    sector_pct = (
        recent_5.groupby("industry")["change_pct"]
        .mean()
        .to_dict()
    )

    # 计算行业近3日涨停数
    # 注意：limit_up_detail.industry 是东财分类（如"元件"），与 stock_info.industry 的
    # 证监会分类（如"计算机、通信和其他电子设备制造业"）不匹配，必须统一用 code 关联到
    # stock_info.industry
    recent_3_limit = limit_up_df[
        (limit_up_df["date"].isin(dates_3))
        & (limit_up_df["status"].isin(["涨停", "limit_up"]))
    ].copy()

    recent_3_limit["csrc_industry"] = recent_3_limit["code"].map(code_industry)

    sector_limit_up = (
        recent_3_limit[recent_3_limit["csrc_industry"].notna() & (recent_3_limit["csrc_industry"] != "")]
        .groupby("csrc_industry")["code"]
        .nunique()
        .to_dict()
    )

    return sector_pct, sector_limit_up


def sector_filter(
    candidates: pd.DataFrame,
    stock_info: pd.DataFrame,
    sector_pct: Dict[str, float],
    sector_limit_up: Dict[str, int],
) -> pd.DataFrame:
    """
    板块共振过滤：
    - 所属行业近5日涨幅 > 0
    - 所属行业近3日涨停 >= 2 只
    """
    # 关联行业
    code_industry = dict(zip(stock_info["code"], stock_info["industry"]))
    candidates = candidates.copy()
    candidates["industry"] = candidates["code"].map(code_industry)

    # 行业涨幅
    candidates["sector_pct_5d"] = candidates["industry"].map(sector_pct)

    # 行业涨停数
    candidates["sector_limit_up_3d"] = candidates["industry"].map(sector_limit_up).fillna(0).astype(int)

    mask = (
        candidates["industry"].notna()
        & (candidates["industry"] != "")
        & (candidates["sector_pct_5d"].notna())
        & (candidates["sector_pct_5d"] > 0)
        & (candidates["sector_limit_up_3d"] >= 2)
    )

    return candidates[mask].copy()


# ─────────────────────────────────────────────
# 评分系统
# ─────────────────────────────────────────────

def compute_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    综合评分（满分 100）：
    - 趋势强度（30分）：MA20斜率、多头排列程度
    - 量价配合（30分）：量比、阳线放量程度
    - 板块共振（20分）：板块涨幅、板块涨停数
    - 涨幅空间（20分）：近20日涨幅越低越好（说明还有空间）
    """
    df = df.copy()

    # 趋势强度（30分）
    # MA20斜率归一化（0~1）
    slope_min = df["ma20_slope"].min()
    slope_max = df["ma20_slope"].max()
    slope_range = slope_max - slope_min if slope_max > slope_min else 1
    df["score_trend"] = ((df["ma20_slope"] - slope_min) / slope_range * 30).clip(0, 30)

    # 量价配合（30分）
    # 量比越高越好（上限3），阳线放量比越高越好
    vol_ratio_score = (df["volume_ratio"].clip(1, 3) - 1) / 2 * 15
    bull_bear_score = (df["bull_bear_vol_ratio"].clip(1, 3) - 1) / 2 * 15
    df["score_volume"] = (vol_ratio_score + bull_bear_score).clip(0, 30)

    # 板块共振（20分）
    sector_pct_score = df["sector_pct_5d"].clip(0, 3) / 3 * 10
    sector_lu_score = df["sector_limit_up_3d"].clip(0, 10) / 10 * 10
    df["score_sector"] = (sector_pct_score + sector_lu_score).clip(0, 20)

    # 涨幅空间（20分）：涨幅越低分越高（5%~30% 映射到 20~0）
    df["score_space"] = ((30 - df["pct_20d"]) / 25 * 20).clip(0, 20)

    # 总分
    df["score"] = (
        df["score_trend"] + df["score_volume"] + df["score_sector"] + df["score_space"]
    ).round(1)

    return df


# ─────────────────────────────────────────────
# 输出格式化
# ─────────────────────────────────────────────

def format_output(df: pd.DataFrame, stock_info: pd.DataFrame) -> str:
    """格式化输出结果"""
    # 按评分降序排列
    df = df.sort_values("score", ascending=False).head(30)

    # 获取股票名称
    code_name = dict(zip(stock_info["code"], stock_info["name"]))

    lines = []
    lines.append("=" * 100)
    lines.append(f"📈 趋势股筛选结果 | 筛选日期: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("=" * 100)
    lines.append("")

    header = f"{'排名':>4} {'代码':<8} {'名称':<10} {'市值(亿)':>8} {'现价':>8} {'涨跌%':>7} {'MA5':>8} {'MA10':>8} {'MA20':>8} {'MA斜率':>7} {'量比':>5} {'板块':>16} {'评分':>5}"
    lines.append(header)
    lines.append("-" * 100)

    for i, (_, row) in enumerate(df.iterrows(), 1):
        name = code_name.get(row["code"], "")[:6]
        market_cap = f"{row.get('market_cap', 0):.0f}" if pd.notna(row.get("market_cap")) and row.get("market_cap", 0) > 0 else "N/A"
        industry = str(row.get("industry", ""))[:8]

        line = (
            f"{i:>4} "
            f"{row['code']:<8} "
            f"{name:<10} "
            f"{market_cap:>8} "
            f"{row['close']:>8.2f} "
            f"{row['change_pct']:>+6.2f}% "
            f"{row['ma5']:>8.2f} "
            f"{row['ma10']:>8.2f} "
            f"{row['ma20']:>8.2f} "
            f"{row['ma20_slope']:>+6.3f} "
            f"{row['volume_ratio']:>5.2f} "
            f"{industry:>16} "
            f"{row['score']:>5.1f}"
        )
        lines.append(line)

    lines.append("-" * 100)
    lines.append(f"共筛选出 {len(df)} 只趋势股（显示前30只）")
    lines.append("")

    # 分项得分明细（前10名）
    lines.append("📊 前10名分项得分明细：")
    lines.append(f"{'排名':>4} {'代码':<8} {'名称':<10} {'趋势(30)':>8} {'量价(30)':>8} {'板块(20)':>8} {'空间(20)':>8} {'总分':>6}")
    lines.append("-" * 80)
    for i, (_, row) in enumerate(df.head(10).iterrows(), 1):
        name = code_name.get(row["code"], "")[:6]
        lines.append(
            f"{i:>4} "
            f"{row['code']:<8} "
            f"{name:<10} "
            f"{row['score_trend']:>8.1f} "
            f"{row['score_volume']:>8.1f} "
            f"{row['score_sector']:>8.1f} "
            f"{row['score_space']:>8.1f} "
            f"{row['score']:>6.1f}"
        )

    return "\n".join(lines)


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="趋势股筛选器")
    parser.add_argument("--min-cap", type=float, default=150, help="最低总市值（亿），默认150")
    parser.add_argument("--min-amount", type=float, default=5, help="最低日均成交额（亿），默认5")
    parser.add_argument("--skip-realtime", action="store_true", help="跳过实时市值获取，仅用本地数据")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)

    # 获取交易日列表
    trade_dates = get_recent_trade_dates(conn, 25)
    latest_date = trade_dates[0]
    print(f"📅 最新交易日: {latest_date}，共加载 {len(trade_dates)} 个交易日\n")

    # 加载数据
    print("📥 加载数据...")
    stock_info = load_stock_info(conn)
    daily_df = load_stock_daily(conn, trade_dates)
    limit_up_df = load_limit_up_detail(conn, trade_dates[:5])
    print(f"  股票基础信息: {len(stock_info)} 只")
    print(f"  日线数据: {len(daily_df)} 条 ({daily_df['code'].nunique()} 只)")
    print(f"  涨停明细: {len(limit_up_df)} 条\n")

    # 获取市值
    if args.skip_realtime:
        print("📊 使用本地市值数据（跳过实时获取）...")
        rows = conn.execute(
            "SELECT code, total_market_cap_yi FROM stock_info WHERE total_market_cap_yi > 0"
        ).fetchall()
        cap_map = {r[0]: r[1] for r in rows}
        print(f"  ✅ 本地市值: {len(cap_map)} 只\n")
    else:
        cap_map = get_market_cap(conn, latest_date)
        print()

    # ── 第一层：硬性过滤 ──
    print("🔍 第一层：硬性过滤...")
    candidates = hard_filter(
        stock_info, daily_df, cap_map,
        recent_5_dates=trade_dates[:5],
        min_market_cap=args.min_cap,
        min_avg_amount_yi=args.min_amount,
    )
    print(f"  ✅ 通过: {len(candidates)} 只（市值>{args.min_cap}亿, 成交额>{args.min_amount}亿, 非ST/北交所）\n")

    if candidates.empty:
        print("❌ 第一层过滤后无结果")
        conn.close()
        return

    # ── 第二层：趋势确认 ──
    print("📈 第二层：趋势确认...")
    ma_df = compute_ma_indicators(daily_df, trade_dates)
    candidates = trend_filter(candidates, ma_df)
    print(f"  ✅ 通过: {len(candidates)} 只（多头排列 + 涨幅5~30% + 底部抬高）\n")

    if candidates.empty:
        print("❌ 第二层过滤后无结果")
        conn.close()
        return

    # ── 第三层：量价健康 ──
    print("📊 第三层：量价健康...")
    vol_df = compute_volume_indicators(daily_df, trade_dates, cap_map)
    candidates = volume_price_filter(candidates, vol_df)
    print(f"  ✅ 通过: {len(candidates)} 只（温和放量 + 涨时放量 + 换手率适中）\n")

    if candidates.empty:
        print("❌ 第三层过滤后无结果")
        conn.close()
        return

    # ── 第四层：板块共振 ──
    print("🔥 第四层：板块共振...")
    sector_pct, sector_limit_up = compute_sector_strength(
        daily_df, stock_info, limit_up_df, trade_dates
    )
    candidates = sector_filter(candidates, stock_info, sector_pct, sector_limit_up)
    print(f"  ✅ 通过: {len(candidates)} 只（板块强势 + 板块有涨停）\n")

    if candidates.empty:
        print("❌ 第四层过滤后无结果，尝试放宽板块条件...")
        # 放宽：只要求板块涨幅 > 0，不要求涨停数
        candidates_relaxed = volume_price_filter(
            trend_filter(
                hard_filter(stock_info, daily_df, cap_map, trade_dates[:5], args.min_cap, args.min_amount),
                ma_df,
            ),
            vol_df,
        )
        if not candidates_relaxed.empty:
            code_industry_map = dict(zip(stock_info["code"], stock_info["industry"]))
            candidates_relaxed = candidates_relaxed.copy()
            candidates_relaxed["industry"] = candidates_relaxed["code"].map(code_industry_map)
            candidates_relaxed["sector_pct_5d"] = candidates_relaxed["industry"].map(sector_pct)
            candidates_relaxed["sector_limit_up_3d"] = candidates_relaxed["industry"].map(sector_limit_up).fillna(0).astype(int)

            # 放宽条件：板块涨幅 > 0 即可
            mask = candidates_relaxed["sector_pct_5d"].notna() & (candidates_relaxed["sector_pct_5d"] > 0)
            candidates = candidates_relaxed[mask].copy()
            print(f"  ✅ 放宽后通过: {len(candidates)} 只（仅要求板块涨幅>0）\n")

    if candidates.empty:
        print("❌ 所有过滤后无结果，当前市场可能没有符合条件的趋势股")
        conn.close()
        return

    # ── 评分 & 输出 ──
    print("🏆 评分排名...")
    candidates = compute_score(candidates)
    output = format_output(candidates, stock_info)
    print()
    print(output)

    conn.close()


if __name__ == "__main__":
    main()
