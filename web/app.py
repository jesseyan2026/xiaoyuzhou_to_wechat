#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
播客转文章Web平台 - Flask后端
支持：微信公众号、小红书文章生成
"""

import os
import sys
import json
import uuid
import threading
import tempfile
import hashlib
from datetime import datetime
from pathlib import Path

import requests

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS

# 添加父目录到路径以导入转录模块
sys.path.append(str(Path(__file__).parent.parent))
from transcribe_podcast import SmartPodcastTranscriber, PodcastInfoExtractor

app = Flask(__name__)
CORS(app)

# 配置
UPLOAD_FOLDER = Path(__file__).parent / 'uploads'
OUTPUT_FOLDER = Path(__file__).parent / 'output'
CACHE_FOLDER = Path(__file__).parent / 'cache'
UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)
CACHE_FOLDER.mkdir(exist_ok=True)

# 存储任务状态的任务字典
tasks = {}

# ============ 缓存功能 ============

def get_cache_key(url: str) -> str:
    """生成URL的缓存键"""
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def get_cache_path(url: str) -> Path:
    """获取缓存文件路径"""
    cache_key = get_cache_key(url)
    return CACHE_FOLDER / f"{cache_key}.json"

def load_cache(url: str) -> dict | None:
    """加载缓存的转录结果"""
    cache_path = get_cache_path(url)
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            print(f"[Cache] 命中缓存: {url[:50]}...")
            return cache_data
        except Exception as e:
            print(f"[Cache] 读取缓存失败: {e}")
    return None

def save_cache(url: str, data: dict) -> bool:
    """保存转录结果到缓存"""
    cache_path = get_cache_path(url)
    try:
        cache_data = {
            'url': url,
            'created_at': datetime.now().isoformat(),
            'data': data
        }
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        print(f"[Cache] 已保存缓存: {url[:50]}...")
        return True
    except Exception as e:
        print(f"[Cache] 保存缓存失败: {e}")
        return False

def list_cache():
    """列出所有缓存"""
    caches = []
    for cache_file in CACHE_FOLDER.glob('*.json'):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            caches.append({
                'url': cache_data.get('url', ''),
                'created_at': cache_data.get('created_at', ''),
                'size': cache_file.stat().st_size
            })
        except:
            pass
    return caches

# ============ 平台风格配置 ============
PLATFORM_CONFIGS = {
    'wechat': {
        'name': '微信公众号',
        'icon': '📱',
        'description': '适合深度长文，支持HTML格式',
        'default_styles': {
            'narrative': {
                'name': '故事叙述风',
                'description': '以第三人称叙述，故事性强，首行缩进',
                'params': {
                    'narrator': '我的朋友',
                    'tone': 'narrative',
                    'first_line_indent': True,
                    'line_height': 2.0,
                    'font_size': 16,
                    'paragraph_spacing': 'large'
                }
            },
            'formal': {
                'name': '正式报道风',
                'description': '客观正式，适合资讯类内容',
                'params': {
                    'narrator': '本报记者',
                    'tone': 'formal',
                    'first_line_indent': False,
                    'line_height': 1.8,
                    'font_size': 16,
                    'paragraph_spacing': 'normal'
                }
            },
            'casual': {
                'name': '轻松随笔风',
                'description': '轻松随意，像朋友聊天',
                'params': {
                    'narrator': '小编',
                    'tone': 'casual',
                    'first_line_indent': True,
                    'line_height': 1.8,
                    'font_size': 15,
                    'paragraph_spacing': 'normal'
                }
            }
        },
        'format_options': {
            'html': True,
            'markdown': True,
            'plain': False
        },
        'max_length': 20000,
        'support_images': True
    },
    'xiaohongshu': {
        'name': '小红书',
        'icon': '📕',
        'description': '短平快，emoji丰富，适合种草',
        'default_styles': {
            'notes': {
                'name': '笔记种草风',
                'description': '分点清晰，emoji多，干货满满',
                'params': {
                    'narrator': '博主',
                    'tone': 'notes',
                    'use_emoji': True,
                    'bullet_points': True,
                    'highlight_key_points': True,
                    'add_tags': True,
                    'max_length': 1000
                }
            },
            'diary': {
                'name': '生活记录风',
                'description': '像个人日记，亲切自然',
                'params': {
                    'narrator': '我',
                    'tone': 'diary',
                    'use_emoji': True,
                    'bullet_points': False,
                    'highlight_key_points': False,
                    'add_tags': True,
                    'max_length': 1000
                }
            },
            'guide': {
                'name': '攻略教程风',
                'description': '步骤清晰，实用性强',
                'params': {
                    'narrator': '攻略君',
                    'tone': 'guide',
                    'use_emoji': True,
                    'bullet_points': True,
                    'highlight_key_points': True,
                    'add_tags': True,
                    'max_length': 800
                }
            }
        },
        'format_options': {
            'html': False,
            'markdown': True,
            'plain': True
        },
        'max_length': 1000,
        'support_images': True
    }
}

# ============ 路由 ============

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/platform')
def platform_select():
    """平台选择页"""
    return render_template('platform.html')

@app.route('/style')
def style_customize():
    """风格自定义页"""
    return render_template('style.html')

@app.route('/preview')
def preview():
    """文章预览页"""
    return render_template('preview.html')

# ============ API端点 ============

@app.route('/api/platforms', methods=['GET'])
def get_platforms():
    """获取所有平台配置"""
    return jsonify({
        'success': True,
        'data': PLATFORM_CONFIGS
    })

@app.route('/api/analyze', methods=['POST'])
def analyze_podcast():
    """分析播客链接"""
    data = request.json
    url = data.get('url', '')

    if not url or 'xiaoyuzhou' not in url:
        return jsonify({
            'success': False,
            'error': '请输入有效的小宇宙播客链接'
        }), 400

    try:
        # 创建任务ID
        task_id = str(uuid.uuid4())

        # 初始化任务状态
        tasks[task_id] = {
            'id': task_id,
            'status': 'analyzing',
            'url': url,
            'progress': 10,
            'message': '正在分析播客信息...',
            'created_at': datetime.now().isoformat()
        }

        # 在后台线程中执行分析
        def analyze_task():
            try:
                extractor = PodcastInfoExtractor()
                info = extractor.extract(url)

                tasks[task_id].update({
                    'status': 'completed',
                    'progress': 100,
                    'message': '分析完成',
                    'data': info
                })
            except Exception as e:
                tasks[task_id].update({
                    'status': 'error',
                    'message': str(e)
                })

        thread = threading.Thread(target=analyze_task)
        thread.start()

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '开始分析播客信息'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """获取任务状态"""
    if task_id not in tasks:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404

    return jsonify({
        'success': True,
        'data': tasks[task_id]
    })

@app.route('/api/task/last', methods=['GET'])
def get_last_task():
    """获取最新的任务"""
    if not tasks:
        return jsonify({
            'success': False,
            'error': '暂无任务'
        }), 404

    # 获取最新的任务
    last_task = max(tasks.values(), key=lambda x: x.get('created_at', ''))
    return jsonify({
        'success': True,
        'data': last_task
    })

@app.route('/api/transcribe', methods=['POST'])
def transcribe_podcast():
    """转录播客音频"""
    data = request.json
    url = data.get('url', '')
    # 总是生成新的 task_id，不接收前端传递的 task_id，避免与 analyze 任务冲突
    task_id = str(uuid.uuid4())

    if not url:
        return jsonify({
            'success': False,
            'error': '请提供播客链接'
        }), 400

    # 初始化任务 - 包含详细的模式状态跟踪
    tasks[task_id] = {
        'id': task_id,
        'status': 'transcribing',
        'url': url,
        'progress': 0,
        'message': '准备转录...',
        'created_at': datetime.now().isoformat(),
        'step': '初始化',
        'detail_log': [],
        # 详细的模式状态跟踪
        'modes': {
            'article': {'status': 'pending', 'message': '等待执行', 'articles': [], 'failed_articles': []},
            'audio': {'status': 'pending', 'message': '等待执行', 'error': None},
            'shownotes': {'status': 'pending', 'message': '等待执行'}
        },
        'current_mode': None
    }

    def add_log(message):
        """添加详细日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f'[{timestamp}] {message}'
        tasks[task_id]['detail_log'].append(log_entry)
        tasks[task_id]['message'] = message
        print(f"[Task {task_id[:8]}] {message}")

    def transcribe_task():
        try:
            transcriber = SmartPodcastTranscriber(output_dir=str(OUTPUT_FOLDER))

            # 步骤0: 检查缓存
            add_log('💾 检查本地缓存...')
            cached_result = load_cache(url)
            if cached_result:
                cache_data = cached_result.get('data', {})
                add_log('✅ 命中缓存！直接返回已转录内容')
                tasks[task_id].update({
                    'status': 'completed',
                    'progress': 100,
                    'step': '完成（来自缓存）',
                    'message': '✅ 已从缓存加载转录内容',
                    'modes': {
                        'article': {'status': 'completed', 'message': '使用缓存内容', 'articles': [], 'failed_articles': []},
                        'audio': {'status': 'completed', 'message': '使用缓存内容', 'error': None},
                        'shownotes': {'status': 'completed', 'message': '使用缓存内容'}
                    },
                    'data': cache_data,
                    'from_cache': True
                })
                return

            # 步骤1: 提取播客信息
            add_log('🎯 步骤1/5: 正在提取播客信息...')
            tasks[task_id].update({
                'progress': 15,
                'step': '提取播客信息'
            })

            try:
                info = transcriber.info_extractor.extract(url)
                add_log(f'✅ 成功提取播客信息: {info.title[:50]}...')
                add_log(f'   主播: {info.author}')
                if info.audio_url:
                    add_log(f'   音频链接: 已获取')
            except Exception as e:
                add_log(f'❌ 提取播客信息失败: {str(e)}')
                raise

            # 步骤2: 搜索外部文稿 (Article模式 - 第一优先级)
            add_log('🔍 步骤2/5: Article模式 - 正在搜索外部文稿...')
            add_log('   优先搜索微信公众号等平台是否有现成文稿...')
            tasks[task_id].update({
                'progress': 30,
                'step': 'Article模式：搜索外部文稿',
                'current_mode': 'article'
            })
            tasks[task_id]['modes']['article']['status'] = 'searching'
            tasks[task_id]['modes']['article']['message'] = '正在搜索外部文章...'

            try:
                search_results = transcriber.source_searcher.search(info)
                add_log(f'✅ 找到 {len(search_results)} 篇相关文章')

                # 保存文章列表到任务状态
                articles_info = []
                for article in search_results[:5]:
                    articles_info.append({
                        'title': article.title,
                        'url': article.url,
                        'source': article.source,
                        'status': 'pending'
                    })
                tasks[task_id]['modes']['article']['articles'] = articles_info

                # 显示找到的文章
                for i, article in enumerate(search_results[:3], 1):
                    add_log(f'   {i}. [{article.source}] {article.title[:40]}...')
            except Exception as e:
                add_log(f'⚠️ 搜索外部文稿出错: {str(e)}')
                tasks[task_id]['modes']['article']['status'] = 'error'
                tasks[task_id]['modes']['article']['message'] = f'搜索失败: {str(e)}'
                search_results = []

            # 步骤3: 尝试获取文章内容 (Article模式继续)
            if search_results:
                add_log('📄 步骤3/5: Article模式 - 正在尝试获取文章内容...')
                tasks[task_id].update({
                    'progress': 50,
                    'step': '获取文章内容'
                })
                tasks[task_id]['modes']['article']['status'] = 'fetching'
                tasks[task_id]['modes']['article']['message'] = '正在获取文章内容...'

                failed_articles = []

                for i, article in enumerate(search_results[:5]):
                    add_log(f'   尝试获取文章 {i+1}/5: {article.title[:40]}...')
                    tasks[task_id].update({
                        'progress': 50 + i * 5,
                        'message': f'正在获取文章: {article.title[:30]}...'
                    })

                    # 更新文章状态
                    if i < len(tasks[task_id]['modes']['article']['articles']):
                        tasks[task_id]['modes']['article']['articles'][i]['status'] = 'fetching'

                    try:
                        content = transcriber.article_fetcher.fetch(article)
                        if content and len(content) > 500:
                            add_log(f'✅ 成功获取文章！({len(content)} 字符)')
                            tasks[task_id]['modes']['article']['status'] = 'completed'
                            tasks[task_id]['modes']['article']['message'] = '成功获取文稿'
                            if i < len(tasks[task_id]['modes']['article']['articles']):
                                tasks[task_id]['modes']['article']['articles'][i]['status'] = 'success'

                            # 准备结果数据
                            result_data = {
                                'source': article.source,
                                'title': info.title,
                                'content': content,
                                'method': 'external'
                            }

                            # 保存到缓存
                            save_cache(url, result_data)

                            tasks[task_id].update({
                                'status': 'completed',
                                'progress': 100,
                                'step': '完成',
                                'message': '成功获取文稿',
                                'data': result_data
                            })
                            return
                        else:
                            add_log(f'   ⚠️ 文章内容太短或为空，跳过')
                            if i < len(tasks[task_id]['modes']['article']['articles']):
                                tasks[task_id]['modes']['article']['articles'][i]['status'] = 'skipped'
                                tasks[task_id]['modes']['article']['articles'][i]['error'] = f'内容太短({len(content) if content else 0}字符)'
                            # 也添加到失败列表，方便用户查看
                            failed_articles.append({
                                'title': article.title,
                                'url': article.url,
                                'source': article.source,
                                'error': f'内容太短({len(content) if content else 0}字符)'
                            })
                    except Exception as e:
                        error_msg = str(e)[:100]
                        add_log(f'   ❌ 获取失败: {error_msg}')
                        failed_articles.append({
                            'title': article.title,
                            'url': article.url,
                            'source': article.source,
                            'error': error_msg
                        })
                        if i < len(tasks[task_id]['modes']['article']['articles']):
                            tasks[task_id]['modes']['article']['articles'][i]['status'] = 'failed'
                            tasks[task_id]['modes']['article']['articles'][i]['error'] = error_msg
                        continue

                # Article模式失败，记录失败的文章
                tasks[task_id]['modes']['article']['status'] = 'failed'
                tasks[task_id]['modes']['article']['message'] = f'尝试{len(search_results[:5])}篇文章均失败'
                tasks[task_id]['modes']['article']['failed_articles'] = failed_articles[:3]  # 保存前3个失败的文章
                add_log('⚠️ Article模式：无法从外部源获取完整内容')
                add_log('⬇️ 将回退到Audio模式...')

            # 步骤4: 音频转录 (Audio模式 - 第二优先级)
            add_log('🎵 步骤4/5: Audio模式 - 开始使用Whisper转录音频...')
            add_log('   使用base模型（平衡速度与准确度）...')
            tasks[task_id].update({
                'progress': 70,
                'step': 'Audio模式：转录音频',
                'current_mode': 'audio'
            })
            tasks[task_id]['modes']['audio']['status'] = 'downloading'
            tasks[task_id]['modes']['audio']['message'] = '正在下载音频文件...'

            if info.audio_url:
                try:
                    # 下载音频
                    add_log('⬇️ 正在下载音频文件...')
                    tasks[task_id].update({
                        'progress': 75,
                        'step': 'Audio模式：下载音频'
                    })
                    audio_path = os.path.join(tempfile.gettempdir(), f"podcast_{task_id}.m4a")
                    response = requests.get(info.audio_url, stream=True, timeout=120)
                    response.raise_for_status()

                    total_size = int(response.headers.get('content-length', 0))
                    add_log(f'   音频大小: {total_size / 1024 / 1024:.1f} MB')

                    downloaded = 0
                    with open(audio_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    percent = (downloaded / total_size) * 100
                                    if int(percent) % 20 == 0:  # 每20%报告一次
                                        add_log(f'   下载进度: {percent:.0f}%')

                    add_log('✅ 音频下载完成')

                    # 检查音频文件大小
                    file_size = os.path.getsize(audio_path)
                    add_log(f'📊 音频文件大小: {file_size / 1024 / 1024:.1f} MB')

                    # 如果音频太大，提示用户
                    if file_size > 200 * 1024 * 1024:  # 200MB
                        add_log('⚠️ 音频文件较大，转录可能需要较长时间...')

                    add_log('🤖 正在启动Whisper进行转录...')
                    add_log('   使用模型: base ( fastest )')
                    add_log('   长音频可能需要10-30分钟，请耐心等待')

                    tasks[task_id].update({
                        'progress': 80,
                        'step': 'Audio模式：AI转录中',
                        'message': 'Whisper正在转录音频（这可能需要较长时间）...'
                    })
                    # 更新Audio模式状态为processing
                    tasks[task_id]['modes']['audio']['status'] = 'processing'
                    tasks[task_id]['modes']['audio']['message'] = 'Whisper正在转录音频（这可能需要10-30分钟）...'

                    # 使用Whisper命令行工具转录
                    import subprocess
                    whisper_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'venv_whisper', 'bin', 'whisper')
                    output_dir = tempfile.gettempdir()

                    # Whisper输出文件名基于输入文件名
                    audio_basename = os.path.basename(audio_path).replace('.m4a', '')
                    transcript_file = os.path.join(output_dir, f"{audio_basename}.txt")

                    add_log(f'   音频路径: {audio_path}')
                    add_log(f'   预期输出: {transcript_file}')

                    # 使用更快的模型(base)，并限制线程数以加快处理
                    cmd = [
                        whisper_path,
                        audio_path,
                        '--model', 'base',
                        '--language', 'zh',
                        '--output_format', 'txt',
                        '--output_dir', output_dir,
                        '--threads', '4',
                    ]

                    add_log('   转录进行中...')
                    add_log(f'   执行命令: whisper {audio_basename}.m4a --model base --language zh')

                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30分钟超时
                    except subprocess.TimeoutExpired:
                        add_log('❌ Whisper转录超时（超过30分钟）')
                        raise Exception("Whisper转录超时，音频可能太长")

                    if result.returncode != 0:
                        add_log(f'❌ Whisper错误输出: {result.stderr[:200]}')
                        raise Exception(f"Whisper转录失败: {result.stderr}")

                    add_log('✅ Whisper转录命令执行完成')

                    # 检查输出文件是否存在
                    if not os.path.exists(transcript_file):
                        # 尝试查找其他可能的输出文件
                        potential_files = [
                            audio_path.replace('.m4a', '.txt'),
                            os.path.join(output_dir, f"{task_id}.txt"),
                        ]
                        for pf in potential_files:
                            if os.path.exists(pf):
                                transcript_file = pf
                                add_log(f'   找到替代输出文件: {pf}')
                                break
                        else:
                            raise Exception(f"找不到转录输出文件: {transcript_file}")

                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        transcription = f.read()

                    add_log(f'📄 转录完成！共 {len(transcription)} 字符')

                    # 清理临时文件
                    try:
                        os.remove(audio_path)
                        if os.path.exists(transcript_file):
                            os.remove(transcript_file)
                        add_log('🧹 清理临时文件')
                    except:
                        pass

                    add_log('🎉 全部完成！')

                    # 更新Audio模式状态为成功
                    tasks[task_id]['modes']['audio']['status'] = 'completed'
                    tasks[task_id]['modes']['audio']['message'] = f'转录完成 ({len(transcription)} 字符)'

                    # 准备结果数据
                    result_data = {
                        'source': 'audio_whisper',
                        'title': info.title,
                        'content': transcription,
                        'method': 'whisper'
                    }

                    # 保存到缓存
                    save_cache(url, result_data)

                    tasks[task_id].update({
                        'status': 'completed',
                        'progress': 100,
                        'step': '完成',
                        'message': '✅ 音频转录完成',
                        'data': result_data
                    })
                    return

                except Exception as audio_e:
                    error_msg = str(audio_e)
                    add_log(f'❌ 音频转录失败: {error_msg[:100]}')
                    add_log('⚠️ Article模式和Audio模式均失败，将回退到Shownotes模式')
                    # 更新Audio模式状态为失败
                    tasks[task_id]['modes']['audio']['status'] = 'failed'
                    tasks[task_id]['modes']['audio']['message'] = f'转录失败: {error_msg[:100]}'
                    tasks[task_id]['modes']['audio']['error'] = error_msg
                    # 继续执行到shownotes回退逻辑
                    pass
            else:
                add_log('❌ 无法获取音频链接')
                add_log('⚠️ Article模式失败且无法获取音频，将回退到Shownotes模式')
                # 更新Audio模式状态为失败
                tasks[task_id]['modes']['audio']['status'] = 'failed'
                tasks[task_id]['modes']['audio']['message'] = '无法获取音频链接'
                # 继续执行到shownotes回退逻辑
                pass

            # 步骤5: 回退到Shownotes（保底方案）
            add_log('📝 步骤5/5: 使用Shownotes作为内容来源...')
            tasks[task_id].update({
                'progress': 90,
                'step': 'Shownotes模式：使用节目简介',
                'message': 'Article和Audio均不可用，使用Shownotes...',
                'current_mode': 'shownotes'
            })
            tasks[task_id]['modes']['shownotes']['status'] = 'processing'
            tasks[task_id]['modes']['shownotes']['message'] = '正在获取节目简介...'

            try:
                # 获取shownotes内容
                shownotes_content = info.description if hasattr(info, 'description') and info.description else "未找到节目简介"

                if shownotes_content and len(shownotes_content) > 50:
                    add_log(f'✅ 成功获取Shownotes！({len(shownotes_content)} 字符)')
                    add_log('💡 提示: 这是节目简介内容，可能不够完整')

                    # 更新Shownotes模式状态为成功
                    tasks[task_id]['modes']['shownotes']['status'] = 'completed'
                    tasks[task_id]['modes']['shownotes']['message'] = f'获取成功 ({len(shownotes_content)} 字符)'

                    # 准备结果数据
                    result_data = {
                        'source': 'shownotes',
                        'title': info.title,
                        'content': shownotes_content,
                        'method': 'shownotes'
                    }

                    # 保存到缓存
                    save_cache(url, result_data)

                    tasks[task_id].update({
                        'status': 'completed',
                        'progress': 100,
                        'step': '完成',
                        'message': '已使用Shownotes生成内容',
                        'data': result_data
                    })
                    return
                else:
                    add_log('❌ Shownotes内容太短或为空')
                    raise Exception("无法获取有效的Shownotes内容")

            except Exception as shownotes_e:
                add_log(f'❌ 所有方式均失败: {str(shownotes_e)[:100]}')
                # 更新Shownotes模式状态为失败
                tasks[task_id]['modes']['shownotes']['status'] = 'failed'
                tasks[task_id]['modes']['shownotes']['message'] = f'获取失败: {str(shownotes_e)[:100]}'

                tasks[task_id].update({
                    'status': 'error',
                    'step': '完全失败',
                    'message': 'Article、Audio、Shownotes均无法获取内容。请手动粘贴转录内容。',
                    'error_detail': str(shownotes_e)
                })
                return

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            add_log(f'❌ 转录过程出错: {str(e)[:100]}')
            print(error_detail)
            tasks[task_id].update({
                'status': 'error',
                'step': '错误',
                'message': f'转录失败: {str(e)}',
                'error_detail': str(e)
            })

    thread = threading.Thread(target=transcribe_task)
    thread.start()

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '开始转录任务'
    })

