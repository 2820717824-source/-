"""
医药行业热点关键词配置
业务：康联达健康（Meditrusthealth）+ 曼斯普医学科技（imsrmt.com）
      两公司在安徽省的独家代理
"""
import re

KEYWORDS: dict[str, list[str]] = {
    # 公司/品牌
    "company": [
        # 康哲药业系
        "康哲药业", "康联达", "康联达健康", "Meditrusthealth",
        "meditrusthealth",
        # 曼斯普系
        "曼斯普", "曼斯普医学", "Unitedwell", "unitedwell",
    ],
    # 业务领域
    "business": [
        # 疾病领域
        "肿瘤", "中枢神经", "神经系统", "自身免疫", "自免",
        "眼科", "眼科用药",
        # 药品/器械类型
        "创新药", "仿制药", "生物类似药", "孤儿药", "首仿药",
        "药品审批", "药品注册", "药品上市", "新药上市",
        "集采", "带量采购", "国家集采", "医保目录", "医保谈判",
        "医疗器械", "医疗设备", "CDMO", "临床试验",
        # 药品引进/开发/营销（康哲核心业务）
        "药品引进", "license-in", "License-in", "商业化",
        # 影像设备（曼斯普核心业务）
        "MRI", "PET", "PET/MRI", "磁共振", "核磁共振", "多模态成像",
        "医学影像", "医学成像",
    ],
    # 区域
    "region": [
        "安徽", "安徽省", "合肥", "合肥市",
        "长三角", "皖", "皖北", "皖南",
        # 安徽省内城市
        "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵",
        "安庆", "黄山", "阜阳", "宿州", "滁州", "六安",
        "宣城", "池州", "亳州",
    ],
    # 行业/政策
    "industry": [
        "NMPA", "GMP", "GSP", "ICH",
        "一致性评价", "MAH", "上市许可持有人",
        "药监局", "卫健委", "医保局", "国家医保",
        "处方药", "OTC", "特药", "国家药品目录",
        "审评审批", "优先审评", "突破性治疗",
        "药品管理法", "医疗器械监督管理",
    ],
}

# 扁平化关键词列表，仅含中文 + 英文特有词（避免单字母误匹配）
def _all_keywords() -> list[str]:
    """返回去重后的全量关键词列表"""
    seen = set()
    result = []
    for v in KEYWORDS.values():
        for kw in v:
            low = kw.lower()
            if low not in seen:
                seen.add(low)
                result.append(kw)
    return result

ALL_KEYWORDS: list[str] = _all_keywords()

# 简短英文关键词（全大写、纯 ASCII、≤6 字符）使用词边界正则匹配，
# 避免 "PET" 匹配 "pet"、"MRI" 匹配 "mrs." 等误报。
_SHORT_ENGLISH_KWS: set[str] = {
    kw for kw in ALL_KEYWORDS
    if kw.isascii() and kw.isupper() and len(kw) <= 6
}

_KEYWORD_PATTERNS: list[re.Pattern | str] = []
for kw in ALL_KEYWORDS:
    if kw in _SHORT_ENGLISH_KWS:
        # 全大写英文缩写（PET、MRI、NMPA 等）—— 大小写敏感，仅匹配大写形式
        _KEYWORD_PATTERNS.append(re.compile(r"\b" + re.escape(kw) + r"\b"))
    else:
        # 中英文通用关键词 —— 不区分大小写子串匹配
        _KEYWORD_PATTERNS.append(kw.lower())


def matches_keywords(title: str = "", content: str = "") -> bool:
    """标题或内容匹配任一关键词（不区分大小写）"""
    text = f"{title} {content}"
    text_lower = text.lower()
    for p in _KEYWORD_PATTERNS:
        if isinstance(p, re.Pattern):
            if p.search(text):
                return True
        else:
            if p in text_lower:
                return True
    return False
