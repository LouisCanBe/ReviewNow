# ArXiv 综述整理工具

![版本](https://img.shields.io/badge/版本-1.0.0-blue.svg)
![Python版本](https://img.shields.io/badge/Python-3.8+-brightgreen.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.0+-red.svg)

一个强大的学术论文检索、下载与管理工具，支持 ArXiv 和 CrossRef 数据源，具备中英文双语界面和自动翻译功能。

## 主要功能

### 1. 多源学术搜索
- **ArXiv 搜索**：搜索 ArXiv 预印本平台的论文
- **CrossRef 备用搜索**：当 ArXiv 结果不足时自动使用 CrossRef 检索更多论文
- **中文关键词支持**：输入中文关键词自动翻译为英文进行搜索

### 2. 强大的翻译功能
- **标题与摘要翻译**：自动将英文标题和摘要翻译为中文
- **多种翻译方式**：集成多种翻译服务，自动容错和切换
- **翻译结果缓存**：避免重复翻译相同内容

### 3. 论文管理系统
- **分类整理**：创建自定义分类管理已下载论文
- **收藏功能**：一键添加论文到收藏夹
- **批量操作**：支持批量下载和分类

### 4. 论文详情浏览
- **双语显示**：并排显示中英文标题和摘要
- **元数据展示**：显示引用数、影响因子等扩展信息
- **内嵌 PDF 预览**：直接在应用内预览论文内容
- **多种访问选项**：提供 ArXiv 页面、PDF 和 DOI 链接

### 5. 智能下载
- **异步下载**：下载过程不阻塞用户界面
- **状态追踪**：实时显示下载进度和状态
- **自动去重**：避免重复下载相同论文

## 安装指南

### 环境要求
- streamlit>=1.0.0
- pandas>=1.0.0
- arxiv>=1.0.0
- requests>=2.25.0
- translate>=3.6.1
- PyPDF2>=2.0.0
- beautifulsoup4
- lxml 

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/yourusername/arxiv-review-tool.git
cd arxiv-review-tool
```

2. 安装依赖包
```bash
pip install -r requirements.txt
```

3. 运行应用
```bash
streamlit run app.py
```

## 使用说明

### 搜索论文
1. 在首页搜索框中输入关键词（支持中英文）
2. 调整搜索选项（结果数量、排序方式等）
3. 点击"搜索"按钮获取结果
4. 在结果列表中点击论文标题查看详情

### 下载论文
1. 在论文详情页点击"📥 下载此论文"按钮
2. 等待下载完成，状态会实时更新
3. 下载完成后可在"整理论文"页面查看

### 论文管理
1. 切换到"整理论文"功能
2. 创建自定义分类
3. 将论文添加到不同分类中
4. 使用分类系统组织和查找论文

### 查看论文
- 使用内嵌 PDF 预览直接阅读
- 点击"在线查看 PDF"在新标签页打开
- 点击"查看 ArXiv 页面"访问原始论文页面

## 高级功能

### 自动翻译系统
本工具使用多层次翻译系统确保可靠性：
1. 首选翻译服务（MyMemory API）
2. 备用翻译服务（Google Translate）
3. 关键词直接映射（当在线服务不可用时）

### 备用搜索源
当 ArXiv 结果不足时，自动使用 CrossRef API 扩展搜索结果：
- CrossRef 提供更广泛的已发表论文信息
- 搜索结果会清晰标记来源（[ArXiv] 或 [CrossRef]）
- 对不同来源的论文提供相应的访问链接

### 数据缓存
- 搜索结果和翻译结果会被缓存以提高性能
- 下载过的论文不会重复下载
- 元数据会持久化保存在本地文件中

## 开发信息

### 技术栈
- **前端**：Streamlit
- **后端**：Python
- **API**：ArXiv API, CrossRef API, 翻译API

### 项目结构
- `app.py`: 主应用和用户界面
- `arxiv_client.py`: ArXiv 和 CrossRef API 客户端
- `paper_manager.py`: 论文管理和分类系统
- `metadata_enricher.py`: 论文元数据增强和翻译功能

### 贡献指南
欢迎贡献代码、报告问题或提出功能建议！
请通过 Issues 或 Pull Requests 参与项目开发。

## 许可证
MIT License
