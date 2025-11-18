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
from collections import defaultdict
from datetime import datetime

class EmbyScannerSetup:
    """环境设置和交互界面"""
    
    def __init__(self):
        self.server_url = ""
        self.api_key = ""
        self.venv_path = os.path.expanduser("~/emby-scanner-env")
        
        # 尝试获取脚本所在目录，如果通过管道运行(__file__未定义)，则使用当前工作目录
        try:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            # 如果是管道运行，配置和报告将保存在当前执行命令的目录下
            self.script_dir = os.getcwd() 
            
        self.version = "2.5" # 版本号更新，简化输入逻辑
        self.github_url = "https://github.com/huanhq99/emby-scanner"
        
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_banner(self):
        """打印横幅"""
        banner = f"""
╔════════════════════════════════════════════════════════════════╗
║                Emby媒体库重复检测工具 v{self.version}              
║                GitHub: {self.github_url}               
╚════════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    def print_menu(self, title, options):
        """打印菜单"""
        print(f"\n{title}")
        print("=" * 50)
        for key, value in options.items():
            print(f"  {key}. {value}")
        print("-" * 50)
    
    def get_user_input(self, prompt, default=""):
        """获取用户输入 (简化版，依赖 Shell 传入 TTY)"""
        full_prompt = f"{prompt} [{default}]: " if default else f"{prompt}: "
        try:
            user_input = input(full_prompt).strip()
            return user_input if user_input else default
        except EOFError:
            print("\n❌ 错误: 交互式输入流已关闭 (EOFError)。请使用完整命令确保输入来自终端。", file=sys.stderr)
            sys.exit(1)
        except Exception:
            raise

    def _prompt_continue(self, prompt="按回车键继续..."):
        """简单的按键继续提示"""
        self.get_user_input(f"\n{prompt}")
    
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
        
        try:
            result = subprocess.run([
                pip_path, "install", "requests"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 依赖安装成功")
                return True
            else:
                print(f"❌ 依赖安装失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 依赖安装失败: {e}")
            return False
    
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
                # 使用 input 获取确认
                confirm = self.get_user_input("⚠️  API密钥似乎过短，是否继续？(y/n)").lower()
                if confirm != 'y':
                    continue
            
            break
        
        print("\n🔗 测试服务器连接...")
        if self.test_connection():
            print("✅ 连接成功！配置验证通过")
            return True
        else:
            print("❌ 连接测试失败")
            # 使用 input 获取重试选项
            retry = self.get_user_input("\n是否重新配置？(y/n)").lower()
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

    def format_size(self, size_bytes):
        """格式化文件大小 (从字节到 KB, MB, GB 等)"""
        if size_bytes is None:
            return "N/A"
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = 0
        size_float = float(size_bytes)
        while size_float >= 1024 and i < len(size_name) - 1:
            size_float /= 1024
            i += 1
        return f"{size_float:.2f} {size_name[i]}"

    # ========================= 真正的重复检测功能 =========================
    
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
            # 如果请求失败，再次检查连接，但这里只返回空列表
            return []
    
    def get_library_items(self, library_id, item_types='Movie,Series'):
        """获取媒体库中的项目，包含文件路径和大小"""
        url = f"{self.server_url}/emby/Items"
        params = {
            'ParentId': library_id,
            'Recursive': True,
            'IncludeItemTypes': item_types,
            # 增加 Size 字段以获取文件体积
            'Fields': 'Path,ProviderIds,Name,Type,Size',
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
        
        # 从路径中提取TMDB ID (备用)
        if not tmdb_id:
            path = item.get('Path', '')
            match = re.search(r'{tmdb-(\d+)}', path)
            if match:
                tmdb_id = match.group(1)
        
        return str(tmdb_id) if tmdb_id else None
    
    def analyze_duplicates(self, items):
        """分析重复项目 (基于TMDB ID 和 文件体积)"""
        # 按TMDB ID分组 (Primary check)
        tmdb_groups = defaultdict(list)
        # 按文件体积分组 (Secondary check)
        size_groups = defaultdict(list)
        
        for item in items:
            item_name = item.get('Name', '未知').strip()
            path = item.get('Path', '无路径')
            item_size = item.get('Size') # Size is in bytes
            tmdb_id = self.extract_tmdb_id(item)
            
            item_info = {
                'id': item['Id'],
                'name': item_name,
                'type': item.get('Type', '未知'),
                'path': path,
                'tmdb_id': tmdb_id,
                'size': item_size,
                'size_formatted': self.format_size(item_size)
            }
            
            # 1. TMDB ID分组
            if tmdb_id:
                tmdb_groups[tmdb_id].append(item_info)
            
            # 2. 文件体积分组 (排除没有体积信息的项目)
            if item_size is not None and item_size > 0:
                # 使用 size 作为 key，确保精确匹配
                size_groups[item_size].append(item_info)
        
        # 3. 检测 TMDB ID 重复 (Primary)
        tmdb_duplicates = []
        for tmdb_id, items_list in tmdb_groups.items():
            if len(items_list) > 1:
                tmdb_duplicates.append({
                    'key': f"TMDB-ID: {tmdb_id}",
                    'items': items_list
                })

        # 4. 检测 文件体积 重复 (Secondary)
        # 只考虑没有 TMDB ID 的项目，避免和 TMDB 重复检测冲突
        size_duplicates = []
        for size, items_list in size_groups.items():
            # 过滤出没有 TMDB ID 的项目
            non_tmdb_items = [item for item in items_list if not item.get('tmdb_id')]
            
            if len(non_tmdb_items) > 1:
                # 再次过滤，确保路径是不同的 (防止同一个文件的多重软链接/条目被误判)
                unique_paths = set(item['path'] for item in non_tmdb_items)
                
                if len(unique_paths) > 1:
                    size_duplicates.append({
                        'key': f"文件体积: {self.format_size(size)}",
                        'size_bytes': size,
                        'items': non_tmdb_items
                    })
        
        return tmdb_duplicates, size_duplicates
    
    def run_real_scanner(self):
        """运行真正的重复检测扫描器"""
        print("\n🚀 开始深度扫描媒体库...")
        print("正在分析重复内容，请耐心等待...")
        
        # 增加反馈：确认开始获取媒体库
        print("-> 正在通过 Emby API 获取媒体库列表...")
        libraries = self.get_libraries()
        
        if not libraries:
            print("❌ 未找到任何媒体库或连接失败。请检查API密钥和服务器地址。")
            return None
        
        # 增加反馈：获取媒体库成功
        print(f"✅ 成功获取 {len(libraries)} 个媒体库。开始项目扫描...")

        total_stats = defaultdict(int)
        all_tmdb_duplicates = []
        all_size_duplicates = [] # 更改为体积重复
        report_lines = []
        
        # 报告头部
        report_lines.append("🎬 Emby媒体库重复检测报告")
        report_lines.append("=" * 70)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"服务器: {self.server_url}")
        report_lines.append("检测规则: TMDB ID重复 > 文件体积重复") # 更新检测规则描述
        report_lines.append("")
        
        # 扫描电影库
        movie_libraries = [lib for lib in libraries if any(keyword in lib['Name'].lower() 
                          for keyword in ['电影', 'movie', 'movies'])]
        
        # 扫描电视剧库
        series_libraries = [lib for lib in libraries if any(keyword in lib['Name'].lower() 
                            for keyword in ['剧集', 'tv', 'series', '电视剧'])]
        
        # 扫描电影
        if movie_libraries:
            report_lines.append("🎥 电影库扫描结果")
            report_lines.append("-" * 50)
            
            for library in movie_libraries:
                lib_name = library['Name']
                print(f"📁 扫描电影库: {lib_name}")
                
                items = self.get_library_items(library['Id'], 'Movie')
                print(f"   找到 {len(items)} 部电影")
                
                if not items:
                    continue
                
                # 统计
                for item in items:
                    total_stats['Movie'] += 1
                
                # 检测重复
                tmdb_duplicates, size_duplicates = self.analyze_duplicates(items)
                
                # 添加到报告
                report_lines.append(f"媒体库: {lib_name}")
                report_lines.append(f"电影数量: {len(items)}")
                
                if tmdb_duplicates:
                    report_lines.append(f"🔴 TMDB ID重复: {len(tmdb_duplicates)} 组")
                    for dup in tmdb_duplicates:
                        report_lines.append(f"  {dup['key']} (重复{len(dup['items'])}次)")
                        for item in dup['items']:
                            # 显示文件体积
                            report_lines.append(f"    - {item['name']} (体积: {item['size_formatted']})")
                            report_lines.append(f"      路径: {item['path']}")
                        report_lines.append("")
                    all_tmdb_duplicates.extend(tmdb_duplicates)
                
                if size_duplicates:
                    report_lines.append(f"🟡 文件体积重复: {len(size_duplicates)} 组") # 更新描述
                    for dup in size_duplicates:
                        # dup['key'] 中包含格式化的文件体积
                        report_lines.append(f"  {dup['key']} (重复{len(dup['items'])}次)")
                        for item in dup['items']:
                            # 显示文件体积
                            report_lines.append(f"    - {item['name']} (体积: {item['size_formatted']})")
                            report_lines.append(f"      路径: {item['path']}")
                        report_lines.append("")
                    all_size_duplicates.extend(size_duplicates) # 更新列表
                
                if not tmdb_duplicates and not size_duplicates:
                    report_lines.append("✅ 未发现重复电影")
                
                report_lines.append("")
        
        # 扫描电视剧
        if series_libraries:
            report_lines.append("📺 电视剧库扫描结果")
            report_lines.append("-" * 50)
            
            for library in series_libraries:
                lib_name = library['Name']
                print(f"📁 扫描电视剧库: {lib_name}")
                
                items = self.get_library_items(library['Id'], 'Series')
                print(f"   找到 {len(items)} 部电视剧")
                
                if not items:
                    continue
                
                # 统计
                for item in items:
                    total_stats['Series'] += 1
                
                # 检测重复
                tmdb_duplicates, size_duplicates = self.analyze_duplicates(items) # 更新变量名
                
                # 添加到报告
                report_lines.append(f"媒体库: {lib_name}")
                report_lines.append(f"电视剧数量: {len(items)}")
                
                if tmdb_duplicates:
                    report_lines.append(f"🔴 TMDB ID重复: {len(tmdb_duplicates)} 组")
                    for dup in tmdb_duplicates:
                        report_lines.append(f"  {dup['key']} (重复{len(dup['items'])}次)")
                        for item in dup['items']:
                            # 显示文件体积
                            report_lines.append(f"    - {item['name']} (体积: {item['size_formatted']})")
                            report_lines.append(f"      路径: {item['path']}")
                        report_lines.append("")
                    all_tmdb_duplicates.extend(tmdb_duplicates)
                
                if size_duplicates:
                    report_lines.append(f"🟡 文件体积重复: {len(size_duplicates)} 组") # 更新描述
                    for dup in size_duplicates:
                        # dup['key'] 中包含格式化的文件体积
                        report_lines.append(f"  {dup['key']} (重复{len(dup['items'])}次)")
                        for item in dup['items']:
                            # 显示文件体积
                            report_lines.append(f"    - {item['name']} (体积: {item['size_formatted']})")
                            report_lines.append(f"      路径: {item['path']}")
                        report_lines.append("")
                    all_size_duplicates.extend(size_duplicates) # 更新列表
                
                if not tmdb_duplicates and not size_duplicates:
                    report_lines.append("✅ 未发现重复电视剧")
                
                report_lines.append("")
        
        # 总结报告
        report_lines.append("=" * 70)
        report_lines.append("📊 扫描统计总结")
        report_lines.append("=" * 70)
        
        total_items = sum(total_stats.values())
        report_lines.append(f"总计扫描: {total_items} 个项目")
        for item_type, count in total_stats.items():
            report_lines.append(f"  {item_type}: {count} 个")
        
        report_lines.append("")
        report_lines.append("🚨 重复检测结果:")
        report_lines.append(f"   🔴 TMDB ID重复: {len(all_tmdb_duplicates)} 组")
        report_lines.append(f"    🟡 文件体积重复: {len(all_size_duplicates)} 组") # 更新描述
        
        if all_tmdb_duplicates or all_size_duplicates:
            report_lines.append("")
            report_lines.append("💡 处理建议:")
            report_lines.append("  1. TMDB ID重复: 同一内容的不同版本，建议保留最佳版本")
            report_lines.append("  2. 文件体积重复: 没有TMDB ID但体积完全相同，极有可能是重复文件，建议手动检查文件路径") # 更新建议
        else:
            report_lines.append("🎉 恭喜！未发现任何重复内容")
        
        report_lines.append("")
        report_lines.append("📁 报告文件位置说明:")
        report_lines.append(f"  文件保存在: {self.script_dir}")
        report_lines.append("  查看方法:")
        report_lines.append("  1. 主菜单 → 查看扫描报告")
        report_lines.append("  2. 使用命令: cat 报告文件名.txt")
        report_lines.append("  3. 使用命令: nano 报告文件名.txt")
        
        # 生成报告文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"emby_library_report_{timestamp}.txt"
        report_path = os.path.join(self.script_dir, report_file)
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n这一步很关键，我把脚本的复杂输入逻辑去掉了。
                现在需要你在命令行中执行一个更精确的命令，才能确保Python执行的是脚本内容，而不是进入交互模式。

### 正确的单行运行命令

请使用以下命令，它通过 `/dev/stdin` **告诉 Python 脚本内容在哪里**，并用 `< /dev/tty` **将终端输入重定向给脚本**：

```bash
curl -sL [https://raw.githubusercontent.com/huanhq99/emby-scanner/main/emby_scanner.py](https://raw.githubusercontent.com/huanhq99/emby-scanner/main/emby_scanner.py) | python3 -u /dev/stdin < /dev/tty
