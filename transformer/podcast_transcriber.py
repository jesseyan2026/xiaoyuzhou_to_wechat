"""
播客转录器 - 以语音内容为主，shownotes为参考

提供多种内容获取方式：
1. 音频转录 (Whisper) - 最准确，但耗时较长
2. 外部文章搜索 - 快速，依赖是否有现成文稿
3. shownotes 内容 - 作为参考备用
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


@dataclass
class TranscriptionResult:
    """转录结果"""
    content: str  # 主要内容（来自音频或外部文章）
    source: str  # 来源: 'audio', 'article', 'shownotes'
    source_url: Optional[str] = None  # 原文链接
    shownotes: Optional[str] = None  # shownotes作为参考
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AudioTranscriber:
    """音频转录器 - 使用Whisper"""

    def __init__(self):
        self.session = requests.Session()
        self.temp_dir = tempfile.mkdtemp(prefix="podcast_audio_")

    def transcribe(self, audio_url: str, title: str = "", model_size: str = "medium") -> str:
        """
        转录音频文件

        Args:
            audio_url: 音频文件URL
            title: 播客标题
            model_size: Whisper模型大小

        Returns:
            str: 转录文本
        """
        print(f"🎵 开始音频转录...")
        print(f"   音频URL: {audio_url[:80]}...")

        # 下载音频
        audio_path = self._download_audio(audio_url)
        print(f"✅ 音频下载完成: {audio_path}")

        try:
            # 使用Whisper转录
            transcription = self._transcribe_with_whisper(audio_path, model_size, title)
            return transcription
        finally:
            # 清理临时文件
            self._cleanup(audio_path)

    def _download_audio(self, audio_url: str) -> str:
        """下载音频文件"""
        print(f"⬇️  正在下载音频...")

        audio_path = os.path.join(self.temp_dir, f"podcast_{int(time.time())}.mp3")

        try:
            response = self.session.get(audio_url, stream=True, timeout=120)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(audio_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"   下载进度: {percent:.1f}%", end='\r')

            print(f"\n✅ 音频下载完成: {downloaded / 1024 / 1024:.1f} MB")
            return audio_path

        except Exception as e:
            raise Exception(f"下载音频失败: {e}")

    def _transcribe_with_whisper(self, audio_path: str, model_size: str, title: str) -> str:
        """使用Whisper转录音频"""
        print(f"🎯 使用Whisper转录（模型: {model_size}）...")

        # 首先尝试直接导入whisper（当前环境）
        try:
            import whisper
            return self._transcribe_with_whisper_local(audio_path, model_size, title)
        except ImportError:
            # 如果当前环境没有whisper，尝试使用venv_whisper
            return self._transcribe_with_whisper_subprocess(audio_path, model_size, title)

    def _transcribe_with_whisper_local(self, audio_path: str, model_size: str, title: str) -> str:
        """在当前环境使用Whisper转录"""
        import whisper

        print(f"   加载模型...")
        model = whisper.load_model(model_size)

        print("   正在转录（这可能需要一段时间，取决于音频长度）...")

        # 准备提示词
        prompt = f"这是一期中文播客节目，标题是《{title}》。内容涉及科技、商业和生活方式。"

        result = model.transcribe(
            audio_path,
            language="zh",
            verbose=False,
            initial_prompt=prompt,
            task="transcribe"
        )

        transcription = result["text"]

        # 格式化输出（添加段落分隔）
        formatted_text = self._format_transcription(transcription, result.get("segments", []))

        print(f"✅ 转录完成！共 {len(formatted_text)} 字符")
        return formatted_text

    def _transcribe_with_whisper_subprocess(self, audio_path: str, model_size: str, title: str) -> str:
        """使用子进程调用venv_whisper中的Python进行转录"""
        # 查找venv_whisper路径
        project_root = Path(__file__).parent.parent
        venv_whisper_python = project_root / "venv_whisper" / "bin" / "python"

        if not venv_whisper_python.exists():
            raise Exception(
                f"未找到Whisper环境: {venv_whisper_python}\n"
                "请确保venv_whisper虚拟环境存在，或安装Whisper到当前环境:\n"
                "  pip install openai-whisper torch"
            )

        print(f"   使用外部Python环境: {venv_whisper_python}")
        print("   正在转录（这可能需要一段时间，取决于音频长度）...")

        # 创建临时脚本来执行转录
        script_content = f'''
import json
import sys
import warnings
warnings.filterwarnings('ignore')

import whisper

model = whisper.load_model("{model_size}")

result = model.transcribe(
    "{audio_path}",
    language="zh",
    verbose=False,
    initial_prompt="这是一期中文播客节目，标题是《{title}》。",
    task="transcribe"
)

# 输出JSON结果
print(json.dumps(result, ensure_ascii=False))
'''

        script_path = os.path.join(self.temp_dir, "transcribe_script.py")
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)

        try:
            # 执行转录脚本
            result = subprocess.run(
                [str(venv_whisper_python), script_path],
                capture_output=True,
                text=True,
                timeout=3600  # 最多1小时
            )

            if result.returncode != 0:
                raise Exception(f"转录脚本执行失败: {result.stderr}")

            # 解析结果
            output = result.stdout.strip()
            # 找到JSON开始的位置
            json_start = output.find('{')
            if json_start == -1:
                raise Exception("无法解析转录结果")

            transcript_data = json.loads(output[json_start:])
            transcription = transcript_data.get("text", "")
            segments = transcript_data.get("segments", [])

            # 格式化输出
            formatted_text = self._format_transcription(transcription, segments)

            print(f"✅ 转录完成！共 {len(formatted_text)} 字符")
            return formatted_text

        except subprocess.TimeoutExpired:
            raise Exception("转录超时（超过1小时）")
        except Exception as e:
            raise Exception(f"Whisper转录失败: {e}")

    def _format_transcription(self, text: str, segments: List[dict]) -> str:
        """格式化转录文本，添加段落结构"""
        if not segments:
            # 如果没有分段信息，简单按句子分割
            sentences = re.split(r'([。！？\.\?\!])', text)
            paragraphs = []
            current_para = []

            for i, sent in enumerate(sentences):
                if sent.strip():
                    current_para.append(sent)
                # 每3-5句形成一个段落
                if len(current_para) >= 4 and i % 5 == 0:
                    paragraphs.append(''.join(current_para))
                    current_para = []

            if current_para:
                paragraphs.append(''.join(current_para))

            return '\n\n'.join(paragraphs)

        # 根据时间分段
        paragraphs = []
        current_para = []
        last_end = 0

        for seg in segments:
            text = seg.get("text", "").strip()
            if not text:
                continue

            start = seg.get("start", 0)

            # 如果停顿超过2秒，形成新段落
            if start - last_end > 2.0 and current_para:
                paragraphs.append(' '.join(current_para))
                current_para = []

            current_para.append(text)
            last_end = seg.get("end", start)

        if current_para:
            paragraphs.append(' '.join(current_para))

        return '\n\n'.join(paragraphs)

    def _cleanup(self, audio_path: str):
        """清理临时文件"""
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            if os.path.exists(self.temp_dir):
                os.rmdir(self.temp_dir)
        except:
            pass


class ArticleSearcher:
    """外部文章搜索器 - 搜索语音稿"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })

    def search(self, title: str, author: str = "", shownotes: str = "") -> Optional[str]:
        """
        搜索外部文章

        Args:
            title: 播客标题
            author: 作者/主播名
            shownotes: shownotes内容用于提取关键词

        Returns:
            Optional[str]: 找到的文章内容，找不到返回None
        """
        print(f"\n🔎 正在搜索外部文章...")
        print(f"   标题: {title}")

        # 构建搜索查询
        queries = self._build_queries(title, author, shownotes)

        # 搜索各个平台
        for query in queries:
            print(f"\n   搜索: {query}")

            # 1. 搜索微信公众号 (通过搜狗)
            result = self._search_wechat(query)
            if result:
                print(f"✅ 找到微信公众号文章")
                return result

            # 2. 搜索其他平台
            result = self._search_other(query)
            if result:
                print(f"✅ 找到文章: {result[:100]}...")
                return result

            time.sleep(0.5)  # 避免请求过快

        print("⚠️  未找到外部文章")
        return None

    def _build_queries(self, title: str, author: str, shownotes: str) -> List[str]:
        """构建搜索查询"""
        queries = [title]  # 优先用完整标题搜索

        # 提取关键词
        keywords = self._extract_keywords(title + " " + shownotes)
        if keywords:
            queries.append(f"{' '.join(keywords[:3])} 播客 逐字稿")
            queries.append(f"{' '.join(keywords[:3])}  transcript")

        if author:
            queries.append(f"{author} {title[:30]}")

        return queries[:4]

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 常见话题关键词
        keywords = [
            'AI', '人工智能', '创业', '投资', '出海', '搞钱', '副业',
            '短视频', '直播', 'TikTok', '抖音', '小红书', '电商',
            '短剧', '漫剧', '内容创作', '自媒体', '流量', '变现',
            '墨西哥', '拉美', '东南亚', '跨境', '外贸', 'MCN',
            '播客', ' podcast', '访谈', '对话', '分享'
        ]

        found = []
        for kw in keywords:
            if kw in text:
                found.append(kw)

        return found[:5]

    def _search_wechat(self, query: str) -> Optional[str]:
        """搜索微信公众号文章"""
        try:
            encoded_query = quote(query)
            url = f"https://weixin.sogou.com/weixin?type=2&query={encoded_query}"

            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取搜索结果
            items = soup.find_all('div', class_='txt-box')[:3]

            for item in items:
                try:
                    title_elem = item.find('h3')
                    if not title_elem:
                        continue

                    link_elem = title_elem.find('a')
                    if not link_elem:
                        continue

                    href = link_elem.get('href', '')
                    if href.startswith('/'):
                        href = f"https://weixin.sogou.com{href}"

                    # 抓取文章内容
                    content = self._fetch_wechat_article(href)
                    if content and len(content) > 800:
                        return content

                except Exception as e:
                    continue

            return None

        except Exception as e:
            print(f"   搜索微信时出错: {e}")
            return None

    def _fetch_wechat_article(self, url: str) -> Optional[str]:
        """抓取微信公众号文章内容"""
        try:
            # 注意：搜狗微信的链接需要跳转
            response = self.session.get(url, timeout=20, allow_redirects=True)

            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取正文
            content = soup.find('div', id='js_content')
            if not content:
                content = soup.find('div', class_='rich_media_content')

            if content:
                # 清理
                for tag in content.find_all(['script', 'style', 'img']):
                    tag.decompose()

                text = content.get_text(separator='\n', strip=True)
                text = re.sub(r'\n+', '\n', text)

                return text

            return None

        except Exception as e:
            return None

    def _search_other(self, query: str) -> Optional[str]:
        """搜索其他平台"""
        # 可以扩展搜索更多平台
        # 如：今日头条、知乎、百度等
        return None


