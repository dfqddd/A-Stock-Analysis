"""
批量更新 stock_info 表的 industry（行业）字段

数据源优先级：
  1. Tushare stock_basic（行业分类更实用，如"银行"、"软件服务"）
  2. baostock query_stock_industry（证监会行业分类，如"货币金融服务"，作为兜底）
"""

import sqlite3
import re
import sys
import time
import yaml


def load_tushare_token() -> str:
    """从 config.yaml 读取 Tushare token"""
    with open("config/config.yaml") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("data_source", {}).get("tushare", {}).get("token", "")


def fetch_industry_from_tushare() -> dict:
    """从 Tushare 获取行业信息（每小时限 1 次）"""
    import tushare as ts

    token = load_tushare_token()
    if not token:
        print("   ⚠️ 未找到 Tushare token，跳过")
        return {}

    pro = ts.pro_api(token)

    for attempt in range(3):
        try:
            df = pro.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,symbol,name,industry",
            )
            print(f"   Tushare 获取到 {len(df)} 只股票")
            industry_map = {}
            for _, row in df.iterrows():
                code = str(row["symbol"]).zfill(6)
                industry = row.get("industry", "")
                if industry and str(industry) != "nan":
                    industry_map[code] = str(industry)
            return industry_map
        except Exception as e:
            msg = str(e)
            if "最多访问" in msg:
                wait_seconds = 65 if "每分钟" in msg else 120
                print(f"   ⏳ Tushare 频率限制，等待 {wait_seconds}s ({attempt + 1}/3)...")
                time.sleep(wait_seconds)
            else:
                print(f"   ⚠️ Tushare 失败: {e}")
                return {}
    return {}


def fetch_industry_from_baostock() -> dict:
    """从 baostock 获取行业信息（无频率限制，证监会分类）"""
    import baostock as bs

    lg = bs.login()
    if lg.error_code != "0":
        print(f"   ⚠️ baostock 登录失败: {lg.error_msg}")
        return {}

    rs = bs.query_stock_industry()
    industry_map = {}
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        # row: [updateDate, code, code_name, industry, industryClassification]
        raw_code = row[1]  # 如 "sh.600000"
        industry_raw = row[3]  # 如 "J66货币金融服务"

        if not industry_raw:
            continue

        # 提取纯代码（去掉 sh./sz./bj. 前缀）
        code = raw_code.split(".")[-1] if "." in raw_code else raw_code

        # 去掉证监会编码前缀（如 "J66" → "货币金融服务"）
        industry_clean = re.sub(r"^[A-Z]\d{1,2}", "", industry_raw)
        if industry_clean:
            industry_map[code] = industry_clean

    bs.logout()
    print(f"   baostock 获取到 {len(industry_map)} 条行业映射")
    return industry_map


def main():
    print("📡 获取股票行业信息...\n")

    # 1. 优先从 Tushare 获取（行业分类更实用）
    print("  [1/2] 尝试 Tushare...")
    tushare_map = fetch_industry_from_tushare()
    print(f"   → 有效映射: {len(tushare_map)} 条\n")

    # 2. 从 baostock 获取（兜底，证监会分类）
    print("  [2/2] 尝试 baostock...")
    baostock_map = fetch_industry_from_baostock()
    print(f"   → 有效映射: {len(baostock_map)} 条\n")

    # 合并：Tushare 优先，baostock 补充
    industry_map = {}
    industry_map.update(baostock_map)
    industry_map.update(tushare_map)
    print(f"📊 合并后有效映射: {len(industry_map)} 条")

    if not industry_map:
        print("❌ 未获取到任何行业信息")
        sys.exit(1)

    # 更新数据库
    conn = sqlite3.connect("data/market.db")
    cursor = conn.cursor()

    total = cursor.execute("SELECT COUNT(*) FROM stock_info").fetchone()[0]
    current_has_industry = cursor.execute(
        "SELECT COUNT(*) FROM stock_info WHERE industry IS NOT NULL AND industry != ''"
    ).fetchone()[0]
    print(f"\n📊 更新前: {current_has_industry}/{total} 有行业信息")

    # 覆盖更新所有匹配的行业信息
    updated_count = 0
    for code, industry in industry_map.items():
        cursor.execute(
            "UPDATE stock_info SET industry = ? WHERE code = ?",
            (industry, code),
        )
        if cursor.rowcount > 0:
            updated_count += 1

    conn.commit()

    after_has_industry = cursor.execute(
        "SELECT COUNT(*) FROM stock_info WHERE industry IS NOT NULL AND industry != ''"
    ).fetchone()[0]
    print(f"✅ 更新后: {after_has_industry}/{total} 有行业信息")
    print(f"   本次更新: {updated_count} 条")

    # 显示行业分布 TOP15
    print("\n📋 行业分布 TOP15:")
    rows = cursor.execute(
        "SELECT industry, COUNT(*) as cnt FROM stock_info "
        "WHERE industry IS NOT NULL AND industry != '' "
        "GROUP BY industry ORDER BY cnt DESC LIMIT 15"
    ).fetchall()
    for industry_name, count in rows:
        print(f"   {industry_name}: {count}")

    # 检查仍然缺失的
    missing = cursor.execute(
        "SELECT COUNT(*) FROM stock_info WHERE industry IS NULL OR industry = ''"
    ).fetchone()[0]
    if missing > 0:
        print(f"\n⚠️  仍有 {missing} 只股票缺少行业信息")
        missing_samples = cursor.execute(
            "SELECT code, name FROM stock_info WHERE industry IS NULL OR industry = '' LIMIT 10"
        ).fetchall()
        for code, name in missing_samples:
            print(f"   {code} {name}")
    else:
        print("\n✅ 所有股票都有行业信息！")

    conn.close()
    print("\n🎉 行业信息更新完成！")


if __name__ == "__main__":
    main()
