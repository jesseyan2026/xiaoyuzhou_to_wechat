"""微信公众号文章格式化器"""

import re
import requests
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from enum import Enum


class FormatStyle(Enum):
    """格式化风格"""
    DEFAULT = "default"
    MINIMAL = "minimal"
    STORY = "story"
    INTERVIEW = "interview"
    REVIEW = "review"


@dataclass
class ReferenceArticle:
    """参考文章结构"""
    title: str
    author: str
    content_html: str
    style_features: dict
    url: str


class WechatFormatter:
    """
    微信公众号文章格式化器

    支持以下格式化方式：
    1. 指定格式要求 - 通过 style 参数选择预设格式
    2. 参考其他公众号文章 - 通过参考文章 URL 学习其格式
    """

    # 微信公众号文章样式模板
    STYLE_TEMPLATES = {
        FormatStyle.DEFAULT: {
            'title_style': 'font-size: 22px; font-weight: bold; color: #333; margin-bottom: 16px;',
            'author_style': 'font-size: 14px; color: #888; margin-bottom: 20px;',
            'content_style': 'font-size: 16px; line-height: 1.8; color: #333;',
            'paragraph_style': 'margin-bottom: 16px; text-align: justify;',
            'quote_style': 'border-left: 4px solid #999; padding-left: 16px; color: #666; font-style: italic;',
            'image_style': 'max-width: 100%; height: auto; margin: 16px 0;',
            'section_header_style': 'font-size: 18px; font-weight: bold; color: #333; margin: 24px 0 12px 0;',
        },
        FormatStyle.MINIMAL: {
            'title_style': 'font-size: 20px; font-weight: normal; color: #000; margin-bottom: 12px;',
            'author_style': 'font-size: 12px; color: #666; margin-bottom: 16px;',
            'content_style': 'font-size: 15px; line-height: 1.6; color: #000;',
            'paragraph_style': 'margin-bottom: 12px;',
            'quote_style': 'color: #444; font-style: italic;',
            'image_style': 'max-width: 100%; margin: 12px 0;',
            'section_header_style': 'font-size: 16px; font-weight: bold; margin: 20px 0 10px 0;',
        },
        FormatStyle.STORY: {
            'title_style': 'font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 20px; text-align: center;',
            'author_style': 'font-size: 14px; color: #7f8c8d; margin-bottom: 24px; text-align: center;',
            'content_style': 'font-size: 17px; line-height: 2; color: #34495e;',
            'paragraph_style': 'margin-bottom: 20px; text-indent: 2em;',
            'quote_style': 'border-left: 3px solid #e74c3c; padding: 12px 20px; background: #f8f9fa; color: #2c3e50; margin: 20px 0;',
            'image_style': 'max-width: 100%; border-radius: 4px; margin: 20px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1);',
            'section_header_style': 'font-size: 20px; font-weight: bold; color: #e74c3c; margin: 32px 0 16px 0;',
        },
        FormatStyle.INTERVIEW: {
            'title_style': 'font-size: 22px; font-weight: bold; color: #1a1a1a; margin-bottom: 16px;',
            'author_style': 'font-size: 13px; color: #999; margin-bottom: 20px;',
            'content_style': 'font-size: 16px; line-height: 1.8; color: #333;',
            'paragraph_style': 'margin-bottom: 16px;',
            'quote_style': 'background: #f5f5f5; padding: 16px; border-radius: 4px; color: #555;',
            'image_style': 'max-width: 100%; margin: 16px 0;',
            'section_header_style': 'font-size: 18px; font-weight: bold; color: #666; margin: 24px 0 12px 0;',
            'speaker_style': 'font-weight: bold; color: #1890ff; margin-right: 8px;',
        },
        FormatStyle.REVIEW: {
            'title_style': 'font-size: 22px; font-weight: bold; color: #1a1a1a; margin-bottom: 12px;',
            'author_style': 'font-size: 13px; color: #666; margin-bottom: 20px;',
            'content_style': 'font-size: 15px; line-height: 1.75; color: #333;',
            'paragraph_style': 'margin-bottom: 14px;',
            'quote_style': 'border-left: 3px solid #52c41a; padding-left: 16px; color: #595959; background: #f6ffed; padding: 12px 16px;',
            'image_style': 'max-width: 100%; border: 1px solid #d9d9d9; margin: 16px 0;',
            'section_header_style': 'font-size: 17px; font-weight: bold; color: #262626; margin: 20px 0 10px 0;',
            'highlight_style': 'background: #fff7e6; padding: 2px 4px; border-radius: 2px;',
        },
    }

    def __init__(self, style: FormatStyle = FormatStyle.DEFAULT):
        self.style = style
        self.template = self.STYLE_TEMPLATES[style]
        self.reference_article: Optional[ReferenceArticle] = None

    def set_style(self, style: FormatStyle):
        """设置格式风格"""
        self.style = style
        self.template = self.STYLE_TEMPLATES[style]

    def learn_from_reference(self, url: str) -> ReferenceArticle:
        """
        从参考文章学习格式

        Args:
            url: 微信公众号文章链接

        Returns:
            ReferenceArticle: 解析的参考文章信息
        """
        if not self._is_wechat_url(url):
            raise ValueError(f"不是有效的微信公众号文章链接: {url}")

        # 获取文章内容
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # 提取标题
        title = self._extract_wechat_title(soup)

        # 提取作者
        author = self._extract_wechat_author(soup)

        # 提取内容区域
        content_elem = self._extract_wechat_content(soup)
        content_html = str(content_elem) if content_elem else ""

        # 分析样式特征
        style_features = self._analyze_style_features(content_elem) if content_elem else {}

        self.reference_article = ReferenceArticle(
            title=title,
            author=author,
            content_html=content_html,
            style_features=style_features,
            url=url
        )

        return self.reference_article

    def format(
        self,
        title: str,
        content: str,
        author: str = "",
        is_html: bool = False,
        use_reference: bool = False
    ) -> str:
        """
        格式化文章为微信公众号格式

        Args:
            title: 文章标题
            content: 文章内容
            author: 作者（可选）
            is_html: 内容是否为HTML
            use_reference: 是否使用参考文章的格式

        Returns:
            str: 格式化后的HTML
        """
        if use_reference and self.reference_article:
            template = self.reference_article.style_features.get('template', self.template)
        else:
            template = self.template

        # 处理内容
        if is_html:
            processed_content = self._process_html_content(content, template)
        else:
            processed_content = self._process_text_content(content, template)

        # 构建完整HTML
        html = self._build_html(title, author, processed_content, template)

        return html

    def _is_wechat_url(self, url: str) -> bool:
        """验证是否为微信公众号链接"""
        parsed = urlparse(url)
        return 'mp.weixin.qq.com' in parsed.netloc or 'weixin.qq.com' in parsed.netloc

    def _extract_wechat_title(self, soup: BeautifulSoup) -> str:
        """提取微信文章标题"""
        # 尝试多种选择器
        for selector in ['h2.rich_media_title', '#activity_name', '.rich_media_title']:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return "未找到标题"

    def _extract_wechat_author(self, soup: BeautifulSoup) -> str:
        """提取微信文章作者"""
        for selector in ['#js_name', '.profile_nickname', '.rich_media_meta_nickname']:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        return ""

    def _extract_wechat_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """提取微信文章内容区域"""
        for selector in ['#js_content', '.rich_media_content']:
            elem = soup.select_one(selector)
            if elem:
                return elem
        return None

    def _analyze_style_features(self, content_elem: BeautifulSoup) -> dict:
        """分析参考文章的样式特征"""
        features = {
            'template': {},
            'has_indent': False,
            'text_align': 'left',
            'font_size': '16px',
            'line_height': '1.8',
        }

        # 查找第一个段落分析样式
        first_p = content_elem.find('p')
        if first_p and first_p.get('style'):
            style = first_p['style']
            if 'text-indent' in style:
                features['has_indent'] = True
            if 'text-align' in style:
                match = re.search(r'text-align:\s*(\w+)', style)
                if match:
                    features['text_align'] = match.group(1)

        return features

    def _process_html_content(self, content: str, template: dict) -> str:
        """处理HTML内容"""
        soup = BeautifulSoup(content, 'html.parser')

        # 为所有段落添加样式
        for p in soup.find_all('p'):
            current_style = p.get('style', '')
            new_style = f"{current_style}; {template.get('paragraph_style', '')}".strip('; ')
            p['style'] = new_style

        # 为图片添加样式
        for img in soup.find_all('img'):
            current_style = img.get('style', '')
            new_style = f"{current_style}; {template.get('image_style', '')}".strip('; ')
            img['style'] = new_style

        # 处理引用
        for quote in soup.find_all(['blockquote', 'q']):
            current_style = quote.get('style', '')
            new_style = f"{current_style}; {template.get('quote_style', '')}".strip('; ')
            quote['style'] = new_style

        return str(soup)

    def _process_text_content(self, content: str, template: dict) -> str:
        """处理纯文本内容，转换为HTML"""
        paragraphs = content.split('\n\n')
        html_parts = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 检测是否是标题
            if self._is_heading(para):
                html_parts.append(
                    f'<h3 style="{template.get("section_header_style", "")}">{para}</h3>'
                )
            # 检测是否是引用
            elif para.startswith('>') or para.startswith('"') or para.startswith('「'):
                html_parts.append(
                    f'<blockquote style="{template.get("quote_style", "")}">'
                    f'<p style="{template.get("paragraph_style", "")}">{para}</p>'
                    f'</blockquote>'
                )
            else:
                html_parts.append(
                    f'<p style="{template.get("paragraph_style", "")}">{para}</p>'
                )

        return '\n'.join(html_parts)

    def _is_heading(self, text: str) -> bool:
        """判断文本是否为标题"""
        # 短文本且没有标点符号结尾
        if len(text) < 30 and not text[-1] in '。！？.!?':
            # 包含特定关键词
            heading_keywords = ['一、', '二、', '三、', '1.', '2.', '3.', '第一章', '第二章',
                              '前言', '结语', '总结', '引言', '关于', '什么是', '为什么', '怎么样']
            for kw in heading_keywords:
                if text.startswith(kw):
                    return True
        return False

    def _build_html(self, title: str, author: str, content: str, template: dict) -> str:
        """构建完整HTML文档"""
        author_section = ''
        if author:
            author_section = f'<div class="author" style="{template.get("author_style", "")}">作者：{author}</div>'

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 677px; margin: 0 auto; padding: 20px; background: #fff;">
    <article style="{template.get('content_style', '')}">
        <h1 style="{template.get('title_style', '')}">{title}</h1>
        {author_section}
        <div class="content">
            {content}
        </div>
    </article>
</body>
</html>"""


class FormatRequirements:
    """格式要求定义"""

    def __init__(
        self,
        title_format: Optional[str] = None,
        paragraph_format: Optional[str] = None,
        image_position: str = "center",
        max_image_width: int = 677,
        font_family: Optional[str] = None,
        font_size: Optional[str] = None,
        line_height: Optional[str] = None,
        color_scheme: Optional[dict] = None
    ):
        self.title_format = title_format
        self.paragraph_format = paragraph_format
        self.image_position = image_position
        self.max_image_width = max_image_width
        self.font_family = font_family
        self.font_size = font_size
        self.line_height = line_height
        self.color_scheme = color_scheme or {}
