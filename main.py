import argparse
from arxiv_client import ArxivClient
from paper_manager import PaperManager
import re
from translate import Translator

# 判断文本是否包含中文
def contains_chinese(text):
    """检查文本是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

# 翻译中文到英文
def translate_to_english(text):
    """将中文文本翻译成英文"""
    if not contains_chinese(text):
        return text, False  # 不包含中文，无需翻译
    
    try:
        translator = Translator(to_lang="en", from_lang="zh")
        translated = translator.translate(text)
        return translated, True
    except Exception as e:
        print(f"翻译出错: {str(e)}，将使用原始文本")
        return text, False

def main():
    parser = argparse.ArgumentParser(description='ArXiv 综述整理工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 搜索命令
    search_parser = subparsers.add_parser('search', help='搜索论文')
    search_parser.add_argument('query', help='搜索关键词')
    search_parser.add_argument('--max-results', type=int, default=10, help='最大结果数量')
    search_parser.add_argument('--sort-by', choices=['relevance', 'lastUpdatedDate', 'submittedDate'], 
                              default='relevance', help='排序方式')
    search_parser.add_argument('--no-translate', action='store_true', help='禁用中文自动翻译')
    
    # 下载命令
    download_parser = subparsers.add_parser('download', help='下载论文')
    download_parser.add_argument('paper_id', help='论文ID')
    download_parser.add_argument('--output-dir', default='papers', help='输出目录')
    
    # 整理命令
    organize_parser = subparsers.add_parser('organize', help='整理论文')
    organize_parser.add_argument('--input-dir', default='papers', help='输入目录')
    organize_parser.add_argument('--output-format', choices=['markdown', 'json'], default='markdown', 
                                help='输出格式')
    
    args = parser.parse_args()
    
    arxiv_client = ArxivClient()
    paper_manager = PaperManager()
    
    # 处理命令
    if args.command == 'search':
        # 处理中文搜索关键词翻译
        query = args.query
        if not args.no_translate:
            query, was_translated = translate_to_english(args.query)
            if was_translated:
                print(f"已将搜索关键词 \"{args.query}\" 翻译为: \"{query}\"")
        
        results = arxiv_client.search(query, args.max_results, args.sort_by)
        print(f"\n找到 {len(results)} 篇论文:")
        for i, paper in enumerate(results, 1):
            print(f"\n{i}. {paper['title']} (ID: {paper['id']})")
            print(f"   作者: {', '.join(paper['authors'])}")
            print(f"   发布: {paper['published']}")
            print(f"   摘要: {paper['summary'][:200]}...")
    
    elif args.command == 'download':
        output_path = arxiv_client.download(args.paper_id, args.output_dir)
        print(f"论文已下载至: {output_path}")
    
    elif args.command == 'organize':
        result = paper_manager.organize(args.input_dir, args.output_format)
        output_file = f"review.{'md' if args.output_format == 'markdown' else 'json'}"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"综述已生成: {output_file}")

if __name__ == "__main__":
    main() 