"""黄金行情数据获取层。

封装新浪行情接口，提供统一的行情数据结构。
GUI 层（main.py）只消费 fetch_all_gold() 的结构化结果，不关心字段细节。
"""

from __future__ import annotations

import requests

# 新浪行情接口
SINA_URL = "https://hq.sinajs.cn/list={codes}"
SINA_HEADERS = {"Referer": "https://finance.sina.com.cn"}

# 行情代码
CODE_LONDON = "hf_XAU"      # 伦敦金（现货 XAU）
CODE_NEWYORK = "hf_GC"      # 纽约金（COMEX 期货 GC）
CODE_USDCNY = "fx_susdcny"  # 美元/人民币汇率
CODE_SHANGHAI = "nf_AU0"    # 沪金连续（新浪内盘期货 nf_ 前缀，实时数据）

# 汇率换算：1 金衡盎司 = 31.1034768 克
OUNCE_TO_GRAM = 31.1034768


def _safe_float(val) -> float:
    """安全转 float：空串/非数字/时间字符串返回 0.0"""
    if val is None:
        return 0.0
    s = str(val).strip()
    if not s or s == "0":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def fetch_sina(codes: list[str]) -> dict[str, list[str]]:
    """从新浪接口抓取行情，返回 {code: fields}。

    新浪返回形如 `var hq_str_<code>="field0,field1,...";` 的文本。
    """
    url = SINA_URL.format(codes=",".join(codes))
    r = requests.get(url, headers=SINA_HEADERS, timeout=6)
    r.encoding = "gbk"
    out: dict[str, list[str]] = {}
    for line in r.text.strip().splitlines():
        if not line.startswith("var hq_str_"):
            continue
        try:
            key = line.split("hq_str_")[1].split("=")[0].strip()
            body = line.split('"')[1]
            if not body:
                continue
            out[key] = body.split(",")
        except Exception:
            continue
    return out


def _parse_london(fields: list[str]) -> dict | None:
    """解析伦敦金 hf_XAU 字段。

    字段顺序: [0]现价 [3]最高 [4]最低 [7]昨结 [8]开盘
    """
    if not fields or not fields[0] or fields[0] == "0":
        return None
    price = _safe_float(fields[0])
    if price <= 0:
        return None
    return {
        "price": price,
        "high": fields[3] if len(fields) > 3 else "",
        "low": fields[4] if len(fields) > 4 else "",
        "prev_close": _safe_float(fields[7]) if len(fields) > 7 else 0.0,
    }


def _parse_newyork(fields: list[str]) -> dict | None:
    """解析纽约金 hf_GC 字段。

    字段顺序: [0]现价 [4]最高 [5]最低 [7]昨收
    """
    if not fields or not fields[0] or fields[0] == "0":
        return None
    price = _safe_float(fields[0])
    if price <= 0:
        return None
    return {
        "price": price,
        "high": fields[4] if len(fields) > 4 else "",
        "low": fields[5] if len(fields) > 5 else "",
        "prev_close": _safe_float(fields[7]) if len(fields) > 7 else 0.0,
    }


def _parse_shanghai(fields: list[str]) -> dict | None:
    """解析沪金连续 nf_AU0 字段。

    新浪内盘期货 nf_ 字段顺序（2026-06 实测）:
        [0]名称 [1]时间(HHMMSS) [2]开盘 [3]最高 [4]最低
        [5]买一价 [6]最新价 [7]卖一价 [8]昨收
        [9]最新成交量 [10]昨结 [16]日期
    注: 最新价取 [6]，[5] 为买一价不能用作最新价。
    """
    if not fields or len(fields) < 11:
        return None
    price = _safe_float(fields[6])
    avg_note = ""
    if price <= 0:
        # 最新价缺失时，用买一价 [5] 与卖一价 [7] 的均值兜底
        bid = _safe_float(fields[5])
        ask = _safe_float(fields[7])
        if bid > 0 and ask > 0:
            price = (bid + ask) / 2
            avg_note = "（买卖一价均值）"
        elif bid > 0:
            price = bid
            avg_note = "（买一价）"
        elif ask > 0:
            price = ask
            avg_note = "（卖一价）"
    if price <= 0:
        return None
    return {
        "name": fields[0],
        "price": price,
        "avg_note": avg_note,
        "open": _safe_float(fields[2]),
        "high": _safe_float(fields[3]),
        "low": _safe_float(fields[4]),
        "prev_close": _safe_float(fields[8]),
        "prev_settle": _safe_float(fields[10]),
        "date": fields[16] if len(fields) > 16 else "",
    }


