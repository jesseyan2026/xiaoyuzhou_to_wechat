#!/usr/bin/env python3
"""
小宇宙博客转微信公众号文章工具

使用示例:
    # 基本用法
    python main.py https://www.xiaoyuzhoufm.com/episode/xxx

    # 指定格式风格
    python main.py https://www.xiaoyuzhoufm.com/episode/xxx --style story

    # 参考其他公众号文章格式
    python main.py https://www.xiaoyuzhoufm.com/episode/xxx --reference https://mp.weixin.qq.com/s/xxx

    # 指定输出格式
    python main.py https://www.xiaoyuzhoufm.com/episode/xxx --format markdown --output ./articles
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from crawler import XiaoyuzhouCrawler, BlogContent
from transformer import ContentProcessor, SubjectTransformer
from transformer.podcast_transcriber import PodcastTranscriber, TranscriptionResult
from formatter import WechatFormatter, FormatStyle
from output import ArticleExporter, ExportFormat


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="将小宇宙博客转换为微信公众号文章",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
【内容获取优先级 - Article → Audio → Shownotes】

  1. article  - 外部文章：搜索微信公众号等平台是否有现成文稿（最快）
  2. audio    - 音频转录：使用Whisper模型转录播客音频（内容最完整准确）
  3. shownotes - 节目简介：使用小宇宙页面的shownotes（保底方案）

  auto模式会按上述顺序自动尝试，失败则回退到下一优先级。

【格式风格】
  default   - 默认格式，适合一般文章
  minimal   - 简洁格式，适合短内容
  story     - 故事格式，适合叙述性文章（首行缩进、更大行距）
  interview - 访谈格式，适合对话内容
  review    - 评论格式，适合书评/影评

【使用示例】

  # 默认使用auto模式（推荐）
  %(prog)s https://www.xiaoyuzhoufm.com/episode/123456

  # 仅使用音频转录（如果确定要完整内容）
  %(prog)s https://www.xiaoyuzhoufm.com/episode/123456 --transcribe-mode audio

  # 使用更大的Whisper模型提高准确度
  %(prog)s https://www.xiaoyuzhoufm.com/episode/123456 --transcribe-mode audio --whisper-model medium

  # 故事风格 + 快速预览（跳过转录）
  %(prog)s https://www.xiaoyuzhoufm.com/episode/123456 --style story --transcribe-mode shownotes

  # 参考其他公众号文章格式
  %(prog)s https://www.xiaoyuzhoufm.com/episode/123456 --reference https://mp.weixin.qq.com/s/xxx
        """
    )

    parser.add_argument(
        'url',
        help='小宇宙博客链接'
    )

    parser.add_argument(
        '--style', '-s',
        choices=['default', 'minimal', 'story', 'interview', 'review'],
        default='default',
        help='文章格式风格 (默认: default)'
    )

    parser.add_argument(
        '--reference', '-r',
        help='参考的微信公众号文章链接，将学习其格式'
    )

    parser.add_argument(
        '--output', '-o',
        default='./output',
        help='输出目录 (默认: ./output)'
    )

    parser.add_argument(
        '--format', '-f',
        choices=['html', 'md', 'txt', 'wechat'],
        default='html',
        help='输出格式 (默认: html)'
    )

    parser.add_argument(
        '--author', '-a',
        help='原作者名称（用于替换为主语）'
    )

    parser.add_argument(
        '--transform-mode', '-t',
        choices=['full', 'first_person_only', 'creator_only'],
        default='full',
        help='主语改写模式 (默认: full)'
    )

    parser.add_argument(
        '--no-transform',
        action='store_true',
        help='不进行主语改写'
    )

    parser.add_argument(
        '--title',
        help='自定义文章标题'
    )

    # 转录相关参数
    # 转录相关参数 - 优先级: Audio → Article → Shownotes
    parser.add_argument(
        '--transcribe-mode', '-tm',
        choices=['auto', 'audio', 'article', 'shownotes'],
        default='auto',
        help='内容获取模式 (默认: auto)。优先级: article → audio → shownotes'
    )

    parser.add_argument(
        '--whisper-model', '-wm',
        choices=['tiny', 'base', 'small', 'medium', 'large'],
        default='base',
        help='Whisper模型大小 (默认: base)。tiny最快但准确度低，large最准但最慢'
    )

    parser.add_argument(
        '--skip-transcribe',
        action='store_true',
        help='跳过转录，直接使用shownotes'
    )

    return parser


