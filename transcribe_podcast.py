#!/usr/bin/env python3
"""
播客音频转录工具 - 智能版

功能：
1. 【智能模式】自动从微信公众号、今日头条等外部信息源搜索相关文稿
2. 【音频模式】从小宇宙下载音频并使用Whisper转录

使用方法：
    python transcribe_podcast.py <小宇宙播客链接>

示例：
    python transcribe_podcast.py https://www.xiaoyuzhoufm.com/episode/69d7f994b977fb2c4789b1ac
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from urllib.parse import urljoin, urlparse, quote
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


@dataclass
class PodcastInfo:
    """播客信息"""
    title: str
    description: str
    author: str
    episode_url: str
    audio_url: Optional[str] = None
    guest_names: List[str] = None
    key_topics: List[str] = None

    def __post_init__(self):
        if self.guest_names is None:
            self.guest_names = []
        if self.key_topics is None:
            self.key_topics = []


@dataclass
class ArticleResult:
    """文章搜索结果"""
    title: str
    url: str
    source: str  # wechat, toutiao, sohu, etc.
    summary: str
    publish_date: Optional[str] = None


class PodcastInfoExtractor:
    """播客信息提取器"""

    def __init__(self, output_dir: str = "../transcriptions"):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.xiaoyuzhoufm.com/',
        })

    def extract(self, episode_url: str) -> PodcastInfo:
        """从小宇宙播客页面提取信息"""
        print(f"🔍 正在分析播客页面: {episode_url}")

        try:
            response = self.session.get(episode_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"无法访问播客页面: {e}")

        soup = BeautifulSoup(response.text, 'html.parser')

        # 提取标题
        title = self._extract_title(soup, response.text)

        # 提取描述
        description = self._extract_description(soup, response.text)

        # 提取作者/主播
        author = self._extract_author(soup)

        # 提取音频链接（可选）
        audio_url = self._find_audio_url(response.text, episode_url)

        # 提取嘉宾名字
        guest_names = self._extract_guest_names(title, description)

        # 提取关键话题
        key_topics = self._extract_key_topics(title, description)

        info = PodcastInfo(
            title=title,
            description=description,
            author=author,
            episode_url=episode_url,
            audio_url=audio_url,
            guest_names=guest_names,
            key_topics=key_topics
        )

        print(f"✅ 提取到播客信息:")
        print(f"   标题: {title}")
        print(f"   主播: {author}")
        if guest_names:
            print(f"   嘉宾: {', '.join(guest_names)}")
        if key_topics:
            print(f"   话题: {', '.join(key_topics[:5])}")

        return info

    def _extract_title(self, soup: BeautifulSoup, html_content: str) -> str:
        """提取标题"""
        # 尝试多种选择器
        selectors = [
            'h1.title',
            'h1.article-title',
            '.article h1',
            'article h1',
            '.post-title',
            'meta[property="og:title"]',
            'title'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                if selector.startswith('meta'):
                    title = elem.get('content', '').strip()
                else:
                    title = elem.get_text(strip=True)
                # 清理标题
                title = re.sub(r'\s+', ' ', title)
                return title

        return "未找到标题"

    def _extract_description(self, soup: BeautifulSoup, html_content: str) -> str:
        """提取描述"""
        # 尝试meta标签
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            return meta_desc.get('content', '')

        meta_og = soup.find('meta', property='og:description')
        if meta_og:
            return meta_og.get('content', '')

        # 尝试正文内容
        content_selectors = [
            '.article-content',
            '.post-content',
            '.content',
            'article',
            '.description'
        ]

        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)[:500]

        return ""

    def _extract_author(self, soup: BeautifulSoup) -> str:
        """提取作者"""
        selectors = [
            '.author-name',
            '.user-name',
            '.publisher-name',
            '[data-testid="author"]',
            '.article-author',
            'meta[name="author"]'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                if selector.startswith('meta'):
                    return elem.get('content', '').strip()
                return elem.get_text(strip=True)

        return "未知作者"

    def _extract_guest_names(self, title: str, description: str) -> List[str]:
        """从标题和描述中提取嘉宾名字"""
        names = []

        # 常见模式：嘉宾XXX、XXX分享、XXX对话等
        text = title + " " + description

        # 模式1: "嘉宾XXX"
        pattern1 = r'嘉宾[：:]?\s*([^，,、。\s]{2,20})'
        matches1 = re.findall(pattern1, text)
        names.extend(matches1)

        # 模式2: 中文名字（2-4个字）
        # 排除常见非名字词汇
        exclude_words = {'本期', '我们', '今天', '分享', '内容', '主题', '节目', '播客'}
        pattern2 = r'[\u4e00-\u9fa5]{2,4}'
        potential_names = re.findall(pattern2, text)
        for name in potential_names:
            if name not in exclude_words and len(name) >= 2:
                names.append(name)

        # 去重并限制数量
        unique_names = list(dict.fromkeys(names))[:5]
        return unique_names

    def _extract_key_topics(self, title: str, description: str) -> List[str]:
        """提取关键话题"""
        topics = []

        # 常见商业/创业话题关键词
        keywords = [
            '出海', '搞钱', '创业', '副业', '投资', '理财', '短视频', '直播',
            'TikTok', '抖音', '小红书', '淘宝', '电商', 'AI', '人工智能',
            '短剧', '漫剧', '内容创作', '自媒体', '流量', '变现',
            '墨西哥', '拉美', '东南亚', '跨境', '外贸', 'MCN'
        ]

        text = title + " " + description

        for keyword in keywords:
            if keyword in text:
                topics.append(keyword)

        return topics[:8]  # 限制数量

    def _find_audio_url(self, html_content: str, base_url: str) -> Optional[str]:
        """查找音频URL"""
        patterns = [
            r'(https?://[^"\'<>\s]+\.(?:mp3|m4a|aac|ogg))',
            r'(https?://audio\.xiaoyuzhoufm\.com/[^"\'<>\s]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                return match.group(1)
        return None


class ExternalSourceSearcher:
    """外部信息源搜索器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })

    def search(self, podcast_info: PodcastInfo) -> List[ArticleResult]:
        """
        搜索外部信息源

        返回找到的相关文章列表
        """
        print("\n" + "=" * 60)
        print("🔎 正在搜索外部信息源...")
        print("=" * 60)

        all_results = []

        # 构建搜索查询
        queries = self._build_search_queries(podcast_info)

        # 1. 搜索微信公众号文章
        print("\n📱 搜索微信公众号文章...")
        wechat_results = self._search_wechat(queries)
        all_results.extend(wechat_results)
        print(f"   找到 {len(wechat_results)} 篇微信公众号文章")

        # 2. 搜索今日头条
        print("\n📰 搜索今日头条...")
        toutiao_results = self._search_toutiao(queries)
        all_results.extend(toutiao_results)
        print(f"   找到 {len(toutiao_results)} 篇今日头条文章")

        # 3. 搜索其他来源
        print("\n🌐 搜索其他来源...")
        other_results = self._search_general(queries)
        all_results.extend(other_results)
        print(f"   找到 {len(other_results)} 篇其他文章")

        # 排序和去重
        all_results = self._deduplicate_and_sort(all_results)

        print(f"\n✅ 共找到 {len(all_results)} 篇相关文章")
        return all_results

    def _build_search_queries(self, podcast_info: PodcastInfo) -> List[str]:
        """构建搜索查询"""
        queries = []

        # 查询1: 完整标题
        queries.append(podcast_info.title)

        # 查询2: 标题 + 嘉宾
        if podcast_info.guest_names:
            guest_str = ' '.join(podcast_info.guest_names[:2])
            queries.append(f"{podcast_info.title} {guest_str}")

        # 查询3: 关键话题组合
        if podcast_info.key_topics:
            topics = ' '.join(podcast_info.key_topics[:3])
            queries.append(f"{topics} 分享")

        # 查询4: 嘉宾 + 播客名
        if podcast_info.guest_names:
            for guest in podcast_info.guest_names[:2]:
                queries.append(f"{guest} 搞钱女孩")

        return queries[:4]  # 限制查询数量

    def _search_wechat(self, queries: List[str]) -> List[ArticleResult]:
        """搜索微信公众号文章"""
        results = []

        # 使用搜狗搜索微信公众号文章
        for query in queries[:2]:  # 限制查询数量
            try:
                encoded_query = quote(query)
                url = f"https://weixin.sogou.com/weixin?type=2&query={encoded_query}"

                response = self.session.get(url, timeout=15)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                # 提取搜索结果
                items = soup.find_all('div', class_='txt-box')[:3]  # 只取前3个

                for item in items:
                    try:
                        title_elem = item.find('h3')
                        if not title_elem:
                            continue

                        title = title_elem.get_text(strip=True)
                        link_elem = title_elem.find('a')
                        if not link_elem:
                            continue

                        href = link_elem.get('href', '')
                        if href.startswith('/'):
                            href = f"https://weixin.sogou.com{href}"

                        summary_elem = item.find('p', class_='txt-info')
                        summary = summary_elem.get_text(strip=True) if summary_elem else ""

                        results.append(ArticleResult(
                            title=title,
                            url=href,
                            source="wechat",
                            summary=summary[:200]
                        ))
                    except Exception as e:
                        continue

                time.sleep(0.5)  # 避免请求过快

            except Exception as e:
                print(f"   搜索微信时出错: {e}")
                continue

        return results

    def _search_toutiao(self, queries: List[str]) -> List[ArticleResult]:
        """搜索今日头条"""
        results = []

        for query in queries[:2]:
            try:
                encoded_query = quote(query)
                # 使用头条搜索
                url = f"https://www.toutiao.com/search?keyword={encoded_query}"

                response = self.session.get(url, timeout=15)

                # 今日头条可能需要特殊处理，这里简化处理
                # 实际实现可能需要分析API或使用其他方式

                time.sleep(0.3)

            except Exception as e:
                continue

        return results

    def _search_general(self, queries: List[str]) -> List[ArticleResult]:
        """通用搜索"""
        results = []

        # 使用Bing搜索
        for query in queries[:2]:
            try:
                encoded_query = quote(query)
                url = f"https://www.bing.com/search?q={encoded_query}+搞钱女孩+长沙听友会"

                response = self.session.get(url, timeout=15)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                # 提取搜索结果
                items = soup.find_all('li', class_='b_algo')[:3]

                for item in items:
                    try:
                        title_elem = item.find('h2')
                        if not title_elem:
                            continue

                        title = title_elem.get_text(strip=True)
                        link_elem = title_elem.find('a')
                        if not link_elem:
                            continue

                        href = link_elem.get('href', '')

                        # 检查是否是微信公众号或其他可信来源
                        source = "other"
                        if 'mp.weixin.qq.com' in href:
                            source = "wechat"
                        elif 'toutiao' in href:
                            source = "toutiao"
                        elif 'sohu.com' in href:
                            source = "sohu"

                        summary_elem = item.find('p')
                        summary = summary_elem.get_text(strip=True) if summary_elem else ""

                        results.append(ArticleResult(
                            title=title,
                            url=href,
                            source=source,
                            summary=summary[:200]
                        ))
                    except Exception:
                        continue

                time.sleep(0.3)

            except Exception as e:
                continue

        return results

    def _deduplicate_and_sort(self, results: List[ArticleResult]) -> List[ArticleResult]:
        """去重并排序"""
        seen_urls = set()
        unique_results = []

        for result in results:
            # 规范化URL用于去重
            normalized_url = result.url.split('?')[0]
            if normalized_url not in seen_urls and len(normalized_url) > 10:
                seen_urls.add(normalized_url)
                unique_results.append(result)

        # 优先显示微信公众号文章
        unique_results.sort(key=lambda x: (0 if x.source == "wechat" else 1, x.source))

        return unique_results[:10]  # 限制总数


