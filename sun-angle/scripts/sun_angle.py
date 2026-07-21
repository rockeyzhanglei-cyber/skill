#!/usr/bin/env python3
"""
太阳方位角与仰角计算器
用法：python sun_angle.py --date 2026-04-30 --lat 36.06 --lon 103.83 --elev 1520 --facing 45
"""
import argparse
import math
from datetime import datetime, timezone, timedelta


def julian_day(dt_utc: datetime) -> float:
    """计算儒略日"""
    a = (14 - dt_utc.month) // 12
    y = dt_utc.year + 4800 - a
    m = dt_utc.month + 12 * a - 3
    jdn = dt_utc.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    jd = jdn + (dt_utc.hour - 12) / 24 + dt_utc.minute / 1440 + dt_utc.second / 86400
    return jd


def sun_position(dt_utc: datetime, lat_deg: float, lon_deg: float):
    """
    计算太阳位置（方位角、仰角）
    返回: (azimuth_north, elevation)
    方位角 azimuth_north: 以正北为0°，顺时针增加
    仰角 elevation: 度
    """
    jd = julian_day(dt_utc)
    n = jd - 2451545.0  # J2000.0 起算天数

    # 平黄经、平近点角
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)

    # 黄经（考虑椭圆轨道修正）
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))

    # 黄赤交角
    eps = math.radians(23.439 - 0.0000004 * n)

    # 赤经、赤纬
    sin_dec = math.sin(eps) * math.sin(lam)
    dec = math.asin(sin_dec)  # 赤纬（弧度）

    # 格林威治恒星时 → 时角
    # 格林威治平恒星时 (度)
    theta0 = (280.46061837 + 360.98564736629 * n) % 360
    # 本地时角
    H = math.radians((theta0 + lon_deg - math.degrees(math.atan2(
        math.cos(eps) * math.sin(lam), math.cos(lam)))) % 360)

    lat = math.radians(lat_deg)

    # 仰角（未修正大气折射）
    sin_elev = (math.sin(lat) * math.sin(dec) +
                math.cos(lat) * math.cos(dec) * math.cos(H))
    elev = math.degrees(math.asin(sin_elev))

    # 大气折射修正（仅在仰角 > -0.575° 时有效）
    if elev > -0.575:
        refraction = 1.02 / math.tan(math.radians(elev + 10.3 / (elev + 5.11))) / 60
        elev += refraction

    # 方位角（正北=0°，顺时针）
    cos_az = (math.sin(dec) - math.sin(lat) * sin_elev) / (math.cos(lat) * math.cos(math.asin(sin_elev)))
    cos_az = max(-1.0, min(1.0, cos_az))
    az = math.degrees(math.acos(cos_az))
    # 判断上午/下午（时角为负时太阳在东边）
    if math.sin(H) > 0:
        az = 360 - az

    return az, elev


def relative_azimuth(sun_az: float, facing: float) -> float:
    """
    将太阳绝对方位角转换为相对朝向的方位角
    facing: 朝向偏北角度（顺时针）
    规则: 正前方=90°，右侧=0°，左侧=180°，正后方=270°（或-90°）
    """
    # 太阳相对于朝向的偏差角（顺时针为正）
    diff = (sun_az - facing) % 360
    # diff=0 → 正前方 → 输出 90
    # diff=90 → 右侧 → 输出 0
    # diff=270 → 左侧 → 输出 180
    rel = (90 - diff) % 360
    return rel


def main():
    parser = argparse.ArgumentParser(description="太阳方位角与仰角计算")
    parser.add_argument("--date", required=True, help="日期，格式 YYYY-MM-DD")
    parser.add_argument("--lat", type=float, required=True, help="纬度（度），北纬为正")
    parser.add_argument("--lon", type=float, required=True, help="经度（度），东经为正")
    parser.add_argument("--elev", type=float, default=0, help="海拔（米），默认0")
    parser.add_argument("--facing", type=float, required=True,
                        help="朝向偏北角（顺时针，度），如正东=90，东北=45")
    parser.add_argument("--tz", type=float, default=8, help="时区偏移（小时），默认+8")
    args = parser.parse_args()

    tz_offset = timedelta(hours=args.tz)
    local_tz = timezone(tz_offset)

    date_obj = datetime.strptime(args.date, "%Y-%m-%d")

    print(f"\n{'='*70}")
    print(f"  日期：{args.date}  坐标：{args.lat}°N {args.lon}°E  海拔：{args.elev}m")
    print(f"  朝向：{args.facing}°（偏北顺时针）  时区：UTC+{args.tz:.0f}")
    print(f"{'='*70}")
    print(f"  {'时间':<8} {'太阳方位角(绝对)':<18} {'相对方位角(前=90°)':<20} {'仰角':<10} {'状态'}")
    print(f"  {'-'*8} {'-'*18} {'-'*20} {'-'*10} {'-'*6}")

    for hour in range(6, 19):
        for minute in [0, 30]:
            if hour == 18 and minute == 30:
                break
            local_dt = datetime(date_obj.year, date_obj.month, date_obj.day,
                                hour, minute, 0, tzinfo=local_tz)
            utc_dt = local_dt.astimezone(timezone.utc)

            az_abs, elev = sun_position(utc_dt, args.lat, args.lon)
            az_rel = relative_azimuth(az_abs, args.facing)

            status = "☀️ 可见" if elev > 0 else "🌑 地平线以下"

            # 海拔修正：海拔越高，地平线修正越大（近似）
            horizon_correction = math.degrees(math.sqrt(2 * args.elev / 6371000))
            if elev > -horizon_correction:
                status = "☀️ 可见" if elev > 0 else f"☀️ 可见(海拔修正+{horizon_correction:.2f}°)"

            time_str = f"{hour:02d}:{minute:02d}"
            print(f"  {time_str:<8} {az_abs:>8.1f}°          {az_rel:>8.1f}°              {elev:>6.1f}°    {status}")

    print(f"{'='*70}")
    print(f"\n  [说明]")
    print(f"  相对方位角：正前方=90°，右侧=0°，左侧=180°，正后方=270°")
    print(f"  太阳方位角：正北=0°，正东=90°，正南=180°，正西=270°（顺时针）\n")


if __name__ == "__main__":
    main()
