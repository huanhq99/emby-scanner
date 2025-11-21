#!/usr/bin/env python3
"""
Emby媒体库重复检测工具 v2.6 Ultimate Edition (Paging Optimized)
GitHub: https://github.com/huanhq99/emby-scanner
核心功能: 
1. 基础：纯体积查重 + 智能保留 + 用户登录深度删除 + ID熔断保护。
2. 扩展：大文件筛选 + 剧集缺集检查 + 空文件夹清理 + 媒体库透视。
3. 优化：全模块采用【分页循环读取】策略，解决国内网络/大库扫描慢和超时问题。
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
        self.version = "2.6 Ultimate"
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
        info_bar = f"{Colors.BOLD}   Emby Scanner {Colors.MAGENTA}v{self.version}{Colors.RESET} {Colors.DIM}|{Colors.RESET} Paging Speedup {Colors.DIM}|{Colors.RESET} All-in-One"
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
                # 300秒超时，防止大包传输中断
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
                    self.headers = {'X-Emby-Token': self.api_key, 'Content-Type': 'application/json', 'User-Agent': 'EmbyScannerPro/2.6'}
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
        
        video_streams = [s for s in stream.get('MediaStreams', []) if s.get('Type') == 'Video']
        if video_streams:
            v = video_streams[0]
            width = v.get('Width', 0)
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

    # --- 分页获取核心 ---
    def _fetch_all_items(self, endpoint, params, limit_per_page=5000):
        all_items = []
        start_index = 0
        
        while True:
            params['StartIndex'] = start_index
            params['Limit'] = limit_per_page
            
            sys.stdout.write(f" 🔄 已读取: {len(all_items)} ...\r")
            sys.stdout.flush()
            
            data = self._request(endpoint, params)
            if not data or not data.get('Items'):
                break
            
            items = data.get('Items')
            count = len(items)
            if count == 0: break
            
            all_items.extend(items)
            start_index += count
            
            # 如果取到的数量少于 Limit，说明取完了
            if count < limit_per_page:
                break
        
        return all_items

    # --- 功能 1: 重复检测 (分页版) ---
    def run_scanner(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🚀 正在扫描媒体库 (查重模式)...{Colors.RESET}")
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: return

        target_libs = [l for l in libs.get('Items', []) if l.get('CollectionType') in ['movies', 'tvshows']]
        
        print(f"\n {Colors.DIM}┌" + "─"*22 + "┬" + "─"*14 + "┬" + "─"*17 + "┬" + "─"*12 + "┐" + f"{Colors.RESET}")
        print(f" {Colors.BOLD}│ {'媒体库名称':<20} │ {'总容量':<12} │ {'冗余(可释放)':<13} │ {'状态':<10} │{Colors.RESET}")
        print(f" {Colors.DIM}├" + "─"*22 + "┼" + "─"*14 + "┼" + "─"*17 + "┼" + "─"*12 + "┤" + f"{Colors.RESET}")

        self.last_scan_results = {}
        lib_summaries = [] 

        for lib in target_libs:
            lib_name = lib.get('Name')
            ctype = lib.get('CollectionType')
            sys.stdout.write(f" │ {lib_name:<20} ...\r")
            sys.stdout.flush()
            
            fetch_type = 'Episode' if ctype == 'tvshows' else 'Movie'
            params = {
                'ParentId': lib['Id'], 'Recursive': 'true', 'IncludeItemTypes': fetch_type,
                'Fields': 'Path,MediaSources,Size,ProductionYear,SeriesName,IndexNumber,ParentIndexNumber'
            }
            
            # 使用分页获取所有项目
            items = self._fetch_all_items("/emby/Items", params)
            
            total_bytes = sum(item.get('Size', 0) for item in items)
            lib_summaries.append(f"{lib_name:<20} : {self.format_size(total_bytes)}")

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

            sys.stdout.write("\r" + " "*50 + "\r") # 清除进度
            print(f" │ {lib_name:<20} │ {self.format_size(total_bytes):<12} │ {dup_str:<15} │ {status:<10} │")

        print(f" {Colors.DIM}└" + "─"*22 + "┴" + "─"*14 + "┴" + "─"*17 + "┴" + "─"*12 + "┘" + f"{Colors.RESET}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.data_dir, f"report_{timestamp}.txt")
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"Emby 重复检测报告 - {timestamp}\n")
                f.write(f"{'='*60}\n")
                f.write(f"【媒体库容量概览】\n")
                for summary in lib_summaries:
                    f.write(f"  - {summary}\n")
                f.write(f"{'='*60}\n\n")

                for lib, groups in self.last_scan_results.items():
                     f.write(f"📁 媒体库: {lib}\n")
                     f.write(f"{'-'*40}\n")
                     for g in groups:
                         size_str = self.format_size(g['size'])
                         f.write(f"📦 重复组 (单文件: {size_str}):\n")
                         for file in g['files']:
                             f.write(f"  - [{size_str}] {file['name']} [{file['info']}]\n")
                             f.write(f"    路径: {file['path']}\n")
                         f.write("\n")
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
        
        print(f" {Colors.BOLD}请选择处理模式:{Colors.RESET}")
        print(f"   {Colors.GREEN}[a] 批量自动模式{Colors.RESET} (保留 #1 长命名文件，自动删除其他)")
        print(f"   {Colors.YELLOW}[m] 手动逐个确认{Colors.RESET} (逐一查看每组详情)")
        
        mode = self.get_user_input("输入 a 或 m").strip().lower()
        final_delete_tasks = []
        
        if mode == 'a':
            print(f"\n {Colors.YELLOW}🔄 正在自动匹配最佳文件...{Colors.RESET}")
            for group in groups:
                files = group['files']
                files = sorted(files, key=lambda x: len(os.path.basename(x['path'])), reverse=True)
                keep_file = files[0]
                del_files = files[1:]
                is_safe = True
                for f in del_files:
                    if f['id'] == keep_file['id']: is_safe = False
                if is_safe: final_delete_tasks.extend(del_files)
                else: print(f" {Colors.RED}⚠️ 跳过一组 ID 冲突{Colors.RESET}")
        else:
            for idx, group in enumerate(groups):
                files = group['files']
                files = sorted(files, key=lambda x: len(os.path.basename(x['path'])), reverse=True)
                print(f"\n{Colors.YELLOW}--- [第 {idx+1}/{len(groups)} 组] 体积: {self.format_size(group['size'])} ---{Colors.RESET}")
                all_ids = [f['id'] for f in files]
                is_merged = len(set(all_ids)) == 1
                for i, f in enumerate(files):
                    print(f"  [{Colors.CYAN}{i+1}{Colors.RESET}] {f['name']} [{f['info']}]")
                    print(f"      {Colors.DIM}{f['path']}{Colors.RESET}")
                if is_merged: print(f"  {Colors.RED}⚠️  警告: ID 冲突 (已合并)。{Colors.RESET}")
                user_sel = self.get_user_input(f"删除序号 (多选逗号, Enter跳过)").strip()
                if user_sel:
                    try:
                        indices = [int(x.strip()) - 1 for x in user_sel.split(',') if x.strip().isdigit()]
                        selected_files = []
                        for sel_idx in indices:
                            if 0 <= sel_idx < len(files): selected_files.append(files[sel_idx])
                        if is_merged and len(selected_files) < len(files):
                             print(f"  {Colors.RED}🚫 阻止操作：检测到合并条目。{Colors.RESET}")
                             continue
                        for f in selected_files:
                            rem_ids = [x['id'] for x in files if x not in selected_files and x != f]
                            if f['id'] in rem_ids: print(f"  {Colors.RED}🚫 跳过：ID 冲突保护。{Colors.RESET}")
                            else: final_delete_tasks.append(f); print(f"      ✅ 已标记")
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
                else: print(f"\n❌ 失败: {item['name']}")
            print(f"\n {Colors.GREEN}✅ 完成！成功删除 {success} 个。{Colors.RESET}")
            self.pause()

    # --- 功能 2: 缺集检查 (分页版) ---
    def run_missing_check(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🔍 正在检查剧集缺集...{Colors.RESET}")
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: return
        target_libs = [l for l in libs.get('Items', []) if l.get('CollectionType') == 'tvshows']
        
        if not target_libs:
             print(f"\n {Colors.RED}❌ 未找到剧集类型的媒体库。{Colors.RESET}")
             self.pause(); return

        print(f"\n {Colors.DIM}┌" + "─"*22 + "┬" + "─"*14 + "┬" + "─"*17 + "┬" + "─"*12 + "┐" + f"{Colors.RESET}")
        print(f" {Colors.BOLD}│ {'媒体库名称':<20} │ {'剧集总数':<12} │ {'缺集统计':<13} │ {'状态':<10} │{Colors.RESET}")
        print(f" {Colors.DIM}├" + "─"*22 + "┼" + "─"*14 + "┼" + "─"*17 + "┼" + "─"*12 + "┤" + f"{Colors.RESET}")

        report_lines = ["🎬 Emby 缺集检测报告", "=" * 60, f"生成时间: {datetime.now()}", ""]
        
        for lib in target_libs:
            lib_name = lib.get('Name')
            sys.stdout.write(f" │ {lib_name:<20} ...\r"); sys.stdout.flush()
            
            params = {'ParentId': lib['Id'], 'Recursive': 'true', 'IncludeItemTypes': 'Series'}
            all_series = self._fetch_all_items("/emby/Items", params, 5000)
            
            series_count = len(all_series)
            lib_missing_count = 0
            lib_report_buffer = []

            for series in all_series:
                ep_params = {'ParentId': series['Id'], 'Recursive': 'true', 'IncludeItemTypes': 'Episode', 'Fields': 'ParentIndexNumber,IndexNumber'}
                episodes = self._fetch_all_items("/emby/Items", ep_params, 2000) # 剧集一般每部也就几百集
                
                season_map = defaultdict(list)
                for ep in episodes:
                    s = ep.get('ParentIndexNumber', 1); e_idx = ep.get('IndexNumber')
                    if e_idx is not None: season_map[s].append(e_idx)
                
                series_has_missing = False
                series_missing_str = []
                for s_idx in sorted(season_map.keys()):
                    if s_idx == 0: continue 
                    eps = sorted(set(season_map[s_idx]))
                    if not eps: continue
                    max_ep = eps[-1]
                    missing = sorted(list(set(range(1, max_ep + 1)) - set(eps)))
                    if missing:
                        series_has_missing = True
                        lib_missing_count += len(missing)
                        series_missing_str.append(f"  - 第 {s_idx} 季: 缺失集数 [{', '.join(map(str, missing))}]")

                if series_has_missing:
                    lib_report_buffer.append(f"📺 {series.get('Name')} ({series.get('ProductionYear', 'Unknown')})")
                    lib_report_buffer.extend(series_missing_str)
                    lib_report_buffer.append("")

            if lib_missing_count > 0:
                report_lines.append(f"📁 媒体库: {lib_name}")
                report_lines.extend(lib_report_buffer)
                report_lines.append("-" * 40)
            
            status = f"{Colors.YELLOW}有缺集{Colors.RESET}" if lib_missing_count > 0 else f"{Colors.GREEN}完整{Colors.RESET}"
            missing_str = f"{Colors.RED}{lib_missing_count} 集{Colors.RESET}" if lib_missing_count > 0 else "0"
            sys.stdout.write("\r")
            print(f" │ {lib_name:<20} │ {str(series_count):<12} │ {missing_str:<13} │ {status:<10} │")

        print(f" {Colors.DIM}└" + "─"*22 + "┴" + "─"*14 + "┴" + "─"*17 + "┴" + "─"*12 + "┘" + f"{Colors.RESET}")
        
        report_name = f"missing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_path = os.path.join(self.data_dir, report_name)
        try:
            with open(report_path, 'w', encoding='utf-8') as f: f.write('\n'.join(report_lines))
            print(f"\n 📄 缺集报告已生成: {Colors.BOLD}{report_path}{Colors.RESET}")
        except: pass
        self.pause()

    # --- 功能 3: 垃圾清理 (空文件夹生成脚本) ---
    def run_junk_cleaner(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🧹 垃圾清理 (空文件夹检测){Colors.RESET}")
        print(f" {Colors.DIM}说明: 此功能将生成一个删除空文件夹的 Shell 脚本。需要您在脚本运行环境中能访问到媒体库路径。{Colors.RESET}")
        
        path = self.get_user_input("请输入要扫描的根目录 (如 /mnt/media)").strip()
        if not path or not os.path.exists(path):
            print(f" {Colors.RED}❌ 路径无效或无法访问。{Colors.RESET}")
            self.pause()
            return

        print(f"\n 🔄 正在扫描空文件夹: {path} ...")
        empty_dirs = []
        for root, dirs, files in os.walk(path, topdown=False):
            if not files and not dirs:
                empty_dirs.append(root)
        
        if not empty_dirs:
            print(f" {Colors.GREEN}✅ 未发现空文件夹。{Colors.RESET}")
            self.pause()
            return

        print(f" {Colors.RED}⚠️  发现 {len(empty_dirs)} 个空文件夹。{Colors.RESET}")
        
        script_content = ["#!/bin/bash", "# Empty Folder Cleaner", f"# Generated: {datetime.now()}", ""]
        for d in empty_dirs:
            script_content.append(f'rmdir -v "{d}"')
        
        sh_name = f"clean_empty_dirs_{datetime.now().strftime('%H%M%S')}.sh"
        sh_path = os.path.join(self.data_dir, sh_name)
        try:
            with open(sh_path, 'w', encoding='utf-8') as f: f.write('\n'.join(script_content))
            os.chmod(sh_path, 0o755)
            print(f" 📄 清理脚本已生成: {Colors.BOLD}{sh_path}{Colors.RESET}")
            print(f" 👉 请检查后运行: {Colors.YELLOW}bash {sh_path}{Colors.RESET}")
        except: pass
        self.pause()

    # --- 功能 5: 媒体库透视分析 (分页版) ---
    def run_analytics(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}📊 正在分析媒体库...{Colors.RESET}")
        
        params = {'Recursive': 'true', 'IncludeItemTypes': 'Movie,Episode', 'Fields': 'MediaSources,Path'}
        # 使用分页获取所有数据
        all_items = self._fetch_all_items("/emby/Items", params, limit_per_page=10000)
        
        if not all_items: return

        stats = {
            'Resolution': defaultdict(int),
            'VideoCodec': defaultdict(int),
            'TotalCount': 0
        }
        
        print(f"\n 🔄 正在统计元数据...")
        
        for item in all_items:
            stats['TotalCount'] += 1
            sources = item.get('MediaSources', [])
            if not sources: continue
            
            for stream in sources[0].get('MediaStreams', []):
                if stream.get('Type') == 'Video':
                    w = stream.get('Width', 0)
                    if w >= 3800: res = "4K"
                    elif w >= 1900: res = "1080P"
                    elif w >= 1200: res = "720P"
                    else: res = "SD"
                    stats['Resolution'][res] += 1
                    codec = stream.get('Codec', 'Unknown').upper()
                    stats['VideoCodec'][codec] += 1
                    break
        
        print(f"\n {Colors.BOLD}=== 媒体库统计 (共 {stats['TotalCount']} 个视频) ==={Colors.RESET}")
        print(f"\n {Colors.CYAN}📺 分辨率分布:{Colors.RESET}")
        for k, v in sorted(stats['Resolution'].items(), key=lambda x: x[1], reverse=True):
            print(f"   {k:<10}: {v}")
            
        print(f"\n {Colors.MAGENTA}🎞️  编码分布:{Colors.RESET}")
        for k, v in sorted(stats['VideoCodec'].items(), key=lambda x: x[1], reverse=True):
            print(f"   {k:<10}: {v}")
            
        print("")
        self.pause()

    # --- 新增功能: 大文件筛选 (>20G) (分页版) ---
    def run_large_file_scanner(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🐘 正在筛选大文件 (>20GB)...{Colors.RESET}")
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: return
        
        target_libs = [l for l in libs.get('Items', []) if l.get('CollectionType') == 'movies']
        large_files = []
        THRESHOLD = 20 * (1024**3) 
        
        for lib in target_libs:
            lib_name = lib.get('Name')
            sys.stdout.write(f" ⏳ 扫描中: {lib_name}...\r"); sys.stdout.flush()
            
            params = {
                'ParentId': lib['Id'], 'Recursive': 'true', 'IncludeItemTypes': 'Movie',
                'Fields': 'Path,MediaSources,Size,ProductionYear'
            }
            items = self._fetch_all_items("/emby/Items", params)
            
            for item in items:
                size = item.get('Size', 0)
                if size > THRESHOLD:
                    large_files.append({'name': item.get('Name'), 'year': item.get('ProductionYear'), 'path': item.get('Path'), 'size': size, 'info': self.get_video_info(item)})
        
        if not large_files:
            print(f"\n {Colors.GREEN}✅ 未发现大于 20GB 的电影。{Colors.RESET}")
            self.pause(); return

        print(f"\n {Colors.RED}⚠️  发现 {len(large_files)} 个大于 20GB 的电影。{Colors.RESET}")
        
        report_lines = ["🎬 Emby 大文件筛选报告 (>20GB)", "=" * 80, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", f"阈值: 20 GB", "=" * 80, ""]
        large_files.sort(key=lambda x: x['size'], reverse=True)
        for f in large_files:
            size_str = self.format_size(f['size'])
            report_lines.append(f"[{size_str}] {f['name']} ({f['year']})")
            report_lines.append(f"  编码: {f['info']}")
            report_lines.append(f"  路径: {f['path']}")
            report_lines.append("-" * 40)
            
        report_name = f"large_files_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        report_path = os.path.join(self.data_dir, report_name)
        try:
            with open(report_path, 'w', encoding='utf-8') as f: f.write('\n'.join(report_lines))
            print(f" 📄 报告已生成: {Colors.BOLD}{report_path}{Colors.RESET}")
        except: pass
        self.pause()

    # --- 菜单 ---
    def main_menu(self):
        while True:
            self.clear_screen()
            self.print_banner()
            
            server_status = f"{Colors.GREEN}● 已连接{Colors.RESET}" if self.server_url else f"{Colors.RED}● 未配置{Colors.RESET}"
            print(f" {Colors.DIM}Server Status:{Colors.RESET} {server_status}   {Colors.DIM}Data Path:{Colors.RESET} {self.data_dir}\n")
            
            print(f" {Colors.BOLD}--- 核心维护 ---{Colors.RESET}")
            print(f" {Colors.CYAN}[1]{Colors.RESET} 🚀  重复文件扫描 (Dedupe)")
            print(f" {Colors.MAGENTA}[5]{Colors.RESET} 🔍  剧集缺集检查 (Missing)")
            
            print(f"\n {Colors.BOLD}--- 扩展工具 ---{Colors.RESET}")
            print(f" {Colors.BLUE}[6]{Colors.RESET} 🧹  垃圾清理 (Empty Folders)")
            print(f" {Colors.BLUE}[7]{Colors.RESET} 📊  媒体库透视 (Analytics)")
            print(f" {Colors.BLUE}[8]{Colors.RESET} 🐘  大文件筛选 (>20GB)") 
            
            print(f"\n {Colors.BOLD}--- 系统设置 ---{Colors.RESET}")
            print(f" {Colors.DIM}[2] 配置服务器   [3] 查看报告   [4] 重置数据   [0] 退出{Colors.RESET}")
            print("")
            
            c = self.get_user_input("请选择").strip()
            if c=='1': self.run_scanner() if self.server_url else print("请先配置") or self.pause()
            elif c=='2': self.init_config() if self.setup_wizard() else None
            elif c=='3': self.view_reports()
            elif c=='4': self.reset_config()
            elif c=='5': self.run_missing_check() if self.server_url else print("请先配置") or self.pause()
            elif c=='6': self.run_junk_cleaner()
            elif c=='7': self.run_analytics() if self.server_url else print("请先配置") or self.pause()
            elif c=='8': self.run_large_file_scanner() if self.server_url else print("请先配置") or self.pause()
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
        print(f"{Colors.YELLOW}📜 历史文件:{Colors.RESET}")
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
