#!/usr/bin/env python3
"""
Emby媒体库重复检测工具 v3.7 Size-Only Edition
GitHub: https://github.com/huanhq99/emby-scanner
核心功能: 
1. 逻辑：纯体积(Size)去重，忽略 TMDB ID，专治"同大异名"
2. UI：回归 v3.0 经典简洁方框 Banner
3. 架构：Zero-Dependency (原生 urllib) + 路径防呆修复
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
import urllib.parse
from collections import defaultdict
from datetime import datetime

# ==================== 颜色工具类 ====================
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

# ==================== 主程序类 ====================
class EmbyScannerPro:
    
    def __init__(self):
        self.version = "3.7 Size-Only"
        self.github_url = "https://github.com/huanhq99/emby-scanner"
        self.server_url = ""
        self.api_key = ""
        self.headers = {}

        # --- 核心路径修复逻辑 ---
        # 强制依赖 $HOME 环境变量，这是远程环境中唯一可靠的起点
        home_dir = os.environ.get('HOME')
        self.script_dir = home_dir if home_dir else os.path.expanduser('~')
        self.data_dir = os.path.join(self.script_dir, "emby_scanner_data")

    # --- 系统工具 ---
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_banner(self):
        """
        回归 v3.0 经典简洁方框 Banner
        """
        banner = f"""
{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗
║             Emby媒体库重复检测工具 {Colors.YELLOW}v{self.version}{Colors.CYAN}              
║             {Colors.RESET}Zero-Dependency | Size-Only Mode | Color UI{Colors.CYAN}             
╚════════════════════════════════════════════════════════════════╝{Colors.RESET}
        """
        print(banner)

    # --- 输入处理 (依赖 Shell TTY) ---
    def get_user_input(self, prompt, default=""):
        full_prompt = f"{Colors.BOLD}{prompt}{Colors.RESET} [{default}]: " if default else f"{Colors.BOLD}{prompt}{Colors.RESET}: "
        try:
            sys.stdout.write(full_prompt)
            sys.stdout.flush()
            user_input = sys.stdin.readline().strip()
            return user_input if user_input else default
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)

    def pause(self):
        self.get_user_input(f"\n按 {Colors.GREEN}回车键{Colors.RESET} 继续...")

    # --- 网络请求 (Zero Dependency) ---
    def _request(self, endpoint, params=None):
        """使用原生urllib发送请求，无需requests库"""
        url = f"{self.server_url}{endpoint}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url += f"?{query_string}"
        
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as e:
            print(f"{Colors.RED}❌ 请求失败: {e}{Colors.RESET}")
            return None
        except Exception as e:
            print(f"{Colors.RED}❌ 未知错误: {e}{Colors.RESET}")
            return None

    # --- 配置管理 ---
    def init_config(self):
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir, exist_ok=True)
            except:
                pass
        
        config_file = os.path.join(self.data_dir, 'emby_config.json')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.server_url = config.get('server_url', '').rstrip('/')
                    self.api_key = config.get('api_key', '')
                    self.headers = {
                        'X-Emby-Token': self.api_key,
                        'Content-Type': 'application/json',
                        'User-Agent': 'EmbyScannerPro/3.7'
                    }
                    return True
            except:
                pass
        return False

    def save_config(self):
        config = {
            'server_url': self.server_url,
            'api_key': self.api_key,
            'updated': datetime.now().isoformat()
        }
        try:
            with open(os.path.join(self.data_dir, 'emby_config.json'), 'w') as f:
                json.dump(config, f)
            print(f"{Colors.GREEN}✅ 配置已保存至: {self.data_dir}/emby_config.json{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}⚠️ 配置保存失败: {e}{Colors.RESET}")

    def setup_wizard(self):
        self.clear_screen()
        self.print_banner()
        print(f"{Colors.YELLOW}首次设置向导{Colors.RESET}\n")
        
        while True:
            url = self.get_user_input("请输入 Emby 服务器地址 (例如 http://localhost:8096)").strip().rstrip('/')
            if not url.startswith(('http://', 'https://')):
                print(f"{Colors.RED}❌ 地址必须以 http:// 或 https:// 开头{Colors.RESET}")
                continue
            self.server_url = url
            break

        self.api_key = self.get_user_input("请输入 API 密钥").strip()
        self.headers = {'X-Emby-Token': self.api_key}

        print("\n🔗 测试连接...")
        info = self._request("/emby/System/Info")
        if info:
            print(f"{Colors.GREEN}✅ 连接成功: {info.get('ServerName')} (v{info.get('Version')}){Colors.RESET}")
            self.save_config()
            self.pause()
            return True
        else:
            print(f"{Colors.RED}❌ 连接失败，请检查地址或密钥。{Colors.RESET}")
            self.pause()
            return False

    # --- 扫描核心逻辑 (v3.7 纯体积去重) ---
    def format_size(self, size_bytes):
        if not size_bytes: return "N/A"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024: return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def get_video_info(self, item):
        """提取增强的视频信息"""
        media_sources = item.get('MediaSources', [])
        if not media_sources: return "未知格式"
        
        info = []
        stream = media_sources[0]
        
        # 容器格式
        container = stream.get('Container', '').upper()
        if container: info.append(container)
        
        # 视频流信息
        video_streams = [s for s in stream.get('MediaStreams', []) if s.get('Type') == 'Video']
        if video_streams:
            v = video_streams[0]
            # 分辨率
            width = v.get('Width')
            if width:
                if width >= 3800: res = "4K"
                elif width >= 1900: res = "1080P"
                elif width >= 1200: res = "720P"
                else: res = "SD"
                info.append(f"{Colors.CYAN}{res}{Colors.RESET}")
            # 编码
            codec = v.get('Codec', '').upper()
            if codec: info.append(codec)
            
        return " | ".join(info)

    def run_scanner(self):
        self.clear_screen()
        self.print_banner()
        print(f"{Colors.YELLOW}🚀 正在获取媒体库...{Colors.RESET}")
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: return

        # 筛选库
        target_libs = [l for l in libs.get('Items', []) if l.get('CollectionType') in ['movies', 'tvshows']]
        print(f"✅ 发现 {len(target_libs)} 个影视库，开始【纯体积】深度查重...\n")

        report = [
            "🎬 Emby 媒体库重复检测报告 (v3.7 Size-Only)",
            "=" * 60,
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"检测逻辑: 仅基于文件体积 (Size) 匹配，忽略文件名和 TMDB ID",
            ""
        ]

        total_dups_groups = 0
        total_dups_files = 0

        for lib in target_libs:
            lib_name = lib.get('Name')
            lib_type = "Series" if lib.get('CollectionType') == 'tvshows' else "Movie"
            print(f"📂 正在扫描: {Colors.BOLD}{lib_name}{Colors.RESET} ({lib_type})...")

            # 获取所有项目
            params = {
                'ParentId': lib['Id'],
                'Recursive': 'true',
                'IncludeItemTypes': lib_type,
                'Fields': 'Path,ProviderIds,MediaSources,Size,ProductionYear', 
                'Limit': 20000 
            }
            
            data = self._request("/emby/Items", params)
            if not data: continue
            items = data.get('Items', [])

            # --- 分组逻辑：纯体积 (Size) ---
            size_groups = defaultdict(list)

            for item in items:
                # 核心修改：忽略 TMDB ID，只看 Size
                item_size = item.get('Size')
                
                # 忽略无体积信息的项目或文件夹
                if not item_size or item_size == 0:
                    continue
                
                # 构造对象
                obj = {
                    'name': item.get('Name'),
                    'path': item.get('Path'),
                    'size': item_size,
                    'info': self.get_video_info(item),
                    'year': item.get('ProductionYear')
                }
                
                # 以体积为 Key 进行分组
                size_groups[item_size].append(obj)

            # --- 筛选重复 (数量 > 1) ---
            duplicate_groups = {k: v for k, v in size_groups.items() if len(v) > 1}
            
            if duplicate_groups:
                report.append(f"📁 媒体库: {lib_name}")
                report.append(f"🔴 发现 {len(duplicate_groups)} 组体积完全一致的文件:")
                
                for size, group in duplicate_groups.items():
                    # 再次确认路径不同，防止同一个文件被扫多次
                    paths = set(g['path'] for g in group)
                    if len(paths) > 1:
                        total_dups_groups += 1
                        total_dups_files += (len(group) - 1)
                        
                        size_str = self.format_size(size)
                        report.append(f"  📦 体积: {size_str} (共 {len(group)} 个文件)")
                        
                        # 在控制台打印进度
                        print(f"   ❌ 发现重复: {size_str} -> {group[0]['name']} 等 {len(group)} 个")

                        for g in group:
                            report.append(f"    - {g['name']} ({g['year']}) [{g['info']}]")
                            report.append(f"      路径: {g['path']}")
                        report.append("")
                report.append("-" * 40)
            else:
                print(f"   ✅ 该库未发现体积重复。")

        # --- 结尾 ---
        report.append("=" * 60)
        if total_dups_groups == 0:
            report.append("🎉 完美！未发现任何体积重复的文件。")
            print(f"\n{Colors.GREEN}🎉 未发现体积重复文件！{Colors.RESET}")
        else:
            summary = f"共发现 {total_dups_groups} 组重复，涉及 {total_dups_files} 个冗余文件。"
            report.append(summary)
            print(f"\n{Colors.RED}🚨 {summary}{Colors.RESET}")

        # 保存报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.data_dir, f"report_{timestamp}.txt")
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report))
            print(f"📄 报告已生成: {Colors.BOLD}{report_path}{Colors.RESET}")
        except Exception as e:
            print(f"❌ 报告保存失败: {e}")
        
        self.pause()

    # --- 菜单系统 ---
    def main_menu(self):
        while True:
            self.clear_screen()
            self.print_banner()
            
            status = f"{Colors.GREEN}已连接{Colors.RESET}" if self.server_url else f"{Colors.RED}未配置{Colors.RESET}"
            print(f"状态: {status} | 存储: {self.data_dir}\n")
            
            print(f"{Colors.BOLD}1.{Colors.RESET} 🚀 开始扫描 (Size Only)")
            print(f"{Colors.BOLD}2.{Colors.RESET} ⚙️  配置服务器")
            print(f"{Colors.BOLD}3.{Colors.RESET} 📊 查看历史报告")
            print(f"{Colors.BOLD}4.{Colors.RESET} 🗑️  重置/删除配置")
            print(f"{Colors.BOLD}0.{Colors.RESET} 🚪 退出")
            
            choice = self.get_user_input("\n请选择").strip()
            
            if choice == '1':
                if not self.server_url:
                    print(f"{Colors.RED}请先配置服务器！{Colors.RESET}")
                    self.pause()
                else:
                    self.run_scanner()
            elif choice == '2':
                if self.setup_wizard():
                    self.init_config()
            elif choice == '3':
                self.view_reports()
            elif choice == '4':
                self.reset_config()
            elif choice == '0':
                sys.exit(0)

    def view_reports(self):
        self.clear_screen()
        if not os.path.exists(self.data_dir):
            print("暂无报告。")
            self.pause()
            return

        files = [f for f in os.listdir(self.data_dir) if f.endswith('.txt')]
        files.sort(reverse=True)
        
        if not files:
            print("暂无报告。")
            self.pause()
            return

        print(f"{Colors.YELLOW}📜 历史报告列表:{Colors.RESET}")
        for i, f in enumerate(files[:10]):
            print(f"{i+1}. {f}")
        
        choice = self.get_user_input("\n输入序号查看 (0返回)").strip()
        if choice.isdigit() and 0 < int(choice) <= len(files):
            file_path = os.path.join(self.data_dir, files[int(choice)-1])
            os.system(f"cat '{file_path}'" if os.name != 'nt' else f"type '{file_path}'")
            self.pause()

    def reset_config(self):
        confirm = self.get_user_input(f"确定要删除所有配置和报告吗? (y/n)").lower()
        if confirm == 'y':
            import shutil
            try:
                shutil.rmtree(self.data_dir)
                self.server_url = ""
                self.api_key = ""
                print(f"{Colors.GREEN}已重置。{Colors.RESET}")
            except Exception as e:
                print(f"重置失败: {e}")
            self.pause()

# ==================== 入口 ====================
if __name__ == "__main__":
    try:
        app = EmbyScannerPro()
        app.init_config()
        # 如果未配置，自动进入向导
        if not app.server_url:
            app.setup_wizard()
        app.main_menu()
    except KeyboardInterrupt:
        print("\n退出。")
        sys.exit(0)
