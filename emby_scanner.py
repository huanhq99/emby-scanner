#!/usr/bin/env python3
"""
Emby媒体库重复检测工具 v5.1 User-Session Edition
GitHub: https://github.com/huanhq99/emby-scanner
核心升级: 
1. 新增【用户登录深度删除】模式：模拟真实用户登录获取 Session，触发 Emby 完整删除逻辑(联动删除源文件)。
2. 逻辑：纯体积(Size)去重 + 智能保留(文件名最长)。
3. 架构：Zero-Dependency / Clean UI
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse
import getpass
from collections import defaultdict
from datetime import datetime

# ==================== 颜色工具类 ====================
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

# ==================== 主程序类 ====================
class EmbyScannerPro:
    
    def __init__(self):
        self.version = "5.1 User-Session"
        self.github_url = "https://github.com/huanhq99/emby-scanner"
        self.server_url = ""
        self.api_key = ""
        self.headers = {}

        # 用户登录相关
        self.user_id = ""
        self.access_token = ""

        # 存储扫描结果
        self.last_scan_results = {} 

        # --- 核心路径修复逻辑 ---
        home_dir = os.environ.get('HOME')
        self.script_dir = home_dir if home_dir else os.path.expanduser('~')
        self.data_dir = os.path.join(self.script_dir, "emby_scanner_data")

    # --- 系统工具 ---
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_banner(self):
        banner = f"""
{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗
║             Emby媒体库重复检测工具 {Colors.YELLOW}v{self.version}{Colors.CYAN}              
║             {Colors.RESET}Deep Delete (User Login) | Size-Only Mode{Colors.CYAN}          
╚════════════════════════════════════════════════════════════════╝{Colors.RESET}
        """
        print(banner)

    # --- 输入处理 ---
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

    # --- 网络请求 ---
    def _request(self, endpoint, params=None, method='GET', auth_header=None, post_data=None):
        url = f"{self.server_url}{endpoint}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url += f"?{query_string}"
        
        # 默认使用 API Key，如果传入 auth_header 则覆盖（用于用户登录模式）
        headers = auth_header if auth_header else self.headers
        
        req = urllib.request.Request(url, headers=headers, method=method)
        
        if post_data:
            json_data = json.dumps(post_data).encode('utf-8')
            req.data = json_data
            req.add_header('Content-Type', 'application/json')

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=300) as response:
                    if response.status == 204: # No Content (常见于删除成功)
                        return {}
                    return json.loads(response.read().decode('utf-8'))
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    err_msg = str(e)
                    if "timed out" in err_msg:
                        err_msg = "连接超时"
                    # 不打印404错误，因为可能是已经删除了
                    if hasattr(e, 'code') and e.code != 404:
                         print(f"{Colors.RED}❌ 请求失败: {err_msg}{Colors.RESET}")
                    return None
            except Exception as e:
                print(f"{Colors.RED}❌ 未知错误: {e}{Colors.RESET}")
                return None

    # --- 用户登录模块 (v5.1 新增) ---
    def login_user(self):
        print(f"\n{Colors.YELLOW}🔐 请登录 Emby 管理员账号 (用于深度删除){Colors.RESET}")
        username = self.get_user_input("用户名")
        try:
            # 尝试使用 getpass，如果在管道中失败则回退
            if sys.stdin.isatty():
                password = getpass.getpass(f"{Colors.BOLD}密码{Colors.RESET}: ")
            else:
                password = self.get_user_input("密码")
        except:
            password = self.get_user_input("密码")

        print(f"🔄 正在验证身份...")
        
        # 构造登录请求
        auth_data = {
            "Username": username,
            "Pw": password
        }
        
        # 临时 Header 用于登录
        login_headers = {
            'Content-Type': 'application/json',
            'X-Emby-Authorization': 'MediaBrowser Client="EmbyScanner", Device="Terminal", DeviceId="PythonScript", Version="5.1"'
        }
        
        try:
            url = f"{self.server_url}/Users/AuthenticateByName"
            req = urllib.request.Request(url, headers=login_headers, method='POST')
            json_data = json.dumps(auth_data).encode('utf-8')
            req.data = json_data
            
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                self.access_token = result['AccessToken']
                self.user_id = result['User']['Id']
                print(f"{Colors.GREEN}✅ 登录成功! 用户: {result['User']['Name']} (ID: {self.user_id}){Colors.RESET}")
                return True
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(f"{Colors.RED}❌ 登录失败: 用户名或密码错误{Colors.RESET}")
            else:
                print(f"{Colors.RED}❌ 登录错误: {e}{Colors.RESET}")
            return False
        except Exception as e:
            print(f"{Colors.RED}❌ 连接错误: {e}{Colors.RESET}")
            return False

    # --- 配置管理 ---
    def init_config(self):
        if not os.path.exists(self.data_dir):
            try: os.makedirs(self.data_dir, exist_ok=True)
            except: pass
        
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
                        'User-Agent': 'EmbyScannerPro/5.1'
                    }
                    return True
            except: pass
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

    # --- 扫描核心逻辑 ---
    def format_size(self, size_bytes):
        if not size_bytes: return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024: return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def get_video_info(self, item):
        media_sources = item.get('MediaSources', [])
        if not media_sources: return "未知格式"
        info = []
        stream = media_sources[0]
        container = stream.get('Container', '').upper()
        if container: info.append(container)
        video_streams = [s for s in stream.get('MediaStreams', []) if s.get('Type') == 'Video']
        if video_streams:
            v = video_streams[0]
            width = v.get('Width')
            if width:
                if width >= 3800: res = "4K"
                elif width >= 1900: res = "1080P"
                elif width >= 1200: res = "720P"
                else: res = "SD"
                info.append(f"{res}") 
            codec = v.get('Codec', '').upper()
            if codec: info.append(codec)
        return " | ".join(info)

    def run_scanner(self):
        self.clear_screen()
        self.print_banner()
        print(f"{Colors.YELLOW}🚀 正在连接服务器获取媒体库...{Colors.RESET}")
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: return

        target_libs = [l for l in libs.get('Items', []) if l.get('CollectionType') in ['movies', 'tvshows']]
        print(f"✅ 发现 {len(target_libs)} 个影视库，开始后台深度扫描...\n")
        print(f"{Colors.BOLD}{'媒体库名称':<20} | {'总容量':<12} | {'冗余占用 (可释放)':<15} | {'状态'}{Colors.RESET}")
        print("-" * 70)

        report = [
            "🎬 Emby 媒体库重复检测报告 (v5.1 User-Session)",
            "=" * 60,
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"去重策略:",
            f"  - 电影: 纯体积(Size)匹配",
            f"  - 剧集: 严格匹配 [剧集名 + 季 + 集 + 体积]",
            ""
        ]

        self.last_scan_results = {} 
        total_scan_dups_groups = 0
        total_scan_redundant_bytes = 0

        for lib in target_libs:
            lib_name = lib.get('Name')
            collection_type = lib.get('CollectionType')
            
            sys.stdout.write(f"⏳ 正在扫描: {lib_name} (可能需要几分钟)...\r")
            sys.stdout.flush()
            
            if collection_type == 'tvshows':
                fetch_type = 'Episode'
            else:
                fetch_type = 'Movie'
            
            params = {
                'ParentId': lib['Id'],
                'Recursive': 'true',
                'IncludeItemTypes': fetch_type, 
                'Fields': 'Path,MediaSources,Size,ProductionYear,SeriesName,IndexNumber,ParentIndexNumber', 
                'Limit': 100000 
            }
            
            data = self._request("/emby/Items", params)
            if not data: 
                sys.stdout.write("\r" + " " * 80 + "\r") 
                print(f"❌ {lib_name:<18} | error        | error           | 超时/失败")
                continue
                
            items = data.get('Items', [])
            total_lib_bytes = sum(item.get('Size', 0) for item in items)

            # 分组逻辑
            groups = defaultdict(list)
            for item in items:
                item_size = item.get('Size')
                if not item_size or item_size == 0: continue
                
                name = item.get('Name')
                if collection_type == 'tvshows':
                    series_name = item.get('SeriesName', 'Unknown')
                    season = item.get('ParentIndexNumber', -1)
                    episode = item.get('IndexNumber', -1)
                    
                    if season != -1 and episode != -1:
                        name = f"{series_name} S{season:02d}E{episode:02d} - {name}"
                    elif series_name:
                         name = f"{series_name} - {name}"
                    
                    group_key = (series_name, season, episode, item_size)
                else:
                    group_key = item_size

                obj = {
                    'id': item.get('Id'), # 关键：记录ID用于API删除
                    'name': name,
                    'path': item.get('Path'),
                    'size': item_size,
                    'info': self.get_video_info(item),
                    'year': item.get('ProductionYear')
                }
                groups[group_key].append(obj)

            # 筛选重复
            duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
            
            lib_redundant_bytes = 0
            lib_dup_groups_count = 0
            lib_dups_list = [] 

            if duplicate_groups:
                report.append(f"📁 媒体库: {lib_name} | 库占用: {self.format_size(total_lib_bytes)}")
                report.append(f"🔴 发现 {len(duplicate_groups)} 组重复:")
                
                for key, group in duplicate_groups.items():
                    if isinstance(key, tuple): size = key[3] 
                    else: size = key
                    
                    paths = set(g['path'] for g in group)
                    if len(paths) > 1:
                        count = len(group)
                        wasted = (count - 1) * size
                        lib_redundant_bytes += wasted
                        lib_dup_groups_count += 1
                        
                        lib_dups_list.append({
                            "size": size,
                            "files": group
                        })
                        
                        size_str = self.format_size(size)
                        report.append(f"  📦 单文件体积: {size_str} | 冗余: {count-1} 份 (共 {count} 个文件)")
                        
                        for g in group:
                            year_str = f" ({g['year']})" if g['year'] else ""
                            report.append(f"    - {g['name']}{year_str} [{g['info']}]")
                            report.append(f"      路径: {g['path']}")
                        report.append("")
                
                if lib_dup_groups_count > 0:
                     report.append("-" * 40)
                     self.last_scan_results[lib_name] = lib_dups_list
                else:
                     report.pop(); report.pop()

            total_scan_dups_groups += lib_dup_groups_count
            total_scan_redundant_bytes += lib_redundant_bytes

            # UI 输出
            cap_str = self.format_size(total_lib_bytes)
            if lib_redundant_bytes > 0:
                dup_str = f"{Colors.RED}{self.format_size(lib_redundant_bytes)}{Colors.RESET}"
                status = f"{Colors.YELLOW}含重复{Colors.RESET}"
            else:
                dup_str = f"{Colors.GREEN}0 B{Colors.RESET}"
                status = f"{Colors.GREEN}完美{Colors.RESET}"

            sys.stdout.write("\r" + " " * 80 + "\r")
            print(f"{Colors.BOLD}{lib_name:<20}{Colors.RESET} | {cap_str:<12} | {dup_str:<24} | {status:<10}")

        # --- 结尾 ---
        print("-" * 70)
        report.append("=" * 60)
        summary = f"扫描结束。共发现 {total_scan_dups_groups} 组重复，总计浪费空间: {self.format_size(total_scan_redundant_bytes)}"
        report.append(summary)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.data_dir, f"report_{timestamp}.txt")
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report))
            print(f"\n📄 报告已生成: {Colors.BOLD}{report_path}{Colors.RESET}")
        except Exception as e:
            print(f"❌ 报告保存失败: {e}")

        # --- 触发清理向导 ---
        if self.last_scan_results:
            self.cleanup_wizard()
        else:
            print(f"{Colors.GREEN}🎉 完美！未发现重复内容。{Colors.RESET}")
            self.pause()

    # --- 清理脚本生成器 (v5.1 三模式) ---
    def cleanup_wizard(self):
        print(f"\n{Colors.YELLOW}💡 发现重复文件！请选择清理模式：{Colors.RESET}")
        print("   规则: 保留文件名最长(信息最全)的文件，删除其他相同大小的副本。")
        print(f"   {Colors.CYAN}1. 生成本地脚本 (rm命令){Colors.RESET} -> 用于本地运行 (安全)")
        print(f"   {Colors.CYAN}2. 生成远程脚本 (API Key){Colors.RESET} -> 用于远程运行 (可能无法深度删除)")
        print(f"   {Colors.MAGENTA}3. 立即登录删除 (User Login){Colors.RESET} -> {Colors.BOLD}推荐{Colors.RESET}：模拟用户登录，联动删除源文件")
        
        mode = self.get_user_input("请选择模式 [1/2/3]").strip()
        if mode not in ['1', '2', '3']:
            print("取消操作。")
            return

        # 模式 3: 交互式登录删除
        if mode == '3':
            if not self.login_user():
                return
            self.interactive_user_delete()
            return

        is_remote = (mode == '2')
        mode_name = "REMOTE_API" if is_remote else "LOCAL_RM"

        # 选择库 (For script generation)
        self._generate_script(is_remote, mode_name)

    def _generate_script(self, is_remote, mode_name):
        libs = list(self.last_scan_results.keys())
        print(f"\n{Colors.CYAN}请选择要清理的媒体库:{Colors.RESET}")
        for i, lib in enumerate(libs):
            print(f"  {i+1}. {lib} ({len(self.last_scan_results[lib])} 组重复)")
        
        choice = self.get_user_input("输入序号 (0=全部生成)").strip()
        
        target_libs = []
        if choice == '0':
            target_libs = libs
        elif choice.isdigit() and 0 < int(choice) <= len(libs):
            target_libs = [libs[int(choice)-1]]
        else:
            return

        script_content = ["#!/bin/bash", f"# Emby Duplicate Cleaner ({mode_name})", f"# Generated: {datetime.now()}", ""]
        
        if is_remote:
            script_content.append(f"# WARNING: API Delete Mode. Files will be deleted from server via API.")
            script_content.append(f"API_KEY='{self.api_key}'")
            script_content.append(f"HOST='{self.server_url}'")
            script_content.append("")

        total_cmds = 0
        for lib in target_libs:
            script_content.append(f"# === Library: {lib} ===")
            groups = self.last_scan_results[lib]
            
            for group in groups:
                files = group['files']
                sorted_files = sorted(files, key=lambda x: len(os.path.basename(x['path'])), reverse=True)
                keep_file = sorted_files[0]
                delete_files = sorted_files[1:]
                
                if not delete_files: continue

                script_content.append(f"# Group: Size {self.format_size(group['size'])}")
                script_content.append(f"# KEEP: {os.path.basename(keep_file['path'])}")
                
                for f in delete_files:
                    if is_remote:
                        cmd = f'curl -X DELETE "$HOST/emby/Items/{f["id"]}?api_key=$API_KEY" && echo "Deleted ID {f["id"]}"'
                    else:
                        cmd = f'rm -v "{f["path"]}"'
                    script_content.append(cmd)
                    total_cmds += 1
                script_content.append("")

        sh_name = f"clean_{mode_name.lower()}_{datetime.now().strftime('%H%M%S')}.sh"
        sh_path = os.path.join(self.data_dir, sh_name)
        
        try:
            with open(sh_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(script_content))
            os.chmod(sh_path, 0o755)
            print(f"\n{Colors.GREEN}✅ 清理脚本已生成！包含 {total_cmds} 条删除命令。{Colors.RESET}")
            print(f"📍 脚本路径: {Colors.BOLD}{sh_path}{Colors.RESET}")
            print(f"👉 执行命令: {Colors.YELLOW}bash {sh_path}{Colors.RESET}")
        except Exception as e:
            print(f"❌ 脚本生成失败: {e}")

    # --- 交互式登录删除逻辑 ---
    def interactive_user_delete(self):
        # 选择库
        libs = list(self.last_scan_results.keys())
        print(f"\n{Colors.CYAN}请选择要【立即删除】的媒体库:{Colors.RESET}")
        for i, lib in enumerate(libs):
            print(f"  {i+1}. {lib} ({len(self.last_scan_results[lib])} 组重复)")
        
        choice = self.get_user_input("输入序号 (0=全部删除)").strip()
        
        target_libs = []
        if choice == '0':
            target_libs = libs
        elif choice.isdigit() and 0 < int(choice) <= len(libs):
            target_libs = [libs[int(choice)-1]]
        else:
            return

        # 汇总要删除的项目
        delete_queue = []
        print(f"\n{Colors.YELLOW}正在分析删除列表...{Colors.RESET}")
        for lib in target_libs:
            groups = self.last_scan_results[lib]
            for group in groups:
                files = group['files']
                # 规则：保留文件名最长的
                sorted_files = sorted(files, key=lambda x: len(os.path.basename(x['path'])), reverse=True)
                # 收集删除项
                for f in sorted_files[1:]:
                     delete_queue.append(f)

        count = len(delete_queue)
        if count == 0:
            print("没有需要删除的文件。")
            return

        print(f"\n{Colors.RED}⚠️  警告: 即将向 Emby 发送 {count} 个删除指令！{Colors.RESET}")
        print(f"   这将模拟用户 '{self.user_id}' 的操作，可能会永久删除源文件。")
        confirm = self.get_user_input(f"确认执行删除吗? 输入 'DELETE' 确认").strip()
        
        if confirm != 'DELETE':
            print("操作已取消。")
            return

        # 执行删除
        print("")
        success_count = 0
        fail_count = 0
        
        # 使用登录后的 Token
        auth_headers = {
            'X-Emby-Token': self.access_token,
            'Content-Type': 'application/json'
        }

        for i, item in enumerate(delete_queue):
            sys.stdout.write(f"Processing {i+1}/{count}: {item['name']}...\r")
            sys.stdout.flush()
            
            # 调用 DELETE API
            res = self._request(f"/Items/{item['id']}", method='DELETE', auth_header=auth_headers)
            
            if res is not None: # None 表示请求异常，{} 表示 204 Success
                success_count += 1
            else:
                fail_count += 1
                print(f"\n❌ 删除失败: {item['name']} (ID: {item['id']})")

        print(f"\n\n{Colors.GREEN}✅ 操作完成！成功删除: {success_count} 个，失败: {fail_count} 个。{Colors.RESET}")
        print("建议在 Emby 后台手动触发一次 '扫描媒体库' 以同步状态。")
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
        files = [f for f in os.listdir(self.data_dir) if f.endswith('.txt') or f.endswith('.sh')]
        files.sort(reverse=True)
        if not files:
            print("暂无报告。")
            self.pause()
            return
        print(f"{Colors.YELLOW}📜 历史文件 (报告/脚本):{Colors.RESET}")
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
        if not app.server_url:
            app.setup_wizard()
        app.main_menu()
    except KeyboardInterrupt:
        print("\n退出。")
        sys.exit(0)
