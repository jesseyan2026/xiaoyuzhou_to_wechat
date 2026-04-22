    def transcribe_task():
        try:
            transcriber = SmartPodcastTranscriber(output_dir=str(OUTPUT_FOLDER))

            # 更新进度
            tasks[task_id].update({
                'progress': 20,
                'message': '正在提取播客信息...'
            })

            # 提取播客信息
            info = transcriber.info_extractor.extract(url)

            # 尝试搜索外部文稿
            tasks[task_id].update({
                'progress': 40,
                'message': '正在搜索外部文稿...'
            })

            search_results = transcriber.source_searcher.search(info)

            # 尝试获取文章内容
            for article in search_results[:5]:  # 最多尝试前5个结果
                tasks[task_id].update({
                    'progress': 60,
                    'message': f'正在获取文章: {article.title[:30]}...'
                })

                content = transcriber.article_fetcher.fetch(article)
                if content:
                    tasks[task_id].update({
                        'status': 'completed',
                        'progress': 100,
                        'message': '成功获取文稿',
                        'data': {
                            'source': article.source,
                            'title': info.title,
                            'content': content,
                            'method': 'external'
                        }
                    })
                    return

            # 如果没有找到外部文稿，提示用户手动转录
            tasks[task_id].update({
                'status': 'error',
                'message': '未找到外部文稿。请使用飞书妙记等工具手动转录，然后粘贴到输入框中。'
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            tasks[task_id].update({
                'status': 'error',
                'message': f'转录失败: {str(e)}'
            })
