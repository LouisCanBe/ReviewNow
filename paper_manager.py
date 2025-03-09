import os
import json
import glob
import PyPDF2
from datetime import datetime

class PaperManager:
    def __init__(self, papers_file="papers.json", categories_file="categories.json"):
        """
        初始化论文管理器
        
        参数:
            papers_file (str): 论文信息文件路径
            categories_file (str): 分类信息文件路径
        """
        self.papers_file = papers_file
        self.categories_file = categories_file
        
        # 确保文件存在
        if not os.path.exists(papers_file):
            with open(papers_file, 'w') as f:
                json.dump({}, f)
        
        if not os.path.exists(categories_file):
            with open(categories_file, 'w') as f:
                json.dump({"categories": {}, "default": []}, f)
    
    def extract_text_from_pdf(self, pdf_path):
        """从PDF中提取文本"""
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            text = f"无法提取文本: {str(e)}"
        return text
    
    def read_metadata(self, meta_path):
        """读取元数据文件"""
        metadata = {}
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip()
        except Exception as e:
            metadata = {"error": f"无法读取元数据: {str(e)}"}
        return metadata
    
    def organize(self, input_dir='papers', output_format='markdown'):
        """
        整理论文并生成综述
        
        参数:
            input_dir (str): 输入目录
            output_format (str): 输出格式 (markdown 或 json)
            
        返回:
            str: 生成的综述内容
        """
        # 查找所有PDF文件
        pdf_files = glob.glob(os.path.join(input_dir, "*.pdf"))
        results = []
        
        for pdf_file in pdf_files:
            # 从文件名中获取论文ID
            paper_id = os.path.basename(pdf_file).replace('.pdf', '')
            
            # 查找对应的元数据文件
            meta_file = os.path.join(input_dir, f"{paper_id}.meta.txt")
            
            if os.path.exists(meta_file):
                # 读取元数据
                metadata = self.read_metadata(meta_file)
                
                # 提取PDF摘要（前500个字符）
                pdf_text = self.extract_text_from_pdf(pdf_file)
                summary = pdf_text[:500] + "..." if len(pdf_text) > 500 else pdf_text
                
                # 添加到结果列表
                paper_data = {
                    'id': paper_id,
                    'title': metadata.get('title', '未知标题'),
                    'authors': metadata.get('authors', '未知作者').split(', '),
                    'published': metadata.get('published', '未知日期'),
                    'summary': metadata.get('summary', '未提供摘要'),
                    'extracted_text': summary
                }
                results.append(paper_data)
        
        # 根据输出格式生成综述
        if output_format == 'json':
            return json.dumps(results, ensure_ascii=False, indent=2)
        else:  # markdown
            markdown = "# 论文综述\n\n"
            markdown += f"*生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            
            for paper in results:
                markdown += f"## {paper['title']}\n\n"
                markdown += f"**ID:** {paper['id']}  \n"
                markdown += f"**作者:** {', '.join(paper['authors'])}  \n"
                markdown += f"**发布日期:** {paper['published']}  \n\n"
                markdown += f"### 摘要\n\n{paper['summary']}\n\n"
                markdown += f"### 提取的内容\n\n{paper['extracted_text']}\n\n"
                markdown += "---\n\n"
                
            return markdown 

    def add_paper(self, paper_data, local_path):
        """
        添加论文到管理器
        
        参数:
            paper_data (dict): 论文元数据
            local_path (str): 论文本地文件路径
            
        返回:
            bool: 是否添加成功
        """
        # 读取当前论文数据
        papers = self._load_papers()
        
        # 添加下载日期和本地路径
        paper_data['download_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        paper_data['local_path'] = local_path
        
        # 添加到论文集合中
        papers[paper_data['id']] = paper_data
        
        # 保存更新
        return self._save_papers(papers)
    
    def get_paper(self, paper_id):
        """
        获取论文信息
        
        参数:
            paper_id (str): 论文ID
            
        返回:
            dict: 论文信息，如果不存在则返回None
        """
        papers = self._load_papers()
        return papers.get(paper_id)
    
    def get_all_papers(self):
        """
        获取所有已保存的论文
        
        返回:
            list: 所有论文的列表
        """
        papers = self._load_papers()
        # 将字典转换为列表
        return list(papers.values())
    
    def add_category(self, category_name):
        """
        添加新的论文分类
        
        参数:
            category_name (str): 分类名称
            
        返回:
            bool: 是否添加成功
        """
        categories = self._load_categories()
        
        # 检查分类是否已存在
        if category_name in categories['categories']:
            return True  # 分类已存在，视为成功
        
        # 添加新分类
        categories['categories'][category_name] = []
        
        # 保存分类
        return self._save_categories(categories)
    
    def add_paper_to_category(self, paper_id, category_name):
        """
        将论文添加到指定分类
        
        参数:
            paper_id (str): 论文ID
            category_name (str): 分类名称
            
        返回:
            bool: 是否添加成功
        """
        categories = self._load_categories()
        
        # 检查分类是否存在
        if category_name not in categories['categories']:
            return False
        
        # 检查论文是否已在分类中
        if paper_id in categories['categories'][category_name]:
            return True  # 论文已在分类中，视为成功
        
        # 将论文添加到分类
        categories['categories'][category_name].append(paper_id)
        
        # 保存分类
        return self._save_categories(categories)
    
    def get_categories(self):
        """
        获取所有分类
        
        返回:
            list: 分类列表
        """
        categories = self._load_categories()
        return list(categories['categories'].keys())
    
    def get_papers_by_category(self, category_name):
        """
        获取指定分类下的所有论文ID
        
        参数:
            category_name (str): 分类名称
            
        返回:
            list: 论文ID列表，如果分类不存在则返回空列表
        """
        categories = self._load_categories()
        
        # 检查分类是否存在
        if category_name not in categories['categories']:
            return []
        
        return categories['categories'][category_name]
    
    def remove_paper_from_category(self, paper_id, category_name):
        """
        从分类中移除论文
        
        参数:
            paper_id (str): 论文ID
            category_name (str): 分类名称
            
        返回:
            bool: 是否移除成功
        """
        categories = self._load_categories()
        
        # 检查分类是否存在
        if category_name not in categories['categories']:
            return False
        
        # 检查论文是否在分类中
        if paper_id not in categories['categories'][category_name]:
            return True  # 论文不在分类中，视为成功
        
        # 从分类中移除论文
        categories['categories'][category_name].remove(paper_id)
        
        # 保存分类
        return self._save_categories(categories)
    
    def delete_category(self, category_name):
        """
        删除分类
        
        参数:
            category_name (str): 分类名称
            
        返回:
            bool: 是否删除成功
        """
        categories = self._load_categories()
        
        # 检查分类是否存在
        if category_name not in categories['categories']:
            return True  # 分类不存在，视为成功
        
        # 删除分类
        del categories['categories'][category_name]
        
        # 保存分类
        return self._save_categories(categories)
        
    def _load_papers(self):
        """
        从文件加载论文数据
        
        返回:
            dict: 论文数据
        """
        try:
            with open(self.papers_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _save_papers(self, papers):
        """
        将论文数据保存到文件
        
        参数:
            papers (dict): 论文数据
            
        返回:
            bool: 是否保存成功
        """
        try:
            with open(self.papers_file, 'w') as f:
                json.dump(papers, f, indent=2)
            return True
        except Exception:
            return False
    
    def _load_categories(self):
        """
        从文件加载分类数据
        
        返回:
            dict: 分类数据
        """
        try:
            with open(self.categories_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"categories": {}, "default": []}
    
    def _save_categories(self, categories):
        """
        将分类数据保存到文件
        
        参数:
            categories (dict): 分类数据
            
        返回:
            bool: 是否保存成功
        """
        try:
            with open(self.categories_file, 'w') as f:
                json.dump(categories, f, indent=2)
            return True
        except Exception:
            return False 