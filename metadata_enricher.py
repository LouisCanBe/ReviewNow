import requests
import time
import urllib.parse
import json
from translate import Translator
import re

class MetadataEnricher:
    """
    通过外部API增强论文元数据
    """
    
    def __init__(self):
        self.translation_cache = {}  # 用于缓存翻译结果
        self.translation_fail_count = 0  # 记录主要翻译方法失败次数
        self.use_google_translate = False  # 是否直接使用Google翻译
    
    def enrich_with_semantic_scholar(self, arxiv_id):
        """
        使用Semantic Scholar API获取额外元数据
        """
        # 移除可能的'arxiv:'前缀
        if arxiv_id.startswith('arxiv:'):
            arxiv_id = arxiv_id[6:]
            
        # 构建API URL
        url = f"https://api.semanticscholar.org/v1/paper/arXiv:{arxiv_id}"
        
        try:
            # 添加等待以避免API限流
            time.sleep(1)
            response = requests.get(url, timeout=10)  # 添加超时参数
            
            if response.status_code == 200:
                data = response.json()
                
                # 提取有用的元数据
                additional_data = {
                    'citation_count': data.get('citationCount', 0),
                    'influence_factor': data.get('influentialCitationCount', 0),
                    'published_in': data.get('venue', '未知'),
                    'year': data.get('year'),
                    'doi': data.get('doi'),
                    'url': data.get('url'),
                    'is_open_access': data.get('isOpenAccess', False),
                    'topics': [topic.get('name') for topic in data.get('topics', [])] if data.get('topics') else []
                }
                
                return additional_data
            else:
                print(f"Semantic Scholar API请求失败: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"获取额外元数据时出错: {str(e)}")
            return {}
    
    def contains_chinese(self, text):
        """检查文本是否包含中文字符"""
        if not text:
            return False
        return bool(re.search(r'[\u4e00-\u9fff]', text))
    
    def chunk_text(self, text, max_chunk_size=450):
        """
        将文本分割成较小的块
        
        参数:
            text (str): 要分割的文本
            max_chunk_size (int): 每个块的最大大小（字符数）
            
        返回:
            list: 文本块列表
        """
        # 如果文本为空或较短，直接返回
        if not text or len(text) <= max_chunk_size:
            return [text]
            
        chunks = []
        # 尝试在句子结束处分割
        start = 0
        while start < len(text):
            # 如果剩余文本小于最大大小，直接添加
            if start + max_chunk_size >= len(text):
                chunks.append(text[start:])
                break
                
            # 寻找最大块内的最后一个句号、问号或感叹号
            end = start + max_chunk_size
            
            # 向后查找句子结束标志
            sentence_end = max(
                text.rfind('. ', start, end),
                text.rfind('? ', start, end),
                text.rfind('! ', start, end),
                text.rfind('.\n', start, end),
                text.rfind('?\n', start, end),
                text.rfind('!\n', start, end)
            )
            
            # 如果找不到句子结束，则在单词边界分割
            if sentence_end == -1:
                sentence_end = text.rfind(' ', start, end)
                if sentence_end == -1:  # 如果没有找到空格，则直接在最大大小处分割
                    sentence_end = end - 1
            
            # 添加文本块
            chunks.append(text[start:sentence_end+1])
            start = sentence_end + 1
            
        return chunks
    
    def google_translate(self, text, to_lang="zh", from_lang="en"):
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
    
    def translate_text(self, text, to_lang="zh", from_lang="en"):
        """
        翻译文本，支持分块翻译长文本
        """
        if not text:
            return ""
            
        # 检查是否需要翻译
        if to_lang == "zh" and self.contains_chinese(text):
            print("文本已经包含中文，无需翻译")
            return text  # 已经是中文，不需要翻译
            
        # 检查缓存
        cache_key = f"{text[:30]}_{from_lang}_{to_lang}"
        if cache_key in self.translation_cache:
            print("使用缓存的翻译结果")
            return self.translation_cache[cache_key]
            
        # 如果之前的主要翻译方法已经失败3次以上，直接使用Google翻译
        if self.translation_fail_count >= 3 or self.use_google_translate:
            print(f"由于之前翻译失败次数较多，直接使用Google翻译")
            self.use_google_translate = True  # 标记使用Google翻译
            
            try:
                # 分割长文本
                chunks = self.chunk_text(text, max_chunk_size=900)  # Google翻译支持更长的文本
                
                if len(chunks) == 1:
                    # 单个块直接翻译
                    translated = self.google_translate(chunks[0], to_lang, from_lang)
                    self.translation_cache[cache_key] = translated
                    return translated
                else:
                    # 多个块分别翻译
                    translated_chunks = []
                    for chunk in chunks:
                        time.sleep(0.5)  # 避免请求过于频繁
                        translated_chunk = self.google_translate(chunk, to_lang, from_lang)
                        translated_chunks.append(translated_chunk)
                    
                    # 合并翻译结果
                    translated = ' '.join(translated_chunks)
                    self.translation_cache[cache_key] = translated
                    return translated
            except Exception as e:
                print(f"Google翻译失败: {str(e)}")
                return text  # 出错时返回原始文本
            
        try:
            # 分割长文本
            chunks = self.chunk_text(text)
            print(f"将文本分割成{len(chunks)}个块进行翻译")
            
            if len(chunks) == 1:
                # 单个块可以直接翻译
                print(f"翻译单个文本块，长度: {len(chunks[0])}")
                try:
                    translator = Translator(to_lang=to_lang, from_lang=from_lang)
                    translated = translator.translate(chunks[0])
                    
                    # 检查是否为错误信息
                    if "MYMEMORY WARNING" in translated.upper() or "QUOTA EXCEEDED" in translated.upper():
                        print("主要翻译API配额已用完，切换到Google翻译")
                        self.translation_fail_count += 1
                        self.use_google_translate = True
                        
                        # 使用Google翻译作为备用
                        translated = self.google_translate(chunks[0], to_lang, from_lang)
                    
                    # 保存到缓存
                    self.translation_cache[cache_key] = translated
                    return translated
                except Exception as e:
                    print(f"主要翻译方法失败: {str(e)}")
                    self.translation_fail_count += 1
                    
                    # 尝试Google翻译
                    try:
                        translated = self.google_translate(chunks[0], to_lang, from_lang)
                        self.translation_cache[cache_key] = translated
                        return translated
                    except:
                        return text  # 如果备用方法也失败，返回原文
            else:
                # 多个块需要分别翻译并合并
                print(f"开始翻译多个文本块")
                translated_chunks = []
                
                for i, chunk in enumerate(chunks):
                    print(f"翻译块 {i+1}/{len(chunks)}, 长度: {len(chunk)}")
                    time.sleep(0.5)  # 翻译API节流
                    
                    try:
                        if self.use_google_translate:
                            # 直接使用Google翻译
                            translated_chunk = self.google_translate(chunk, to_lang, from_lang)
                        else:
                            # 尝试使用主要翻译方法
                            translator = Translator(to_lang=to_lang, from_lang=from_lang)
                            translated_chunk = translator.translate(chunk)
                            
                            # 检查是否为错误信息
                            if "MYMEMORY WARNING" in translated_chunk.upper() or "QUOTA EXCEEDED" in translated_chunk.upper():
                                print(f"块 {i+1} 翻译时主要API配额已用完，切换到Google翻译")
                                self.translation_fail_count += 1
                                self.use_google_translate = True
                                
                                # 使用Google翻译
                                translated_chunk = self.google_translate(chunk, to_lang, from_lang)
                        
                        translated_chunks.append(translated_chunk)
                        print(f"块 {i+1} 翻译成功")
                    except Exception as chunk_error:
                        print(f"块 {i+1} 翻译失败: {str(chunk_error)}")
                        self.translation_fail_count += 1
                        
                        # 尝试Google翻译
                        try:
                            translated_chunk = self.google_translate(chunk, to_lang, from_lang)
                            translated_chunks.append(translated_chunk)
                        except:
                            # 如果备用方法也失败，使用原始块
                            translated_chunks.append(chunk)
                
                # 合并翻译结果
                translated = ' '.join(translated_chunks)
                print("所有块翻译完成并合并")
                
                # 保存到缓存
                self.translation_cache[cache_key] = translated
                return translated
                
        except Exception as e:
            print(f"翻译过程出错: {str(e)}")
            # 尝试Google翻译作为最后的备用方法
            try:
                return self.google_translate(text, to_lang, from_lang)
            except:
                return text  # 出错时返回原始文本
    
    def translate_paper_data(self, paper_data):
        """
        翻译论文的标题和摘要
        """
        # 创建一个新的字典来存储翻译后的数据
        translated_data = paper_data.copy()
        
        # 翻译标题
        if 'title' in paper_data:
            try:
                translated_data['title_zh'] = self.translate_text(paper_data['title'])
            except Exception as e:
                print(f"标题翻译出错: {str(e)}")
                translated_data['title_zh'] = paper_data['title']
            
        # 翻译摘要
        if 'summary' in paper_data:
            try:
                translated_data['summary_zh'] = self.translate_text(paper_data['summary'])
            except Exception as e:
                print(f"摘要翻译出错: {str(e)}")
                translated_data['summary_zh'] = paper_data['summary']
            
        return translated_data 