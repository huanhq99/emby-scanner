#!/usr/bin/env python3
"""
Emby媒体库重复检测工具
GitHub: https://github.com/huanhq99/emby-scanner
"""

import os
import sys
import subprocess
import requests
import json
import re
import hashlib
from collections import defaultdict
from datetime import datetime
import humanize

class EmbyScannerSetup:
    """环境设置和交互界面"""
    
    def __init__(self):
        self.server_url = ""
        self.api_key = ""
        self.venv_path = os.path.expanduser("~/emby-scanner-env")
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.version = "2.2"  # 更新版本号
        self.github_url = "https://github.com/huanhq99/emby-scanner"
        
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_banner(self):
        """打印横幅"""
        banner = f"""
╔════════════════════════════════════════════════════════════════╗
║            Emby媒体库重复检测工具 v{self.version}           
║                GitHub: {self.github_url}               
╚════════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    def get_file_size(self, file_path):
        """获取文件大小（字节）"""
        try:
            if os.path.isfile(file_path):
                return os.path.getsize(file_path)
            else:
                # 对于目录或不存在文件，返回0
                return 0
        except:
            return 0
    
    def get_folder_size(self, folder_path):
        """获取文件夹总大小"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total_size += self.get_file_size(filepath)
        except:
            pass
        return total_size
    
    def format_file_size(self, size_bytes):
        """格式化文件大小显示"""
        if size_bytes == 0:
            return "0 B"
        return humanize.naturalsize(size_bytes)
    
    def calculate_file_hash(self, file_path, chunk_size=8192):
        """计算文件哈希（用于精确重复检测）"""
        try:
            if not os.path.isfile(file_path):
                return None
                
            file_hash = hashlib.md5()
            with open(file_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    file_hash.update(chunk)
            return file_hash.hexdigest()
        except:
            return None

    def get_library_items_with_size(self, library_id, item_types='Movie,Series'):
        """获取媒体库项目并包含文件大小信息"""
        url = f"{self.server_url}/emby/Items"
        params = {
            'ParentId': library_id,
            'Recursive': True,
            'IncludeItemTypes': item_types,
            'Fields': 'Path,ProviderIds,Name,Type,MediaSources',
            'Limit': 1000
        }
        
        all_items = []
        start_index = 0
        
        while True:
            params['StartIndex'] = start_index
            try:
                response = requests.get(url, headers={'X-Emby-Token': self.api_key}, 
                                      params=params, timeout=60)  # 增加超时时间
                response.raise_for_status()
                data = response.json()
                
                items = data.get('Items', [])
                if not items:
                    break
                
                # 为每个项目添加大小信息
                processed_items = []
                for item in items:
                    item_with_size = self.process_item_size(item)
                    if item_with_size:  # 只保留有路径的项目
                        processed_items.append(item_with_size)
                
                all_items.extend(processed_items)
                start_index += len(items)
                
                print(f"已处理 {len(all_items)} 个项目...")
                
                if len(items) < params['Limit']:
                    break
                    
            except Exception as e:
                print(f"❌ 获取项目失败: {e}")
                break
        
        return all_items
    
    def process_item_size(self, item):
        """处理单个项目的文件大小信息"""
        try:
            item_path = item.get('Path', '')
            if not item_path or not os.path.exists(item_path):
                # 尝试从MediaSources获取路径
                media_sources = item.get('MediaSources', [])
                if media_sources and media_sources[0].get('Path'):
                    item_path = media_sources[0]['Path']
            
            if not item_path or not os.path.exists(item_path):
                return None
            
            # 计算大小
            if os.path.isfile(item_path):
                file_size = self.get_file_size(item_path)
                item['FileSize'] = file_size
                item['IsFile'] = True
            elif os.path.isdir(item_path):
                file_size = self.get_folder_size(item_path)
                item['FileSize'] = file_size
                item['IsFile'] = False
            else:
                item['FileSize'] = 0
            
            # 添加文件哈希（用于精确比较）
            if os.path.isfile(item_path) and item['FileSize'] > 0:
                item['FileHash'] = self.calculate_file_hash(item_path)
            else:
                item['FileHash'] = None
                
            return item
            
        except Exception as e:
            print(f"⚠️ 处理项目大小失败: {e}")
            item['FileSize'] = 0
            item['FileHash'] = None
            return item
    
    def analyze_duplicates_by_size(self, items):
        """根据文件大小分析重复项目"""
        # 按文件大小分组
        size_groups = defaultdict(list)
        hash_groups = defaultdict(list)
        
        print("🔍 分析文件大小重复...")
        
        for item in items:
            if item.get('FileSize', 0) == 0:
                continue  # 跳过大小为0的项目
                
            item_id = item['Id']
            item_name = item.get('Name', '未知').strip()
            item_type = item.get('Type', '未知')
            path = item.get('Path', '无路径')
            file_size = item.get('FileSize', 0)
            file_hash = item.get('FileHash')
            
            item_info = {
                'id': item_id,
                'name': item_name,
                'type': item_type,
                'path': path,
                'size': file_size,
                'size_formatted': self.format_file_size(file_size),
                'hash': file_hash,
                'is_file': item.get('IsFile', True)
            }
            
            # 按大小分组
            size_groups[file_size].append(item_info)
            
            # 按哈希分组（如果有哈希值）
            if file_hash:
                hash_groups[file_hash].append(item_info)
        
        # 检测大小重复
        size_duplicates = []
        for size, items_list in size_groups.items():
            if len(items_list) > 1:
                # 检查是否真的有重复（排除相同路径的情况）
                unique_paths = set(item['path'] for item in items_list)
                if len(unique_paths) > 1:
                    size_duplicates.append({
                        'key': f"大小: {self.format_file_size(size)}",
                        'size': size,
                        'items': items_list
                    })
        
        # 检测哈希重复（精确重复）
        hash_duplicates = []
        for file_hash, items_list in hash_groups.items():
            if len(items_list) > 1:
                unique_paths = set(item['path'] for item in items_list)
                if len(unique_paths) > 1:
                    hash_duplicates.append({
                        'key': f"文件哈希: {file_hash[:8]}...",
                        'hash': file_hash,
                        'items': items_list
                    })
        
        return size_duplicates, hash_duplicates
    
    def run_size_based_scanner(self):
        """运行基于文件大小的重复检测"""
        print("\n🚀 开始文件体积查重扫描...")
        print("正在分析文件大小，请耐心等待（大文件可能需要较长时间）...")
        
        libraries = self.get_libraries()
        if not libraries:
            print("❌ 未找到任何媒体库")
            return None
        
        total_stats = defaultdict(int)
        total_size = 0
        all_size_duplicates = []
        all_hash_duplicates = []
        report_lines = []
        
        # 报告头部
        report_lines.append("🎬 Emby媒体库体积查重检测报告")
        report_lines.append("=" * 80)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"服务器: {self.server_url}")
        report_lines.append("检测规则: 文件大小重复 > 文件哈希重复（精确匹配）")
        report_lines.append("")
        
        # 扫描电影库
        movie_libraries = [lib for lib in libraries if any(keyword in lib['Name'].lower() 
                          for keyword in ['电影', 'movie', 'movies'])]
        
        # 扫描电视剧库
        series_libraries = [lib for lib in libraries if any(keyword in lib['Name'].lower() 
                            for keyword in ['剧集', 'tv', 'series', '电视剧'])]
        
        # 扫描电影
        if movie_libraries:
            report_lines.append("🎥 电影库体积查重结果")
            report_lines.append("-" * 60)
            
            for library in movie_libraries:
                lib_name = library['Name']
                print(f"📁 扫描电影库: {lib_name}")
                
                items = self.get_library_items_with_size(library['Id'], 'Movie')
                print(f"   找到 {len(items)} 部电影，正在分析文件大小...")
                
                if not items:
                    continue
                
                # 统计
                lib_total_size = 0
                for item in items:
                    total_stats['Movie'] += 1
                    lib_total_size += item.get('FileSize', 0)
                
                total_size += lib_total_size
                
                # 检测重复
                size_duplicates, hash_duplicates = self.analyze_duplicates_by_size(items)
                
                # 添加到报告
                report_lines.append(f"媒体库: {lib_name}")
                report_lines.append(f"电影数量: {len(items)}")
                report_lines.append(f"总大小: {self.format_file_size(lib_total_size)}")
                
                if hash_duplicates:
                    report_lines.append(f"🔴 哈希重复（精确重复）: {len(hash_duplicates)} 组")
                    saved_space = 0
                    for dup in hash_duplicates:
                        dup_size = dup['items'][0]['size']
                        saved_space += dup_size * (len(dup['items']) - 1)
                        report_lines.append(f"  {dup['key']} (重复{len(dup['items'])}次)")
                        for item in dup['items']:
                            report_lines.append(f"    - {item['name']}")
                            report_lines.append(f"      路径: {item['path']}")
                            report_lines.append(f"      大小: {item['size_formatted']}")
                        report_lines.append("")
                    report_lines.append(f"🚀 可释放空间: {self.format_file_size(saved_space)}")
                    all_hash_duplicates.extend(hash_duplicates)
                
                if size_duplicates:
                    report_lines.append(f"🟡 大小重复: {len(size_duplicates)} 组")
                    for dup in size_duplicates:
                        report_lines.append(f"  {dup['key']} (重复{len(dup['items'])}次)")
                        for item in dup['items']:
                            report_lines.append(f"    - {item['name']}")
                            report_lines.append(f"      路径: {item['path']}")
                    report_lines.append("")
                    all_size_duplicates.extend(size_duplicates)
                
                if not size_duplicates and not hash_duplicates:
                    report_lines.append("✅ 未发现重复文件")
                
                report_lines.append("")
        
        # 扫描电视剧
        if series_libraries:
            report_lines.append("📺 电视剧库体积查重结果")
            report_lines.append("-" * 60)
            
            for library in series_libraries:
                lib_name = library['Name']
                print(f"📁 扫描电视剧库: {lib_name}")
                
                items = self.get_library_items_with_size(library['Id'], 'Series')
                print(f"   找到 {len(items)} 部电视剧，正在分析文件大小...")
                
                if not items:
                    continue
                
                # 统计
                lib_total_size = 0
                for item in items:
                    total_stats['Series'] += 1
                    lib_total_size += item.get('FileSize', 0)
                
                total_size += lib_total_size
                
                # 检测重复
                size_duplicates, hash_duplicates = self.analyze_duplicates_by_size(items)
                
                # 添加到报告
                report_lines.append(f"媒体库: {lib_name}")
                report_lines.append(f"电视剧数量: {len(items)}")
                report_lines.append(f"总大小: {self.format_file_size(lib_total_size)}")
                
                if hash_duplicates:
                    report_lines.append(f"🔴 哈希重复（精确重复）: {len(hash_duplicates)} 组")
                    saved_space = 0
                    for dup in hash_duplicates:
                        dup_size = dup['items'][0]['size']
                        saved_space += dup_size * (len(dup['items']) - 1)
                        report_lines.append(f"  {dup['key']} (重复{len(dup['items'])}次)")
                    all_hash_duplicates.extend(hash_duplicates)
                    report_lines.append(f"🚀 可释放空间: {self.format_file_size(saved_space)}")
                
                if size_duplicates:
                    report_lines.append(f"🟡 大小重复: {len(size_duplicates)} 组")
                    for dup in size_duplicates:
                        report_lines.append(f"  {dup['key']} (重复{len(dup['items'])}次)")
                    all_size_duplicates.extend(size_duplicates)
                
                if not size_duplicates and not hash_duplicates:
                    report_lines.append("✅ 未发现重复文件")
                
                report_lines.append("")
        
        # 总结报告
        report_lines.append("=" * 80)
        report_lines.append("📊 体积查重统计总结")
        report_lines.append("=" * 80)
        
        total_items = sum(total_stats.values())
        report_lines.append(f"总计扫描: {total_items} 个项目")
        report_lines.append(f"总文件大小: {self.format_file_size(total_size)}")
        
        for item_type, count in total_stats.items():
            report_lines.append(f"  {item_type}: {count} 个")
        
        # 计算可释放空间
        total_saved_space = 0
        for dup_group in all_hash_duplicates:
            if dup_group['items']:
                file_size = dup_group['items'][0]['size']
                total_saved_space += file_size * (len(dup_group['items']) - 1)
        
        report_lines.append("")
        report_lines.append("🚨 体积查重结果:")
        report_lines.append(f"    🔴 哈希重复（精确重复）: {len(all_hash_duplicates)} 组")
        report_lines.append(f"    大小重复（可疑重复）: {len(all_size_duplicates)} 组")
        
        if total_saved_space > 0:
            report_lines.append(f"    💰 可释放空间: {self.format_file_size(total_saved_space)}")
        
        if all_hash_duplicates or all_size_duplicates:
            report_lines.append("")
            report_lines.append("💡 处理建议:")
            report_lines.append("  1.  🔴 哈希重复: 文件内容完全相同的重复文件，可安全删除")
            report_lines.append("  2.  大小重复: 文件大小相同但内容可能不同，建议手动检查")
            report_lines.append("  3. 删除前请确认文件内容，建议先备份")
        else:
            report_lines.append("🎉 恭喜！未发现任何重复文件")
        
        # 生成报告文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"emby_size_duplicate_report_{timestamp}.txt"
        report_path = os.path.join(self.script_dir, report_file)
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            
            return report_path
        except Exception as e:
            print(f"❌ 生成报告失败: {e}")
            return None

    # 保留原有的连接测试、配置管理等方法的其他部分保持不变
    # 只需要修改运行扫描的方法，添加体积查重选项

    def run_scanner(self):
        """运行扫描器（现在包含体积查重）"""
        self.clear_screen()
        self.print_banner()
        
        print("🔍 选择扫描模式:")
        print("1.  🔄 智能查重（TMDB ID + 名称 + 体积）")
        print("2.  📊 体积查重（文件大小 + 哈希值）")
        print("3.  🎬 传统查重（TMDB ID + 名称）")
        
        choice = input("\n请选择扫描模式 [1-3]: ").strip()
        
        if choice == "1":
            print("\n🚀 开始智能查重扫描...")
            # 这里可以组合多种检测方法
            report_path = self.run_real_scanner()
        elif choice == "2":
            print("\n🚀 开始体积查重扫描...")
            report_path = self.run_size_based_scanner()
        elif choice == "3":
            print("\n🚀 开始传统查重扫描...")
            report_path = self.run_real_scanner()
        else:
            print("❌ 无效选择")
            input("按回车键返回主菜单...")
            return
        
        if report_path:
            print(f"\n✅ 扫描完成！")
            print(f"📄 报告文件: {os.path.basename(report_path)}")
            print(f"📍 文件位置: {self.script_dir}/")
            print("\n💡 查看报告方法:")
            print("1. 主菜单 → 查看扫描报告")
            print(f"2. 命令: cat '{report_path}'")
            print(f"3. 命令: nano '{report_path}'")
        else:
            print("❌ 扫描失败")
        
        input("\n按回车键返回主菜单...")
    
    def run_real_scanner(self):
        """运行传统的TMDB ID和名称查重"""
        print("\n🚀 开始传统查重扫描...")
        
        libraries = self.get_libraries()
        if not libraries:
            print("❌ 未找到任何媒体库")
            return None
        
        total_stats = defaultdict(int)
        all_tmdb_duplicates = []
        all_name_duplicates = []
        report_lines = []
        
        # 报告头部
        report_lines.append("🎬 Emby媒体库传统查重检测报告")
        report_lines.append("=" * 70)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"服务器: {self.server_url}")
        report_lines.append("检测规则: TMDB ID重复 > 名称重复")
        report_lines.append("")
        
        # 保留原有的TMDB ID和名称查重逻辑
        for library in libraries:
            lib_name = library['Name']
            item_types = 'Series' if any(keyword in lib_name.lower() for keyword in ['剧集', 'tv', 'series', '电视剧']) else 'Movie'
            
            print(f"📁 扫描媒体库: {lib_name}")
            items = self.get_library_items(library['Id'], item_types)
            print(f"   找到 {len(items)} 个项目")
            
            if not items:
                continue
            
            # 统计
            for item in items:
                total_stats[item_types] += 1
            
            # 检测重复
            tmdb_duplicates, name_duplicates = self.analyze_duplicates(items)
            
            # 添加到报告
            report_lines.append(f"媒体库: {lib_name}")
            report_lines.append(f"项目数量: {len(items)}")
            
            if tmdb_duplicates:
                report_lines.append(f"🔴 TMDB ID重复: {len(tmdb_duplicates)} 组")
                for dup in tmdb_duplicates:
                    report_lines.append(f"  {dup['key']} (重复{len(dup['items'])}次)")
                    for item in dup['items']:
                        report_lines.append(f"    - {item['name']}")
                        report_lines.append(f"      路径: {item['path']}")
                    report_lines.append("")
                all_tmdb_duplicates.extend(tmdb_duplicates)
            
            if name_duplicates:
                report_lines.append(f"🟡 名称重复: {len(name_duplicates)} 组")
                for dup in name_duplicates:
                    report_lines.append(f"  {dup['key']} (重复{len(dup['items'])}次)")
                all_name_duplicates.extend(name_duplicates)
            
            if not tmdb_duplicates and not name_duplicates:
                report_lines.append("✅ 未发现重复内容")
            
            report_lines.append("")
        
        # 生成报告文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"emby_traditional_report_{timestamp}.txt"
        report_path = os.path.join(self.script_dir, report_file)
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            return report_path
        except Exception as e:
            print(f"❌ 生成报告失败: {e}")
            return None
    
    def get_libraries(self):
        """获取所有媒体库"""
        try:
            headers = {'X-Emby-Token': self.api_key}
            response = requests.get(f"{self.server_url}/emby/Library/MediaFolders", 
                                  headers=headers, timeout=30)
            response.raise_for_status()
            return response.json().get('Items', [])
        except Exception as e:
            print(f"❌ 获取媒体库失败: {e}")
            return []
    
    def get_library_items(self, library_id, item_types='Movie,Series'):
        """获取媒体库中的项目（不含大小信息）"""
        url = f"{self.server_url}/emby/Items"
        params = {
            'ParentId': library_id,
            'Recursive': True,
            'IncludeItemTypes': item_types,
            'Fields': 'Path,ProviderIds,Name,Type',
            'Limit': 1000
        }
        
        all_items = []
        start_index = 0
        
        while True:
            params['StartIndex'] = start_index
            try:
                response = requests.get(url, headers={'X-Emby-Token': self.api_key}, 
                                      params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                items = data.get('Items', [])
                if not items:
                    break
                
                all_items.extend(items)
                start_index += len(items)
                
                if len(items) < params['Limit']:
                    break
                    
            except Exception as e:
                print(f"❌ 获取项目失败: {e}")
                break
        
        return all_items
    
    def extract_tmdb_id(self, item):
        """提取TMDB ID"""
        provider_ids = item.get('ProviderIds', {})
        tmdb_id = provider_ids.get('Tmdb')
        
        # 从路径中提取TMDB ID
        if not tmdb_id:
            path = item.get('Path', '')
            match = re.search(r'{tmdb-(\d+)}', path)
            if match:
                tmdb_id = match.group(1)
        
        return str(tmdb_id) if tmdb_id else None
    
    def analyze_duplicates(self, items):
        """分析重复项目（传统方法）"""
        tmdb_groups = defaultdict(list)
        name_groups = defaultdict(list)
        
        for item in items:
            item_id = item['Id']
            item_name = item.get('Name', '未知').strip()
            item_type = item.get('Type', '未知')
            path = item.get('Path', '无路径')
            
            tmdb_id = self.extract_tmdb_id(item)
            
            item_info = {
                'id': item_id,
                'name': item_name,
                'type': item_type,
                'path': path,
                'tmdb_id': tmdb_id
            }
            
            # TMDB ID分组
            if tmdb_id:
                tmdb_groups[tmdb_id].append(item_info)
            
            # 名称分组
            name_groups[item_name].append(item_info)
        
        # 检测重复
        tmdb_duplicates = []
        name_duplicates = []
        
        for tmdb_id, items_list in tmdb_groups.items():
            if len(items_list) > 1:
                tmdb_duplicates.append({
                    'key': f"TMDB-ID: {tmdb_id}",
                    'items': items_list
                })
        
        for name, items_list in name_groups.items():
            if len(items_list) > 1 and name != '未知':
                if len(set(item['path'] for item in items_list)) > 1:
                    name_duplicates.append({
                        'key': f"名称: {name}",
                        'items': items_list
                    })
        
        return tmdb_duplicates, name_duplicates
    
    def show_reports(self):
        """显示报告文件"""
        self.clear_screen()
        self.print_banner()
        print("\n📊 扫描报告列表")
        print("=" * 50)
        
        reports = []
        for file in os.listdir(self.script_dir):
            if (file.startswith("emby_library_report_") or 
                file.startswith("emby_size_duplicate_report_") or
                file.startswith("emby_traditional_report_")) and file.endswith(".txt"):
                file_path = os.path.join(self.script_dir, file)
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                file_size = os.path.getsize(file_path)
                file_type = "智能查重" if "library_report" in file else "体积查重" if "size_duplicate" in file else "传统查重"
                reports.append((file, file_time, file_size, file_type))
        
        if not reports:
            print("暂无扫描报告")
            print("请先运行扫描功能生成报告")
        else:
            reports.sort(key=lambda x: x[1], reverse=True)
            
            print(f"找到 {len(reports)} 个报告文件:")
            for i, (report, report_time, size, report_type) in enumerate(reports[:10], 1):
                time_str = report_time.strftime("%Y-%m-%d %H:%M")
                size_kb = size / 1024
                print(f"{i}. [{report_type}] {report}")
                print(f"   时间: {time_str} | 大小: {size_kb:.1f}KB")
            
            choice = input("\n输入报告编号查看，或按回车返回: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(reports):
                self.view_report(reports[int(choice)-1][0])
        
        input("\n按回车键返回主菜单...")
    
    def view_report(self, filename):
        """查看报告内容"""
        file_path = os.path.join(self.script_dir, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            page_size = 20
            current_page = 0
            
            while current_page * page_size < len(lines):
                self.clear_screen()
                print(f"📄 报告文件: {filename}")
                print(f"📍 文件路径: {file_path}")
                print(f"📄 页码: {current_page + 1}/{(len(lines)-1)//page_size + 1}")
                print("=" * 70)
                
                start = current_page * page_size
                end = min((current_page + 1) * page_size, len(lines))
                
                for i, line in enumerate(lines[start:end], start + 1):
                    print(f"{line}")
                
                print("=" * 70)
                if end < len(lines):
                    action = input("回车下一页，q退出，f查看文件路径: ").lower()
                    if action == 'q':
                        break
                    elif action == 'f':
                        print(f"\n📁 报告文件完整路径: {file_path}")
                        print("💡 你可以用以下命令查看:")
                        print(f"   cat '{file_path}'")
                        print(f"   nano '{file_path}'")
                        input("\n按回车继续...")
                    else:
                        current_page += 1
                else:
                    print(f"\n📁 报告文件完整路径: {file_path}")
                    input("已到报告末尾，按回车返回...")
                    break
                    
        except Exception as e:
            print(f"❌ 读取报告失败: {e}")
            input("按回车键继续...")
    
    # 以下是缺失的配置管理方法
    def show_server_examples(self):
        """显示服务器地址示例"""
        print("\n💡 服务器地址示例:")
        print("  - 本地服务器: http://192.168.1.100:8096")
        print("  - 本地服务器: http://localhost:8096") 
        print("  - 远程服务器: https://your-domain.com")
        print("  - 远程服务器: https://emby.example.com")
        print("  - 默认端口: 8096 (HTTP) 或 8920 (HTTPS)")
    
    def show_api_help(self):
        """显示API密钥获取帮助"""
        print("\n📋 如何获取API密钥:")
        print("1. 登录Emby网页管理界面")
        print("2. 点击右上角用户图标 → 下拉菜单选择「高级」")
        print("3. 在左侧菜单选择「API密钥」")
        print("4. 点击「新建API密钥」按钮")
        print("5. 输入描述（如：扫描工具），点击「确定」")
        print("6. 复制生成的API密钥")
    
    def get_emby_config(self):
        """获取Emby配置"""
        print("\n⚙️  Emby服务器配置")
        print("=" * 50)
        
        self.show_server_examples()
        
        while True:
            self.server_url = self.get_user_input("\n请输入Emby服务器地址").strip()
            if not self.server_url:
                print("❌ 服务器地址不能为空")
                continue
            
            if not self.server_url.startswith(('http://', 'https://')):
                self.server_url = 'http://' + self.server_url
                print(f"💡 已自动添加协议: {self.server_url}")
            
            if '://' not in self.server_url:
                print("❌ 服务器地址格式不正确")
                continue
                
            break
        
        self.show_api_help()
        
        while True:
            self.api_key = self.get_user_input("\n请输入API密钥").strip()
            if not self.api_key:
                print("❌ API密钥不能为空")
                continue
                
            if len(self.api_key) < 10:
                confirm = input("⚠️  API密钥似乎过短，是否继续？(y/n): ").lower()
                if confirm != 'y':
                    continue
            
            break
        
        print("\n🔗 测试服务器连接...")
        if self.test_connection():
            print("✅ 连接成功！配置验证通过")
            return True
        else:
            print("❌ 连接测试失败")
            retry = input("\n是否重新配置？(y/n): ").lower()
            if retry == 'y':
                return self.get_emby_config()
            return False
    
    def test_connection(self):
        """测试Emby连接"""
        try:
            headers = {'X-Emby-Token': self.api_key}
            response = requests.get(f"{self.server_url}/emby/System/Info", 
                                  headers=headers, timeout=15)
            
            if response.status_code == 200:
                system_info = response.json()
                server_name = system_info.get('ServerName', '未知')
                version = system_info.get('Version', '未知')
                print(f"✅ 连接成功!")
                print(f"   服务器名称: {server_name}")
                print(f"   Emby版本: {version}")
                return True
            else:
                print(f"❌ 服务器返回错误: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            print("❌ 连接超时（15秒），请检查服务器地址和网络")
            return False
        except requests.exceptions.ConnectionError:
            print("❌ 无法连接到服务器，请检查地址和端口")
            return False
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    def save_config(self):
        """保存配置到文件"""
        config = {
            'server_url': self.server_url,
            'api_key': self.api_key,
            'last_updated': datetime.now().isoformat(),
            'version': self.version
        }
        
        config_file = os.path.join(self.script_dir, 'emby_config.json')
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ 配置保存失败: {e}")
            return False
    
    def load_config(self):
        """从文件加载配置"""
        config_file = os.path.join(self.script_dir, 'emby_config.json')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.server_url = config.get('server_url', '')
                self.api_key = config.get('api_key', '')
                return True
            except:
                pass
        return False
    
    def print_menu(self, title, options):
        """打印菜单"""
        print(f"\n{title}")
        print("=" * 50)
        for key, value in options.items():
            print(f"  {key}. {value}")
        print("-" * 50)
    
    def get_user_input(self, prompt, default=""):
        """获取用户输入"""
        if default:
            user_input = input(f"{prompt} [{default}]: ").strip()
            return user_input if user_input else default
        else:
            return input(f"{prompt}: ").strip()
    
    def check_python(self):
        """检查Python环境"""
        print("\n🔍 检查Python环境...")
        if sys.version_info < (3, 6):
            print("❌ 需要Python 3.6或更高版本")
            return False
        print(f"✅ Python版本: {sys.version.split()[0]}")
        return True
    
    def setup_virtualenv(self):
        """设置虚拟环境"""
        print("\n🚀 设置虚拟环境...")
        
        if os.path.exists(self.venv_path):
            print("✅ 虚拟环境已存在")
            return True
        
        try:
            print("创建虚拟环境中...")
            result = subprocess.run([
                sys.executable, "-m", "venv", self.venv_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 虚拟环境创建成功")
                return True
            else:
                print(f"❌ 虚拟环境创建失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 虚拟环境设置失败: {e}")
            return False
    
    def install_dependencies(self):
        """安装依赖"""
        print("\n📦 安装依赖包...")
        
        pip_path = os.path.join(self.venv_path, "bin", "pip")
        if os.name == 'nt':
            pip_path = os.path.join(self.venv_path, "Scripts", "pip.exe")
        
        dependencies = ["requests", "humanize"]
        
        try:
            result = subprocess.run([
                pip_path, "install"] + dependencies, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 依赖安装成功")
                return True
            else:
                print(f"❌ 依赖安装失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 依赖安装失败: {e}")
            return False
    
    def setup_wizard(self):
        """设置向导"""
        self.clear_screen()
        self.print_banner()
        
        print("欢迎使用Emby媒体库重复检测工具！")
        print("本向导将引导您完成初始设置。")
        print("=" * 50)
        
        if not self.check_python():
            input("\n按回车键退出...")
            return False
        
        if not self.setup_virtualenv():
            input("\n按回车键退出...")
            return False
        
        if not self.install_dependencies():
            input("\n按回车键退出...")
            return False
        
        if not self.get_emby_config():
            input("\n按回车键退出...")
            return False
        
        if self.save_config():
            print("✅ 配置已保存到本地文件")
        else:
            print("⚠️  配置保存失败，下次需要重新输入")
        
        print("\n🎉 初始设置完成！")
        print("您现在可以使用完整的重复检测功能了。")
        input("\n按回车键进入主菜单...")
        return True
    
    def show_system_info(self):
        """显示系统信息"""
        self.clear_screen()
        self.print_banner()
        
        print("🔧 系统信息")
        print("=" * 50)
        print(f"工具版本: v{self.version}")
        print(f"Python版本: {sys.version.split()[0]}")
        print(f"当前目录: {self.script_dir}")
        
        if self.server_url:
            print(f"服务器: {self.server_url}")
        
        # 检查报告文件
        reports = []
        for file in os.listdir(self.script_dir):
            if (file.startswith("emby_library_report_") or 
                file.startswith("emby_size_duplicate_report_") or
                file.startswith("emby_traditional_report_")) and file.endswith(".txt"):
                reports.append(file)
        
        print(f"报告文件: {len(reports)} 个")
        
        if reports:
            latest = max(reports, key=lambda f: os.path.getctime(os.path.join(self.script_dir, f)))
            latest_time = datetime.fromtimestamp(os.path.getctime(os.path.join(self.script_dir, latest)))
            print(f"最新报告: {latest}")
            print(f"生成时间: {latest_time.strftime('%Y-%m-%d %H:%M')}")
            
            # 统计各类报告数量
            size_reports = [f for f in reports if "size_duplicate" in f]
            trad_reports = [f for f in reports if "traditional" in f]
            smart_reports = [f for f in reports if "library_report" in f]
            
            print(f"📊 报告统计:")
            print(f"  体积查重报告: {len(size_reports)} 个")
            print(f"  传统查重报告: {len(trad_reports)} 个")
            print(f"  智能查重报告: {len(smart_reports)} 个")
        
        input("\n按回车键返回主菜单...")
    
    def show_help(self):
        """显示帮助信息"""
        self.clear_screen()
        self.print_banner()
        print("""
📖 使用指南（体积查重版）

🎯 主要功能:
   🔄 智能查重模式: TMDB ID + 名称 + 体积综合检测
   📊 体积查重模式: 文件大小 + 哈希值精确检测（推荐）
   🎬 传统查重模式: TMDB ID + 名称检测

🔍 体积查重原理:
  1. 🔴 哈希重复: 文件内容完全相同的重复文件（最准确）
  2.  大小重复: 文件大小相同但内容可能不同
  3.  📏 文件大小: 显示每个文件的精确大小
  4.  💰 空间统计: 计算可释放的存储空间

📊 检测等级:
   🟢 安全: 哈希重复 - 内容完全相同，可安全删除
   警告: 大小重复 - 需要手动确认内容
   🔴 危险: 名称重复 - 可能有误判风险

💡 使用建议:
  1. 首次使用推荐「体积查重模式」
  2. 大型媒体库建议分库扫描
  3. 删除前务必确认文件内容
  4. 建议先备份重要文件

📁 文件位置:
  - 配置文件: emby_config.json
  - 体积报告: emby_size_duplicate_report_时间戳.txt
  - 传统报告: emby_traditional_report_时间戳.txt
  - 智能报告: emby_library_report_时间戳.txt
""")
        input("\n按回车键返回主菜单...")
    
    def cleanup_old_reports(self):
        """清理旧报告文件"""
        self.clear_screen()
        self.print_banner()
        print("\n🗑️  清理旧报告文件")
        print("=" * 50)
        
        reports = []
        for file in os.listdir(self.script_dir):
            if (file.startswith("emby_library_report_") or 
                file.startswith("emby_size_duplicate_report_") or
                file.startswith("emby_traditional_report_")) and file.endswith(".txt"):
                file_path = os.path.join(self.script_dir, file)
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                reports.append((file, file_time, file_path))
        
        if not reports:
            print("暂无报告文件可清理")
            input("\n按回车键返回主菜单...")
            return
        
        reports.sort(key=lambda x: x[1])
        
        print(f"找到 {len(reports)} 个报告文件:")
        for i, (report, report_time, file_path) in enumerate(reports[:10], 1):
            time_str = report_time.strftime("%Y-%m-%d %H:%M")
            size_kb = os.path.getsize(file_path) / 1024
            print(f"{i}. {report} - {time_str} ({size_kb:.1f}KB)")
        
        print("\n💡 清理选项:")
        print("1. 删除除最新5个外的所有报告")
        print("2. 删除7天前的报告")
        print("3. 删除指定报告")
        print("4. 返回主菜单")
        
        choice = input("\n请选择清理选项 [1-4]: ").strip()
        
        if choice == "1":
            # 保留最新5个，删除其他
            if len(reports) > 5:
                to_delete = reports[:-5]
                self.delete_reports(to_delete, "除最新5个外的所有报告")
            else:
                print("报告文件不足5个，无需清理")
        
        elif choice == "2":
            # 删除7天前的报告
            seven_days_ago = datetime.now().timestamp() - 7 * 24 * 3600
            to_delete = [report for report in reports if report[1].timestamp() < seven_days_ago]
            self.delete_reports(to_delete, "7天前的报告")
        
        elif choice == "3":
            # 删除指定报告
            report_num = input("请输入要删除的报告编号: ").strip()
            if report_num.isdigit() and 1 <= int(report_num) <= len(reports):
                to_delete = [reports[int(report_num)-1]]
                self.delete_reports(to_delete, "指定报告")
            else:
                print("❌ 无效的报告编号")
        
        elif choice == "4":
            return
        else:
            print("❌ 无效选择")
        
        input("\n按回车键返回主菜单...")
    
    def delete_reports(self, reports_to_delete, description):
        """删除指定的报告文件"""
        if not reports_to_delete:
            print("没有符合条件的报告文件")
            return
        
        total_size = 0
        print(f"\n🗑️  即将删除 {len(reports_to_delete)} 个{description}:")
        for report, report_time, file_path in reports_to_delete:
            size_kb = os.path.getsize(file_path) / 1024
            total_size += size_kb
            print(f"  - {report} ({size_kb:.1f}KB)")
        
        confirm = input(f"\n⚠️  确认删除以上 {len(reports_to_delete)} 个文件？(y/N): ").lower()
        if confirm == 'y':
            deleted_count = 0
            for _, _, file_path in reports_to_delete:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ 删除失败 {os.path.basename(file_path)}: {e}")
            
            print(f"✅ 成功删除 {deleted_count}/{len(reports_to_delete)} 个报告文件")
            print(f"💾 释放空间: {total_size:.1f}KB")
        else:
            print("❌ 取消删除操作")
    
    def main_menu(self):
        """主菜单"""
        while True:
            self.clear_screen()
            self.print_banner()
            
            if self.server_url and self.api_key:
                display_url = self.server_url
                if len(display_url) > 35:
                    display_url = display_url[:32] + "..."
                print(f"当前服务器: {display_url}")
                print("配置状态: ✅ 已配置")
            else:
                print("配置状态: ❌ 未配置")
            
            menu_options = {
                "1": "🚀 开始扫描（三种模式可选）",
                "2": "⚙️  重新配置服务器",
                "3": "📊 查看扫描报告", 
                "4": "🗑️  清理旧报告",
                "5": "🔧 系统信息",
                "6": "📖 使用指南",
                "0": "🚪 退出程序"
            }
            
            self.print_menu("主菜单", menu_options)
            
            choice = input("请输入选项 [0-6]: ").strip()
            
            if choice == "1":
                if not self.server_url or not self.api_key:
                    print("❌ 请先配置服务器信息")
                    input("按回车键继续...")
                    continue
                self.run_scanner()
            elif choice == "2":
                if self.setup_wizard():
                    self.load_config()
            elif choice == "3":
                self.show_reports()
            elif choice == "4":
                self.cleanup_old_reports()
            elif choice == "5":
                self.show_system_info()
            elif choice == "6":
                self.show_help()
            elif choice == "0":
                print("\n👋 感谢使用！")
                print(f"项目地址: {self.github_url}")
                break
            else:
                print("❌ 无效选择，请重新输入")
                input("按回车键继续...")

def main():
    """主函数"""
    try:
        # 尝试导入humanize库
        import humanize
    except ImportError:
        print("❌ 缺少依赖库，正在自动安装...")
        # 临时安装humanize
        subprocess.run([sys.executable, "-m", "pip", "install", "humanize"], check=True)
        print("✅ 依赖安装完成，请重新运行程序")
        return
    
    setup = EmbyScannerSetup()
    
    # 尝试加载现有配置
    setup.load_config()
    
    # 如果未配置，运行设置向导
    if not setup.server_url or not setup.api_key:
        if not setup.setup_wizard():
            return
    
    # 显示主菜单
    setup.main_menu()

if __name__ == "__main__":
    main()

