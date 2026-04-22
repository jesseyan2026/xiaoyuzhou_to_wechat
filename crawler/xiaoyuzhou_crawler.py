"""小宇宙博客爬虫"""

import re
import requests
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


@dataclass
class BlogContent:
    """博客内容数据结构"""
    title: str
    author: str
    content: str  # shownotes/描述文本
    html_content: str
    images: List[dict]
    original_url: str
    publish_date: Optional[str] = None
    audio_url: Optional[str] = None  # 音频链接
    episode_id: Optional[str] = None  # 播客集ID


class XiaoyuzhouCrawler:
    """小宇宙博客爬虫"""

    BASE_URL = "https://www.xiaoyuzhoufm.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
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
        })

    def fetch_blog(self, url: str) -> BlogContent:
        """
        抓取小宇宙博客内容

        Args:
            url: 小宇宙博客链接

        Returns:
            BlogContent: 博客内容
        """
        if not self._is_valid_url(url):
            raise ValueError(f"无效的小宇宙博客链接: {url}")

        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')

        # 提取标题
        title = self._extract_title(soup)

        # 提取作者
        author = self._extract_author(soup)

        # 提取发布日期
        publish_date = self._extract_date(soup)

        # 提取正文内容 (shownotes)
        content_html, content_text = self._extract_content(soup)

        # 提取图片
        images = self._extract_images(soup, url)

        # 提取播客集ID
        episode_id = self._extract_episode_id(url)

        # 提取音频URL
        audio_url = self._extract_audio_url(response.text, episode_id)

        return BlogContent(
            title=title,
            author=author,
            content=content_text,
            html_content=content_html,
            images=images,
            original_url=url,
            publish_date=publish_date,
            audio_url=audio_url,
            episode_id=episode_id
        )

    def _is_valid_url(self, url: str) -> bool:
        """验证是否为小宇宙博客链接"""
        parsed = urlparse(url)
        return 'xiaoyuzhoufm.com' in parsed.netloc

    def _extract_episode_id(self, url: str) -> Optional[str]:
        """从URL中提取播客集ID"""
        # 匹配 /episode/xxxx 格式
        match = re.search(r'/episode/([a-zA-Z0-9]+)', url)
        if match:
            return match.group(1)
        return None

    def _extract_audio_url(self, html_content: str, episode_id: Optional[str] = None) -> Optional[str]:
        """提取音频URL"""
        # 方法1: 从页面中的音频标签提取
        patterns = [
            r'(https?://[^"\'<>\s]+\.xiaoyuzhoufm\.com/[^"\'<>\s]*\.mp3)',
            r'(https?://[^"\'<>\s]+\.xyzcdn\.net/[^"\'<>\s]*\.mp3)',
            r'(https?://[^"\'<>\s]+\.m4a)',
            r'"audioUrl"[:\s]*"([^"]+)"',
            r'"audio_url"[:\s]*"([^"]+)"',
            r'"mediaUrl"[:\s]*"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                url = match.group(1)
                # 清理URL
                url = url.replace('\\u002F', '/').replace('\\/', '/')
                return url

        # 方法2: 如果知道episode_id，尝试构造API URL
        if episode_id:
            api_url = f"https://www.xiaoyuzhoufm.com/episode/{episode_id}"
            # 这里可以进一步调用API获取音频链接
            pass

        return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取文章标题"""
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
                    return elem.get('content', '').strip()
                return elem.get_text(strip=True)

        return "未找到标题"

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

    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """提取发布日期"""
        selectors = [
            '.publish-time',
            '.article-date',
            'time',
            '.date',
            'meta[property="article:published_time"]'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                if selector.startswith('meta'):
                    return elem.get('content', '').strip()
                if elem.name == 'time':
                    return elem.get('datetime', elem.get_text(strip=True))
                return elem.get_text(strip=True)

        return None

    def _extract_content(self, soup: BeautifulSoup) -> tuple:
        """提取正文内容"""
        # 尝试多种内容容器选择器
        content_selectors = [
            'article',
            '.article-content',
            '.post-content',
            '.content',
            '[data-testid="article-content"]',
            '.rich-text',
            '.entry-content',
            '#article-content'
        ]

        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                break

        if not content_elem:
            # 如果找不到明确的内容容器，尝试从 body 中提取
            content_elem = soup.find('body')

        # 清理无用元素
        for tag in content_elem.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()

        # 获取 HTML 内容
        html_content = str(content_elem)

        # 获取纯文本内容（保留段落结构）
        content_text = self._clean_text(content_elem.get_text(separator='\n', strip=True))

        return html_content, content_text

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[dict]:
        """提取图片"""
        images = []
        seen_urls = set()

        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if not src:
                continue

            # 处理相对 URL
            src = urljoin(base_url, src)

            if src in seen_urls:
                continue
            seen_urls.add(src)

            alt = img.get('alt', '')
            images.append({
                'url': src,
                'alt': alt,
                'width': img.get('width'),
                'height': img.get('height')
            })

        return images

    def _clean_text(self, text: str) -> str:
        """清理文本内容"""
        # 移除多余空白行
        lines = text.split('\n')
        cleaned_lines = []
        prev_empty = False

        for line in lines:
            stripped = line.strip()
            if stripped:
                cleaned_lines.append(stripped)
                prev_empty = False
            elif not prev_empty:
                cleaned_lines.append('')
                prev_empty = True

        return '\n'.join(cleaned_lines)
