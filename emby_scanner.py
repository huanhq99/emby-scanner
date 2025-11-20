#!/usr/bin/env python3
"""
Emby媒体库重复检测工具 v2.2 Ultimate Edition
GitHub: https://github.com/huanhq99/emby-scanner
核心功能: 
1. 逻辑：纯体积(Size)去重 + 智能保留(文件名最长) + 用户登录深度删除。
2. 交互：支持【批量自动标记】删除短文件名副本，显示完整路径。
3. 安全：ID熔断保护。
4. 架构：Zero-Dependency
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
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

# ==================== 主程序类 ====================
class EmbyScannerPro:
    
    def __init__(self):
        self.version = "2.2 Ultimate"
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

    # --- UI 升级: 仪表盘风格 Banner ---
    def print_banner(self):
        # 居中对齐的 Logo
        logo = f"""
{Colors.CYAN}   ______      _             {Colors.YELLOW}_____                                  {Colors.RESET}
{Colors.CYAN}  |  ____|    | |           {Colors.YELLOW}/ ____|                                 {Colors.RESET}
{Colors.CYAN}  | |__   _ __| |__  _   _ {Colors.YELLOW}| (___   ___ __ _ _ __  _ __   ___ _ __  {Colors.RESET}
{Colors.CYAN}  |  __| | '_ \ '_ \| | | | {Colors.YELLOW}\___ \ / __/ _` | '_ \| '_ \ / _ \ '__| {Colors.RESET}
{Colors.CYAN}  | |____| | | | |_) | |_| | {Colors.YELLOW}____) | (_| (_| | | | | | | |  __/ |    {Colors.RESET}
{Colors.CYAN}  |______|_| |_|_.__/ \__, |{Colors.YELLOW}|_____/ \___\__,_|_| |_|_| |_|\___|_|    {Colors.RESET}
{Colors.CYAN}                       __/ |                                        {Colors.RESET}
{Colors.CYAN}                      |___/                                         {Colors.RESET}
        """
        
        info_bar = f"{Colors.BOLD}   Emby Duplicate Scanner {Colors.MAGENTA}v{self.version}{Colors.RESET} {Colors.DIM}|{Colors.RESET} Batch Clean {Colors.DIM}|{Colors.RESET} User-Login"
        
        print(logo)
        print(info_bar.center(80))
        print(f"\n{Colors.DIM}" + "—" * 65 + f"{Colors.RESET}\n")

    def get_user_input(self, prompt, default=""):
        full_prompt = f" {Colors.CYAN}▶{Colors.RESET} {Colors.BOLD}{prompt}{Colors.RESET}"
        if default:
            full_prompt += f" [{default}]"
        full_prompt += ": "
        
        try:
            sys.stdout.write(full_prompt)
            sys.stdout.flush()
            user_input = sys.stdin.readline().strip()
            return user_input if user_input else default
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)

    def pause(self):
        print(f"\n {Colors.DIM}Press {Colors.GREEN}[Enter]{Colors.RESET}{Colors.DIM} to continue...{Colors.RESET}", end="")
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

    def login_user(self):
        print(f"\n{Colors.YELLOW} 🔐  管理员登录 (User Login){Colors.RESET}")
        print(f" {Colors.DIM} 说明: 登录以获取 Session，触发 Emby 联动删除源文件。{Colors.RESET}")
        print(f"{Colors.DIM}" + "-" * 40 + f"{Colors.RESET}")
        
        username = self.get_user_input("用户名")
        try:
            if sys.stdin.isatty():
                import getpass
                password = getpass.getpass(f" {Colors.CYAN}▶{Colors.RESET} {Colors.BOLD}密码{Colors.RESET}: ")
            else:
                password = self.get_user_input("密码")
        except:
            password = self.get_user_input("密码")

        print(f"\n 🔄 正在验证...")
        auth_data = {"Username": username, "Pw": password}
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
                print(f" {Colors.GREEN}✅ 登录成功: {result['User']['Name']}{Colors.RESET}")
                return True
        except Exception as e:
            print(f" {Colors.RED}❌ 登录失败: {e}{Colors.RESET}")
            return False

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
                    self.headers = {'X-Emby-Token': self.api_key, 'Content-Type': 'application/json', 'User-Agent': 'EmbyScannerPro/2.0'}
                    return True
            except: pass
        return False

    def save_config(self):
        config = {'server_url': self.server_url, 'api_key': self.api_key, 'updated': datetime.now().isoformat()}
        try:
            with open(os.path.join(self.data_dir, 'emby_config.json'), 'w') as f:
                json.dump(config, f)
            print(f" {Colors.GREEN}✅ 配置已保存{Colors.RESET}")
        except: pass

    def setup_wizard(self):
        self.clear_screen()
        self.print_banner()
        print(f"{Colors.YELLOW} 🛠️  初始化设置{Colors.RESET}\n")
        while True:
            url = self.get_user_input("Emby 地址 (http://ip:port)").strip().rstrip('/')
            if not url.startswith(('http://', 'https://')): continue
            self.server_url = url
            break
        self.api_key = self.get_user_input("API 密钥").strip()
        self.headers = {'X-Emby-Token': self.api_key}
        if self._request("/emby/System/Info"):
            print(f" {Colors.GREEN}✅ 连接成功{Colors.RESET}")
            self.save_config()
            self.pause()
            return True
        return False

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
        print(f" {Colors.YELLOW}🚀 正在扫描媒体库 (查重模式)...{Colors.RESET}")
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: return

        target_libs = [l for l in libs.get('Items', []) if l.get('CollectionType') in ['movies', 'tvshows']]
        
        # 优化表头
        print(f"\n {Colors.DIM}┌" + "─"*22 + "┬" + "─"*14 + "┬" + "─"*17 + "┬" + "─"*12 + "┐" + f"{Colors.RESET}")
        print(f" {Colors.BOLD}│ {'媒体库名称':<20} │ {'总容量':<12} │ {'冗余(可释放)':<13} │ {'状态':<10} │{Colors.RESET}")
        print(f" {Colors.DIM}├" + "─"*22 + "┼" + "─"*14 + "┼" + "─"*17 + "┼" + "─"*12 + "┤" + f"{Colors.RESET}")

        self.last_scan_results = {}
        total_bytes_scanned = 0

        for lib in target_libs:
            lib_name = lib.get('Name')
            ctype = lib.get('CollectionType')
            sys.stdout.write(f" │ {lib_name:<20} ...\r")
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

            sys.stdout.write("\r") # 清除行内
            print(f" │ {lib_name:<20} │ {self.format_size(total_bytes):<12} │ {dup_str:<15} │ {status:<10} │")

        print(f" {Colors.DIM}└" + "─"*22 + "┴" + "─"*14 + "┴" + "─"*17 + "┴" + "─"*12 + "┘" + f"{Colors.RESET}")
        
        # 保存报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.data_dir, f"report_{timestamp}.txt")
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"Emby 重复检测报告 - {timestamp}\n\n")
                for lib, groups in self.last_scan_results.items():
                     f.write(f"Library: {lib}\n")
                     for g in groups:
                         f.write(f"Size: {g['size']} Bytes\n")
                         for file in g['files']:
                             f.write(f" - {file['path']}\n")
                     f.write("\n")
            print(f"\n 📄 查重报告已生成: {report_path}")
        except: pass

        if self.last_scan_results:
            self.manual_select_wizard()
        else:
            print(f"\n {Colors.GREEN}🎉 完美！未发现重复。{Colors.RESET}")
            self.pause()

    def manual_select_wizard(self):
        print(f"\n {Colors.YELLOW}💡 发现重复文件！进入清理模式{Colors.RESET}")
        libs = list(self.last_scan_results.keys())
        for i, lib in enumerate(libs):
            print(f"   [{i+1}] {lib} ({len(self.last_scan_results[lib])} 组)")
        
        choice = self.get_user_input("选择库序号 (0=退出)").strip()
        if not choice.isdigit() or int(choice) == 0: return
        target_lib = libs[int(choice)-1]
        groups = self.last_scan_results[target_lib]

        self.clear_screen()
        print(f"{Colors.CYAN}>>> 正在处理: {target_lib}{Colors.RESET}")
        
        # --- v2.2 核心交互升级 ---
        print(f" {Colors.BOLD}请选择处理模式:{Colors.RESET}")
        print(f"   {Colors.GREEN}[a] 批量自动模式{Colors.RESET} (保留 #1 长命名文件，自动删除其他)")
        print(f"   {Colors.YELLOW}[m] 手动逐个确认{Colors.RESET} (逐一查看每组详情)")
        
        mode = self.get_user_input("输入 a 或 m").strip().lower()
        
        final_delete_tasks = []
        
        if mode == 'a':
            print(f"\n {Colors.YELLOW}🔄 正在自动匹配最佳文件...{Colors.RESET}")
            for group in groups:
                files = group['files']
                # 排序：文件名最长 -> 放在 #1
                files = sorted(files, key=lambda x: len(os.path.basename(x['path'])), reverse=True)
                
                # #1 保留， #2... 删除
                keep_file = files[0]
                del_files = files[1:]
                
                # 简单的 ID 冲突检查
                is_safe = True
                for f in del_files:
                    if f['id'] == keep_file['id']: is_safe = False
                
                if is_safe:
                    final_delete_tasks.extend(del_files)
                else:
                    print(f" {Colors.RED}⚠️ 跳过一组 ID 冲突 (合并条目){Colors.RESET}")

        else:
            # 手动模式
            for idx, group in enumerate(groups):
                files = group['files']
                # 排序：文件名最长 -> #1
                files = sorted(files, key=lambda x: len(os.path.basename(x['path'])), reverse=True)
                
                print(f"\n{Colors.YELLOW}--- [第 {idx+1}/{len(groups)} 组] 体积: {self.format_size(group['size'])} ---{Colors.RESET}")
                
                all_ids = [f['id'] for f in files]
                is_merged = len(set(all_ids)) == 1

                for i, f in enumerate(files):
                    # --- UI 优化：显示完整路径 ---
                    print(f"  [{Colors.CYAN}{i+1}{Colors.RESET}] {f['name']} [{f['info']}]")
                    print(f"      {Colors.DIM}{f['path']}{Colors.RESET}") # 显示完整路径
            
                if is_merged:
                     print(f"  {Colors.RED}⚠️  警告: ID 冲突 (已合并条目)。请谨慎操作。{Colors.RESET}")
            
                user_sel = self.get_user_input(f"删除序号 (多选逗号隔开, Enter跳过)").strip()
                
                if user_sel:
                    try:
                        indices = [int(x.strip()) - 1 for x in user_sel.split(',') if x.strip().isdigit()]
                        selected_files = []
                        for sel_idx in indices:
                            if 0 <= sel_idx < len(files):
                                selected_files.append(files[sel_idx])
                        
                        if is_merged and len(selected_files) < len(files):
                             print(f"  {Colors.RED}🚫 阻止操作：检测到合并条目，无法单独删除。{Colors.RESET}")
                             continue
                        
                        for f in selected_files:
                            rem_ids = [x['id'] for x in files if x not in selected_files and x != f]
                            if f['id'] in rem_ids:
                                 print(f"  {Colors.RED}🚫 跳过：ID 冲突保护。{Colors.RESET}")
                            else:
                                 final_delete_tasks.append(f)
                                 print(f"      ✅ 已标记")
                    except: pass

        if not final_delete_tasks:
            print("\n 无文件被选中。")
            self.pause()
            return

        print(f"\n{Colors.RED}⚠️  即将删除 {len(final_delete_tasks)} 个文件！{Colors.RESET}")
        if self.get_user_input("输入 YES 确认").strip() != "YES": return

        if self.login_user():
            auth_headers = {
                'X-Emby-Token': self.access_token,
                'Content-Type': 'application/json',
                'X-Emby-Authorization': 'MediaBrowser Client="Emby Web", Device="Chrome", DeviceId="EmbyScanner_Script", Version="4.7.14.0"'
            }
            
            success = 0
            for i, item in enumerate(final_delete_tasks):
                sys.stdout.write(f"删除 {i+1}/{len(final_delete_tasks)}...\r")
                sys.stdout.flush()
                if self._request(f"/Items/{item['id']}", method='DELETE', auth_header=auth_headers) is not None:
                    success += 1
                    time.sleep(1.5)
                else:
                    print(f"\n❌ 失败: {item['name']}")
            
            print(f"\n {Colors.GREEN}✅ 完成！成功删除 {success} 个。{Colors.RESET}")
            self.pause()

    # --- 新增功能：缺集检查 ---
    def run_missing_check(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🔍 正在检查剧集缺集...{Colors.RESET}")
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: return

        target_libs = [l for l in libs.get('Items', []) if l.get('CollectionType') == 'tvshows']
        
        if not target_libs:
             print(f"\n {Colors.RED}❌ 未找到剧集类型的媒体库。{Colors.RESET}")
             self.pause()
             return

        print(f"\n {Colors.DIM}┌" + "─"*22 + "┬" + "─"*14 + "┬" + "─"*17 + "┬" + "─"*12 + "┐" + f"{Colors.RESET}")
        print(f" {Colors.BOLD}│ {'媒体库名称':<20} │ {'剧集总数':<12} │ {'缺集统计':<13} │ {'状态':<10} │{Colors.RESET}")
        print(f" {Colors.DIM}├" + "─"*22 + "┼" + "─"*14 + "┼" + "─"*17 + "┼" + "─"*12 + "┤" + f"{Colors.RESET}")

        report_lines = [
            "🎬 Emby 缺集检测报告",
            "=" * 60,
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"检测逻辑: 基于现有集数序号检测中间缺失 (例如有1,3集，则缺失2)",
            ""
        ]
        
        total_missing_count = 0

        for lib in target_libs:
            lib_name = lib.get('Name')
            sys.stdout.write(f" │ {lib_name:<20} ...\r")
            sys.stdout.flush()
            
            params = {'ParentId': lib['Id'], 'Recursive': 'true', 'IncludeItemTypes': 'Series', 'Limit': 100000}
            series_data = self._request("/emby/Items", params)
            if not series_data: continue
            
            all_series = series_data.get('Items', [])
            series_count = len(all_series)
            lib_missing_count = 0
            lib_report_buffer = []

            for series in all_series:
                ep_params = {
                    'ParentId': series['Id'], 
                    'Recursive': 'true', 
                    'IncludeItemTypes': 'Episode',
                    'Fields': 'ParentIndexNumber,IndexNumber',
                    'Limit': 10000 
                }
                ep_data = self._request("/emby/Items", ep_params)
                if not ep_data: continue
                
                episodes = ep_data.get('Items', [])
                season_map = defaultdict(list)
                
                for ep in episodes:
                    s = ep.get('ParentIndexNumber', 1) # 默认第1季
                    e_idx = ep.get('IndexNumber')
                    if e_idx is not None: season_map[s].append(e_idx)
                
                series_has_missing = False
                series_missing_str = []

                for s_idx in sorted(season_map.keys()):
                    if s_idx == 0: continue 
                    
                    eps = sorted(set(season_map[s_idx]))
                    if not eps: continue
                    
                    max_ep = eps[-1]
                    expected = set(range(1, max_ep + 1))
                    current = set(eps)
                    missing = sorted(list(expected - current))
                    
                    if missing:
                        series_has_missing = True
                        lib_missing_count += len(missing)
                        miss_list_str = ", ".join(map(str, missing))
                        series_missing_str.append(f"  - 第 {s_idx} 季: 缺失集数 [{miss_list_str}]")

                if series_has_missing:
                    lib_report_buffer.append(f"📺 {series.get('Name')} ({series.get('ProductionYear', 'Unknown')})")
                    lib_report_buffer.extend(series_missing_str)
                    lib_report_buffer.append("")

            if lib_missing_count > 0:
                report_lines.append(f"📁 媒体库: {lib_name}")
                report_lines.extend(lib_report_buffer)
                report_lines.append("-" * 40)
            
            total_missing_count += lib_missing_count
            
            status = f"{Colors.YELLOW}有缺集{Colors.RESET}" if lib_missing_count > 0 else f"{Colors.GREEN}完整{Colors.RESET}"
            missing_str = f"{Colors.RED}{lib_missing_count} 集{Colors.RESET}" if lib_missing_count > 0 else "0"
            
            sys.stdout.write("\r")
            print(f" │ {lib_name:<20} │ {str(series_count):<12} │ {missing_str:<13} │ {status:<10} │")

        print(f" {Colors.DIM}└" + "─"*22 + "┴" + "─"*14 + "┴" + "─"*17 + "┴" + "─"*12 + "┘" + f"{Colors.RESET}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_name = f"missing_report_{timestamp}.txt"
        report_path = os.path.join(self.data_dir, report_name)
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            print(f"\n 📄 缺集报告已生成: {Colors.BOLD}{report_path}{Colors.RESET}")
        except Exception as e:
            print(f"❌ 报告保存失败: {e}")
        
        self.pause()

    # --- 菜单 ---
    def main_menu(self):
        while True:
            self.clear_screen()
            self.print_banner()
            
            server_status = f"{Colors.GREEN}● 已连接{Colors.RESET}" if self.server_url else f"{Colors.RED}● 未配置{Colors.RESET}"
            
            print(f" {Colors.DIM}Server Status:{Colors.RESET} {server_status}")
            print(f" {Colors.DIM}Data Path:    {Colors.RESET} {self.data_dir}\n")
            
            print(f" {Colors.CYAN}[1]{Colors.RESET} 🚀  开始扫描重复 (查重)")
            print(f" {Colors.CYAN}[2]{Colors.RESET} ⚙️   配置服务器信息")
            print(f" {Colors.CYAN}[3]{Colors.RESET} 📂  查看历史报告")
            print(f" {Colors.CYAN}[4]{Colors.RESET} 🗑️   重置工具数据")
            print(f" {Colors.MAGENTA}[5]{Colors.RESET} 🔍  缺集检查 (Missing)")  
            print(f" {Colors.CYAN}[0]{Colors.RESET} 🚪  退出程序")
            print("")
            
            c = self.get_user_input("请选择").strip()
            if c=='1': self.run_scanner() if self.server_url else print("请先配置") or self.pause()
            elif c=='2': self.init_config() if self.setup_wizard() else None
            elif c=='3': self.view_reports()
            elif c=='4': self.reset_config()
            elif c=='5': self.run_missing_check() if self.server_url else print("请先配置") or self.pause()
            elif c=='0': sys.exit(0)

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

if __name__ == "__main__":
    try:
        app = EmbyScannerPro()
        app.init_config()
        if not app.server_url: app.setup_wizard()
        app.main_menu()
    except: sys.exit(0)