class ArticleFetcher:
    """文章抓取器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })

    def fetch(self, article: ArticleResult) -> Optional[str]:
        """抓取文章内容"""
        print(f"\n📄 正在抓取文章: {article.title[:50]}...")

        try:
            if article.source == "wechat":
                return self._fetch_wechat(article.url)
            else:
                return self._fetch_general(article.url)
        except Exception as e:
            print(f"   抓取失败: {e}")
            return None

    def _fetch_wechat(self, url: str) -> Optional[str]:
        """抓取微信公众号文章"""
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取标题
            title = soup.find('h1', class_='rich_media_title')
            title_text = title.get_text(strip=True) if title else ""

            # 提取正文
            content = soup.find('div', id='js_content')
            if not content:
                content = soup.find('div', class_='rich_media_content')

            if content:
                # 清理文本
                for script in content.find_all('script'):
                    script.decompose()
                for style in content.find_all('style'):
                    style.decompose()

                text = content.get_text(separator='\n', strip=True)
                # 清理多余空行
                text = re.sub(r'\n+', '\n', text)

                return f"# {title_text}\n\n{text}"

            return None

        except Exception as e:
            raise Exception(f"微信公众号文章抓取失败: {e}")

    def _fetch_general(self, url: str) -> Optional[str]:
        """抓取一般网页"""
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # 尝试提取标题
            title = soup.find('h1')
            title_text = title.get_text(strip=True) if title else ""

            # 尝试提取正文
            content = None
            selectors = [
                'article',
                '.article-content',
                '.post-content',
                '.content',
                'main',
                '[role="main"]'
            ]

            for selector in selectors:
                content = soup.select_one(selector)
                if content:
                    break

            if content:
                # 清理
                for script in content.find_all('script'):
                    script.decompose()
                for style in content.find_all('style'):
                    style.decompose()
                for nav in content.find_all(['nav', 'header', 'footer']):
                    nav.decompose()

                text = content.get_text(separator='\n', strip=True)
                text = re.sub(r'\n+', '\n', text)

                return f"# {title_text}\n\n{text}"

            return None

        except Exception as e:
            raise Exception(f"网页抓取失败: {e}")


class SmartPodcastTranscriber:
    """智能播客转录器"""

    def __init__(self, output_dir: str = "./transcriptions"):
        self.info_extractor = PodcastInfoExtractor()
        self.source_searcher = ExternalSourceSearcher()
        self.article_fetcher = ArticleFetcher()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = tempfile.mkdtemp(prefix="podcast_transcribe_")

    def run(self, episode_url: str, output_dir: str = "./transcriptions",
            model_size: str = "medium", use_api: bool = False,
            api_key: Optional[str] = None, skip_search: bool = False) -> Tuple[str, str]:
        """
        执行智能转录流程

        流程：
        1. 提取播客信息
        2. 搜索外部信息源
        3. 如果找到相关文稿，直接使用
        4. 如果没找到，转录音频
        """
        print("=" * 60)
        print("🎙️  智能播客转录工具")
        print("=" * 60)

        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 步骤1: 提取播客信息
        podcast_info = self.info_extractor.extract(episode_url)

        # 步骤2: 搜索外部信息源（除非跳过）
        if not skip_search:
            articles = self.source_searcher.search(podcast_info)

            if articles:
                print("\n" + "=" * 60)
                print("📚 找到以下相关文章:")
                print("=" * 60)

                for i, article in enumerate(articles[:5], 1):
                    print(f"\n{i}. [{article.source.upper()}] {article.title}")
                    print(f"   摘要: {article.summary[:100]}...")

                # 尝试抓取最相关的文章
                print("\n🤖 正在尝试抓取文章内容...")
                for article in articles[:3]:
                    content = self.article_fetcher.fetch(article)
                    if content and len(content) > 500:
                        print(f"\n✅ 成功获取文章内容！({len(content)} 字符)")

                        # 保存
                        episode_id = episode_url.split('/')[-1].split('?')[0]
                        output_file = output_path / f"episode_{episode_id}_from_{article.source}.md"

                        metadata = {
                            'url': episode_url,
                            'source_url': article.url,
                            'title': podcast_info.title,
                            'author': podcast_info.author,
                            'source_type': article.source,
                            'fetched_at': time.strftime('%Y-%m-%d %H:%M:%S')
                        }

                        self._save_content(content, str(output_file), metadata)

                        print("\n" + "=" * 60)
                        print("✅ 完成！已从外部信息源获取文稿")
                        print(f"📄 文件位置: {output_file}")
                        print("=" * 60)

                        return str(output_file), content

                print("\n⚠️  无法从外部源获取完整内容，将尝试音频转录...")
            else:
                print("\n⚠️  未找到外部文稿，将尝试音频转录...")
        else:
            print("\n⏭️  跳过外部搜索，直接进行音频转录...")

        # 步骤3: 音频转录（备用方案）
        if podcast_info.audio_url:
            return self._transcribe_audio(
                podcast_info, output_path, model_size, use_api, api_key
            )
        else:
            raise Exception("无法获取音频链接，且未找到外部文稿。\n"
                          "建议：使用小宇宙App下载音频后，使用飞书妙记转录。")

    def _transcribe_audio(self, podcast_info: PodcastInfo, output_path: Path,
                          model_size: str, use_api: bool, api_key: Optional[str]) -> Tuple[str, str]:
        """转录音频"""
        print("\n" + "=" * 60)
        print("🎵 开始音频转录流程...")
        print("=" * 60)

        # 下载音频
        audio_path = os.path.join(self.temp_dir, f"podcast_{int(time.time())}.mp3")
        self._download_audio(podcast_info.audio_url, audio_path)

        # 转录
        if use_api:
            transcription = self._transcribe_with_api(audio_path, api_key)
        else:
            transcription = self._transcribe_with_whisper(audio_path, model_size)

        # 保存
        episode_id = podcast_info.episode_url.split('/')[-1].split('?')[0]
        output_file = output_path / f"episode_{episode_id}_transcription.md"

        metadata = {
            'url': podcast_info.episode_url,
            'audio_url': podcast_info.audio_url,
            'title': podcast_info.title,
            'author': podcast_info.author,
            'transcribed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'method': 'whisper'
        }

        self._save_content(transcription, str(output_file), metadata)

        # 清理
        try:
            os.remove(audio_path)
            os.rmdir(self.temp_dir)
        except:
            pass

        print("\n" + "=" * 60)
        print("✅ 音频转录完成！")
        print(f"📄 文件位置: {output_file}")
        print("=" * 60)

        return str(output_file), transcription

    def _download_audio(self, audio_url: str, output_path: str):
        """下载音频"""
        print(f"⬇️  正在下载音频...")

        try:
            response = requests.get(audio_url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"   下载进度: {percent:.1f}%", end='\r')

            print(f"\n✅ 音频下载完成")

        except Exception as e:
            raise Exception(f"下载音频失败: {e}")

    def _transcribe_with_whisper(self, audio_path: str, model_size: str) -> str:
        """使用Whisper转录"""
        print(f"🎯 使用Whisper转录（模型: {model_size}）...")

        try:
            import whisper

            print(f"   加载模型...")
            model = whisper.load_model(model_size)

            print("   正在转录（这可能需要一段时间）...")
            result = model.transcribe(
                audio_path,
                language="zh",
                verbose=True,
                initial_prompt="这是一段中文播客内容。"
            )

            transcription = result["text"]
            print(f"✅ 转录完成！共 {len(transcription)} 字符")

            return transcription

        except ImportError:
            raise Exception(
                "未安装Whisper。请运行: pip install openai-whisper\n"
                "同时需要安装ffmpeg。"
            )
        except Exception as e:
            raise Exception(f"Whisper转录失败: {e}")

    def _transcribe_with_api(self, audio_path: str, api_key: Optional[str]) -> str:
        """使用API转录"""
        api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise Exception("需要提供API Key或设置 OPENAI_API_KEY 环境变量")

        print("🎯 使用OpenAI API转录...")

        try:
            with open(audio_path, 'rb') as audio_file:
                response = requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": ("audio.mp3", audio_file, "audio/mpeg")},
                    data={"model": "whisper-1", "language": "zh", "response_format": "text"},
                    timeout=300
                )

            response.raise_for_status()
            return response.text

        except Exception as e:
            raise Exception(f"API转录失败: {e}")

    def _save_content(self, content: str, output_path: str, metadata: dict):
        """保存内容"""
        # 保存Markdown
        with open(output_path, 'w', encoding='utf-8') as f:
            if not content.startswith('#'):
                f.write(f"# {metadata.get('title', '播客文稿')}\n\n")
            f.write(f"**来源**: {metadata.get('url', 'N/A')}\n")
            if metadata.get('source_url'):
                f.write(f"**文章来源**: {metadata.get('source_url')}\n")
            f.write(f"**获取时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(content)

        # 保存JSON
        json_path = output_path.replace('.md', '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({'metadata': metadata, 'content': content}, f, ensure_ascii=False, indent=2)

        print(f"💾 已保存到: {output_path}")


def check_dependencies():
    """检查依赖"""
    missing = []

    try:
        import requests
    except ImportError:
        missing.append("requests")

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        missing.append("beautifulsoup4")

    if missing:
        print("❌ 缺少必要的Python包，请安装:")
        print(f"   pip install {' '.join(missing)}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="智能播客转录工具 - 优先从外部信息源获取文稿，找不到再转录音频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 智能模式（默认）：先搜索外部文稿，找不到再转录
  python transcribe_podcast.py https://www.xiaoyuzhoufm.com/episode/xxx

  # 跳过外部搜索，直接转录音频
  python transcribe_podcast.py <URL> --skip-search

  # 使用更大的Whisper模型
  python transcribe_podcast.py <URL> --model large

  # 使用OpenAI API转录
  python transcribe_podcast.py <URL> --use-api --api-key your_key

说明:
  1. 默认会优先搜索微信公众号、今日头条等外部信息源
  2. 如果找到相关文稿，会直接使用，节省token和时间
  3. 如果找不到，会自动下载音频并使用Whisper转录
  4. 如果音频也无法获取，会提示手动方案
        """
    )

    parser.add_argument('url', help='小宇宙播客链接')
    parser.add_argument('--output', '-o', default='./transcriptions',
                        help='输出目录 (默认: ./transcriptions)')
    parser.add_argument('--model', '-m', default='medium',
                        choices=['tiny', 'base', 'small', 'medium', 'large'],
                        help='Whisper模型大小 (默认: medium)')
    parser.add_argument('--use-api', action='store_true',
                        help='使用OpenAI API而非本地Whisper')
    parser.add_argument('--api-key', '-k',
                        help='OpenAI API Key')
    parser.add_argument('--skip-search', action='store_true',
                        help='跳过外部信息源搜索，直接转录音频')

    args = parser.parse_args()

    # 检查依赖
    check_dependencies()

    # 执行转录
    transcriber = SmartPodcastTranscriber()
    try:
        output_file, content = transcriber.run(
            episode_url=args.url,
            output_dir=args.output,
            model_size=args.model,
            use_api=args.use_api,
            api_key=args.api_key,
            skip_search=args.skip_search
        )

        # 显示内容预览
        print("\n📝 内容预览（前800字符）:")
        print("-" * 60)
        preview = content[:800] + "..." if len(content) > 800 else content
        print(preview)
        print("-" * 60)

        print(f"\n✨ 完整内容已保存到: {output_file}")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n💡 建议:")
        print("   1. 检查网络连接")
        print("   2. 确认播客链接有效")
        print("   3. 使用小宇宙App下载音频")
        print("   4. 使用飞书妙记手动转录: https://www.feishu.cn/product/minutes")
        sys.exit(1)


if __name__ == '__main__':
    main()
