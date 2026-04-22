"""内容处理器 - 整合各种转换逻辑"""

from typing import Optional, Callable
try:
    from ..crawler import BlogContent
except ImportError:
    from crawler import BlogContent
from .subject_transformer import SubjectTransformer


class ContentProcessor:
    """内容处理器"""

    def __init__(self, original_author: Optional[str] = None):
        self.subject_transformer = SubjectTransformer(original_author)
        self.preprocessors: list[Callable[[str], str]] = []
        self.postprocessors: list[Callable[[str], str]] = []

    def process(
        self,
        content: BlogContent,
        subject_mode: str = 'full',
        use_html: bool = True
    ) -> 'ProcessedContent':
        """
        处理博客内容

        Args:
            content: 原始博客内容
            subject_mode: 主语改写模式
            use_html: 是否使用 HTML 内容

        Returns:
            ProcessedContent: 处理后的内容
        """
        # 选择内容源
        source_content = content.html_content if use_html else content.content

        # 应用前置处理器
        for preprocessor in self.preprocessors:
            source_content = preprocessor(source_content)

        # 主语改写
        if use_html:
            transformed_content = self.subject_transformer.transform_html(source_content, subject_mode)
        else:
            transformed_content = self.subject_transformer.transform(source_content, subject_mode)

        # 应用后置处理器
        for postprocessor in self.postprocessors:
            transformed_content = postprocessor(transformed_content)

        return ProcessedContent(
            original=content,
            transformed_content=transformed_content,
            subject_mode=subject_mode,
            is_html=use_html
        )

    def add_preprocessor(self, func: Callable[[str], str]):
        """添加前置处理器"""
        self.preprocessors.append(func)

    def add_postprocessor(self, func: Callable[[str], str]):
        """添加后置处理器"""
        self.postprocessors.append(func)


class ProcessedContent:
    """处理后的内容"""

    def __init__(
        self,
        original: BlogContent,
        transformed_content: str,
        subject_mode: str,
        is_html: bool
    ):
        self.original = original
        self.transformed_content = transformed_content
        self.subject_mode = subject_mode
        self.is_html = is_html

    def get_text(self) -> str:
        """获取纯文本内容"""
        if self.is_html:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(self.transformed_content, 'html.parser')
            return soup.get_text(separator='\n', strip=True)
        return self.transformed_content

    def get_html(self) -> str:
        """获取 HTML 内容"""
        return self.transformed_content