def _parse_usdcny(fields: list[str]) -> float | None:
    """解析 USD/CNY 汇率字段。fields[1] 为现价。"""
    if not fields or len(fields) < 2 or fields[1] == "0.0000":
        return None
    return _safe_float(fields[1])


def _implied_cny_per_gram(usd_price: float, usdcny: float) -> float:
    """国际金价 (USD/oz) × 汇率 ÷ 31.1035 → 上海金理论价 (CNY/g)。"""
    if not usd_price or not usdcny:
        return 0.0
    return usd_price * usdcny / OUNCE_TO_GRAM


def _diff_pct(price: float, prev_close: float) -> tuple[float, float]:
    """计算涨跌额与涨跌幅 (%)。"""
    if not prev_close:
        return 0.0, 0.0
    diff = price - prev_close
    return diff, diff / prev_close * 100


def fetch_all_gold() -> dict:
    """一次性抓取伦敦金、纽约金、上海金及 USD/CNY 汇率。

    返回结构:
        {
            "usdcny": float | None,
            "implied_cny_g": float,           # 折算上海金理论价 (CNY/g)
            "implied_source": str,            # 折算锚定品种名 ("纽约金"/"伦敦金"/"")
            "london":   {price, high, low, prev_close, diff, pct, implied} | None,
            "newyork":  {price, high, low, prev_close, diff, pct, implied} | None,
            "shanghai": {price, high, low, prev_close, diff, pct, implied} | None,
        }
    其中每个品种的 implied 为"折算/基差"副标注文本，已格式化好供卡片直接显示。
    """
    data = fetch_sina([CODE_LONDON, CODE_NEWYORK, CODE_SHANGHAI, CODE_USDCNY])

    usdcny = _parse_usdcny(data.get(CODE_USDCNY, []))
    london = _parse_london(data.get(CODE_LONDON, []))
    newyork = _parse_newyork(data.get(CODE_NEWYORK, []))
    shanghai = _parse_shanghai(data.get(CODE_SHANGHAI, []))

    # 各品种独立折算 CNY/g（用各自价格 × 汇率 ÷ 31.1035）
    london_implied = (_implied_cny_per_gram(london["price"], usdcny)
                      if london and london["price"] and usdcny else 0.0)
    newyork_implied = (_implied_cny_per_gram(newyork["price"], usdcny)
                       if newyork and newyork["price"] and usdcny else 0.0)
    # 上海金卡片对比基准：纽约金与伦敦金折算价的平均值
    implied_vals = [v for v in (newyork_implied, london_implied) if v]
    implied_cny_g = sum(implied_vals) / len(implied_vals) if implied_vals else 0.0
    implied_source = "纽约金/伦敦金均值" if len(implied_vals) == 2 else (
        "纽约金" if newyork_implied else ("伦敦金" if london_implied else ""))

    def _enrich(item: dict | None, own_implied: float) -> dict | None:
        if not item:
            return None
        diff, pct = _diff_pct(item["price"], item["prev_close"])
        item["diff"] = diff
        item["pct"] = pct
        item["implied_cny_g"] = own_implied
        item["implied"] = (f"折算 ≈ {own_implied:,.2f} CNY/g"
                           if own_implied else "")
        return item

    def _enrich_shanghai(item: dict | None) -> dict | None:
        if not item:
            return None
        diff, pct = _diff_pct(item["price"], item["prev_close"])
        item["diff"] = diff
        item["pct"] = pct
        item["implied_cny_g"] = item["price"]
        if implied_cny_g:
            basis = item["price"] - implied_cny_g
            note = f"  {item['avg_note']}" if item.get("avg_note") else ""
            item["implied"] = (f"折算价 {implied_cny_g:,.2f}  基差 {basis:+.2f}{note}")
        else:
            item["implied"] = item.get("avg_note", "")
        return item

    return {
        "usdcny": usdcny,
        "implied_cny_g": implied_cny_g,
        "implied_source": implied_source,
        "london": _enrich(london, london_implied),
        "newyork": _enrich(newyork, newyork_implied),
        "shanghai": _enrich_shanghai(shanghai),
    }
