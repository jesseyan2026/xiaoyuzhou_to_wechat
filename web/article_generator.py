#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文章生成器 - 调用AI API生成微信公众号/小红书文章
支持: Kimi (Moonshot AI), Claude (Anthropic)
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# 添加父目录到路径
sys.path.append(str(Path(__file__).parent.parent))

# 尝试导入SDK
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("警告: openai SDK未安装，将使用模拟模式")

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class ArticleGenerator:
    """文章生成器"""

    def __init__(self, api_key: Optional[str] = None, provider: Optional[str] = None):
        """
        初始化生成器

        Args:
            api_key: API Key，如果不提供则尝试从环境变量获取
            provider: 提供商 (kimi/claude)，默认自动检测
        """
        self.provider = provider or self._detect_provider()
        self.api_key = api_key or self._get_api_key()
        self.client = None

        if self.api_key:
            self._init_client()

    def _detect_provider(self) -> str:
        """自动检测提供商"""
        if os.getenv('KIMI_API_KEY'):
            return 'kimi'
        elif os.getenv('ANTHROPIC_API_KEY'):
            return 'claude'
        return 'kimi'  # 默认尝试kimi

    def _get_api_key(self) -> Optional[str]:
        """获取API Key"""
        if self.provider == 'kimi':
            return os.getenv('KIMI_API_KEY')
        elif self.provider == 'claude':
            return os.getenv('ANTHROPIC_API_KEY')
        return None

    def _init_client(self):
        """初始化API客户端"""
        try:
            if self.provider == 'kimi' and OPENAI_AVAILABLE:
                # Kimi使用OpenAI兼容的API
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://api.moonshot.cn/v1"
                )
                print(f"[ArticleGenerator] 已初始化Kimi客户端")
            elif self.provider == 'claude' and ANTHROPIC_AVAILABLE:
                self.client = Anthropic(api_key=self.api_key)
                print(f"[ArticleGenerator] 已初始化Claude客户端")
            else:
                print(f"[ArticleGenerator] 未找到合适的SDK，将使用模拟模式")
        except Exception as e:
            print(f"[ArticleGenerator] 初始化客户端失败: {e}")
            self.client = None

    def generate(self, content: str, platform: str, style: Dict[str, Any]) -> Dict[str, str]:
        """
        生成文章

        Args:
            content: 播客转录内容
            platform: 平台类型 (wechat/xiaohongshu)
            style: 风格配置

        Returns:
            包含标题、HTML内容、Markdown内容的字典
        """
        if not self.client:
            print("[ArticleGenerator] API客户端未初始化，使用模拟模式")
            return self._mock_generate(content, platform, style)

        # 构建prompt
        prompt = self._build_prompt(content, platform, style)

        try:
            if self.provider == 'kimi':
                return self._generate_with_kimi(prompt, content, platform, style)
            else:
                return self._generate_with_claude(prompt, content, platform, style)

        except Exception as e:
            print(f"[ArticleGenerator] API调用失败: {e}")
            import traceback
            traceback.print_exc()
            return self._mock_generate(content, platform, style)

    def _generate_with_kimi(self, prompt: str, original_content: str, platform: str, style: Dict) -> Dict[str, str]:
        """使用Kimi生成"""
        print(f"[ArticleGenerator] 调用Kimi API...")

        response = self.client.chat.completions.create(
            model="kimi-k2.5",  # 使用Kimi最新模型
            messages=[{
                "role": "user",
                "content": prompt
            }],
            max_tokens=4096
            # temperature: kimi-k2.5 only supports temperature=1
        )

        generated_text = response.choices[0].message.content
        print(f"[ArticleGenerator] Kimi生成完成，长度: {len(generated_text)}")

        # 解析生成的内容
        title = self._extract_title(generated_text)
        html_content = self._convert_to_html(generated_text, platform, style)

        return {
            'title': title,
            'content': generated_text,
            'html': html_content,
            'markdown': generated_text,
            'is_mock': False,
            'provider': 'kimi'
        }

    def _generate_with_claude(self, prompt: str, original_content: str, platform: str, style: Dict) -> Dict[str, str]:
        """使用Claude生成"""
        print(f"[ArticleGenerator] 调用Claude API...")

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        generated_text = response.content[0].text
        print(f"[ArticleGenerator] Claude生成完成，长度: {len(generated_text)}")

        # 解析生成的内容
        title = self._extract_title(generated_text)
        html_content = self._convert_to_html(generated_text, platform, style)

        return {
            'title': title,
            'content': generated_text,
            'html': html_content,
            'markdown': generated_text,
            'is_mock': False,
            'provider': 'claude'
        }

    def _build_prompt(self, content: str, platform: str, style: Dict[str, Any]) -> str:
        """构建Prompt"""
        narrator = style.get('narrator', '我的朋友')
        content_scope = style.get('content_scope', '')
        special_requirements = style.get('special_requirements', '')

        if platform == 'wechat':
            return self._build_wechat_prompt(content, narrator, content_scope, special_requirements, style)
        else:
            return self._build_xiaohongshu_prompt(content, narrator, content_scope, special_requirements, style)

    def _build_wechat_prompt(self, content: str, narrator: str, scope: str, requirements: str, style: Dict) -> str:
        """构建微信公众号Prompt"""
        first_indent = "需要" if style.get('first_line_indent', True) else "不需要"
        line_height = style.get('line_height', 2.0)

        prompt = f"""请将以下播客转录内容整理成一篇高质量的微信公众号文章。

## 角色设定

你是一位专业的内容编辑，擅长将口语化的播客转录内容改写成流畅、易读的文章。

## 改写要求

1. **叙述视角**: 以"{narrator}"作为叙述者，将所有第一人称（我/我们/我的）改为第三人称
   - "我觉得" → "{narrator}觉得"
   - "我认为" → "{narrator}认为"
   - "我的" → "{narrator}的"
   - "我想" → "{narrator}想"
   - "我说" → "{narrator}说"

2. **语言风格**:
   - 去除口语化的口头禅（嗯、啊、那个、就是等）
   - 将重复、啰嗦的表达精简
   - 保持原意不变，但让表达更书面化、流畅

3. **文章结构**:
   - 第一行：文章标题（简洁有力，不超过20字）
   - 开头：用1-2段引入主题，吸引读者
   - 正文：用小标题分段，逻辑清晰
   - 结尾：总结升华，给出思考或行动建议

4. **排版格式**:
   - 段落首行缩进：{first_indent}
   - 行距：{line_height}倍
   - 使用小标题（## 标题）分段
   - 重点内容可以加粗（**文字**）

5. **内容处理**:
   - 保留所有关键信息、数据、案例
   - 删除主持人过渡语、重复内容
   - 合并相似的表达
"""
        if scope:
            prompt += f"\n## 内容范围\n{scope}\n"

        if requirements:
            prompt += f"\n## 特殊要求\n{requirements}\n"

        prompt += f"""
## 播客转录内容

{content[:15000]}

## 输出格式

请直接输出完整的文章，包括标题。使用Markdown格式：
- 标题使用 # 或 ##
- 重点使用 **加粗**
- 段落之间空一行
"""
        return prompt

    def _build_xiaohongshu_prompt(self, content: str, narrator: str, scope: str, requirements: str, style: Dict) -> str:
        """构建小红书Prompt"""
        use_emoji = "使用" if style.get('use_emoji', True) else "不使用"
        bullet_points = "需要" if style.get('bullet_points', True) else "不需要"
        highlight = "需要" if style.get('highlight_key_points', True) else "不需要"
        tags = style.get('tags', '')

        prompt = f"""请将以下播客转录内容整理成一篇小红书笔记。

## 角色设定

你是一位擅长写小红书爆款笔记的内容创作者，风格亲切、有干货、易读。

## 改写要求

1. **叙述视角**: 以"{narrator}"作为叙述者，将第一人称改为第三人称
   - 保留内容原意，但转换叙述角度

2. **语言风格**:
   - 像朋友聊天一样亲切自然
   - 去除过于口语化的表达
   - 精简内容，突出重点

3. **文章结构**:
   - 第一行：标题（15字以内，有吸引力）
   - 开头：1-2句抓人眼球的开场
   - 正文：分点列出干货，每点配emoji
   - 结尾：引导互动（如"你觉得呢？"）
   - 文末：相关标签

4. **排版格式**:
   - Emoji：{use_emoji}
   - 分点：{bullet_points}
   - 高亮重点：{highlight}
   - 字数控制在800-1200字
"""
        if scope:
            prompt += f"\n## 内容范围\n{scope}\n"

        if requirements:
            prompt += f"\n## 特殊要求\n{requirements}\n"

        if tags:
            prompt += f"\n## 标签\n请在文末添加这些标签：{tags}\n"

        prompt += f"""
## 播客转录内容

{content[:8000]}

## 输出格式

请直接输出完整的笔记内容，使用小红书风格。
"""
        return prompt

    def _extract_title(self, text: str) -> str:
        """从生成的文本中提取标题"""
        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            # 移除Markdown标记
            line = line.replace('#', '').replace('**', '').strip()
            if line and len(line) < 100:
                return line
        return "未命名文章"

    def _convert_to_html(self, text: str, platform: str, style: Dict) -> str:
        """将文本转换为HTML"""
        lines = text.strip().split('\n')
        html_lines = []

        first_line_indent = style.get('first_line_indent', True)
        line_height = style.get('line_height', 2.0)
        font_size = style.get('font_size', 16)

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                html_lines.append('<p></p>')
                continue

            # 处理标题 (第一行 或 # 开头)
            if i == 0 or line.startswith('# '):
                title = line.replace('# ', '').replace('#', '').strip()
                html_lines.append(f'<h1 style="font-size: 24px; font-weight: bold; margin-bottom: 20px; line-height: 1.4;">{title}</h1>')
                continue

            # 处理小标题 (## 开头)
            if line.startswith('## '):
                title = line.replace('## ', '').replace('**', '').strip()
                html_lines.append(f'<h2 style="font-size: 18px; font-weight: bold; margin: 24px 0 12px 0; color: #ff6b6b;">{title}</h2>')
                continue

            # 处理加粗
            import re
            # 将 **text** 转换为 <strong>text</strong>
            line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)

            # 处理普通段落
            indent_style = 'text-indent: 2em;' if first_line_indent else ''
            html_lines.append(f'<p style="{indent_style} margin-bottom: 1em; line-height: {line_height}; font-size: {font_size}px;">{line}</p>')

        return '\n'.join(html_lines)

    def _mock_generate(self, content: str, platform: str, style: Dict) -> Dict[str, str]:
        """模拟生成（当API不可用时）- 应用基本风格转换"""
        narrator = style.get('narrator', '我的朋友')
        first_indent = style.get('first_line_indent', True)
        line_height = style.get('line_height', 2.0)
        font_size = style.get('font_size', 16)

        print(f"[ArticleGenerator] 使用模拟模式生成，叙述者: {narrator}")

        # 提取前几行作为标题
        lines = content.strip().split('\n')[:5]
        title = lines[0][:50] if lines else "播客转录"

        # 处理内容 - 应用基本风格转换
        content_lines = content.strip().split('\n')
        processed_lines = []

        for line in content_lines:
            line = line.strip()
            if not line:
                continue

            # 模拟叙述者转换 - 替换常见的第一人称
            line = line.replace('我觉得', f'{narrator}觉得')
            line = line.replace('我认为', f'{narrator}认为')
            line = line.replace('我的', f'{narrator}的')
            line = line.replace('我想', f'{narrator}想')
            line = line.replace('我说', f'{narrator}说')
            line = line.replace('我不喜欢', f'{narrator}不喜欢')
            line = line.replace('我喜欢', f'{narrator}喜欢')
            line = line.replace('我们要', f'{narrator}们要')
            line = line.replace('我们是', f'{narrator}们是')

            processed_lines.append(line)

        processed_content = '\n\n'.join(processed_lines[:100])  # 取前100段

        # 生成HTML
        if platform == 'wechat':
            indent_style = 'text-indent: 2em;' if first_indent else ''
            html_lines = []
            html_lines.append(f'<h1 style="font-size: 24px; font-weight: bold; margin-bottom: 20px; line-height: 1.4;">{title}</h1>')

            for line in processed_lines[:80]:
                html_lines.append(f'<p style="{indent_style} margin-bottom: 1em; line-height: {line_height}; font-size: {font_size}px;">{line}</p>')

            html_content = '\n'.join(html_lines)
        else:
            # 小红书样式
            use_emoji = style.get('use_emoji', True)
            html_lines = []
            html_lines.append(f'<h1 style="font-size: 20px; font-weight: bold; margin-bottom: 16px;">{title}</h1>')

            for i, line in enumerate(processed_lines[:50]):
                prefix = '✨ ' if (use_emoji and i > 0) else ''
                html_lines.append(f'<p style="margin-bottom: 0.8em; line-height: 1.8;">{prefix}{line}</p>')

            if style.get('tags'):
                html_lines.append(f'<p style="margin-top: 20px; color: #999;">{style["tags"]}</p>')

            html_content = '\n'.join(html_lines)

        return {
            'title': title,
            'content': processed_content,
            'html': html_content,
            'markdown': processed_content,
            'is_mock': True,
            'applied_style': {
                'narrator': narrator,
                'first_line_indent': first_indent,
                'line_height': line_height,
                'font_size': font_size
            }
        }


def generate_article(content: str, platform: str, style: Dict[str, Any]) -> Dict[str, str]:
    """
    便捷函数：生成文章

    Args:
        content: 播客转录内容
        platform: 平台类型
        style: 风格配置

    Returns:
        生成的文章字典
    """
    generator = ArticleGenerator()
    return generator.generate(content, platform, style)


if __name__ == '__main__':
    # 测试
    test_content = """
人间清醒，搞钱要紧，搞钱就是搞自己。

这是搞钱女孩播客的一期内容，讲述了三位女性创业者的故事...
我觉得创业最重要的是坚持。我的想法是，要有清晰的目标。
"""

    test_style = {
        'narrator': '我的朋友',
        'first_line_indent': True,
        'line_height': 2.0
    }

    result = generate_article(test_content, 'wechat', test_style)
    print("生成结果:")
    print(f"标题: {result['title']}")
    print(f"内容预览: {result['content'][:200]}...")