@app.route('/api/generate', methods=['POST'])
def generate_article():
    """生成文章"""
    data = request.json
    content = data.get('content', '')
    platform = data.get('platform', 'wechat')
    style = data.get('style', {})

    if not content:
        return jsonify({
            'success': False,
            'error': '请提供内容'
        }), 400

    try:
        task_id = str(uuid.uuid4())

        tasks[task_id] = {
            'id': task_id,
            'status': 'generating',
            'progress': 0,
            'message': '正在生成文章...',
            'created_at': datetime.now().isoformat()
        }

        def generate_task():
            try:
                from article_generator import ArticleGenerator

                tasks[task_id].update({
                    'progress': 30,
                    'message': '正在调用Claude API生成文章...'
                })

                # 创建生成器并生成文章
                generator = ArticleGenerator()
                result = generator.generate(content, platform, style)

                tasks[task_id].update({
                    'status': 'completed',
                    'progress': 100,
                    'message': '文章生成完成',
                    'data': result
                })

            except Exception as e:
                tasks[task_id].update({
                    'status': 'error',
                    'message': str(e)
                })

        thread = threading.Thread(target=generate_task)
        thread.start()

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '开始生成文章'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/save', methods=['POST'])
def save_article():
    """保存文章"""
    data = request.json
    title = data.get('title', '')
    content = data.get('content', '')
    platform = data.get('platform', 'wechat')
    format_type = data.get('format', 'html')

    if not title or not content:
        return jsonify({
            'success': False,
            'error': '标题和内容不能为空'
        }), 400

    try:
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = "".join(c for c in title[:20] if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{timestamp}_{safe_title}.{format_type}"
        filepath = OUTPUT_FOLDER / filename

        # 保存文件
        with open(filepath, 'w', encoding='utf-8') as f:
            if format_type == 'html':
                f.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.8; padding: 20px; max-width: 800px; margin: 0 auto; }}
        h1 {{ font-size: 24px; margin-bottom: 20px; }}
        p {{ margin-bottom: 1em; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {content}
</body>
</html>""")
            else:
                f.write(content)

        return jsonify({
            'success': True,
            'message': '文章保存成功',
            'data': {
                'filename': filename,
                'filepath': str(filepath),
                'download_url': f'/api/download/{filename}'
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """下载文件"""
    filepath = OUTPUT_FOLDER / filename
    if not filepath.exists():
        return jsonify({
            'success': False,
            'error': '文件不存在'
        }), 404

    return send_file(filepath, as_attachment=True)

@app.route('/api/cache', methods=['GET'])
def get_cache_list():
    """获取缓存列表"""
    caches = list_cache()
    return jsonify({
        'success': True,
        'data': caches
    })

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """清空缓存"""
    try:
        for cache_file in CACHE_FOLDER.glob('*.json'):
            cache_file.unlink()
        return jsonify({
            'success': True,
            'message': '缓存已清空'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/preview', methods=['POST'])
def preview_article():
    """预览文章（实时）"""
    data = request.json
    content = data.get('content', '')
    platform = data.get('platform', 'wechat')
    style = data.get('style', {})

    # 这里应该调用Claude API进行实时预览
    # 返回简化版本用于预览

    narrator = style.get('narrator', '我的朋友')

    # 模拟预览内容
    preview_html = f"""
    <div style="padding: 20px;">
        <h2>文章预览</h2>
        <div style="background: #f9f9f9; padding: 15px; border-radius: 8px; margin-top: 20px;">
            <p><strong>叙述者：</strong>{narrator}</p>
            <p><strong>平台：</strong>{PLATFORM_CONFIGS.get(platform, {}).get('name', '微信公众号')}</p>
            <p><strong>内容预览：</strong></p>
            <div style="border-left: 3px solid #007bff; padding-left: 15px; color: #666;">
                {content[:500]}...
            </div>
        </div>
    </div>
    """

    return jsonify({
        'success': True,
        'data': {
            'html': preview_html,
            'word_count': len(content),
            'estimated_read_time': max(1, len(content) // 500)
        }
    })

# ============ 启动 ============

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