def process_article(
    url: str,
    style: FormatStyle,
    reference_url: Optional[str],
    output_dir: str,
    export_format: ExportFormat,
    original_author: Optional[str],
    transform_mode: str,
    no_transform: bool,
    custom_title: Optional[str],
    transcribe_mode: str = 'shownotes',
    whisper_model: str = 'medium',
    skip_transcribe: bool = False
) -> str:
    """
    处理文章转换流程

    Returns:
        str: 输出文件路径
    """
    print(f"🔍 正在抓取博客内容: {url}")

    # 1. 抓取博客内容
    crawler = XiaoyuzhouCrawler()
    try:
        blog_content = crawler.fetch_blog(url)
        print(f"✅ 成功抓取: {blog_content.title}")
        print(f"   作者: {blog_content.author}")
        if blog_content.publish_date:
            print(f"   发布日期: {blog_content.publish_date}")
        if blog_content.audio_url:
            print(f"   音频: 已找到")
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        sys.exit(1)

    # 2. 内容转录（获取主要内容）
    if skip_transcribe or transcribe_mode == 'shownotes':
        print("⏭️  跳过转录，使用shownotes")
        main_content = blog_content.content
    else:
        try:
            transcriber = PodcastTranscriber(output_dir=output_dir)

            result = transcriber.transcribe(
                title=blog_content.title,
                audio_url=blog_content.audio_url,
                shownotes=blog_content.content,
                author=blog_content.author,
                episode_url=url,
                mode=transcribe_mode,
                whisper_model=whisper_model
            )

            main_content = result.content

            # 保存转录结果
            transcriber.save_result(result, blog_content.episode_id or "")

            print(f"✅ 内容获取完成 (来源: {result.source})")

            # 将shownotes作为参考附加
            if result.shownotes and result.source != 'shownotes':
                print(f"   已将shownotes保存为参考")

        except Exception as e:
            print(f"⚠️  转录失败: {e}")
            print("   回退到使用shownotes")
            main_content = blog_content.content

    # 3. 处理内容转换（主语改写）
    if no_transform:
        print("⏭️  跳过主语改写")
        processed_content = main_content
        final_author = blog_content.author
    else:
        print(f"📝 正在进行主语改写 (模式: {transform_mode})...")

        # 确定原作者
        author_to_replace = original_author or blog_content.author
        processor = ContentProcessor(original_author=author_to_replace)

        # 创建临时BlogContent用于处理
        temp_content = BlogContent(
            title=blog_content.title,
            author=author_to_replace,
            content=main_content,
            html_content=f"<p>{main_content}</p>",
            images=blog_content.images,
            original_url=url
        )

        processed = processor.process(
            content=temp_content,
            subject_mode=transform_mode,
            use_html=False  # 转录内容是纯文本
        )
        processed_content = processed.transformed_content
        final_author = "我的朋友"  # 改写后使用"我的朋友"作为作者
        print("✅ 主语改写完成")

    # 3. 格式化文章
    print(f"🎨 正在格式化文章 (风格: {style.value})...")
    formatter = WechatFormatter(style=style)

    # 如果提供了参考文章，学习其格式
    if reference_url:
        print(f"📖 正在学习参考文章格式: {reference_url}")
        try:
            formatter.learn_from_reference(reference_url)
            print("✅ 已学习参考文章格式")
        except Exception as e:
            print(f"⚠️  无法学习参考文章格式: {e}")

    # 确定标题
    title = custom_title or blog_content.title

    # 格式化内容
    formatted_html = formatter.format(
        title=title,
        content=processed_content,
        author=final_author,
        is_html=True,
        use_reference=reference_url is not None
    )
    print("✅ 格式化完成")

    # 4. 导出文章
    print(f"💾 正在导出文章...")
    exporter = ArticleExporter(output_dir=output_dir)
    output_path = exporter.export(
        title=title,
        content=formatted_html,
        author=final_author,
        format_type=export_format
    )
    print(f"✅ 导出成功: {output_path}")

    return output_path


def main():
    """主入口函数"""
    parser = create_parser()
    args = parser.parse_args()

    # 映射参数
    style_map = {
        'default': FormatStyle.DEFAULT,
        'minimal': FormatStyle.MINIMAL,
        'story': FormatStyle.STORY,
        'interview': FormatStyle.INTERVIEW,
        'review': FormatStyle.REVIEW,
    }

    format_map = {
        'html': ExportFormat.HTML,
        'md': ExportFormat.MARKDOWN,
        'txt': ExportFormat.TEXT,
        'wechat': ExportFormat.WECHAT_MP,
    }

    try:
        output_path = process_article(
            url=args.url,
            style=style_map[args.style],
            reference_url=args.reference,
            output_dir=args.output,
            export_format=format_map[args.format],
            original_author=args.author,
            transform_mode=args.transform_mode,
            no_transform=args.no_transform,
            custom_title=args.title,
            transcribe_mode=args.transcribe_mode,
            whisper_model=args.whisper_model,
            skip_transcribe=args.skip_transcribe
        )

        print("\n" + "=" * 50)
        print("🎉 转换完成!")
        print(f"📄 输出文件: {output_path}")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n\n⛔ 操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