class PodcastTranscriber:
    """
    播客转录器主类

    内容获取优先级（auto模式）：
    1. 外部文章搜索（最快获取现成文稿）
    2. 音频转录（内容最完整准确）
    3. shownotes（保底方案）
    """

    # 默认优先级配置
    DEFAULT_PRIORITY = ['article', 'audio', 'shownotes']

    def __init__(self, output_dir: str = "./transcriptions"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.audio_transcriber = AudioTranscriber()
        self.article_searcher = ArticleSearcher()

    def transcribe(
        self,
        title: str,
        audio_url: Optional[str] = None,
        shownotes: str = "",
        author: str = "",
        episode_url: str = "",
        mode: str = "auto",  # 'auto', 'audio', 'article', 'shownotes'
        whisper_model: str = "base"
    ) -> TranscriptionResult:
        """
        转录播客内容

        优先级顺序：Audio → Article → Shownotes

        Args:
            title: 播客标题
            audio_url: 音频URL（可选）
            shownotes: shownotes内容
            author: 作者/主播
            episode_url: 播客页面URL
            mode: 转录模式
                - 'auto': 自动按优先级尝试（audio → article → shownotes）
                - 'audio': 仅使用音频转录
                - 'article': 仅使用外部文章搜索
                - 'shownotes': 仅使用shownotes
            whisper_model: Whisper模型大小（默认base，平衡速度与准确度）

        Returns:
            TranscriptionResult: 转录结果
        """
        print("=" * 60)
        print("🎙️  播客转录")
        print("=" * 60)
        print(f"标题: {title}")
        print(f"模式: {mode}")
        print(f"优先级: {' → '.join(self.DEFAULT_PRIORITY)}")

        # 模式1: 外部文章搜索（最高优先级 - 最快获取现成文稿）
        if mode in ('auto', 'article'):
            try:
                print("\n" + "-" * 60)
                print("🔎 尝试搜索外部文章...")
                print("-" * 60)

                content = self.article_searcher.search(title, author, shownotes)

                if content:
                    print("✅ 成功获取外部文章")
                    return TranscriptionResult(
                        content=content,
                        source='article',
                        shownotes=shownotes,
                        metadata={
                            'title': title,
                            'author': author,
                            'method': 'article_search'
                        }
                    )

            except Exception as e:
                print(f"⚠️  文章搜索失败: {e}")
                if mode == 'article':
                    raise

        # 模式2: 音频转录（第二优先级 - 内容最完整）
        if mode in ('auto', 'audio') and audio_url:
            try:
                print("\n" + "-" * 60)
                print("🎵 尝试音频转录...")
                print("-" * 60)

                content = self.audio_transcriber.transcribe(audio_url, title, whisper_model)

                return TranscriptionResult(
                    content=content,
                    source='audio',
                    source_url=audio_url,
                    shownotes=shownotes,
                    metadata={
                        'title': title,
                        'author': author,
                        'method': 'whisper',
                        'model': whisper_model
                    }
                )

            except Exception as e:
                print(f"⚠️  音频转录失败: {e}")
                if mode == 'audio':
                    raise

        # 模式2: 外部文章搜索
        if mode in ('auto', 'article'):
            try:
                content = self.article_searcher.search(title, author, shownotes)

                if content:
                    return TranscriptionResult(
                        content=content,
                        source='article',
                        shownotes=shownotes,
                        metadata={
                            'title': title,
                            'author': author,
                            'method': 'article_search'
                        }
                    )

            except Exception as e:
                print(f"⚠️  文章搜索失败: {e}")
                if mode == 'article':
                    raise

        # 模式3: 使用shownotes
        print("\n" + "-" * 60)
        print("📝 使用shownotes作为内容")
        print("-" * 60)

        return TranscriptionResult(
            content=shownotes,
            source='shownotes',
            shownotes=shownotes,
            metadata={
                'title': title,
                'author': author,
                'method': 'shownotes'
            }
        )

    def save_result(self, result: TranscriptionResult, episode_id: str = "") -> str:
        """保存转录结果"""
        # 生成文件名
        safe_title = re.sub(r'[^\w\s-]', '', result.metadata.get('title', 'podcast'))
        safe_title = safe_title.strip()[:50]

        if not episode_id:
            episode_id = str(int(time.time()))

        output_file = self.output_dir / f"{safe_title}_{episode_id}.md"

        # 构建内容
        lines = [
            f"# {result.metadata.get('title', '播客转录')}",
            "",
            f"**来源**: {result.source}",
            f"**作者**: {result.metadata.get('author', '未知')}",
        ]

        if result.source_url:
            lines.append(f"**音频链接**: {result.source_url}")

        lines.extend([
            f"**转录时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
            "## 主要内容",
            "",
            result.content,
        ])

        if result.shownotes and result.source != 'shownotes':
            lines.extend([
                "",
                "---",
                "",
                "## 节目简介 (shownotes)",
                "",
                result.shownotes,
            ])

        # 保存
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"\n💾 已保存到: {output_file}")
        return str(output_file)
