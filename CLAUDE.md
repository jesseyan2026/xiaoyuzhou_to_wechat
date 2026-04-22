# 播客转文章工具 - 项目文档

## 项目概述

将小宇宙播客内容转换为微信公众号/小红书文章的一站式工具。

## 核心功能

### 1. 内容获取（三级优先级）

| 模式 | 说明 | 优先级 |
|------|------|--------|
| Article | 搜索微信公众号等平台的现成文稿 | 1 |
| Audio | 使用Whisper模型转录播客音频 | 2 |
| Shownotes | 使用小宇宙页面的节目简介 | 3 |

自动模式会按顺序尝试，失败则回退到下一级。

### 2. 文章生成

- **AI生成**：调用Kimi API（moonshot）或Claude API智能改写
- **模拟生成**：基础风格转换（第一人称→第三人称）
- **缓存机制**：转录内容本地缓存，避免重复处理

### 3. 编辑器功能

- 粗体、斜体、下划线
- 文字颜色（8种颜色选择器）
- 标题、列表
- 实时预览（手机/PC双视图）

### 4. 风格定制

**微信公众号：**
- 叙述者人称（如"我的朋友"）
- 首行缩进开关
- 行距倍数（1.6-2.2）
- 正文字号（14-18px）

**小红书：**
- Emoji开关
- 要点分点
- 高亮重点
- 自定义标签

## 项目结构

```
xiaoyuzhou_to_wechat/
├── web/                    # Flask Web应用
│   ├── app.py             # 主入口
│   ├── article_generator.py  # AI文章生成
│   ├── templates/         # HTML模板
│   │   ├── index.html     # 首页（输入链接）
│   │   ├── platform.html  # 选择平台
│   │   ├── style.html     # 定制风格
│   │   └── preview.html   # 编辑预览
│   ├── uploads/           # 上传目录
│   ├── output/            # 输出目录
│   └── cache/             # 缓存目录
├── crawler/               # 爬虫模块
├── transformer/           # 内容处理
├── formatter/             # 格式输出
├── output/                # 导出模块
├── main.py                # CLI入口
└── transcribe_podcast.py  # 转录模块
```

## 环境变量

```bash
# Kimi API Key（用于AI文章生成）
export KIMI_API_KEY="sk-..."

# 可选：Claude API Key
export ANTHROPIC_API_KEY="sk-ant-..."
```

## 启动命令

```bash
cd web
python app.py
```

访问 http://127.0.0.1:5000

## 技术要点

1. **Kimi API**: 使用OpenAI兼容接口，`base_url="https://api.moonshot.cn/v1"`
2. **Temperature**: kimi-k2.5只支持temperature=1，不能设置其他值
3. **缓存**: MD5哈希URL作为缓存键，存储在web/cache/
4. **任务状态**: 使用全局tasks字典+后台线程，支持实时进度查询

## 用户偏好

- 美国华裔，需用中文沟通
