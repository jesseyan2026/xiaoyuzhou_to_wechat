"""小宇宙博客转微信公众号文章工具

一个用于将小宇宙播客博客转换为微信公众号文章的工具，
支持主语改写（改为"我的朋友"）和多种格式风格。
"""

__version__ = "1.0.0"
__author__ = "Claude"

from .crawler import XiaoyuzhouCrawler, BlogContent
from .transformer import SubjectTransformer, ContentProcessor
from .formatter import WechatFormatter, FormatStyle
from .output import ArticleExporter, ExportFormat

__all__ = [
    'XiaoyuzhouCrawler',
    'BlogContent',
    'SubjectTransformer',
    'ContentProcessor',
    'WechatFormatter',
    'FormatStyle',
    'ArticleExporter',
    'ExportFormat',
]
