#!/usr/bin/env python3
"""
使用示例 - 展示如何使用 Python API 调用转换功能
"""

from xiaoyuzhou_to_wechat import (
    XiaoyuzhouCrawler,
    ContentProcessor,
    WechatFormatter,
    FormatStyle,
    ArticleExporter,
    ExportFormat
)


def example_basic():
    """基础用法示例"""
    # 小宇宙博客链接
    url = "https://www.xiaoyuzhoufm.com/episode/123456"

    # 1. 抓取博客
    print("正在抓取博客...")
    crawler = XiaoyuzhouCrawler()
    blog = crawler.fetch_blog(url)
    print(f"标题: {blog.title}")
    print(f"作者: {blog.author}")

    # 2. 处理内容（主语改写为"我的朋友"）
    print("\n正在改写主语...")
    processor = ContentProcessor(original_author=blog.author)
    processed = processor.process(blog, subject_mode='full', use_html=True)

    # 3. 使用故事风格格式化
    print("\n正在格式化...")
    formatter = WechatFormatter(style=FormatStyle.STORY)
    html = formatter.format(
        title=blog.title,
        content=processed.transformed_content,
        author="我的朋友",
        is_html=True
    )

    # 4. 导出为 HTML
    print("\n正在导出...")
    exporter = ArticleExporter(output_dir="./output")
    output_path = exporter.export(
        title=blog.title,
        content=html,
        author="我的朋友",
        format_type=ExportFormat.HTML
    )
    print(f"导出成功: {output_path}")


def example_with_reference():
    """参考其他公众号文章格式的示例"""
    url = "https://www.xiaoyuzhoufm.com/episode/123456"
    reference_url = "https://mp.weixin.qq.com/s/xxxxxx"  # 参考文章

    # 抓取博客
    crawler = XiaoyuzhouCrawler()
    blog = crawler.fetch_blog(url)

    # 处理内容
    processor = ContentProcessor(original_author=blog.author)
    processed = processor.process(blog, subject_mode='full', use_html=True)

    # 格式化（学习参考文章的格式）
    formatter = WechatFormatter()
    formatter.learn_from_reference(reference_url)  # 学习参考格式

    html = formatter.format(
        title=blog.title,
        content=processed.transformed_content,
        author="我的朋友",
        is_html=True,
        use_reference=True  # 使用学习的格式
    )

    # 导出
    exporter = ArticleExporter(output_dir="./output")
    output_path = exporter.export(
        title=blog.title,
        content=html,
        author="我的朋友",
        format_type=ExportFormat.HTML
    )
    print(f"导出成功: {output_path}")


def example_different_styles():
    """不同格式风格示例"""
    url = "https://www.xiaoyuzhoufm.com/episode/123456"

    crawler = XiaoyuzhouCrawler()
    blog = crawler.fetch_blog(url)

    processor = ContentProcessor(original_author=blog.author)
    processed = processor.process(blog, subject_mode='full', use_html=True)

    # 导出为不同风格
    styles = [FormatStyle.DEFAULT, FormatStyle.STORY, FormatStyle.INTERVIEW, FormatStyle.REVIEW]

    for style in styles:
        formatter = WechatFormatter(style=style)
        html = formatter.format(
            title=f"{blog.title} ({style.value})",
            content=processed.transformed_content,
            author="我的朋友",
            is_html=True
        )

        exporter = ArticleExporter(output_dir="./output")
        output_path = exporter.export(
            title=f"{blog.title}_{style.value}",
            content=html,
            author="我的朋友",
            format_type=ExportFormat.HTML
        )
        print(f"[{style.value}] 导出: {output_path}")


if __name__ == '__main__':
    print("=" * 50)
    print("示例 1: 基础用法")
    print("=" * 50)
    # example_basic()  # 取消注释以运行

    print("\n" + "=" * 50)
    print("示例 2: 参考其他公众号文章")
    print("=" * 50)
    # example_with_reference()  # 取消注释以运行

    print("\n" + "=" * 50)
    print("示例 3: 不同格式风格")
    print("=" * 50)
    # example_different_styles()  # 取消注释以运行

    print("\n请根据需要取消注释相应的示例函数来运行")
