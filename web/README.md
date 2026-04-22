# 播客转文章Web平台

基于Flask构建的Web应用，支持将小宇宙播客转换为微信公众号或小红书文章。

## 功能特点

- 🤖 **智能转录**：优先搜索外部文稿，无结果时自动转录音频
- 📝 **多平台支持**：一键生成微信公众号和小红书风格文章
- 🎨 **风格定制**：多种默认风格，支持自定义参数
- 👀 **实时预览**：在线编辑、预览效果、一键保存

## 项目结构

```
web/
├── app.py                 # Flask应用主文件
├── run.py                 # 启动脚本
├── article_generator.py   # 文章生成器（Claude API）
├── static/
│   └── css/
│       └── style.css      # 样式文件
├── templates/
│   ├── index.html         # 首页（输入播客链接）
│   ├── platform.html      # 平台选择页
│   ├── style.html         # 风格自定义页
│   └── preview.html       # 文章预览编辑页
├── uploads/               # 上传文件目录
└── output/                # 输出文件目录
```

## 安装依赖

```bash
# 安装基础依赖
pip install flask flask-cors requests beautifulsoup4 lxml

# 如需音频转录功能，安装Whisper（可选）
pip install openai-whisper torch

# 如需AI文章生成，安装Anthropic SDK（可选）
pip install anthropic
```

## 配置环境变量

```bash
# 设置Anthropic API Key（用于AI文章生成）
export ANTHROPIC_API_KEY="your-api-key"

# 或添加到 ~/.bashrc 或 ~/.zshrc
```

## 启动服务

```bash
# 方法1：使用启动脚本
cd web
python run.py

# 方法2：直接运行Flask
export FLASK_APP=web/app.py
flask run --host=0.0.0.0 --port=5000
```

访问 http://localhost:5000 即可使用。

## 使用流程

### 1. 输入播客链接

- 在首页输入小宇宙播客链接
- 或粘贴已有的转录内容
- 点击"开始分析"

### 2. 选择目标平台

- **微信公众号**：适合深度长文，支持HTML格式
- **小红书**：短平快，emoji丰富，适合种草

### 3. 定制文章风格

- 选择默认风格模板
- 自定义叙述者人称
- 调整排版参数（行距、字号、首行缩进等）
- 设置内容范围要求

### 4. 预览与保存

- 在线编辑文章内容
- 实时预览效果（手机/电脑双模式）
- 选择保存格式（HTML/Markdown/纯文本）
- 一键下载

## API端点

### 获取平台配置
```
GET /api/platforms
```

### 分析播客
```
POST /api/analyze
Body: { "url": "https://www.xiaoyuzhoufm.com/episode/xxx" }
```

### 转录播客
```
POST /api/transcribe
Body: { "url": "...", "task_id": "..." }
```

### 生成文章
```
POST /api/generate
Body: { "content": "...", "platform": "wechat", "style": {...} }
```

### 保存文章
```
POST /api/save
Body: { "title": "...", "content": "...", "format": "html" }
```

## 风格配置说明

### 微信公众号风格参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| narrator | 叙述者人称 | 我的朋友 |
| first_line_indent | 首行缩进 | true |
| line_height | 行距倍数 | 2.0 |
| font_size | 正文字号 | 16px |

### 小红书风格参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| narrator | 叙述者人称 | 博主 |
| use_emoji | 使用emoji | true |
| bullet_points | 要点分点 | true |
| highlight_key_points | 高亮重点 | true |
| tags | 标签 | #播客推荐 |

## 注意事项

1. **Claude API**：如需AI文章生成功能，需配置有效的ANTHROPIC_API_KEY
2. **音频转录**：如需自动转录功能，需安装Whisper和ffmpeg
3. **文件存储**：上传和输出文件存储在web/uploads和web/output目录
4. **任务状态**：转录和生成任务在后台异步执行，可通过任务ID查询状态

## 开发计划

- [ ] 用户认证和历史记录
- [ ] 批量处理多个播客
- [ ] 更多平台支持（知乎、今日头条等）
- [ ] 图片自动提取和排版
- [ ] 文章模板市场
