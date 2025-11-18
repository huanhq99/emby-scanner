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
from collections import defaultdict
from datetime import datetime

class EmbyScannerSetup:
    """环境设置和交互界面"""
    
    def __init__(self):
        self.server_url = ""
        self.api_key = ""
        self.venv_path = os.path.expanduser("~/emby-scanner-env")
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.version = "2.0"
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
        """获取用户输入"""
        if default:
            user_input = input(f"{prompt} [{default}]: ").strip()
            return user_input if user_input else default
        else:
            return input(f"{prompt}: ").strip()

    def format_file_size(self, size_bytes):
        """格式化文件大小"""
        if not size_bytes:
            return "未知大小"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
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

    # ========================= 真正的扫描功能 =========================
    
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
        """获取媒体库中的项目"""
        url = f"{self.server_url}/emby/Items"
        params = {
            'ParentId': library_id,
            'Recursive': True,
            'IncludeItemTypes': item_types,
            'Fields': 'Path,ProviderIds',
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
            import re
            match = re.search(r'{tmdb-(\d+)}', path)
            if match:
                tmdb_id = match.group(1)
        
        return str(tmdb_id) if tmdb_id else None
    
    def analyze_duplicates(self, items):
        """分析重复项目"""
        tmdb_groups = defaultdict(list)
        
        for item in items:
            item_id = item['Id']
            item_name = item.get('Name', '未知')
            item_type = item.get('Type', '未知')
            path = item.get('Path', '无路径')
            
            tmdb_id = self.extract_tmdb_id(item)
            
            if tmdb_id:
                item_info = {
                    'id': item_id,
                    'name': item_name,
                    'type': item_type,
                    'path': path,
                    'tmdb_id': tmdb_id
                }
                tmdb_groups[tmdb_id].append(item_info)
        
        duplicates = []
        for tmdb_id, items_list in tmdb_groups.items():
            if len(items_list) > 1:
                duplicates.append({
                    'tmdb_id': tmdb_id,
                    'items': items_list
                })
        
        return duplicates
    
    def run_real_scanner(self):
        """运行真正的扫描器"""
        print("\n🚀 开始扫描媒体库...")
        print("正在连接服务器，请等待...")
        
        libraries = self.get_libraries()
        if not libraries:
            print("❌ 未找到任何媒体库")
            return None
        
        total_stats = defaultdict(int)
        all_duplicates = []
        report_lines = []
        
        # 报告头部
        report_lines.append("Emby媒体库重复检测报告")
        report_lines.append("=" * 60)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"服务器: {self.server_url}")
        report_lines.append("")
        
        for library in libraries:
            lib_name = library['Name']
            print(f"📁 扫描媒体库: {lib_name}")
            
            # 根据库类型设置扫描项目类型
            if lib_name.lower() in ['电影', 'movies', 'movie']:
                item_types = 'Movie'
            elif lib_name.lower() in ['剧集', 'tv', 'series', '电视剧']:
                item_types = 'Series'
            else:
                item_types = 'Movie,Series'
            
            items = self.get_library_items(library['Id'], item_types)
            print(f"   找到 {len(items)} 个项目")
            
            if not items:
                continue
            
            # 统计
            lib_stats = defaultdict(int)
            for item in items:
                item_type = item['Type']
                lib_stats[item_type] += 1
                total_stats[item_type] += 1
            
            # 检测重复
            duplicates = self.analyze_duplicates(items)
            
            # 添加到报告
            report_lines.append(f"媒体库: {lib_name}")
            report_lines.append(f"项目数量: {len(items)}")
            for item_type, count in lib_stats.items():
                report_lines.append(f"  {item_type}: {count}")
            
            if duplicates:
                report_lines.append(f"🔴 发现 {len(duplicates)} 组重复项目:")
                for dup in duplicates:
                    report_lines.append(f"  TMDB-ID: {dup['tmdb_id']} (重复{len(dup['items'])}次)")
                    for item in dup['items']:
                        report_lines.append(f"    - {item['name']} ({item['type']})")
                    report_lines.append("")
                all_duplicates.extend(duplicates)
            else:
                report_lines.append("✅ 未发现重复项目")
            
            report_lines.append("")
        
        # 总结
        report_lines.append("=" * 60)
        report_lines.append("📊 统计总结")
        report_lines.append("=" * 60)
        
        for item_type, count in total_stats.items():
            report_lines.append(f"{item_type}: {count}")
        
        total_items = sum(total_stats.values())
        report_lines.append(f"总计: {total_items} 个项目")
        
        if all_duplicates:
            report_lines.append(f"🚨 总共发现 {len(all_duplicates)} 组重复项目")
        else:
            report_lines.append("🎉 恭喜！未发现任何重复项目")
        
        # 生成报告文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"emby_library_report_{timestamp}.txt"
        report_path = os.path.join(self.script_dir, report_file)
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            
            return report_path
        except Exception as e:
            print(f"❌ 生成报告失败: {e}")
            return None

    # ========================= 主程序功能 =========================
    
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
        print("您现在可以使用所有功能了。")
        input("\n按回车键进入主菜单...")
        return True
    
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
                print("配置状态:  ❌ 未配置")
            
            menu_options = {
                "1": "🚀 开始扫描媒体库（真实扫描）",
                "2": "⚙️  重新配置服务器",
                "3": "📊 查看扫描报告", 
                "4": "🔧 系统信息",
                "5": "📖 使用指南",
                "0": "🚪 退出程序"
            }
            
            self.print_menu("主菜单", menu_options)
            
            choice = input("请输入选项 [0-5]: ").strip()
            
            if choice == "1":
                if not self.server_url or not self.api_key:
                    print("❌ 请先配置服务器信息")
                    input("按回车键继续...")
                    continue
                self.run_scanner()
            elif choice == "2":
                if self.setup_wizard
