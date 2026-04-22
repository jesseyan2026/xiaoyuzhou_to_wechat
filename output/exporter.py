"""文章导出器"""

import os
import re
from enum import Enum
from datetime import datetime
from pathlib import Path
from typing import Optional


class ExportFormat(Enum):
    """导出格式"""
    HTML = "html"
    MARKDOWN = "md"
    TEXT = "txt"
    WECHAT_MP = "wechat"  # 微信公众号专用格式


class ArticleExporter:
    """文章导出器"""

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        title: str,
        content: str,
        author: str = "",
        format_type: ExportFormat = ExportFormat.HTML,
        filename: Optional[str] = None
    ) -> str:
        """
        导出文章

        Args:
            title: 文章标题
            content: 文章内容（HTML或纯文本）
            author: 作者
            format_type: 导出格式
            filename: 自定义文件名（可选）

        Returns:
            str: 导出文件的完整路径
        """
        if filename is None:
            filename = self._generate_filename(title, format_type)

        output_path = self.output_dir / filename

        if format_type == ExportFormat.HTML:
            self._export_html(output_path, title, content, author)
        elif format_type == ExportFormat.MARKDOWN:
            self._export_markdown(output_path, title, content, author)
        elif format_type == ExportFormat.TEXT:
            self._export_text(output_path, title, content, author)
        elif format_type == ExportFormat.WECHAT_MP:
            self._export_wechat_mp(output_path, title, content, author)

        return str(output_path)

    def _generate_filename(self, title: str, format_type: ExportFormat) -> str:
        """生成文件名"""
        # 清理标题中的非法字符
        clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
        clean_title = clean_title[:50]  # 限制长度

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = format_type.value

        return f"{clean_title}_{timestamp}.{extension}"

    def _export_html(self, path: Path, title: str, content: str, author: str):
        """导出为HTML"""
        # 如果内容已经是完整HTML文档，直接保存
        if content.strip().startswith('<!DOCTYPE') or content.strip().startswith('<html'):
            path.write_text(content, encoding='utf-8')
        else:
            # 包装为完整HTML
            html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 677px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.8;
            color: #333;
        }}
        h1 {{ font-size: 22px; margin-bottom: 16px; }}
        .author {{ color: #888; font-size: 14px; margin-bottom: 20px; }}
        p {{ margin-bottom: 16px; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {f'<div class="author">作者：{author}</div>' if author else ''}
    {content}
</body>
</html>"""
            path.write_text(html, encoding='utf-8')

    def _export_markdown(self, path: Path, title: str, content: str, author: str):
        """导出为Markdown"""
        from bs4 import BeautifulSoup

        # 如果内容是HTML，转换为Markdown
        if '<' in content and '>' in content:
            soup = BeautifulSoup(content, 'html.parser')
            text_content = self._html_to_markdown(soup)
        else:
            text_content = content

        md_content = f"# {title}\n\n"
        if author:
            md_content += f"**作者：**{author}\n\n"
        md_content += f"---\n\n"
        md_content += text_content

        path.write_text(md_content, encoding='utf-8')

    def _export_text(self, path: Path, title: str, content: str, author: str):
        """导出为纯文本"""
        from bs4 import BeautifulSoup

        # 如果内容是HTML，提取纯文本
        if '<' in content and '>' in content:
            soup = BeautifulSoup(content, 'html.parser')
            text_content = soup.get_text(separator='\n', strip=True)
        else:
            text_content = content

        text_output = f"标题：{title}\n"
        if author:
            text_output += f"作者：{author}\n"
        text_output += f"{'=' * 40}\n\n"
        text_output += text_content

        path.write_text(text_output, encoding='utf-8')

    def _export_wechat_mp(self, path: Path, title: str, content: str, author: str):
        """导出为微信公众号编辑器兼容格式"""
        # 微信公众号编辑器需要特定的HTML结构
        wechat_html = f"""<!-- 微信公众号文章 -->
<div class="rich_media_content" id="js_content">
    <h2 class="rich_media_title">{title}</h2>
    {f'<p class="author">作者：{author}</p>' if author else ''}
    <div class="content">
        {content}
    </div>
</div>"""
        path.write_text(wechat_html, encoding='utf-8')

    def _html_to_markdown(self, soup) -> str:
        """将HTML转换为Markdown"""
        lines = []

        for elem in soup.find_all(['h1', 'h2', 'h3', 'p', 'blockquote', 'img', 'br']):
            if elem.name in ['h1', 'h2']:
                lines.append(f"# {elem.get_text(strip=True)}")
                lines.append("")
            elif elem.name == 'h3':
                lines.append(f"## {elem.get_text(strip=True)}")
                lines.append("")
            elif elem.name == 'p':
                text = elem.get_text(strip=True)
                if text:
                    lines.append(text)
                    lines.append("")
            elif elem.name == 'blockquote':
                text = elem.get_text(strip=True)
                for line in text.split('\n'):
                    lines.append(f"> {line}")
                lines.append("")

        return '\n'.join(lines)
