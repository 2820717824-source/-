#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
安徽省卫健委（wjw.ah.gov.cn）公告爬虫
目标：
  - https://wjw.ah.gov.cn/jbyfkzj/xwzx/gzdt/index.html  工作动态
  - https://wjw.ah.gov.cn/xwzx/tzgg/index.html            通知公告
"""
import re
from datetime import datetime
from urllib.parse import urljoin

from lxml import etree

from base import BaseSpider
from logger_utils import logger


class AnhuiWJW(BaseSpider):
    source_name = "安徽省卫健委"
    category = "政策"

    page_list = [
        {
            "name": "工作动态",
            "url": "https://wjw.ah.gov.cn/jbyfkzj/xwzx/gzdt/index.html",
        },
        {
            "name": "通知公告",
            "url": "https://wjw.ah.gov.cn/xwzx/tzgg/index.html",
        },
    ]

    async def get_news_list(self, page_info: dict | None = None):
        if page_info is None:
            all_items = []
            for pi in self.page_list:
                items = await self._parse_list_page(pi)
                all_items.extend(items)
            return all_items
        else:
            return await self._parse_list_page(page_info)

    async def _parse_list_page(self, page_info: dict) -> list[dict]:
        try:
            text = await self.request(url=page_info["url"])
            tree = etree.HTML(text)

            items = []
            # 安徽政府网站通用结构
            lis = tree.xpath('//ul[contains(@class,"list")]/li')
            if not lis:
                lis = tree.xpath('//div[contains(@class,"list")]//li')
            if not lis:
                lis = tree.xpath('//div[contains(@class,"main")]//li')

            for li in lis[:20]:
                link = li.xpath('.//a')
                if not link:
                    continue
                href = ""
                for a in link:
                    h = a.xpath('./@href')
                    if h:
                        href = h[0]
                        break

                title = (li.xpath('.//a/@title')[0] if li.xpath('.//a/@title')
                         else (li.xpath('string(.//a)') or "").strip())

                date_el = li.xpath('.//span[contains(@class,"date")]/text()')
                if not date_el:
                    date_el = li.xpath('.//text()[contains(.,"202")]')
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
        try:
            text = await self.request(url=item["article_url"])
            tree = etree.HTML(text)

            # 政府网站标题模式
            title_el = (tree.xpath('//h1/text()')
                        or tree.xpath('//div[contains(@class,"title")]/text()')
                        or tree.xpath('//meta[@name="ArticleTitle"]/@content'))
            title = (title_el[0].strip() if title_el else item.get("title", ""))

            # 正文
            content_el = (tree.xpath('//div[contains(@class,"content")]//text()')
                          or tree.xpath('//div[@id="UCAP-CONTENT"]//text()')
                          or tree.xpath('//div[contains(@class,"article")]//text()'))
            content = "\n".join(c.strip() for c in content_el if c.strip())

            # 日期
            date_el = (tree.xpath('//meta[@name="PubDate"]/@content')
                       or tree.xpath('//span[contains(@class,"date")]/text()')
                       or tree.xpath('//div[contains(@class,"info")]//text()'))
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

    keyword_filter = False


if __name__ == "__main__":
    import asyncio
    import os

    async def test():
        from database import db_manager
        from dotenv import load_dotenv

        if db_manager.pool is None:
            load_dotenv()
            db_manager.host = os.getenv("DB_HOST", "localhost")
            db_manager.port = int(os.getenv("DB_PORT", 5432))
            db_manager.user = os.getenv("DB_USER", "anning")
            db_manager.password = os.getenv("DB_PASSWORD", "123456")
            db_manager.database = os.getenv("DB_DATABASE", "article_spider")
            await db_manager.create_pool()
            await db_manager.init_tables()

        spider = AnhuiWJW()
        count = await spider.crawl_and_save()
        print(f"Saved {count} articles")
        await db_manager.close_pool()

    asyncio.run(test())
