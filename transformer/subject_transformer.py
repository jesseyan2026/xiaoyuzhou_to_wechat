"""主语改写模块 - 将文章主语改为'我的朋友'"""

import re
from typing import List, Tuple, Optional


class SubjectTransformer:
    """
    主语改写器 - 将文章中的主语改为"我的朋友"

    支持的改写模式：
    1. 第一人称 -> 我的朋友
       我/我们 -> 我的朋友
       我的/我们的 -> 我的朋友的

    2. 第三人称（特定作者） -> 我的朋友
       如果知道原作者是谁，可以将其名字替换为"我的朋友"

    3. 通用替换模式
       主播/博主/作者 -> 我的朋友
    """

    # 第一人称及其变体
    FIRST_PERSON_PATTERNS = [
        (r'我(?=[们\s,，.。!！?？])', '我的朋友'),  # 我，但不匹配"我们"中的"我"
        (r'我们', '我的朋友们'),
        (r'我的', '我的朋友的'),
        (r'我们的', '我的朋友们的'),
        (r'我自己', '我的朋友自己'),
        (r'我认为', '我的朋友认为'),
        (r'我觉得', '我的朋友觉得'),
        (r'我想', '我的朋友想'),
        (r'我发现', '我的朋友发现'),
        (r'我希望', '我的朋友希望'),
    ]

    # 播客/创作者相关称谓
    CREATOR_PATTERNS = [
        (r'主播', '我的朋友'),
        (r'主持人', '我的朋友'),
        (r'博主', '我的朋友'),
        (r'UP主', '我的朋友'),
        (r'作者', '我的朋友'),
        (r'创作者', '我的朋友'),
        (r'播客主', '我的朋友'),
    ]

    # 句首特定模式（需要更谨慎处理）
    SENTENCE_START_PATTERNS = [
        (r'^(\s*)我[\s,，]', r'\1我的朋友，'),
        (r'^(\s*)今天我觉得', r'\1今天我的朋友觉得'),
        (r'^(\s*)最近我发现', r'\1最近我的朋友发现'),
    ]

    def __init__(self, original_author: Optional[str] = None):
        """
        初始化主语改写器

        Args:
            original_author: 原作者名称，如果提供则会将原作者名称也替换为"我的朋友"
        """
        self.original_author = original_author
        self.custom_patterns: List[Tuple[str, str]] = []

        # 如果提供了原作者，添加替换模式
        if original_author:
            self._add_author_patterns(original_author)

    def _add_author_patterns(self, author: str):
        """添加原作者相关的替换模式"""
        # 精确匹配作者名
        self.custom_patterns.append((rf'\b{re.escape(author)}\b', '我的朋友'))
        # 作者名 + 说/认为/觉得等
        self.custom_patterns.append((rf'\b{re.escape(author)}\s*说\b', '我的朋友说'))
        self.custom_patterns.append((rf'\b{re.escape(author)}\s*认为\b', '我的朋友认为'))
        self.custom_patterns.append((rf'\b{re.escape(author)}\s*觉得\b', '我的朋友觉得'))
        self.custom_patterns.append((rf'\b{re.escape(author)}\s*分享\b', '我的朋友分享'))

    def transform(self, text: str, mode: str = 'full') -> str:
        """
        执行主语改写

        Args:
            text: 原始文本
            mode: 改写模式
                - 'full': 完整改写（第一人称 + 创作者称谓 + 原作者）
                - 'first_person_only': 仅改写第一人称
                - 'creator_only': 仅改写创作者称谓

        Returns:
            str: 改写后的文本
        """
        result = text

        if mode in ('full', 'first_person_only'):
            result = self._apply_patterns(result, self.FIRST_PERSON_PATTERNS)
            result = self._apply_sentence_start_patterns(result)

        if mode in ('full', 'creator_only'):
            result = self._apply_patterns(result, self.CREATOR_PATTERNS)

        if self.custom_patterns and mode == 'full':
            result = self._apply_patterns(result, self.custom_patterns)

        return result

    def _apply_patterns(self, text: str, patterns: List[Tuple[str, str]]) -> str:
        """应用替换模式"""
        result = text
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.MULTILINE | re.UNICODE)
        return result

    def _apply_sentence_start_patterns(self, text: str) -> str:
        """应用句首特定模式"""
        result = text
        lines = result.split('\n')
        new_lines = []

        for line in lines:
            modified_line = line
            for pattern, replacement in self.SENTENCE_START_PATTERNS:
                modified_line = re.sub(pattern, replacement, modified_line)
            new_lines.append(modified_line)

        return '\n'.join(new_lines)

    def transform_html(self, html_content: str, mode: str = 'full') -> str:
        """
        对 HTML 内容执行主语改写

        Args:
            html_content: HTML 格式的内容
            mode: 改写模式

        Returns:
            str: 改写后的 HTML
        """
        # 对于 HTML，我们需要更小心地处理
        # 只替换文本节点，不替换标签

        from bs4 import BeautifulSoup, NavigableString

        soup = BeautifulSoup(html_content, 'html.parser')

        def transform_text_node(node):
            """转换文本节点"""
            if isinstance(node, NavigableString):
                text = str(node)
                transformed = self.transform(text, mode)
                if text != transformed:
                    node.replace_with(transformed)

        # 遍历所有文本节点
        for element in soup.find_all(text=True):
            # 跳过脚本和样式标签内的内容
            if element.parent and element.parent.name in ['script', 'style']:
                continue
            transform_text_node(element)

        return str(soup)


class TransformationConfig:
    """转换配置"""

    def __init__(
        self,
        transform_first_person: bool = True,
        transform_creator_titles: bool = True,
        transform_author_name: bool = True,
        preserve_quotes: bool = True,
        custom_replacements: Optional[List[Tuple[str, str]]] = None
    ):
        self.transform_first_person = transform_first_person
        self.transform_creator_titles = transform_creator_titles
        self.transform_author_name = transform_author_name
        self.preserve_quotes = preserve_quotes
        self.custom_replacements = custom_replacements or []
