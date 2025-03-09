import streamlit as st
import pandas as pd
import os
import json
import re
import requests
import urllib.parse
from arxiv_client import ArxivClient
from paper_manager import PaperManager
from translate import Translator
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
import threading
import time

# 安全的获取字典值的函数
def safe_get(dictionary, key, default=""):
    """安全地从字典中获取值，如果不存在则返回默认值"""
    if not isinstance(dictionary, dict):
        return default
    return dictionary.get(key, default)

# 初始化ArxivClient和PaperManager
arxiv_client = ArxivClient()
paper_manager = PaperManager()

# 设置页面标题
st.set_page_config(page_title="ArXiv综述整理工具", layout="wide")
st.title("ArXiv 综述整理工具")

# 创建侧边栏，用于切换功能
st.sidebar.title("功能")
option = st.sidebar.radio("选择功能", ["搜索论文", "下载论文", "整理论文"])

# 判断文本是否包含中文
def contains_chinese(text):
    """检查文本是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

# 使用Google Translate进行翻译（无需API密钥的方法）
def google_translate(text, to_lang="en", from_lang="zh"):
    """使用Google Translate API进行翻译（无需API密钥）"""
    try:
        # 构建URL
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",  # 使用gtx作为客户端，不需要API密钥
            "dt": "t",        # 表示我们只需要翻译
            "sl": from_lang,  # 源语言
            "tl": to_lang,    # 目标语言
            "q": text         # 要翻译的文本
        }
        
        # 发送请求
        encoded_params = urllib.parse.urlencode(params)
        full_url = f"{url}?{encoded_params}"
        response = requests.get(full_url, timeout=5)
        
        if response.status_code != 200:
            print(f"Google翻译请求失败: {response.status_code}")
            return text
        
        # 解析响应（Google Translate返回的是嵌套列表）
        result = response.json()
        # 第一个列表包含翻译结果，我们需要合并所有翻译片段
        translated_text = ""
        for sentence in result[0]:
            if sentence[0]:
                translated_text += sentence[0]
        
        return translated_text
    except Exception as e:
        print(f"Google翻译出错: {str(e)}")
        return text

# 改进的翻译函数，带备用方法
def translate_to_english(text):
    """将中文文本翻译成英文，带备用方法"""
    if not contains_chinese(text):
        return text, False  # 不包含中文，无需翻译
    
    try:
        # 首先尝试原始翻译方法
        translator = Translator(to_lang="en", from_lang="zh")
        translated = translator.translate(text)
        
        # 检查是否为错误信息
        if "MYMEMORY WARNING" in translated.upper() or "QUOTA EXCEEDED" in translated.upper():
            print("主要翻译API配额已用完，切换到Google翻译")
            # 使用备用Google翻译
            translated = google_translate(text, to_lang="en", from_lang="zh")
            return translated, True
        
        return translated, True
        
    except Exception as e:
        print(f"主要翻译方法失败: {str(e)}，切换到Google翻译")
        # 使用备用Google翻译
        try:
            translated = google_translate(text, to_lang="en", from_lang="zh")
            return translated, True
        except Exception as backup_e:
            print(f"备用翻译也失败: {str(backup_e)}")
            return text, False

# 在app.py的开头初始化部分添加
if 'download_states' not in st.session_state:
    st.session_state.download_states = {}
if 'download_messages' not in st.session_state:
    st.session_state.download_messages = {}

# 添加异步下载函数
def download_paper_async(paper_id):
    """异步下载论文，不阻塞UI"""
    try:
        # 更新下载状态为"正在下载"
        st.session_state.download_states[paper_id] = "downloading"
        st.session_state.download_messages[paper_id] = "正在下载论文..."
        
        # 执行下载
        output_path = arxiv_client.download(paper_id)
        
        # 检查下载结果
        if isinstance(output_path, dict) and "error" in output_path:
            st.session_state.download_states[paper_id] = "error"
            st.session_state.download_messages[paper_id] = f"下载失败: {output_path['error']}"
        else:
            # 下载成功
            st.session_state.download_states[paper_id] = "success"
            st.session_state.download_messages[paper_id] = f"下载成功: {output_path}"
            
            # 添加到论文管理器
            try:
                paper = arxiv_client.get_paper_details(paper_id)
                paper_manager.add_paper(paper, output_path)
                st.session_state.download_messages[paper_id] += " (已添加到论文管理器)"
            except Exception as add_err:
                st.session_state.download_messages[paper_id] += f" (添加到管理器失败: {str(add_err)})"
    
    except Exception as e:
        st.session_state.download_states[paper_id] = "error"
        st.session_state.download_messages[paper_id] = f"下载出错: {str(e)}"

# 根据选择的功能显示不同的内容
if option == "搜索论文":
    st.header("搜索ArXiv论文")
    
    # 在选择论文的部分
    if 'selected_paper_id' not in st.session_state:
        st.session_state.selected_paper_id = None

    # 搜索表单部分 - 使用回调函数而不是直接在表单中处理
    def search_papers():
        query = st.session_state.search_query
        max_results = st.session_state.max_results
        sort_by = st.session_state.sort_by
        auto_translate = st.session_state.auto_translate
        use_backup = st.session_state.use_backup
        
        with st.spinner("搜索中..."):
            translated_query = query
            translation_performed = False
            
            # 如果需要翻译查询（包含中文）
            if auto_translate and contains_chinese(query):
                translated_query, translation_performed = translate_to_english(query)
                
            if translation_performed:
                st.info(f"已将搜索关键词翻译为: \"{translated_query}\"")
                
            # 执行搜索
            results = arxiv_client.search(translated_query, max_results=max_results, sort_by=sort_by, use_backup=use_backup)
            
            # 将搜索结果保存到session_state以便后续使用
            st.session_state.search_results = results
            
            # 将结果转换为DataFrame以便显示
            df_data = []
            for paper in results:
                # 添加来源标记
                source_label = "[ArXiv]" if paper.get('source', '') == 'arxiv' else "[CrossRef]" if paper.get('source', '') == 'crossref' else ""
                
                # 确保有URL字段
                if 'url' not in paper and paper.get('id'):
                    arxiv_id = paper.get('id')
                    if arxiv_id.startswith('arxiv:'):
                        arxiv_id = arxiv_id[6:]
                    paper['url'] = f"https://arxiv.org/abs/{arxiv_id}"
                    paper['pdf_url'] = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                
                df_data.append({
                    "ID": paper['id'],
                    "来源": source_label,
                    "标题": paper['title'],
                    "作者": ', '.join(paper['authors']) if isinstance(paper['authors'], list) else paper['authors'],
                    "发布日期": paper['published'].split()[0] if isinstance(paper['published'], str) else paper['published'],
                    "分类": ', '.join(paper['categories']) if isinstance(paper['categories'], list) else paper['categories']
                })
            
            st.session_state.df_data = df_data

    # 初始化session_state变量
    if 'search_query' not in st.session_state:
        st.session_state.search_query = ""
    if 'max_results' not in st.session_state:
        st.session_state.max_results = 10
    if 'sort_by' not in st.session_state:
        st.session_state.sort_by = "relevance"
    if 'auto_translate' not in st.session_state:
        st.session_state.auto_translate = True
    if 'use_backup' not in st.session_state:
        st.session_state.use_backup = True

    # 搜索输入字段 - 不使用表单
    st.text_input("搜索论文", value="", key="search_query", help="输入关键词，例如：quantum computing")

    # 搜索选项
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.number_input("最大结果数", min_value=5, max_value=100, value=10, key="max_results")
    with col2:
        st.selectbox("排序方式", ["relevance", "lastUpdatedDate", "submittedDate"], key="sort_by")
    with col3:
        st.checkbox("自动翻译查询", value=True, key="auto_translate")
    with col4:
        st.checkbox("使用备用源", value=True, key="use_backup", help="如果ArXiv结果较少，自动使用其他学术搜索源")

    # 搜索按钮 - 不在表单内
    if st.button("搜索", key="search_button"):
        search_papers()

    # 显示搜索结果
    if 'df_data' in st.session_state and st.session_state.df_data:
        df_data = st.session_state.df_data
        results = st.session_state.search_results
        
        st.write(f"找到 {len(df_data)} 篇论文:")
        
        # 使用表格展示简要信息
        df = pd.DataFrame(df_data)
        st.dataframe(df)
        
        # 创建选择框 - 不在表单内
        paper_options = {f"{paper['id']} - {paper['title'][:50]}...": paper['id'] for paper in results}
        
        # 定义选择论文时的回调函数
        def on_paper_select():
            # 从选择框的值中获取论文ID
            selected_option = st.session_state.paper_selector
            paper_id = paper_options[selected_option]
            # 更新selected_paper_id
            st.session_state.selected_paper_id = paper_id

        # 使用on_change参数指定回调函数
        selected_paper_option = st.selectbox(
            "选择论文查看详情", 
            list(paper_options.keys()),
            key="paper_selector",
            on_change=on_paper_select  # 当选择变化时调用回调函数
        )
        
        # 不再需要查看详情按钮，因为选择论文时会自动获取详情
        # 但可以保留按钮用于重新加载详情
        if st.button("重新加载详情", key="reload_details_button"):
            # 这里不需要做任何事情，因为Streamlit会自动重新运行脚本
            pass

    # 显示选定论文详情 - 不在表单内
    if st.session_state.selected_paper_id:
        paper_id = st.session_state.selected_paper_id
        with st.spinner("获取论文详情..."):
            paper = arxiv_client.get_paper_details(paper_id)
            
            if "error" not in paper:
                # 在session_state中存储当前论文详情
                st.session_state.current_paper = paper
                
                # 使用两列并排显示中英文内容
                col_en, col_zh = st.columns(2)
                
                # 英文原文显示
                with col_en:
                    st.markdown("### Original")
                    st.markdown(f"**Title:** {paper['title']}")
                    st.markdown(f"**Authors:** {', '.join(paper['authors'])}")
                    st.markdown(f"**Published:** {paper['published']}")
                    
                    # 元数据 - 英文
                    if 'citation_count' in paper:
                        st.markdown(f"**Citations:** {paper['citation_count']}")
                    if 'influence_factor' in paper:
                        st.markdown(f"**Influence Factor:** {paper['influence_factor']}")
                    if 'published_in' in paper and paper['published_in'] != '未知':
                        st.markdown(f"**Published in:** {paper['published_in']}")
                    
                    # 分类 - 英文
                    st.markdown(f"**Categories:** {', '.join(paper['categories']) if isinstance(paper['categories'], list) else paper['categories']}")
                    
                    # 摘要 - 英文
                    st.markdown("### Abstract")
                    st.markdown(paper['summary'])
                
                # 中文翻译显示
                with col_zh:
                    st.markdown("### 中文翻译")
                    st.markdown(f"**标题:** {safe_get(paper, 'title_zh', paper['title'])}")
                    st.markdown(f"**作者:** {', '.join(paper['authors'])}")
                    st.markdown(f"**发布日期:** {paper['published']}")
                    
                    # 元数据 - 中文
                    if 'citation_count' in paper:
                        st.markdown(f"**引用次数:** {paper['citation_count']}")
                    if 'influence_factor' in paper:
                        st.markdown(f"**影响因子:** {paper['influence_factor']}")
                    if 'published_in' in paper and paper['published_in'] != '未知':
                        st.markdown(f"**发表于:** {paper['published_in']}")
                    
                    # 分类 - 中文  
                    st.markdown(f"**分类:** {', '.join(paper['categories']) if isinstance(paper['categories'], list) else paper['categories']}")
                    
                    # 摘要 - 中文
                    st.markdown("### 摘要")
                    st.markdown(safe_get(paper, 'summary_zh', paper['summary']))
                
                # 主题标签 (如果有)
                if 'topics' in paper and paper['topics']:
                    st.markdown("### 主题 / Topics")
                    tags = paper['topics']
                    st.write(' '.join([f"<span style='background-color: #E6F6FF; padding: 2px 8px; border-radius: 12px; margin-right: 8px;'>{tag}</span>" for tag in tags]), unsafe_allow_html=True)
                
                # 分隔线
                st.markdown("---")
                
                # 添加论文链接区域
                st.markdown("### 论文链接")
                link_col1, link_col2, = st.columns(2)
                
                with link_col1:
                    # 在线查看PDF按钮
                    pdf_url = None
                    if paper.get('source') == 'crossref':
                        # CrossRef论文的URL
                        pdf_url = paper.get('url')
                    else:
                        # ArXiv论文的PDF URL
                        if paper.get('id'):
                            arxiv_id = paper.get('id')
                            # 移除可能的'arxiv:'前缀
                            if arxiv_id.startswith('arxiv:'):
                                arxiv_id = arxiv_id[6:]
                            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                    
                    if pdf_url:
                        st.markdown(f"[在线查看PDF]({pdf_url})")
                
                with link_col2:
                    # ArXiv页面链接
                    arxiv_url = None
                    if paper.get('id') and not paper.get('id').startswith('doi:'):
                        arxiv_id = paper.get('id')
                        # 移除可能的'arxiv:'前缀
                        if arxiv_id.startswith('arxiv:'):
                            arxiv_id = arxiv_id[6:]
                        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
                        st.markdown(f"[查看ArXiv页面]({arxiv_url})")
                    elif paper.get('arxiv_url'):
                        st.markdown(f"[查看ArXiv页面]({paper.get('arxiv_url')})")
                    elif paper.get('source') == 'crossref' and paper.get('doi'):
                        doi = paper.get('doi')
                        doi_url = f"https://doi.org/{doi}" if not doi.startswith('http') else doi
                        st.markdown(f"[查看DOI页面]({doi_url})")
                
                # 添加嵌入式PDF查看器
                st.markdown("### 预览")
                
                # 为PDF创建一个嵌入式框架
                if pdf_url:
                    # 使用HTML iframe嵌入PDF
                    pdf_display = f"""
                    <iframe src="{pdf_url}" width="100%" height="600" style="border:none;"></iframe>
                    """
                    st.markdown(pdf_display, unsafe_allow_html=True)
                    st.markdown("*如果PDF加载失败，请使用上方链接直接访问*")
                else:
                    st.info("无法预览PDF，请使用链接在线查看或下载后查看")
                
                # 分隔线
                st.markdown("---")
                
                # 添加下载和收藏按钮区域
                st.markdown("### 操作")
                action_col1, action_col2 = st.columns(2)
                
                with action_col1:
                    # 下载按钮实现
                    if paper['id'] not in st.session_state.download_states:
                        if st.button("📥 下载此论文", key=f"download_button_{paper['id']}"):
                            # 初始化下载状态
                            st.session_state.download_states[paper['id']] = "initialized"
                            st.session_state.download_messages[paper['id']] = "正在准备下载..."
                            
                            # 创建并启动下载线程
                            download_thread = threading.Thread(
                                target=download_paper_async,
                                args=(paper['id'],)
                            )
                            # 添加脚本运行上下文以允许线程内更新session_state
                            ctx = get_script_run_ctx()
                            add_script_run_ctx(download_thread)
                            download_thread.start()
                
                with action_col2:
                    # 添加收藏按钮
                    if st.button("⭐ 添加到收藏", key=f"favorite_{paper['id']}"):
                        try:
                            # 确保默认分类存在
                            if "收藏" not in paper_manager.get_categories():
                                paper_manager.add_category("收藏")
                            
                            # 添加到收藏分类
                            # 先确保论文已保存
                            if paper_manager.get_paper(paper['id']) is None:
                                # 如果论文未保存，先添加到论文列表
                                local_path = paper.get('local_path', '')
                                paper_manager.add_paper(paper, local_path)
                            
                            # 添加到收藏分类
                            paper_manager.add_paper_to_category(paper['id'], "收藏")
                            st.success("已添加到收藏")
                        except Exception as fav_err:
                            st.error(f"添加到收藏失败: {str(fav_err)}")
            else:
                st.error(paper["error"])

elif option == "下载论文":
    st.header("批量下载论文")
    
    # 批量下载表单
    with st.form(key='download_form'):
        paper_ids = st.text_area("输入论文ID（每行一个）", height=150, help="输入ArXiv论文ID，每行一个，例如: 2106.14572")
        download_button = st.form_submit_button("下载论文")
        
        if download_button and paper_ids:
            # 分割输入的ID
            ids = [id.strip() for id in paper_ids.split('\n') if id.strip()]
            
            if ids:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                downloaded_papers = []
                failed_papers = []
                
                for i, paper_id in enumerate(ids):
                    status_text.text(f"下载中 ({i+1}/{len(ids)}): {paper_id}")
                    try:
                        output_path = arxiv_client.download(paper_id)
                        downloaded_papers.append((paper_id, output_path))
                    except Exception as e:
                        failed_papers.append((paper_id, str(e)))
                    
                    # 更新进度条
                    progress_bar.progress((i + 1) / len(ids))
                
                # 显示结果
                if downloaded_papers:
                    st.success(f"成功下载 {len(downloaded_papers)} 篇论文")
                    for paper_id, path in downloaded_papers:
                        st.write(f"- {paper_id}: {path}")
                
                if failed_papers:
                    st.error(f"下载失败 {len(failed_papers)} 篇论文")
                    for paper_id, error in failed_papers:
                        st.write(f"- {paper_id}: {error}")
                        
elif option == "整理论文":
    st.header("整理下载的论文")
    
    # 获取所有已下载的论文
    papers = paper_manager.get_all_papers()  # 使用新添加的方法
    if papers:
        st.subheader("已下载的论文")
        
        # 转换为适合显示的格式
        paper_data = []
        for paper in papers:
            paper_data.append({
                "ID": paper.get('id', ''),
                "标题": paper.get('title', ''),
                "作者": ', '.join(paper.get('authors', [])) if isinstance(paper.get('authors'), list) else paper.get('authors', ''),
                "下载日期": paper.get('download_date', ''),
                "本地路径": paper.get('local_path', '')
            })
        
        df = pd.DataFrame(paper_data)
        st.dataframe(df)
        
        # 添加搜索功能
        search_term = st.text_input("搜索已下载的论文", "")
        if search_term:
            filtered_papers = [p for p in paper_data if 
                               search_term.lower() in p['标题'].lower() or 
                               search_term.lower() in p['作者'].lower() or
                               search_term.lower() in p['ID'].lower()]
            if filtered_papers:
                st.write(f"找到 {len(filtered_papers)} 个匹配结果:")
                st.dataframe(pd.DataFrame(filtered_papers))
            else:
                st.info("未找到匹配的论文")
        
        # 添加分类管理
        st.subheader("论文分类管理")
        
        # 显示现有分类
        categories = paper_manager.get_categories()
        if categories:
            st.write("现有分类:")
            for category in categories:
                st.write(f"- {category}")
        
        # 添加新分类
        new_category = st.text_input("新建分类")
        if st.button("添加分类") and new_category:
            paper_manager.add_category(new_category)
            st.success(f"已添加分类: {new_category}")
            st.experimental_rerun()
        
        # 为论文添加分类
        st.subheader("为论文添加分类")
        paper_options = {f"{p['ID']} - {p['标题'][:50]}...": p['ID'] for p in paper_data}
        selected_paper = st.selectbox("选择论文", list(paper_options.keys()))
        selected_paper_id = paper_options[selected_paper] if selected_paper else None
        
        if selected_paper_id and categories:
            selected_category = st.selectbox("选择分类", categories)
            if st.button("添加到分类") and selected_category:
                paper_manager.add_paper_to_category(selected_paper_id, selected_category)
                st.success(f"已将论文添加到分类: {selected_category}")
        
        # 查看分类下的论文
        st.subheader("查看分类")
        if categories:
            view_category = st.selectbox("选择要查看的分类", categories, key="view_category")
            if view_category:
                category_papers = paper_manager.get_papers_by_category(view_category)
                if category_papers:
                    st.write(f"{view_category} 分类下的论文:")
                    
                    # 将分类下的论文转换为DataFrame
                    cat_paper_data = []
                    for paper_id in category_papers:
                        paper = paper_manager.get_paper(paper_id)
                        if paper:
                            cat_paper_data.append({
                                "ID": paper.get('id', ''),
                                "标题": paper.get('title', ''),
                                "作者": ', '.join(paper.get('authors', [])),
                                "下载日期": paper.get('download_date', '')
                            })
                    
                    if cat_paper_data:
                        st.dataframe(pd.DataFrame(cat_paper_data))
                    else:
                        st.info(f"{view_category} 分类下暂无论文")
                else:
                    st.info(f"{view_category} 分类下暂无论文")
    else:
        st.info("暂无下载的论文。请先使用\"下载论文\"功能下载一些论文。")