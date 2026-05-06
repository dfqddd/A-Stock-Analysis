"""
通过 baostock 获取总股本，结合最新收盘价计算市值并更新到 stock_info 表。

baostock query_profit_data 提供 totalShare（总股本）和 liqaShare（流通股本），
结合 stock_daily 最新收盘价即可计算：
  总市值(亿) = close * totalShare / 1e8
"""

import sqlite3
import sys
import time

import baostock as bs


DB_PATH = "data/market.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取最新交易日
    latest_date = cursor.execute("SELECT MAX(date) FROM stock_daily").fetchone()[0]
    print(f"📅 最新交易日: {latest_date}")

    # 获取所有需要更新市值的股票代码和最新收盘价
    rows = cursor.execute(
        """
        SELECT si.code, sd.close
        FROM stock_info si
        JOIN stock_daily sd ON si.code = sd.code AND sd.date = ?
        WHERE si.code NOT LIKE '4%' AND si.code NOT LIKE '92%'
        ORDER BY si.code
        """,
        (latest_date,),
    ).fetchall()
    print(f"📊 待处理: {len(rows)} 只股票")

    # 登录 baostock
    lg = bs.login()
    if lg.error_code != "0":
        print(f"❌ baostock 登录失败: {lg.error_msg}")
        sys.exit(1)

    updated_count = 0
    error_count = 0
    batch_size = 200

    for i, (code, close_price) in enumerate(rows):
        # 构建 baostock 代码格式
        if code.startswith("6"):
            bscode = f"sh.{code}"
        elif code.startswith("8") or code.startswith("4"):
            continue
        else:
            bscode = f"sz.{code}"

        try:
            # 查询最近的盈利数据（2025Q3 -> 2025Q2 -> 2025Q1 -> 2024Q4 降级）
            total_share = None
            for year, quarter in [(2025, 3), (2025, 2), (2025, 1), (2024, 4)]:
                rs = bs.query_profit_data(code=bscode, year=year, quarter=quarter)
                while rs.error_code == "0" and rs.next():
                    row_data = rs.get_row_data()
                    raw_share = row_data[9]  # totalShare
                    if raw_share and raw_share != "":
                        total_share = float(raw_share)
                        break
                if total_share:
                    break

            if total_share and total_share > 0 and close_price and close_price > 0:
                market_cap_yi = round(close_price * total_share / 1e8, 2)
                cursor.execute(
                    "UPDATE stock_info SET total_market_cap_yi = ? WHERE code = ?",
                    (market_cap_yi, code),
                )
                updated_count += 1
        except Exception:
            error_count += 1

        # 进度报告
        if (i + 1) % batch_size == 0:
            conn.commit()
            progress = (i + 1) / len(rows) * 100
            print(f"  ⏳ {i + 1}/{len(rows)} ({progress:.0f}%) 已更新: {updated_count}, 失败: {error_count}")

    conn.commit()
    bs.logout()

    # 验证结果
    has_cap = cursor.execute(
        "SELECT COUNT(*) FROM stock_info WHERE total_market_cap_yi > 0"
    ).fetchone()[0]
    total = cursor.execute("SELECT COUNT(*) FROM stock_info").fetchone()[0]
    cap_gt_150 = cursor.execute(
        "SELECT COUNT(*) FROM stock_info WHERE total_market_cap_yi >= 150"
    ).fetchone()[0]

    print(f"\n✅ 更新完成！")
    print(f"   已更新: {updated_count} 只")
    print(f"   失败: {error_count} 只")
    print(f"   有市值: {has_cap}/{total}")
    print(f"   市值 >= 150亿: {cap_gt_150}")

    conn.close()


if __name__ == "__main__":
    main()
