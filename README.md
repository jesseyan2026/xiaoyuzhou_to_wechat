# 小宇宙博客转微信公众号文章工具

将小宇宙播客博客转换为微信公众号文章，支持主语改写和多种格式风格。

## 核心功能

1. **博客抓取** - 自动抓取小宇宙博客内容
2. **主语改写** - 将文章主语改为"我的朋友"
3. **格式转换** - 支持多种微信公众号文章格式
4. **参考学习** - 可学习参考公众号文章的格式

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

### 默认用法（Auto模式 - 推荐）

默认按 **Article → Audio → Shownotes** 优先级自动获取内容：

```bash
python main.py https://www.xiaoyuzhoufm.com/episode/123456
```

系统会依次尝试：
1. 搜索外部文章（最快获取现成文稿）
2. 音频转录（内容最完整准确）
3. 使用shownotes（保底方案）

### 仅使用音频转录（追求完整内容）

```bash
# 使用默认base模型（平衡速度与准确度）
python main.py https://www.xiaoyuzhoufm.com/episode/123456 --transcribe-mode audio

# 使用更大的模型提高准确度（但更慢）
python main.py https://www.xiaoyuzhoufm.com/episode/123456 --transcribe-mode audio --whisper-model medium

# 使用large模型（最高准确度，但最慢）
python main.py https://www.xiaoyuzhoufm.com/episode/123456 --transcribe-mode audio --whisper-model large
```

### 仅搜索外部文章

```bash
python main.py https://www.xiaoyuzhoufm.com/episode/123456 --transcribe-mode article
```

### 仅使用Shownotes（最快预览）

```bash
python main.py https://www.xiaoyuzhoufm.com/episode/123456 --transcribe-mode shownotes
```

### 指定格式风格

```bash
# 故事风格（首行缩进、更大行距）
python main.py https://www.xiaoyuzhoufm.com/episode/123456 --style story

# 访谈风格
python main.py https://www.xiaoyuzhoufm.com/episode/123456 --style interview
```

### 参考其他公众号文章格式

```bash
python main.py https://www.xiaoyuzhoufm.com/episode/123456 \
    --reference https://mp.weixin.qq.com/s/xxxxxx
```

### 完整示例

```bash
# 音频转录 + 故事风格 + 自定义输出
python main.py https://www.xiaoyuzhoufm.com/episode/123456 \
    --transcribe-mode audio \
    --style story \
    --output ./articles \
    --format html \
    --title "自定义标题"
```

## 命令行参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `url` | - | 小宇宙博客链接（必需） | - |
| `--style` | `-s` | 格式风格：default/minimal/story/interview/review | default |
| `--reference` | `-r` | 参考的微信公众号文章链接 | - |
| `--output` | `-o` | 输出目录 | ./output |
| `--format` | `-f` | 输出格式：html/md/txt/wechat | html |
| `--author` | `-a` | 原作者名称（用于替换） | 自动提取 |
| `--transform-mode` | `-t` | 改写模式：full/first_person_only/creator_only | full |
| `--no-transform` | - | 不进行主语改写 | - |
| `--title` | - | 自定义文章标题 | 原标题 |
| `--transcribe-mode` | `-tm` | 内容获取优先级：auto/audio/article/shownotes | **auto** |
| `--whisper-model` | `-wm` | Whisper模型：tiny/base/small/medium/large | **base** |
| `--skip-transcribe` | - | 跳过转录，直接使用shownotes | - |

### 内容获取优先级说明

**auto模式**（默认）按以下顺序尝试：

1. **article** - 外部文章搜索
   - 搜索微信公众号等平台是否有现成文稿
   - 最快获取完整内容（如果有的话）
   - 耗时：5-15秒

2. **audio** - 音频转录
   - 使用Whisper模型转录播客音频
   - 内容最完整准确（约10,000+字）
   - 耗时：3-10分钟（取决于模型和音频长度）

3. **shownotes** - 节目简介
   - 使用小宇宙页面的shownotes
   - 内容较简略（约1,000字）
   - 耗时：2-3秒

## 格式风格说明

- **default** - 默认格式，适合一般文章
- **minimal** - 简洁格式，适合短内容
- **story** - 故事格式，适合叙述性文章（首行缩进、更大行距）
- **interview** - 访谈格式，适合对话内容
- **review** - 评论格式，适合书评/影评

## 音频转录安装依赖

如需使用音频转录功能，需要安装：

```bash
# 安装Python依赖
pip install openai-whisper torch

# 安装系统依赖 ffmpeg
# Mac:
brew install ffmpeg

# Linux:
sudo apt-get install ffmpeg

# Windows: 从 https://ffmpeg.org/download.html 下载
```

## 主语改写说明

工具会自动将文章中的主语改为"我的朋友"：

- "我/我们" → "我的朋友/我的朋友们"
- "我的/我们的" → "我的朋友的/我的朋友们的"
- "主播/主持人/博主" → "我的朋友"
- 原作者名称 → "我的朋友"

## Python API 使用

```python
from xiaoyuzhou_to_wechat import (
    XiaoyuzhouCrawler,
    ContentProcessor,
    WechatFormatter,
    FormatStyle,
    ArticleExporter,
    ExportFormat
)

# 1. 抓取博客
crawler = XiaoyuzhouCrawler()
blog = crawler.fetch_blog("https://www.xiaoyuzhoufm.com/episode/123456")

# 2. 处理内容（主语改写）
processor = ContentProcessor(original_author=blog.author)
processed = processor.process(blog, subject_mode='full', use_html=True)

# 3. 格式化
formatter = WechatFormatter(style=FormatStyle.STORY)
html = formatter.format(
    title=blog.title,
    content=processed.transformed_content,
    author="我的朋友",
    is_html=True
)

# 4. 导出
exporter = ArticleExporter(output_dir="./output")
output_path = exporter.export(
    title=blog.title,
    content=html,
    author="我的朋友",
    format_type=ExportFormat.HTML
)
```

## 项目结构

```
xiaoyuzhou_to_wechat/
├── crawler/           # 爬虫模块
│   └── xiaoyuzhou_crawler.py
├── transformer/       # 内容转换模块
│   ├── subject_transformer.py    # 主语改写
│   └── content_processor.py      # 内容处理
├── formatter/         # 格式化模块
│   └── wechat_formatter.py       # 微信公众号格式化
├── output/            # 输出模块
│   └── exporter.py               # 文章导出
├── main.py            # CLI入口
├── requirements.txt
└── README.md
```
