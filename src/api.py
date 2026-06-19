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

    字段顺序: [0]名称 [2]开盘 [3]最高 [4]最低
             [5]最新 [8]昨收 [10]昨结 [16]日期
    """
    if not fields or len(fields) < 11:
        return None
    price = _safe_float(fields[5])
    if price <= 0:
        return None
    return {
        "name": fields[0],
        "price": price,
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

    # 折算价锚定：优先纽约金，其次伦敦金
    implied_cny_g = 0.0
    implied_source = ""
    for name, src in [("纽约金", newyork), ("伦敦金", london)]:
        if src and src["price"] and usdcny:
            implied_cny_g = _implied_cny_per_gram(src["price"], usdcny)
            implied_source = name
            break

    def _enrich(item: dict | None, is_intl: bool) -> dict | None:
        if not item:
            return None
        diff, pct = _diff_pct(item["price"], item["prev_close"])
        item["diff"] = diff
        item["pct"] = pct
        if is_intl:
            # 国际金卡片显示折算 CNY/g
            item["implied"] = (f"折算 ≈ {implied_cny_g:,.2f} CNY/g"
                               if implied_cny_g else "")
        else:
            # 上海金卡片显示折算价对比 + 基差
            if implied_cny_g:
                basis = item["price"] - implied_cny_g
                item["implied"] = (f"折算价 {implied_cny_g:,.2f}  基差 {basis:+.2f}")
            else:
                item["implied"] = ""
        return item

    return {
        "usdcny": usdcny,
        "implied_cny_g": implied_cny_g,
        "implied_source": implied_source,
        "london": _enrich(london, is_intl=True),
        "newyork": _enrich(newyork, is_intl=True),
        "shanghai": _enrich(shanghai, is_intl=False),
    }
