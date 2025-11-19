#!/usr/bin/env python3
"""
Emby媒体库重复检测工具 v6.2 Ultimate Edition
GitHub: https://github.com/huanhq99/emby-scanner
核心升级: 
1. 完美逻辑闭环：用户模拟登录(触发深度删除) + 手动精选(防止乱删) + ID熔断保护(防止合并误删)。
2. 修复：解决了 v6.0/6.1 中断输入流的问题，同时找回了 v5.4 的登录功能。
3. 架构：Zero-Dependency
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
        self.version = "6.2 Ultimate"
        self.github_url = "https://github.com/huanhq99/emby-scanner"
        self.server_url = ""
        self.api_key = ""
        self.headers = {}

        self.user_id = ""
        self.access_token = ""
        self.last_scan_results = {} 

        home_dir = os.environ.get('HOME')
        self.script_dir = home_dir if home_dir else os.path.expanduser('~')
        self.data_dir = os.path.join(self.script_dir, "emby_scanner_data")

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_banner(self):
        banner = f"""
{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗
║             Emby媒体库重复检测工具 {Colors.YELLOW}v{self.version}{Colors.CYAN}              
║             {Colors.RESET}User Login Delete | Manual Select | ID-Safe{Colors.CYAN}          
╚════════════════════════════════════════════════════════════════╝{Colors.RESET}
        """
        print(banner)

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
        print(f"\n按 {Colors.GREEN}回车键{Colors.RESET} 继续...", end="")
        sys.stdout.flush()
        sys.stdin.readline()

    def _request(self, endpoint, params=None, method='GET', auth_header=None, post_data=None):
        url = f"{self.server_url}{endpoint}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url += f"?{query_string}"
        
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
                    if response.status == 204: return {}
                    return json.loads(response.read().decode('utf-8'))
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    if hasattr(e, 'code') and e.code != 404:
                         pass 
                    return None
            except Exception:
                return None

    # --- 用户登录 (用于触发联动删除) ---
    def login_user(self):
        print(f"\n{Colors.YELLOW}🔐 请登录 Emby 管理员账号 (触发源文件联动删除){Colors.RESET}")
        username = self.get_user_input("用户名")
        try:
            # 尝试隐藏输入，管道环境下可能回退明文
            if sys.stdin.isatty():
                import getpass
                password = getpass.getpass(f"{Colors.BOLD}密码{Colors.RESET}: ")
            else:
                password = self.get_user_input("密码")
        except:
            password = self.get_user_input("密码")

        print(f"🔄 正在验证身份...")
        auth_data = {"Username": username, "Pw": password}
        # 伪装成 Web 客户端
        login_headers = {
            'Content-Type': 'application/json',
            'X-Emby-Authorization': 'MediaBrowser Client="Emby Web", Device="Chrome", DeviceId="EmbyScanner_Script", Version="4.7.14.0"'
        }
        
        try:
            url = f"{self.server_url}/Users/AuthenticateByName"
            req = urllib.request.Request(url, headers=login_headers, method='POST')
            req.data = json.dumps(auth_data).encode('utf-8')
            
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                self.access_token = result['AccessToken']
                self.user_id = result['User']['Id']
                print(f"{Colors.GREEN}✅ 登录成功! 用户: {result['User']['Name']}{Colors.RESET}")
                return True
        except Exception as e:
            print(f"{Colors.RED}❌ 登录失败: {e}{Colors.RESET}")
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
                    self.headers = {'X-Emby-Token': self.api_key, 'Content-Type': 'application/json', 'User-Agent': 'EmbyScannerPro/6.2'}
                    return True
            except: pass
        return False

    def save_config(self):
        config = {'server_url': self.server_url, 'api_key': self.api_key, 'updated': datetime.now().isoformat()}
        try:
            with open(os.path.join(self.data_dir, 'emby_config.json'), 'w') as f:
                json.dump(config, f)
            print(f"{Colors.GREEN}✅ 配置已保存{Colors.RESET}")
        except: pass

    def setup_wizard(self):
        self.clear_screen()
        self.print_banner()
        print(f"{Colors.YELLOW}首次设置向导{Colors.RESET}\n")
        while True:
            url = self.get_user_input("Emby 地址").strip().rstrip('/')
            if not url.startswith(('http://', 'https://')): continue
            self.server_url = url
            break
        self.api_key = self.get_user_input("API 密钥").strip()
        self.headers = {'X-Emby-Token': self.api_key}
        if self._request("/emby/System/Info"):
            print(f"{Colors.GREEN}✅ 连接成功{Colors.RESET}")
            self.save_config()
            self.pause()
            return True
        return False

    # --- 扫描核心 ---
    def format_size(self, size_bytes):
        if not size_bytes: return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024: return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    def get_video_info(self, item):
        media_sources = item.get('MediaSources', [])
        if not media_sources: return "未知"
        info = []
        stream = media_sources[0]
        container = stream.get('Container', '').upper()
        # if container: info.append(container)
        video_streams = [s for s in stream.get('MediaStreams', []) if s.get('Type') == 'Video']
        if video_streams:
            v = video_streams[0]
            width = v.get('Width')
            if width:
                if width >= 3800: res = "4K"
                elif width >= 1900: res = "1080P"
                elif width >= 1200: res = "720P"
                else: res = "SD"
                if res == "4K": res = f"{Colors.MAGENTA}4K{Colors.RESET}"
                elif res == "1080P": res = f"{Colors.GREEN}1080P{Colors.RESET}"
                info.append(res)
            codec = v.get('Codec', '').upper()
            if codec: info.append(codec)
        if 'HDR' in str(video_streams).upper(): info.append(f"{Colors.YELLOW}HDR{Colors.RESET}")
        if 'DOLBY' in str(video_streams).upper() or 'DV' in str(video_streams).upper(): info.append(f"{Colors.CYAN}DV{Colors.RESET}")
        return " | ".join(info)

    def run_scanner(self):
        self.clear_screen()
        self.print_banner()
        print(f"{Colors.YELLOW}🚀 正在扫描媒体库...{Colors.RESET}")
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: return

        target_libs = [l for l in libs.get('Items', []) if l.get('CollectionType') in ['movies', 'tvshows']]
        print(f"{Colors.BOLD}{'媒体库名称':<20} | {'总容量':<12} | {'冗余占用':<15} | {'状态'}{Colors.RESET}")
        print("-" * 70)

        self.last_scan_results = {}
        total_bytes_scanned = 0

        for lib in target_libs:
            lib_name = lib.get('Name')
            ctype = lib.get('CollectionType')
            sys.stdout.write(f"⏳ 扫描中: {lib_name}...\r")
            sys.stdout.flush()
            
            fetch_type = 'Episode' if ctype == 'tvshows' else 'Movie'
            params = {
                'ParentId': lib['Id'], 'Recursive': 'true', 'IncludeItemTypes': fetch_type,
                'Fields': 'Path,MediaSources,Size,ProductionYear,SeriesName,IndexNumber,ParentIndexNumber', 
                'Limit': 100000 
            }
            
            data = self._request("/emby/Items", params)
            if not data: continue
            items = data.get('Items', [])
            
            total_bytes = sum(item.get('Size', 0) for item in items)
            groups = defaultdict(list)
            
            for item in items:
                size = item.get('Size')
                if not size: continue
                name = item.get('Name')
                if ctype == 'tvshows':
                    s_name = item.get('SeriesName', '')
                    s = item.get('ParentIndexNumber', -1)
                    e = item.get('IndexNumber', -1)
                    if s != -1 and e != -1: name = f"{s_name} S{s:02d}E{e:02d}"
                    key = (s_name, s, e, size)
                else:
                    key = size
                groups[key].append({
                    'id': item.get('Id'),
                    'name': name,
                    'path': item.get('Path'),
                    'size': size,
                    'info': self.get_video_info(item),
                    'year': item.get('ProductionYear')
                })

            dups = {k: v for k, v in groups.items() if len(v) > 1}
            redundant = 0
            lib_dup_list = []

            if dups:
                for k, group in dups.items():
                    if isinstance(k, tuple): size = k[3]
                    else: size = k
                    paths = set(g['path'] for g in group)
                    if len(paths) > 1:
                        redundant += (len(group) - 1) * size
                        lib_dup_list.append({'size': size, 'files': group})
            
            if lib_dup_list:
                self.last_scan_results[lib_name] = lib_dup_list
                status = f"{Colors.YELLOW}含重复{Colors.RESET}"
                dup_str = f"{Colors.RED}{self.format_size(redundant)}{Colors.RESET}"
            else:
                status = f"{Colors.GREEN}完美{Colors.RESET}"
                dup_str = f"{Colors.GREEN}0 B{Colors.RESET}"

            sys.stdout.write("\r" + " " * 60 + "\r")
            print(f"{Colors.BOLD}{lib_name:<20}{Colors.RESET} | {self.format_size(total_bytes):<12} | {dup_str:<24} | {status:<10}")

        if self.last_scan_results:
            self.manual_select_wizard()
        else:
            print(f"\n{Colors.GREEN}🎉 完美！未发现重复。{Colors.RESET}")
            self.pause()

    # --- 核心: 手动选择与删除 ---
    def manual_select_wizard(self):
        print(f"\n{Colors.YELLOW}💡 发现重复文件！请选择操作：{Colors.RESET}")
        libs = list(self.last_scan_results.keys())
        for i, lib in enumerate(libs):
            print(f"  {i+1}. {lib} ({len(self.last_scan_results[lib])} 组重复)")
        
        choice = self.get_user_input("选择库 (序号/0退出)").strip()
        if not choice.isdigit() or int(choice) == 0: return
        target_lib = libs[int(choice)-1]
        groups = self.last_scan_results[target_lib]

        print(f"\n{Colors.BOLD}>>> 正在处理: {target_lib}{Colors.RESET}")
        
        # 待删除列表 (ID, Name, Path)
        final_delete_tasks = []
        
        for idx, group in enumerate(groups):
            files = group['files']
            # 默认按名称长度排序，方便用户参考
            files = sorted(files, key=lambda x: len(os.path.basename(x['path'])), reverse=True)
            
            print(f"\n{Colors.YELLOW}--- [第 {idx+1}/{len(groups)} 组] 体积: {self.format_size(group['size'])} ---{Colors.RESET}")
            
            # 收集该组所有 ID，用于后续熔断检查
            all_ids_in_group = [f['id'] for f in files]
            is_merged_item = len(set(all_ids_in_group)) == 1 # 如果 ID 只有 1 个，说明合并了

            for i, f in enumerate(files):
                fname = os.path.basename(f['path'])
                # 显示 ID，方便排查
                print(f"  [{Colors.CYAN}{i+1}{Colors.RESET}] {f['name']} [{f['info']}] (ID: {f['id']})")
                print(f"      📂 {fname}")
            
            if is_merged_item:
                 print(f"  {Colors.RED}⚠️  警告: 本组文件共享同一个 Emby ID (已合并)。删除任意一个都会导致全部删除！{Colors.RESET}")
                 print(f"  {Colors.MAGENTA}👉 建议跳过，去 Emby 网页端手动拆分版本后再删。{Colors.RESET}")
            
            user_sel = self.get_user_input(f"输入要{Colors.RED}删除{Colors.RESET}的序号 (逗号隔开, Enter跳过)").strip()
            
            if user_sel:
                try:
                    indices = [int(x.strip()) - 1 for x in user_sel.split(',') if x.strip().isdigit()]
                    selected_files = []
                    for sel_idx in indices:
                        if 0 <= sel_idx < len(files):
                            selected_files.append(files[sel_idx])
                    
                    # --- 核心熔断逻辑 ---
                    # 如果是合并条目 (ID相同)，且用户试图删除其中一个...
                    if is_merged_item and len(selected_files) < len(files):
                         print(f"  {Colors.RED}🚫 阻止操作：检测到合并条目 ID 冲突。脚本无法通过 API 单独删除。{Colors.RESET}")
                         continue
                    
                    # 如果 ID 不冲突（是独立条目），或者用户疯狂到把所有都删了
                    for f in selected_files:
                        # 再次确认：如果我删了 f，剩下的文件里有没有和 f ID 一样的？
                        # 剩下的文件 = [x for x in files if x not in selected_files]
                        # 如果剩下的文件里有和 f.id 一样的，说明这是合并条目，不能删 f。
                        remaining_ids = [x['id'] for x in files if x not in selected_files and x != f]
                        
                        if f['id'] in remaining_ids:
                             print(f"  {Colors.RED}🚫 跳过 {f['name']}：与保留文件 ID 冲突，防止误删保留文件。{Colors.RESET}")
                        else:
                             final_delete_tasks.append(f)
                             print(f"      ✅ 已加入删除队列")

                except: pass

        if not final_delete_tasks:
            print("\n未选择任何文件。")
            return

        # 确认执行
        print(f"\n{Colors.RED}⚠️  即将删除 {len(final_delete_tasks)} 个文件/条目！{Colors.RESET}")
        if self.get_user_input("确认执行? (输入 YES)").strip() != "YES":
            return

        # 登录并执行
        if self.login_user():
            auth_headers = {
                'X-Emby-Token': self.access_token,
                'Content-Type': 'application/json',
                'X-Emby-Authorization': 'MediaBrowser Client="Emby Web", Device="Chrome", DeviceId="EmbyScanner_Script", Version="4.7.14.0"'
            }
            
            success_count = 0
            for i, item in enumerate(final_delete_tasks):
                sys.stdout.write(f"Processing {i+1}/{len(final_delete_tasks)}: {item['name']}...\r")
                sys.stdout.flush()
                # 调用 DELETE API
                res = self._request(f"/Items/{item['id']}", method='DELETE', auth_header=auth_headers)
                if res is not None:
                    success_count += 1
                    time.sleep(1.5) # 慢速防封
                else:
                    print(f"\n❌ 删除失败: {item['name']}")
            
            print(f"\n{Colors.GREEN}✅ 任务完成。成功删除 {success_count} 个。{Colors.RESET}")
            self.pause()

    # --- 菜单 ---
    def main_menu(self):
        while True:
            self.clear_screen()
            self.print_banner()
            print(f"状态: {Colors.GREEN if self.server_url else Colors.RED}{'已连接' if self.server_url else '未配置'}{Colors.RESET}")
            print("1. 扫描  2. 配置  3. 历史  4. 重置  0. 退出")
            c = self.get_user_input("选择").strip()
            if c=='1': self.run_scanner() if self.server_url else print("请先配置") or self.pause()
            elif c=='2': self.init_config() if self.setup_wizard() else None
            elif c=='3': self.view_reports()
            elif c=='4': self.reset_config()
            elif c=='0': sys.exit(0)

    def view_reports(self): pass 
    def reset_config(self): pass

if __name__ == "__main__":
    try:
        app = EmbyScannerPro()
        app.init_config()
        if not app.server_url: app.setup_wizard()
        app.main_menu()
    except: sys.exit(0)
