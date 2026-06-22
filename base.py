#!/usr/bin/python
# -*- coding: UTF-8 -*-
# @author:anning
# @email:anningforchina@gmail.com
# @time:2025/05/25 17:29
# @file:base.py
import json

import aiohttp
import chardet

from database import db_manager
from logger_utils import logger
from typing import List, Dict, Optional
import asyncio
from datetime import datetime


class BaseSpider:
    """
    BaseSpider 类，继承自 Base 类，使用 aiohttp 进行异步请求。
    """

    url = None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    source_name = "Unknown"  # 子类需要设置这个属性
    category = "General"  # 子类可以设置分类

    async def request(
        self,
        method="GET",
        url=None,
        headers=None,
        params=None,
        data=None,
        json=None,
        timeout=10,
    ):
        """
        异步发送 HTTP 请求。

        :param method: 请求方法，默认为 GET
        :param url: 请求URL，如果不提供则使用self.url
        :param headers: 请求头
        :param params: 请求参数
        :param data: 请求数据
        :param timeout: 请求超时时间，默认为 10 秒
        :return: 响应对象或 None
        """
        request_url = url or self.url
        if not request_url:
            raise ValueError("URL is required")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.request(
                    method=method,
                    url=request_url,
                    headers=headers or self.headers,
                    params=params,
                    json=json,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as response:
                    # 检查响应状态码
                    response.raise_for_status()

                    content = await response.read()
                    code = chardet.detect(content)["encoding"]
                    if code == "Windows-1254":  # 误判 chardet底层的问题
                        code = "utf-8"
                    return await response.text(encoding=code)
            except aiohttp.ClientError as e:
                raise e
            except Exception as e:
                raise e

    async def get_news_list(self, code=None) -> List[Dict]:
        """
        获取新闻列表，子类需要实现此方法

        :param code: 分类代码或URL
        :return: 新闻列表
        """
        raise NotImplementedError("Subclasses must implement get_news_list method")

    async def get_news_info(self, item: Dict, category=None) -> Optional[Dict]:
        """
        获取新闻详情，子类需要实现此方法

        :param item: 新闻项目
        :param category: 分类
        :return: 新闻详情字典
        """
        raise NotImplementedError("Subclasses must implement get_news_info method")

    async def save_article(self, article_data: Dict) -> bool:
        """
        保存文章到数据库

        :param article_data: 文章数据
        :return: 是否保存成功
        """
        try:
            img_list_json = (
                json.dumps(article_data.get("img_list", []))
                if article_data.get("img_list")
                else "[]"
            )
            date_str = article_data.get("date_str")
            if not date_str:
                logger.error(
                    f"来源{self.source_name}，文章{article_data.get('title')}缺少时间"
                )
                return False

            # 插入新文章
            sql = """
                INSERT INTO accounts_accountnews (
                    title, article_url, cover_url, content, 
                    date_str, source, category, img_list, status,
                    platform_data, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """
            params = (
                article_data["title"],
                article_data["article_url"],
                article_data.get("cover_url"),
                article_data.get("article_info"),
                datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S"),
                self.source_name,
                article_data.get("category", self.category),
                img_list_json,
                0,
                json.dumps({}),
                datetime.now(),
                datetime.now(),
            )
            await db_manager.execute(sql, params)
            return True

        except Exception as e:

            if "duplicate key value violates unique constraint" in str(e).lower():
                logger.skip(f"文章已存在: {article_data['title']}")
                return False
            logger.error(f"SQL参数: {params}")
            logger.error(f"报错: {e}")
            return False

    async def crawl_and_save(
        self,
        code=None,
        limit=None,
        class_sleep_time=0,
        info_sleep_time=0,
        addition_msg="",
    ) -> int:
        """
        爬取并保存文章

        :param code: 分类代码
        :param limit: 限制数量
        :return: 保存的文章数量
        """
        try:
            # 获取新闻列表
            news_list = await self.get_news_list(code)
            if limit:
                news_list = news_list[:limit]

            # 并发获取新闻详情并保存
            semaphore = asyncio.Semaphore(5)  # 限制并发数

            # 先检查数据库中是否已存在相同标题的文章
            filtered_news_list = []
            skip_count = 0
            for item in news_list:
                # 检查标题或URL是否已存在
                existing = await db_manager.fetchone(
                    "SELECT id FROM accounts_accountnews WHERE title = $1 OR article_url = $2",
                    (item["title"], item["article_url"]),
                )
                if not existing:
                    filtered_news_list.append(item)
                else:
                    skip_count += 1
            logger.skip(f"跳过{skip_count}篇已存在的文章")
            logger.info(
                f"{self.source_name}{addition_msg} 总共 {len(news_list)} 篇文章，需要爬取 {len(filtered_news_list)} 篇"
            )

            async def process_news_item(item):
                async with semaphore:
                    try:
                        news_info = await self.get_news_info(item)
                        if news_info and await self.save_article(news_info):
                            return 1
                    except Exception as e:
                        logger.error(f"处理新闻项目失败: {e}")
                    return 0

            tasks = []
            for item in filtered_news_list:
                task = process_news_item(item)
                tasks.append(task)
                if info_sleep_time:
                    await asyncio.sleep(info_sleep_time)

            if not tasks:  # 如果没有需要爬取的文章，直接返回
                logger.info(f"{self.source_name}{addition_msg} 没有新文章需要爬取")
                return 0

            results = await asyncio.gather(*tasks, return_exceptions=True)

            saved_count = sum(r for r in results if isinstance(r, int))

            logger.success(
                f"{self.source_name}{addition_msg} 爬取完成，保存了 {saved_count if saved_count > 0 else 0} 篇文章"
            )
            return saved_count

        except Exception as e:
            logger.error(f"{self.source_name} 爬取失败: {e}")
            return 0
