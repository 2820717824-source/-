#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
国家药监局（NMPA）药品公告爬虫
目标：
  - https://www.nmpa.gov.cn/yaopin/index.html          药品相关公告
  - https://www.nmpa.gov.cn/xxgk/ggtg/index.html        公告通告
  - https://www.nmpa.gov.cn/xxgk/zhcjd/index.html       政策解读
"""
import re
from datetime import datetime
from urllib.parse import urljoin

from lxml import etree

from base import BaseSpider
from logger_utils import logger


class NMPASpider(BaseSpider):
    source_name = "国家药监局"
    category = "政策"

    # 医药相关的列表页
    page_list = [
        {
            "name": "药品公告",
            "url": "https://www.nmpa.gov.cn/yaopin/index.html",
        },
        {
            "name": "公告通告",
            "url": "https://www.nmpa.gov.cn/xxgk/ggtg/index.html",
        },
        {
            "name": "政策解读",
            "url": "https://www.nmpa.gov.cn/xxgk/zhcjd/index.html",
        },
    ]

    async def get_news_list(self, page_info: dict | None = None):
        """
        解析列表页，返回文章链接列表。
        传入 page_info（page_list 中一个字典）或默认遍历全部列表页。
        """
        if page_info is None:
            all_items = []
            for pi in self.page_list:
                items = await self._parse_list_page(pi)
                all_items.extend(items)
            return all_items
        else:
            return await self._parse_list_page(page_info)

    async def _parse_list_page(self, page_info: dict) -> list[dict]:
        """解析单个列表页"""
        try:
            text = await self.request(url=page_info["url"])
            tree = etree.HTML(text)

            items = []
            # 政府网站常用列表结构：ul.list > li，含 a 标签 + span.date
            lis = tree.xpath('//ul[contains(@class,"list")]/li')
            if not lis:
                lis = tree.xpath('//div[contains(@class,"list")]//li')
            if not lis:
                lis = tree.xpath('//div[@id="newslist"]//li')

            for li in lis[:20]:
                link = li.xpath('./a')
                if not link:
                    continue
                href = link[0].xpath('./@href')[0] if link[0].xpath('./@href') else ""
                if not href:
                    href = link[0].xpath('./@href')[0] if link[0].xpath('./@href') else ""

                title = (link[0].xpath('string(.)') or "").strip()
                if not title:
                    title = link[0].xpath('./@title')[0] if link[0].xpath('./@title') else ""

                # 日期
                date_el = li.xpath('.//span[contains(@class,"date")]/text()')
                date_str = date_el[0].strip() if date_el else datetime.now().strftime("%Y-%m-%d")

                full_url = urljoin(page_info["url"], href)

                items.append({
                    "title": title,
                    "article_url": full_url,
                    "cover_url": "",
                    "date_str": date_str,
                    "page_name": page_info["name"],
                })

            return items

        except Exception as e:
            logger.error(f"解析{page_info['name']}列表失败: {e}")
            return []

    async def get_news_info(self, item: dict, category=None):
        """解析详情页"""
        try:
            text = await self.request(url=item["article_url"])
            tree = etree.HTML(text)

            # 标题
            title_el = tree.xpath('//h1/text()')
            if not title_el:
                title_el = tree.xpath('//div[contains(@class,"title")]/text()')
            title = (title_el[0].strip() if title_el else item.get("title", ""))

            # 正文
            content_el = tree.xpath('//div[contains(@class,"content")]//text()')
            if not content_el:
                content_el = tree.xpath('//div[@id="content"]//text()')
            if not content_el:
                content_el = tree.xpath('//div[contains(@class,"article")]//text()')
            content = "\n".join(c.strip() for c in content_el if c.strip())

            # 日期
            date_el = tree.xpath('//span[contains(@class,"date")]/text()')
            if not date_el:
                date_el = tree.xpath('//div[contains(@class,"info")]//text()')
            raw_date = date_el[0].strip() if date_el else ""

            date_str = item.get("date_str", "")
            if raw_date:
                match = re.search(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}', raw_date)
                if match:
                    d = match.group().replace("年", "-").replace("月", "-").replace("/", "-")
                    date_str = d + " 00:00:00" if len(d) == 10 else d

            return {
                "title": title,
                "article_url": item["article_url"],
                "cover_url": item.get("cover_url", ""),
                "date_str": date_str,
                "article_info": content,
                "img_list": [],
                "category": item.get("page_name", ""),
            }

        except Exception as e:
            logger.error(f"解析文章详情失败: {e}, URL: {item.get('article_url')}")
            return None

    # 不启用关键词过滤 — 药监局内容本身就全是医药相关
    keyword_filter = False


if __name__ == "__main__":
    import asyncio

    async def test():
        from database import db_manager

        if db_manager.pool is None:
            import os
            from dotenv import load_dotenv
            load_dotenv()
            db_manager.host = os.getenv("DB_HOST", "localhost")
            db_manager.port = int(os.getenv("DB_PORT", 5432))
            db_manager.user = os.getenv("DB_USER", "anning")
            db_manager.password = os.getenv("DB_PASSWORD", "123456")
            db_manager.database = os.getenv("DB_DATABASE", "article_spider")
            await db_manager.create_pool()
            await db_manager.init_tables()

        spider = NMPASpider()
        count = await spider.crawl_and_save()
        print(f"Saved {count} articles")
        await db_manager.close_pool()

    asyncio.run(test())
