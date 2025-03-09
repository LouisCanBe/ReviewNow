import arxiv
import os
import datetime
import requests
import json
from metadata_enricher import MetadataEnricher

class ArxivClient:
    """
    与ArXiv API交互的客户端
    """
    
    def __init__(self):
        """
        初始化ArXiv客户端
        """
        self.client = arxiv.Client()
        self.metadata_enricher = MetadataEnricher()
    
    def search(self, query, max_results=10, sort_by="relevance", use_backup=True):
        """
        搜索ArXiv论文
        
        参数:
            query (str): 搜索查询
            max_results (int): 返回的最大结果数
            sort_by (str): 排序方式，可选值: relevance, lastUpdatedDate, submittedDate
            use_backup (bool): 如果ArXiv结果少于3篇，是否使用备用搜索源
            
        返回:
            list: 论文信息列表
        """
        print(f"使用ArXiv搜索: {query}")
        
        # 创建搜索对象
        sort_options = {
            "relevance": arxiv.SortCriterion.Relevance,
            "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
            "submittedDate": arxiv.SortCriterion.SubmittedDate
        }
        
        sort_criterion = sort_options.get(sort_by, arxiv.SortCriterion.Relevance)
        
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=sort_criterion
        )
        
        # 获取搜索结果
        results = []
        try:
            for result in self.client.results(search):
                paper = {
                    'id': result.get_short_id(),
                    'title': result.title,
                    'authors': [author.name for author in result.authors],
                    'summary': result.summary,
                    'published': str(result.published),
                    'updated': str(result.updated),
                    'categories': result.categories,
                    'pdf_url': result.pdf_url,
                    'arxiv_url': result.entry_id,
                    'source': 'arxiv'  # 标记来源
                }
                results.append(paper)
        except Exception as e:
            print(f"ArXiv搜索出错: {str(e)}")
        
        print(f"ArXiv搜索结果数量: {len(results)}")
        
        # 如果结果很少，尝试使用备用源
        if use_backup and len(results) < 3:
            print(f"ArXiv结果较少，尝试使用备用源")
            backup_results = self.search_with_crossref(query, max_results=max_results)
            
            # 将备用源结果添加到主结果中
            if backup_results:
                # 确保没有重复
                existing_ids = {r['id'] for r in results}
                for br in backup_results:
                    if br['id'] not in existing_ids:
                        results.append(br)
                        existing_ids.add(br['id'])
                
                print(f"添加备用源后总结果数量: {len(results)}")
        
        return results
    
    def search_with_crossref(self, query, max_results=10):
        """
        使用CrossRef API作为备用搜索源
        
        参数:
            query (str): 搜索查询
            max_results (int): 返回的最大结果数
            
        返回:
            list: 论文信息列表
        """
        print(f"使用CrossRef搜索: {query}")
        
        # 构建API URL
        url = f"https://api.crossref.org/works"
        params = {
            'query': query,
            'rows': max_results,
            'sort': 'relevance',
            'order': 'desc',
            'filter': 'type:journal-article',
        }
        
        # 添加Email以符合CrossRef的礼仪要求
        headers = {
            'User-Agent': 'ArxivReviewApp/1.0 (mailto:contact@example.com)'
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"CrossRef API请求失败: {response.status_code}")
                return []
            
            data = response.json()
            
            if 'message' not in data or 'items' not in data['message']:
                print("CrossRef返回格式异常")
                return []
            
            items = data['message']['items']
            print(f"CrossRef搜索结果数量: {len(items)}")
            
            results = []
            for item in items:
                # 提取基本信息
                paper_id = item.get('DOI', '').replace('/', '_')
                
                # 确保有标题
                if 'title' not in item or not item['title']:
                    continue
                
                # 提取作者
                authors = []
                if 'author' in item:
                    for author in item['author']:
                        name_parts = []
                        if 'given' in author:
                            name_parts.append(author['given'])
                        if 'family' in author:
                            name_parts.append(author['family'])
                        if name_parts:
                            authors.append(' '.join(name_parts))
                
                # 发布日期
                published = ''
                if 'published' in item and item['published'] and 'date-parts' in item['published']:
                    date_parts = item['published']['date-parts'][0]
                    if len(date_parts) >= 3:
                        published = f"{date_parts[0]}-{date_parts[1]:02d}-{date_parts[2]:02d}"
                    elif len(date_parts) >= 1:
                        published = str(date_parts[0])
                
                # 摘要
                summary = item.get('abstract', '')
                if not summary:
                    summary = item.get('subtitle', [''])[0] if 'subtitle' in item and item['subtitle'] else ''
                
                # URL
                url = ''
                if 'URL' in item:
                    url = item['URL']
                elif 'link' in item and item['link']:
                    for link in item['link']:
                        if 'URL' in link:
                            url = link['URL']
                            break
                
                paper = {
                    'id': f"doi:{paper_id}",
                    'title': item['title'][0] if isinstance(item['title'], list) else item['title'],
                    'authors': authors,
                    'summary': summary,
                    'published': published,
                    'updated': published,
                    'categories': item.get('subject', []),
                    'pdf_url': url,
                    'arxiv_url': url,
                    'doi': item.get('DOI', ''),
                    'source': 'crossref'  # 标记来源
                }
                
                results.append(paper)
            
            return results
        
        except Exception as e:
            print(f"CrossRef搜索出错: {str(e)}")
            return []
    
    def get_paper_details(self, paper_id):
        """
        获取论文的详细信息，包括增强的元数据
        
        参数:
            paper_id (str): 论文ID
            
        返回:
            dict: 论文详情
        """
        # 处理CrossRef来源的论文
        if paper_id.startswith('doi:'):
            return self.get_crossref_paper_details(paper_id)
        
        # 处理论文ID格式
        # 移除可能存在的"arxiv:"前缀
        if paper_id.startswith('arxiv:'):
            paper_id = paper_id[6:]
        
        try:
            # 创建搜索对象，注意这里不添加前缀
            search = arxiv.Search(id_list=[paper_id])
            
            # 获取基本信息
            paper = next(self.client.results(search))
            
            # 基本信息
            paper_data = {
                'id': paper.get_short_id(),
                'title': paper.title,
                'authors': [author.name for author in paper.authors],
                'summary': paper.summary,
                'published': str(paper.published),
                'updated': str(paper.updated),
                'categories': paper.categories,
                'pdf_url': paper.pdf_url,
                'arxiv_url': paper.entry_id,
                'comment': getattr(paper, 'comment', ''),
                'journal_ref': getattr(paper, 'journal_ref', ''),
                'source': 'arxiv'
            }
            
            # 先翻译基本信息
            try:
                print("正在翻译标题...")
                translated_title = self.metadata_enricher.translate_text(paper_data['title'])
                paper_data['title_zh'] = translated_title
                
                print("正在翻译摘要...")
                # 使用分块翻译功能处理长摘要
                translated_summary = self.metadata_enricher.translate_text(paper_data['summary'])
                paper_data['summary_zh'] = translated_summary
                
            except Exception as e:
                print(f"翻译失败: {str(e)}")
                paper_data['title_zh'] = paper_data['title']
                paper_data['summary_zh'] = paper_data['summary']
            
            # 尝试获取增强元数据，但不影响基本功能
            try:
                # 注意这里传递的是没有前缀的ID
                additional_data = self.metadata_enricher.enrich_with_semantic_scholar(paper_id)
                if additional_data:  # 只有当返回有效数据时才更新
                    paper_data.update(additional_data)
            except Exception as e:
                print(f"增强元数据获取失败: {str(e)}")
            
            return paper_data
            
        except StopIteration:
            return {"error": f"未找到ID为{paper_id}的论文"}
        except Exception as e:
            return {"error": f"获取论文详情出错: {str(e)}"}
    
    def get_crossref_paper_details(self, paper_id):
        """
        获取CrossRef来源论文的详细信息
        
        参数:
            paper_id (str): 论文ID (格式: doi:xxx)
            
        返回:
            dict: 论文详情
        """
        try:
            # 提取DOI
            doi = paper_id[4:].replace('_', '/')
            
            # 请求CrossRef API
            url = f"https://api.crossref.org/works/{doi}"
            headers = {
                'User-Agent': 'ArxivReviewApp/1.0 (mailto:contact@example.com)'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return {"error": f"CrossRef API请求失败: {response.status_code}"}
            
            data = response.json()
            
            if 'message' not in data:
                return {"error": "CrossRef返回格式异常"}
            
            item = data['message']
            
            # 提取作者
            authors = []
            if 'author' in item:
                for author in item['author']:
                    name_parts = []
                    if 'given' in author:
                        name_parts.append(author['given'])
                    if 'family' in author:
                        name_parts.append(author['family'])
                    if name_parts:
                        authors.append(' '.join(name_parts))
            
            # 发布日期
            published = ''
            if 'published' in item and item['published'] and 'date-parts' in item['published']:
                date_parts = item['published']['date-parts'][0]
                if len(date_parts) >= 3:
                    published = f"{date_parts[0]}-{date_parts[1]:02d}-{date_parts[2]:02d}"
                elif len(date_parts) >= 1:
                    published = str(date_parts[0])
            
            # 摘要
            summary = item.get('abstract', '')
            if not summary:
                summary = item.get('subtitle', [''])[0] if 'subtitle' in item and item['subtitle'] else ''
            
            # URL
            url = ''
            if 'URL' in item:
                url = item['URL']
            elif 'link' in item and item['link']:
                for link in item['link']:
                    if 'URL' in link:
                        url = link['URL']
                        break
            
            paper_data = {
                'id': paper_id,
                'title': item.get('title', ['Untitled'])[0] if isinstance(item.get('title'), list) else item.get('title', 'Untitled'),
                'authors': authors,
                'summary': summary,
                'published': published,
                'updated': published,
                'categories': item.get('subject', []),
                'pdf_url': url,
                'arxiv_url': url,
                'doi': item.get('DOI', ''),
                'source': 'crossref'
            }
            
            # 翻译标题和摘要
            try:
                print("正在翻译CrossRef论文标题...")
                translated_title = self.metadata_enricher.translate_text(paper_data['title'])
                paper_data['title_zh'] = translated_title
                
                if summary:
                    print("正在翻译CrossRef论文摘要...")
                    translated_summary = self.metadata_enricher.translate_text(summary)
                    paper_data['summary_zh'] = translated_summary
                else:
                    paper_data['summary_zh'] = "无摘要"
                
            except Exception as e:
                print(f"翻译失败: {str(e)}")
                paper_data['title_zh'] = paper_data['title']
                paper_data['summary_zh'] = paper_data['summary'] if paper_data['summary'] else "无摘要"
            
            return paper_data
            
        except Exception as e:
            return {"error": f"获取CrossRef论文详情出错: {str(e)}"}
            
    def download(self, paper_id):
        """
        下载论文PDF
        
        参数:
            paper_id (str): 论文ID
            
        返回:
            str或dict: 成功返回保存路径，失败返回错误字典
        """
        # 处理CrossRef来源的论文
        if paper_id.startswith('doi:'):
            return {"error": "目前不支持直接下载CrossRef来源的论文，请使用提供的URL手动下载"}
        
        # 确保下载目录存在
        download_dir = os.path.join(os.getcwd(), "downloads")
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        
        # 检查是否已经下载过
        existing_path = os.path.join(download_dir, f"{paper_id}.pdf")
        if os.path.exists(existing_path):
            print(f"论文已下载: {existing_path}")
            return existing_path
        
        try:
            # 创建搜索对象
            search = arxiv.Search(id_list=[paper_id])
            
            # 获取论文并下载
            paper = next(self.client.results(search))
            
            # 设置下载选项
            paper.download_pdf(dirpath=download_dir, filename=f"{paper_id}.pdf")
            
            # 返回保存的路径
            downloaded_path = os.path.join(download_dir, f"{paper_id}.pdf")
            
            # 验证文件确实已下载
            if os.path.exists(downloaded_path) and os.path.getsize(downloaded_path) > 0:
                print(f"论文下载成功: {downloaded_path}")
                return downloaded_path
            else:
                return {"error": "下载完成但文件不存在或为空"}
            
        except StopIteration:
            error_msg = f"未找到ID为{paper_id}的论文"
            print(error_msg)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"下载论文时出错: {str(e)}"
            print(error_msg)
            return {"error": error_msg} 