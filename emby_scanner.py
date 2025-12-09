#!/usr/bin/env python3
"""
Emby媒体库重复检测工具 v4.0 Ultimate Edition (Dual Strategy + Web UI)
GitHub: https://github.com/huanhq99/emby-scanner
核心功能: 
1. 双重查重模式：
   - [1] 严格体积模式：仅当文件字节数完全一致时，才视为重复。(防误删，最安全)
   - [2] 同集优先模式：只要是【同一集】(SxxExx)，无论体积大小/文件名差异，均视为重复。(专治同集洗版)
2. 智能清理：
   - 剧集：同集模式下，自动保留【体积最大】且【文件名最长】的文件。
   - 电影：自动保留【文件名最长】的文件。
3. 功能全集：登录深度删除 + 手动精选 + 缺集检查 + 媒体库透视 + Web预览。
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse
import unicodedata
import re
import getpass
import threading
import webbrowser
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
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
        self.version = "4.0 Ultimate"
        self.github_url = "https://github.com/huanhq99/emby-scanner"
        self.server_url = ""
        self.api_key = ""
        self.headers = {}

        self.user_id = ""
        self.access_token = ""
        self.last_scan_results = {} 
        self.lib_types = {}
        self.scan_mode = "strict" # strict / loose
        
        # Web UI 相关
        self.web_data = {}  # 存储用于 Web 展示的数据
        self.web_server = None

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
        info_bar = f"{Colors.BOLD}   Emby Scanner {Colors.MAGENTA}v{self.version}{Colors.RESET} {Colors.DIM}|{Colors.RESET} Dual Strategy {Colors.DIM}|{Colors.RESET} All-in-One"
        print(logo)
        print(info_bar.center(80))
        print(f"\n{Colors.DIM}" + "—" * 65 + f"{Colors.RESET}\n")

    # --- 输入流 ---
    def _read_input(self):
        try:
            if not sys.stdin.isatty():
                with open('/dev/tty', 'r') as tty:
                    return tty.readline().strip()
            else:
                return sys.stdin.readline().strip()
        except Exception:
            return input().strip()

    def get_user_input(self, prompt, default=""):
        full_prompt = f" {Colors.CYAN}▶{Colors.RESET} {Colors.BOLD}{prompt}{Colors.RESET}"
        if default:
            full_prompt += f" [{default}]"
        full_prompt += ": "
        try:
            sys.stdout.write(full_prompt)
            sys.stdout.flush()
            user_input = self._read_input()
            return user_input if user_input else default
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)

    def pause(self):
        print(f"\n {Colors.DIM}Press {Colors.GREEN}[Enter]{Colors.RESET}{Colors.DIM} to continue...{Colors.RESET}", end="")
        sys.stdout.flush()
        try:
            if not sys.stdin.isatty():
                with open('/dev/tty', 'r') as tty: tty.readline()
            else: sys.stdin.readline()
        except: pass

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
                    if hasattr(e, 'code') and e.code != 404: pass 
                    return None
            except Exception:
                return None

    def _fetch_all_items(self, endpoint, params, limit_per_page=5000):
        all_items = []
        start_index = 0
        while True:
            params['StartIndex'] = start_index
            params['Limit'] = limit_per_page
            sys.stdout.write(f" 🔄 已读取: {len(all_items)} ...\r")
            sys.stdout.flush()
            data = self._request(endpoint, params)
            if not data or not data.get('Items'): break
            items = data.get('Items')
            if not items: break
            all_items.extend(items)
            if len(items) < limit_per_page: break
            start_index += len(items)
        return all_items

    def login_user(self):
        print(f"\n{Colors.YELLOW} 🔐  管理员登录 (User Login){Colors.RESET}")
        print(f" {Colors.DIM} 说明: 登录以获取 Session，触发 Emby 联动删除源文件。{Colors.RESET}")
        print(f"{Colors.DIM}" + "-" * 40 + f"{Colors.RESET}")
        
        username = self.get_user_input("用户名")
        print(f" {Colors.CYAN}▶{Colors.RESET} {Colors.BOLD}密码{Colors.RESET}: ", end="")
        sys.stdout.flush()
        try:
            if not sys.stdin.isatty():
                 with open('/dev/tty', 'r') as tty: password = tty.readline().strip()
            else:
                password = getpass.getpass("")
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
                    self.headers = {'X-Emby-Token': self.api_key, 'Content-Type': 'application/json', 'User-Agent': 'EmbyScannerPro/3.8'}
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

    def get_clean_info(self, info_str):
        return re.sub(r'\x1b\[[0-9;]*m', '', info_str)

    def get_display_width(self, text):
        width = 0
        for char in text:
            if unicodedata.east_asian_width(char) in ('F', 'W', 'A'): width += 2
            else: width += 1
        return width

    def pad_text(self, text, width):
        clean_text = self.get_clean_info(text)
        d_width = self.get_display_width(clean_text)
        padding = width - d_width
        if padding > 0: return text + " " * padding
        return text
    
    # --- 中文检测 ---
    def has_chinese_content(self, item):
        orig_lang = (item.get('OriginalLanguage') or '').lower()
        if orig_lang in ['zh', 'chi', 'zho', 'yue', 'wuu', 'cn', 'zh-cn', 'zh-tw']: return True
        locations = item.get('ProductionLocations', [])
        for loc in locations:
            if loc in ['China', 'Hong Kong', 'Taiwan', "People's Republic of China"]: return True
        media_sources = item.get('MediaSources', [])
        if media_sources:
            for source in media_sources:
                for stream in source.get('MediaStreams', []):
                    stype = stream.get('Type')
                    if stype in ['Subtitle', 'Audio']:
                        lang = (stream.get('Language') or '').lower()
                        title = (stream.get('Title') or '').lower()
                        display_title = (stream.get('DisplayTitle') or '').lower()
                        if lang in ['chi', 'zho', 'chn', 'zh', 'yue', 'wuu']: return True
                        keywords = ['chinese', '中文', '简', '繁', 'chs', 'cht', 'hanzi', '中字', 'zh-cn', 'zh-tw', '国语', '普通话', '粤语', 'cantonese', 'mandarin']
                        for kw in keywords:
                            if kw in title or kw in display_title: return True
        path = (item.get('Path') or '').lower()
        name = (item.get('Name') or '').lower()
        filename_keywords = ['国语', '中配', '台配', '粤语', 'chinese', 'cantonese', 'mandarin', 'cmn', 'dubbed']
        for kw in filename_keywords:
            if kw in path or kw in name: return True
        if re.search(r'[\u4e00-\u9fff]', name): return True 
        return False

    # --- v3.3 增强: 提取制作组信息 ---
    def get_video_info(self, item, source):
        info = []
        video_streams = [s for s in source.get('MediaStreams', []) if s.get('Type') == 'Video']
        if video_streams:
            v = video_streams[0]
            width = v.get('Width', 0)
            height = v.get('Height', 0)
            if width >= 3800 or height >= 2100: res = f"{Colors.MAGENTA}4K{Colors.RESET}"
            elif width >= 1900 or height >= 1000: res = f"{Colors.GREEN}1080P{Colors.RESET}"
            elif width >= 1200 or height >= 700: res = "720P"
            else: res = "SD"
            info.append(res)
            codec = v.get('Codec', '').upper()
            if codec: info.append(codec)
        if 'HDR' in str(video_streams).upper(): info.append(f"{Colors.YELLOW}HDR{Colors.RESET}")
        if 'DOLBY' in str(video_streams).upper() or 'DV' in str(video_streams).upper(): info.append(f"{Colors.CYAN}DV{Colors.RESET}")
        if self.has_chinese_content(item): info.append(f"{Colors.GREEN}中字/国语{Colors.RESET}")

        path = source.get('Path', '')
        if path:
            fname = os.path.basename(path)
            fname_no_ext = os.path.splitext(fname)[0]
            if '-' in fname_no_ext:
                group = fname_no_ext.split('-')[-1].strip()
                if 1 < len(group) < 15 and not group.isdigit() and not re.match(r'^S\d+E\d+', group, re.IGNORECASE):
                    info.append(f"{Colors.BLUE}{group}{Colors.RESET}")

        return " | ".join(info)

    # --- 功能 1: 重复检测 (v3.2 Smart TV Fix) ---
    def run_scanner(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🚀 正在扫描媒体库 (查重模式)...{Colors.RESET}\n")
        
        # 策略选择
        print(f" 请选择查重策略:")
        print(f"   {Colors.GREEN}[1] 严格体积模式{Colors.RESET} (推荐) -> 仅当字节完全一致时算重复 (防误删)")
        print(f"   {Colors.MAGENTA}[2] 同集优先模式{Colors.RESET} (洗版) -> 只要是同一集，不管大小都算重复")
        
        st = self.get_user_input("选择模式", default="1").strip()
        self.scan_mode = "loose" if st == '2' else "strict"
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: return

        target_libs = [l for l in libs.get('Items', []) if l.get('CollectionType') in ['movies', 'tvshows']]
        
        W_NAME = 22
        W_COUNT = 10 
        W_SIZE = 12
        W_DUP = 17
        W_STAT = 10

        header_line = f" {Colors.DIM}┌" + "─"*W_NAME + "┬" + "─"*W_COUNT + "┬" + "─"*W_SIZE + "┬" + "─"*W_DUP + "┬" + "─"*W_STAT + "┐" + f"{Colors.RESET}"
        title_line = f" {Colors.BOLD}│ {self.pad_text('媒体库名称', W_NAME)} │ {self.pad_text('文件数', W_COUNT)} │ {self.pad_text('总容量', W_SIZE)} │ {self.pad_text('冗余(可释放)', W_DUP)} │ {self.pad_text('状态', W_STAT)} │{Colors.RESET}"
        sep_line = f" {Colors.DIM}├" + "─"*W_NAME + "┼" + "─"*W_COUNT + "┼" + "─"*W_SIZE + "┼" + "─"*W_DUP + "┼" + "─"*W_STAT + "┤" + f"{Colors.RESET}"

        print(f"\n{header_line}\n{title_line}\n{sep_line}")

        self.last_scan_results = {}
        self.lib_types = {} 
        lib_summaries = [] 
        grand_total_bytes = 0
        grand_total_count = 0 

        for lib in target_libs:
            lib_name = lib.get('Name')
            ctype = lib.get('CollectionType')
            self.lib_types[lib_name] = ctype
            
            loading_txt = f"{Colors.DIM}Scanning...{Colors.RESET}"
            sys.stdout.write(f" │ {self.pad_text(lib_name, W_NAME)} │ {self.pad_text(loading_txt, W_COUNT)} ...\r")
            sys.stdout.flush()
            
            fetch_type = 'Episode' if ctype == 'tvshows' else 'Movie'
            params = {
                'ParentId': lib['Id'], 'Recursive': 'true', 'IncludeItemTypes': fetch_type,
                'Fields': 'Path,MediaSources,Size,ProductionYear,SeriesName,IndexNumber,ParentIndexNumber,OriginalLanguage,ProductionLocations,VideoRange,VideoRangeType'
            }
            
            items = self._fetch_all_items("/emby/Items", params)
            
            lib_total_bytes = 0
            lib_file_count = 0
            groups = defaultdict(list)
            
            for item in items:
                sources = item.get('MediaSources', [])
                if not sources: continue
                
                name = item.get('Name')
                year = item.get('ProductionYear')
                
                for source in sources:
                    size = source.get('Size')
                    if not size: continue
                    
                    lib_total_bytes += size
                    lib_file_count += 1
                    
                    path = source.get('Path')
                    
                    # 分组 Key 策略
                    if ctype == 'tvshows':
                        s_name = item.get('SeriesName', '')
                        s = item.get('ParentIndexNumber', -1)
                        e = item.get('IndexNumber', -1)
                        if s != -1 and e != -1: display_name = f"{s_name} S{s:02d}E{e:02d}"
                        else: display_name = name
                        
                        if self.scan_mode == "loose":
                            # 宽松模式：Key = 剧集ID信息 (同集即重复)
                            key = (s_name, s, e)
                        else:
                            # 严格模式：Key = 剧集ID + 体积 (同集且同大才重复)
                            key = (s_name, s, e, size)
                    else:
                        display_name = name
                        key = size # 电影纯体积查重
                    
                    groups[key].append({
                        'id': item.get('Id'), 
                        'media_source_id': source.get('Id'),
                        'name': display_name,
                        'path': path,
                        'size': size,
                        'info': self.get_video_info(item, source),
                        'year': year
                    })

            grand_total_bytes += lib_total_bytes
            grand_total_count += lib_file_count
            lib_summaries.append(f"{lib_name:<20} : {self.format_size(lib_total_bytes)} ({lib_file_count} files)")

            dups = {k: v for k, v in groups.items() if len(v) > 1}
            redundant = 0
            lib_dup_list = []

            if dups:
                for k, group in dups.items():
                    # 排序策略
                    # Loose: 剧集按Size排序保留最大；电影按Filename长度
                    # Strict: 都是同Size，按Filename长度
                    
                    if self.scan_mode == "loose" and ctype == 'tvshows':
                        # 保留体积最大的
                        sorted_group = sorted(group, key=lambda x: x['size'], reverse=True)
                    else:
                        # 保留文件名最长的
                        sorted_group = sorted(group, key=lambda x: len(os.path.basename(x['path'])), reverse=True)

                    drops = sorted_group[1:]
                    unique_paths = set(g['path'] for g in group)
                    if len(unique_paths) <= 1: continue

                    for d in drops: redundant += d['size']
                    lib_dup_list.append({'group_key': k, 'files': sorted_group})
            
            count_str = f"{lib_file_count}"
            size_str = self.format_size(lib_total_bytes)
            
            if lib_dup_list:
                self.last_scan_results[lib_name] = lib_dup_list
                status = f"{Colors.YELLOW}含重复{Colors.RESET}"
                dup_str = f"{Colors.RED}{self.format_size(redundant)}{Colors.RESET}"
            else:
                status = f"{Colors.GREEN}完美{Colors.RESET}"
                dup_str = f"{Colors.GREEN}0 B{Colors.RESET}"

            sys.stdout.write("\r" + " "*80 + "\r") 
            row_str = f" │ {self.pad_text(lib_name, W_NAME)} │ {self.pad_text(count_str, W_COUNT)} │ {self.pad_text(size_str, W_SIZE)} │ {self.pad_text(dup_str, W_DUP)} │ {self.pad_text(status, W_STAT)} │"
            print(row_str)

        print(f" {Colors.DIM}└" + "─"*W_NAME + "┴" + "─"*W_COUNT + "┴" + "─"*W_SIZE + "┴" + "─"*W_DUP + "┴" + "─"*W_STAT + "┘" + f"{Colors.RESET}")
        print(f"\n {Colors.CYAN}📊 媒体库总容量: {self.format_size(grand_total_bytes)}  {Colors.DIM}|{Colors.RESET}  {Colors.CYAN}总文件数: {grand_total_count}{Colors.RESET}")
        
        # 保存报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.data_dir, f"report_{timestamp}.txt")
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"Emby 重复检测报告 - {timestamp}\nStrategy: {self.scan_mode}\n{'='*60}\n")
                for summary in lib_summaries: f.write(f"  - {summary}\n")
                f.write(f"{'='*60}\n\n")
                for lib, groups in self.last_scan_results.items():
                     f.write(f"📁 媒体库: {lib}\n{'-'*40}\n")
                     for g in groups:
                         group_files = g['files']
                         if self.scan_mode == 'loose':
                             f.write(f"📦 重复组 (保留最大文件):\n")
                         else:
                             s_str = self.format_size(group_files[0]['size'])
                             f.write(f"📦 重复组 (单文件: {s_str}):\n")

                         for file in group_files:
                             clean_info = self.get_clean_info(file['info'])
                             fs = self.format_size(file['size'])
                             f.write(f"  - [{fs}] {file['name']} [{clean_info}]\n    路径: {file['path']}\n")
                         f.write("\n")
            print(f"\n 📄 查重报告已生成: {report_path}")
        except: pass

        if self.last_scan_results: self.manual_select_wizard()
        else:
            print(f"\n {Colors.GREEN}🎉 完美！未发现重复。{Colors.RESET}")
            self.pause()

    def manual_select_wizard(self):
        print(f"\n {Colors.YELLOW}💡 发现重复文件！进入清理模式{Colors.RESET}")
        libs = list(self.last_scan_results.keys())
        for i, lib in enumerate(libs): print(f"   [{i+1}] {lib} ({len(self.last_scan_results[lib])} 组)")
        choice = self.get_user_input("选择库序号 (0=退出)").strip()
        if not choice.isdigit() or int(choice) == 0: return
        target_lib = libs[int(choice)-1]
        groups = self.last_scan_results[target_lib]
        
        is_tv = (self.lib_types.get(target_lib) == 'tvshows')
        if self.scan_mode == 'loose' and is_tv: auto_policy = "保留 #1 最大体积"
        else: auto_policy = "保留 #1 长命名文件"

        self.clear_screen()
        print(f"{Colors.CYAN}>>> 正在处理: {target_lib}{Colors.RESET}")
        print(f" {Colors.BOLD}请选择处理模式:{Colors.RESET}")
        print(f"   {Colors.GREEN}[a] 批量自动模式{Colors.RESET} ({auto_policy})")
        print(f"   {Colors.YELLOW}[m] 手动逐个确认{Colors.RESET} (逐一查看每组详情)")
        
        mode = self.get_user_input("输入 a 或 m").strip().lower()
        final_delete_tasks = []
        
        if mode == 'a':
            print(f"\n {Colors.YELLOW}🔄 正在自动匹配最佳文件...{Colors.RESET}")
            for group in groups:
                files = group['files']
                # 已经排序好了 (在扫描阶段)
                keep_file = files[0]; del_files = files[1:]
                is_safe = True
                for f in del_files:
                    if f['id'] == keep_file['id']: is_safe = False 
                if is_safe: final_delete_tasks.extend(del_files)
                else: print(f" {Colors.RED}⚠️ 跳过一组 ID 冲突 (合并条目){Colors.RESET}")
        else:
            for idx, group in enumerate(groups):
                files = group['files']
                if 'size' in group: title_info = self.format_size(group['size']) # strict
                else: title_info = "同集不同源" # loose

                print(f"\n{Colors.YELLOW}--- [第 {idx+1}/{len(groups)} 组] {title_info} ---{Colors.RESET}")
                all_ids = [f['id'] for f in files]
                is_merged = len(set(all_ids)) == 1
                for i, f in enumerate(files):
                    fsize = self.format_size(f['size'])
                    print(f"  [{Colors.CYAN}{i+1}{Colors.RESET}] [{fsize}] {f['name']} [{f['info']}]")
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
            print("\n 无文件被选中。"); self.pause(); return

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
                sys.stdout.write(f"删除 {i+1}/{len(final_delete_tasks)}...\r"); sys.stdout.flush()
                if self._request(f"/Items/{item['id']}", method='DELETE', auth_header=auth_headers) is not None:
                    success += 1; time.sleep(1.5)
                else: print(f"\n❌ 失败: {item['name']}")
            print(f"\n {Colors.GREEN}✅ 完成！成功删除 {success} 个。{Colors.RESET}"); self.pause()

    # --- 其他功能 ---
    def run_missing_check(self):
        """缺集检查 - 智能版：支持多种检测模式"""
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🔍 检查缺集 (智能版)...{Colors.RESET}\n")
        
        # 选择检测模式
        print(f" 请选择检测模式:")
        print(f"   {Colors.GREEN}[1] 标准模式{Colors.RESET} - 检测从第1集到最大集号之间的缺集")
        print(f"   {Colors.CYAN}[2] 宽容模式{Colors.RESET} - 只检测连续序列中的断档 (忽略开头缺集)")
        print(f"   {Colors.MAGENTA}[3] 严格模式{Colors.RESET} - 只检测已有集数中间的缺集 (最精确)")
        
        mode = self.get_user_input("选择模式", default="1").strip()
        if mode == '2':
            check_mode = 'tolerant'
            mode_desc = "宽容模式"
        elif mode == '3':
            check_mode = 'strict'
            mode_desc = "严格模式"
        else:
            check_mode = 'standard'
            mode_desc = "标准模式"
        
        print(f"\n {Colors.DIM}使用 {mode_desc} 进行检测...{Colors.RESET}")
        
        start_time = time.time()
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: 
            print(f" {Colors.RED}❌ 无法获取媒体库信息。{Colors.RESET}")
            self.pause()
            return
        target_libs = [l for l in libs.get('Items', []) if l.get('CollectionType') == 'tvshows']
        if not target_libs: 
            print(f" {Colors.RED}❌ 无剧集库。{Colors.RESET}")
            self.pause()
            return
        
        print(f"\n {Colors.DIM}┌" + "─"*22 + "┬" + "─"*12 + "┬" + "─"*14 + "┬" + "─"*17 + "┬" + "─"*10 + "┐" + f"{Colors.RESET}")
        print(f" {Colors.BOLD}│ {'媒体库名称':<20} │ {'剧集数':<10} │ {'缺集剧数':<10} │ {'缺集总数':<13} │ {'状态':<8} │{Colors.RESET}")
        print(f" {Colors.DIM}├" + "─"*22 + "┼" + "─"*12 + "┼" + "─"*14 + "┼" + "─"*17 + "┼" + "─"*10 + "┤" + f"{Colors.RESET}")
        report_lines = ["🎬 Emby 缺集检测报告", "="*60, f"时间: {datetime.now()}", f"检测模式: {mode_desc}", ""]
        
        total_missing_episodes = 0  # 总缺集数
        total_series = 0            # 总剧集数（去重后的 Series）
        total_series_with_missing = 0  # 有缺集的剧数
        all_missing_details = []    # 存储所有缺集详情供 Web 使用
        
        for lib in target_libs:
            lib_name = lib.get('Name')
            sys.stdout.write(f" │ {self.pad_text(lib_name, 22)} │ 批量加载中...                                    \r")
            sys.stdout.flush()
            
            try:
                # 步骤1: 使用 TotalRecordCount 获取准确的 Series 数量（不获取全部数据）
                count_params = {
                    'ParentId': lib['Id'], 
                    'Recursive': 'true', 
                    'IncludeItemTypes': 'Series',
                    'Limit': 0  # 只获取数量，不获取数据
                }
                count_data = self._request("/emby/Items", count_params)
                if not count_data: 
                    print(f" │ {self.pad_text(lib_name, 22)} │ {self.pad_text('N/A', 12)} │ {self.pad_text('请求失败', 14)} │ {self.pad_text('-', 17)} │ {self.pad_text('❌', 10)} │")
                    continue
                
                # 使用 API 返回的 TotalRecordCount（与 Emby 界面一致）
                series_count = count_data.get('TotalRecordCount', 0)
                total_series += series_count
                
                sys.stdout.write(f" │ {self.pad_text(lib_name, 22)} │ 批量获取剧集...                                  \r")
                sys.stdout.flush()
                
                # 步骤2: 一次性批量获取该库下所有 Episode（关键优化！）
                # Episode 自带 SeriesName，不需要单独获取 Series 列表
                ep_params = {
                    'ParentId': lib['Id'], 
                    'Recursive': 'true', 
                    'IncludeItemTypes': 'Episode', 
                    'Fields': 'SeriesId,SeriesName,ParentIndexNumber,IndexNumber',
                    'Limit': 500000
                }
                all_episodes = self._fetch_all_items("/emby/Items", ep_params, limit_per_page=10000)
                
                sys.stdout.write(f" │ {self.pad_text(lib_name, 22)} │ 分析 {len(all_episodes)} 集...                           \r")
                sys.stdout.flush()
                
                # 步骤3: 按 SeriesId 分组，同时收集 SeriesName
                series_episodes = defaultdict(lambda: defaultdict(list))
                series_names = {}  # SeriesId -> SeriesName 映射
                for ep in all_episodes:
                    series_id = ep.get('SeriesId')
                    if not series_id:
                        continue
                    # 收集 series name
                    if series_id not in series_names:
                        series_names[series_id] = ep.get('SeriesName', 'Unknown')
                    season = ep.get('ParentIndexNumber', 1)
                    episode = ep.get('IndexNumber')
                    if episode is not None:
                        series_episodes[series_id][season].append(episode)
                
                # 步骤4: 分析缺集（根据模式）
                lib_missing_episodes = 0  # 该库缺集总数
                lib_series_with_missing = 0  # 该库有缺集的剧数
                lib_report_buffer = []
                
                for series_id, seasons in series_episodes.items():
                    series_name = series_names.get(series_id, 'Unknown')
                    series_missing = []
                    series_missing_count = 0
                    series_missing_details = []
                    
                    for s in sorted(seasons.keys()):
                        if s == 0 or s is None:  # 跳过特别篇
                            continue
                        eps = sorted(set(seasons[s]))
                        if not eps:
                            continue
                        
                        missing = []
                        if check_mode == 'standard':
                            # 标准模式：检测从1到最大集号之间的所有缺集
                            max_ep = eps[-1]
                            missing = sorted(list(set(range(1, max_ep + 1)) - set(eps)))
                        elif check_mode == 'tolerant':
                            # 宽容模式：从第一个已有集开始检测到最后一个已有集
                            min_ep = eps[0]
                            max_ep = eps[-1]
                            missing = sorted(list(set(range(min_ep, max_ep + 1)) - set(eps)))
                        elif check_mode == 'strict':
                            # 严格模式：只检测连续集数中间的断档
                            # 例如：有 1,2,3,5,6 则只报告缺少 4
                            for i in range(len(eps) - 1):
                                gap_start = eps[i] + 1
                                gap_end = eps[i + 1]
                                if gap_end > gap_start:
                                    missing.extend(range(gap_start, gap_end))
                        
                        if missing:
                            series_missing_count += len(missing)
                            series_missing.append(f"  - S{s}: 缺 [{', '.join(map(str, missing))}]")
                            series_missing_details.append({'season': s, 'missing': missing})
                    
                    if series_missing:
                        lib_missing_episodes += series_missing_count
                        lib_series_with_missing += 1
                        lib_report_buffer.append(f"📺 {series_name} (缺 {series_missing_count} 集)")
                        all_missing_details.append({
                            'series': series_name,
                            'lib': lib_name,
                            'missing_count': series_missing_count,
                            'details': series_missing_details
                        })
                        lib_report_buffer.extend(series_missing)
                        lib_report_buffer.append("")
                
                total_missing_episodes += lib_missing_episodes
                total_series_with_missing += lib_series_with_missing
                
                if lib_missing_episodes > 0:
                    report_lines.append(f"📁 {lib_name} ({lib_series_with_missing} 部剧缺集，共缺 {lib_missing_episodes} 集)")
                    report_lines.extend(lib_report_buffer)
                    report_lines.append("-" * 40)
                
                status = f"{Colors.YELLOW}有缺集{Colors.RESET}" if lib_missing_episodes > 0 else f"{Colors.GREEN}完整{Colors.RESET}"
                missing_series_str = f"{Colors.RED}{lib_series_with_missing} 部{Colors.RESET}" if lib_series_with_missing > 0 else "0"
                missing_ep_str = f"{Colors.RED}{lib_missing_episodes} 集{Colors.RESET}" if lib_missing_episodes > 0 else "0"
                
                sys.stdout.write("\r" + " " * 100 + "\r")
                row_str = f" │ {self.pad_text(lib_name, 22)} │ {self.pad_text(str(series_count), 12)} │ {self.pad_text(missing_series_str, 14)} │ {self.pad_text(missing_ep_str, 17)} │ {self.pad_text(status, 10)} │"
                print(row_str)
                
            except Exception as e:
                sys.stdout.write("\r" + " " * 100 + "\r")
                print(f" │ {self.pad_text(lib_name, 22)} │ {self.pad_text('错误', 12)} │ {self.pad_text('-', 14)} │ {self.pad_text(str(e)[:15], 17)} │ {self.pad_text('❌', 10)} │")
                continue
        
        print(f" {Colors.DIM}└" + "─"*22 + "┴" + "─"*12 + "┴" + "─"*14 + "┴" + "─"*17 + "┴" + "─"*10 + "┘" + f"{Colors.RESET}")
        
        elapsed = time.time() - start_time
        print(f"\n {Colors.CYAN}📊 汇总: {total_series} 部剧集，{Colors.RED}{total_series_with_missing}{Colors.RESET}{Colors.CYAN} 部有缺集，共缺 {Colors.RED}{total_missing_episodes}{Colors.RESET}{Colors.CYAN} 集{Colors.RESET}")
        print(f" {Colors.DIM}⏱️  耗时: {elapsed:.2f} 秒{Colors.RESET}")
        
        # 存储数据供 Web 使用
        self.web_data['missing'] = {
            'total_series': total_series,
            'total_series_with_missing': total_series_with_missing,
            'total_missing_episodes': total_missing_episodes,
            'details': all_missing_details,
            'elapsed': elapsed
        }
        
        try:
            report_path = os.path.join(self.data_dir, f"missing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            with open(report_path, 'w', encoding='utf-8') as f: 
                f.write('\n'.join(report_lines))
                f.write(f"\n\n{'='*60}\n")
                f.write(f"汇总: {total_series} 部剧集\n")
                f.write(f"缺集剧数: {total_series_with_missing} 部\n")
                f.write(f"缺集总数: {total_missing_episodes} 集\n")
                f.write(f"耗时: {elapsed:.2f} 秒\n")
            print(f" 📄 缺集报告已保存: {report_path}")
        except Exception as e:
            print(f" {Colors.RED}保存报告失败: {e}{Colors.RESET}")
        
        # 提供 Web 预览选项
        if total_series_with_missing > 0:
            preview = self.get_user_input("是否在浏览器中预览? (y/n)", default="n").strip().lower()
            if preview == 'y':
                self.start_web_preview('missing')
        
        self.pause()

    def run_junk_cleaner(self):
        self.clear_screen(); self.print_banner(); print(f" {Colors.YELLOW}🧹 垃圾清理...{Colors.RESET}")
        path = self.get_user_input("扫描路径").strip()
        if not path or not os.path.exists(path): print("❌ 无效"); self.pause(); return
        print("\n 🔄 扫描中..."); empty_dirs = []
        for root, dirs, files in os.walk(path, topdown=False):
            if not files and not dirs: empty_dirs.append(root)
        if not empty_dirs: print(f" {Colors.GREEN}✅ 无空文件夹。{Colors.RESET}"); self.pause(); return
        print(f" {Colors.RED}⚠️  发现 {len(empty_dirs)} 个空文件夹。{Colors.RESET}")
        sh_path = os.path.join(self.data_dir, f"clean_empty_{datetime.now().strftime('%H%M%S')}.sh")
        with open(sh_path, 'w') as f: f.write('\n'.join([f'rmdir -v "{d}"' for d in empty_dirs]))
        print(f" 📄 脚本已生成: {sh_path}"); self.pause()

    def run_analytics(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}📊 媒体库透视 (全面增强版)...{Colors.RESET}")
        
        # 获取基础统计
        print(f"\n {Colors.DIM}正在获取媒体库概览...{Colors.RESET}")
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs:
            print(f" {Colors.RED}❌ 无法获取媒体库信息。{Colors.RESET}")
            self.pause()
            return
        
        # 统计各类型数量
        lib_stats = []
        for lib in libs.get('Items', []):
            lib_name = lib.get('Name')
            lib_id = lib.get('Id')
            ctype = lib.get('CollectionType', 'unknown')
            
            # 获取该库的统计
            count_params = {'ParentId': lib_id, 'Recursive': 'true', 'Limit': 0}
            if ctype == 'movies':
                count_params['IncludeItemTypes'] = 'Movie'
            elif ctype == 'tvshows':
                count_params['IncludeItemTypes'] = 'Series'
            else:
                continue
            
            count_data = self._request("/emby/Items", count_params)
            count = count_data.get('TotalRecordCount', 0) if count_data else 0
            lib_stats.append({'name': lib_name, 'type': ctype, 'count': count})
        
        params = {'Recursive': 'true', 'IncludeItemTypes': 'Movie,Episode', 'Fields': 'MediaSources,Path,Container,Size,RunTimeTicks'}
        items = self._fetch_all_items("/emby/Items", params, 10000)
        if not items: 
            print(f" {Colors.RED}❌ 无法获取媒体信息。{Colors.RESET}")
            self.pause()
            return
        
        stats = {
            'Resolution': defaultdict(int), 
            'Codec': defaultdict(int),
            'AudioCodec': defaultdict(int),
            'Container': defaultdict(int),
            'SourceType': defaultdict(int), 
            'DynamicRange': defaultdict(int), 
            'ReleaseGroup': defaultdict(int),
            'FrameRate': defaultdict(int),
            'BitDepth': defaultdict(int),
            'AudioChannels': defaultdict(int),
            'TotalCount': 0,
            'TotalSize': 0,
            'TotalDuration': 0,
            'Movies': 0,
            'Episodes': 0,
            'SizeByRes': defaultdict(int),
        }
        
        print(f" 🔄 分析 {len(items)} 个文件...")
        for item in items:
            stats['TotalCount'] += 1
            item_type = item.get('Type', '')
            if item_type == 'Movie':
                stats['Movies'] += 1
            else:
                stats['Episodes'] += 1
            
            sources = item.get('MediaSources', [])
            if not sources: continue
            source = sources[0]
            path = item.get('Path', '').upper()
            
            # 统计大小
            size = source.get('Size', 0)
            if size: stats['TotalSize'] += size
            
            # 统计时长
            runtime = item.get('RunTimeTicks', 0)
            if runtime: stats['TotalDuration'] += runtime
            
            # 统计容器格式
            container = source.get('Container', 'unknown').upper()
            stats['Container'][container] += 1
            
            # 统计来源类型
            if 'REMUX' in path: 
                stats['SourceType']['Remux'] += 1
            elif 'BLURAY' in path or 'BLU-RAY' in path: 
                stats['SourceType']['BluRay'] += 1
            elif 'WEB-DL' in path or 'WEBDL' in path: 
                stats['SourceType']['WEB-DL'] += 1
            elif 'WEBRIP' in path: 
                stats['SourceType']['WEBRip'] += 1
            elif 'HDTV' in path: 
                stats['SourceType']['HDTV'] += 1
            elif 'DVDRIP' in path or 'DVD' in path:
                stats['SourceType']['DVDRip'] += 1
            else: 
                stats['SourceType']['Other'] += 1
            
            # 统计制作组
            try:
                fname = os.path.basename(item.get('Path', ''))
                if '-' in fname:
                    group = os.path.splitext(fname)[0].split('-')[-1].strip()
                    if 1 < len(group) < 15 and not group.isdigit():
                        stats['ReleaseGroup'][group] += 1
            except Exception:
                pass
            
            # 统计视频流信息
            for stream in source.get('MediaStreams', []):
                if stream.get('Type') == 'Video':
                    w = stream.get('Width', 0)
                    h = stream.get('Height', 0)
                    if w >= 3800 or h >= 2100: 
                        res = "4K"
                    elif w >= 1900 or h >= 1000: 
                        res = "1080P"
                    elif w >= 1200 or h >= 700: 
                        res = "720P"
                    elif w >= 640:
                        res = "480P"
                    else: 
                        res = "SD"
                    stats['Resolution'][res] += 1
                    stats['SizeByRes'][res] += size
                    
                    # 编码
                    codec = stream.get('Codec', 'unknown').upper()
                    if codec in ['HEVC', 'H265']: 
                        stats['Codec']['HEVC/H.265'] += 1
                    elif codec in ['AVC', 'H264']: 
                        stats['Codec']['AVC/H.264'] += 1
                    elif codec in ['AV1']: 
                        stats['Codec']['AV1'] += 1
                    elif codec in ['VP9']:
                        stats['Codec']['VP9'] += 1
                    elif codec in ['MPEG4', 'MPEG2VIDEO', 'MPEG2']:
                        stats['Codec']['MPEG'] += 1
                    else: 
                        stats['Codec']['Other'] += 1
                    
                    # 帧率
                    fps = stream.get('RealFrameRate') or stream.get('AverageFrameRate', 0)
                    if fps:
                        if fps >= 59:
                            stats['FrameRate']['60fps'] += 1
                        elif fps >= 49:
                            stats['FrameRate']['50fps'] += 1
                        elif fps >= 29:
                            stats['FrameRate']['30fps'] += 1
                        elif fps >= 23:
                            stats['FrameRate']['24fps'] += 1
                        else:
                            stats['FrameRate']['其他'] += 1
                    
                    # 位深
                    bit_depth = stream.get('BitDepth', 8)
                    if bit_depth >= 10:
                        stats['BitDepth']['10bit+'] += 1
                    else:
                        stats['BitDepth']['8bit'] += 1
                    
                    # HDR
                    vr = stream.get('VideoRange', '').upper()
                    vrt = stream.get('VideoRangeType', '').upper()
                    if 'DOLBY' in vrt or 'DV' in vrt: 
                        stats['DynamicRange']['Dolby Vision'] += 1
                    elif 'HDR10+' in vrt or 'HDR10PLUS' in vrt: 
                        stats['DynamicRange']['HDR10+'] += 1
                    elif 'HDR' in vr or 'HDR10' in vrt: 
                        stats['DynamicRange']['HDR10'] += 1
                    elif 'HLG' in vrt:
                        stats['DynamicRange']['HLG'] += 1
                    else: 
                        stats['DynamicRange']['SDR'] += 1
                    break
            
            # 统计音频流信息
            for stream in source.get('MediaStreams', []):
                if stream.get('Type') == 'Audio':
                    acodec = stream.get('Codec', 'unknown').upper()
                    if 'TRUEHD' in acodec or 'ATMOS' in acodec:
                        stats['AudioCodec']['TrueHD/Atmos'] += 1
                    elif 'DTS' in acodec:
                        if 'HD' in acodec or 'MA' in acodec:
                            stats['AudioCodec']['DTS-HD MA'] += 1
                        else:
                            stats['AudioCodec']['DTS'] += 1
                    elif 'AC3' in acodec or 'EAC3' in acodec:
                        stats['AudioCodec']['AC3/EAC3'] += 1
                    elif 'AAC' in acodec:
                        stats['AudioCodec']['AAC'] += 1
                    elif 'FLAC' in acodec:
                        stats['AudioCodec']['FLAC'] += 1
                    else:
                        stats['AudioCodec']['Other'] += 1
                    
                    # 声道
                    channels = stream.get('Channels', 2)
                    if channels >= 8:
                        stats['AudioChannels']['7.1'] += 1
                    elif channels >= 6:
                        stats['AudioChannels']['5.1'] += 1
                    elif channels >= 2:
                        stats['AudioChannels']['立体声'] += 1
                    else:
                        stats['AudioChannels']['单声道'] += 1
                    break
        
        # 存储数据供 Web 使用
        self.web_data['analytics'] = stats
        self.web_data['lib_stats'] = lib_stats
        
        # 显示统计结果
        print(f"\n {Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f" {Colors.CYAN}📊 媒体库全面统计报告{Colors.RESET}")
        print(f" {Colors.BOLD}{'='*60}{Colors.RESET}\n")
        
        # 媒体库概览
        print(f" {Colors.BOLD}📁 媒体库概览:{Colors.RESET}")
        for lib in lib_stats:
            icon = "🎬" if lib['type'] == 'movies' else "📺"
            print(f"   {icon} {lib['name']}: {Colors.GREEN}{lib['count']}{Colors.RESET}")
        
        # 总览
        total_hours = stats['TotalDuration'] / (10000000 * 3600) if stats['TotalDuration'] else 0
        print(f"\n {Colors.BOLD}📈 总览:{Colors.RESET}")
        print(f"   总文件数: {Colors.GREEN}{stats['TotalCount']}{Colors.RESET} (电影 {stats['Movies']}, 剧集 {stats['Episodes']})")
        print(f"   总容量: {Colors.GREEN}{self.format_size(stats['TotalSize'])}{Colors.RESET}")
        print(f"   总时长: {Colors.GREEN}{total_hours:.1f} 小时{Colors.RESET} ({total_hours/24:.1f} 天)")
        
        # 分辨率分布（带容量）
        print(f"\n {Colors.BOLD}🖥️  分辨率分布:{Colors.RESET}")
        for res in ['4K', '1080P', '720P', '480P', 'SD']:
            count = stats['Resolution'].get(res, 0)
            size = stats['SizeByRes'].get(res, 0)
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
            color = Colors.MAGENTA if res == '4K' else Colors.GREEN if res == '1080P' else Colors.YELLOW if res == '720P' else Colors.DIM
            print(f"   {color}{res:>6}{Colors.RESET}: {bar} {count:>6} ({pct:>5.1f}%) | {self.format_size(size)}")
        
        # 视频编码
        print(f"\n {Colors.BOLD}🎞️  视频编码:{Colors.RESET}")
        for codec, count in sorted(stats['Codec'].items(), key=lambda x: -x[1]):
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            print(f"   {codec:>12}: {count:>6} ({pct:>5.1f}%)")
        
        # 动态范围
        print(f"\n {Colors.BOLD}🌈 动态范围:{Colors.RESET}")
        for dr in ['Dolby Vision', 'HDR10+', 'HDR10', 'HLG', 'SDR']:
            count = stats['DynamicRange'].get(dr, 0)
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            color = Colors.CYAN if 'Dolby' in dr else Colors.YELLOW if 'HDR' in dr else Colors.DIM
            print(f"   {color}{dr:>14}{Colors.RESET}: {count:>6} ({pct:>5.1f}%)")
        
        # 位深和帧率
        print(f"\n {Colors.BOLD}🎨 位深 & 帧率:{Colors.RESET}")
        for bd, count in sorted(stats['BitDepth'].items(), key=lambda x: -x[1]):
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            color = Colors.CYAN if '10' in bd else Colors.RESET
            print(f"   {color}{bd:>8}{Colors.RESET}: {count:>6} ({pct:>5.1f}%)")
        for fr, count in sorted(stats['FrameRate'].items(), key=lambda x: -x[1]):
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            color = Colors.GREEN if '60' in fr or '50' in fr else Colors.RESET
            print(f"   {color}{fr:>8}{Colors.RESET}: {count:>6} ({pct:>5.1f}%)")
        
        # 音频编码
        print(f"\n {Colors.BOLD}🔊 音频编码:{Colors.RESET}")
        for ac, count in sorted(stats['AudioCodec'].items(), key=lambda x: -x[1])[:6]:
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            color = Colors.MAGENTA if 'Atmos' in ac or 'TrueHD' in ac else Colors.CYAN if 'DTS' in ac else Colors.RESET
            print(f"   {color}{ac:>14}{Colors.RESET}: {count:>6} ({pct:>5.1f}%)")
        
        # 声道
        print(f"\n {Colors.BOLD}🎧 声道分布:{Colors.RESET}")
        for ch in ['7.1', '5.1', '立体声', '单声道']:
            count = stats['AudioChannels'].get(ch, 0)
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            print(f"   {ch:>8}: {count:>6} ({pct:>5.1f}%)")
        
        # 来源类型
        print(f"\n {Colors.BOLD}📀 来源类型:{Colors.RESET}")
        for src, count in sorted(stats['SourceType'].items(), key=lambda x: -x[1])[:6]:
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            color = Colors.MAGENTA if src == 'Remux' else Colors.GREEN if 'WEB' in src else Colors.RESET
            print(f"   {color}{src:>12}{Colors.RESET}: {count:>6} ({pct:>5.1f}%)")
        
        # 容器格式
        print(f"\n {Colors.BOLD}📦 容器格式:{Colors.RESET}")
        for fmt, count in sorted(stats['Container'].items(), key=lambda x: -x[1])[:5]:
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            print(f"   {fmt:>12}: {count:>6} ({pct:>5.1f}%)")
        
        # TOP 制作组
        if stats['ReleaseGroup']:
            print(f"\n {Colors.BOLD}👥 TOP 15 制作组:{Colors.RESET}")
            for group, count in sorted(stats['ReleaseGroup'].items(), key=lambda x: -x[1])[:15]:
                print(f"   {Colors.BLUE}{group:>18}{Colors.RESET}: {count}")
        
        print(f"\n {Colors.BOLD}{'='*60}{Colors.RESET}")
        
        # 提供 Web 预览选项
        preview = self.get_user_input("是否在浏览器中预览? (y/n)", default="n").strip().lower()
        if preview == 'y':
            self.start_web_preview('analytics')
        
        self.pause()

    def run_large_file_scanner(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🐘 大文件筛选 (增强版)...{Colors.RESET}\n")
        
        # 选择模式
        print(f" 请选择筛选模式:")
        print(f"   {Colors.GREEN}[1] 按大小筛选{Colors.RESET} - 大于指定 GB 的文件")
        print(f"   {Colors.CYAN}[2] TOP N 最大文件{Colors.RESET} - 显示最大的 N 个文件")
        print(f"   {Colors.MAGENTA}[3] 低质量大文件{Colors.RESET} - SD/720P 但大于 5GB 的文件 (可能需要压缩)")
        
        mode = self.get_user_input("选择模式", default="1").strip()
        
        if mode == '2':
            top_n = int(self.get_user_input("显示前多少个?", default="50").strip() or 50)
            threshold_bytes = 0
            scan_mode = 'topn'
        elif mode == '3':
            threshold_bytes = 5 * (1024**3)  # 5GB
            scan_mode = 'lowquality'
        else:
            threshold_input = self.get_user_input("文件大小阈值 (GB)", default="20").strip()
            try:
                threshold_gb = float(threshold_input)
            except ValueError:
                threshold_gb = 20
            threshold_bytes = threshold_gb * (1024**3)
            scan_mode = 'size'
            top_n = 0
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: 
            print(f" {Colors.RED}❌ 无法获取媒体库信息。{Colors.RESET}")
            self.pause()
            return
        
        # 同时扫描电影和剧集
        targets = [l for l in libs.get('Items', []) if l.get('CollectionType') in ['movies', 'tvshows']]
        large_files = []
        
        for lib in targets:
            lib_name = lib.get('Name')
            sys.stdout.write(f" ⏳ 扫描: {lib_name}...                    \r")
            sys.stdout.flush()
            
            ctype = lib.get('CollectionType')
            item_type = 'Episode' if ctype == 'tvshows' else 'Movie'
            params = {
                'ParentId': lib['Id'], 
                'Recursive': 'true', 
                'IncludeItemTypes': item_type, 
                'Fields': 'Path,MediaSources,Size,SeriesName,RunTimeTicks'
            }
            items = self._fetch_all_items("/emby/Items", params)
            
            for item in items:
                sources = item.get('MediaSources', [])
                for source in sources:
                    size = source.get('Size', 0)
                    if not size:
                        continue
                    
                    # 获取分辨率信息
                    resolution = "Unknown"
                    codec = "Unknown"
                    for stream in source.get('MediaStreams', []):
                        if stream.get('Type') == 'Video':
                            w = stream.get('Width', 0)
                            if w >= 3800: resolution = "4K"
                            elif w >= 1900: resolution = "1080P"
                            elif w >= 1200: resolution = "720P"
                            else: resolution = "SD"
                            codec = stream.get('Codec', 'unknown').upper()
                            break
                    
                    # 根据模式决定是否添加
                    should_add = False
                    if scan_mode == 'size' and size > threshold_bytes:
                        should_add = True
                    elif scan_mode == 'topn':
                        should_add = True
                    elif scan_mode == 'lowquality' and size > threshold_bytes and resolution in ['SD', '720P']:
                        should_add = True
                    
                    if should_add:
                        display_name = item.get('Name', 'Unknown')
                        if ctype == 'tvshows':
                            series = item.get('SeriesName', '')
                            if series:
                                display_name = f"{series} - {display_name}"
                        
                        # 计算比特率
                        runtime = item.get('RunTimeTicks', 0)
                        bitrate = 0
                        if runtime > 0:
                            duration_sec = runtime / 10000000
                            bitrate = (size * 8) / duration_sec / 1000000  # Mbps
                        
                        large_files.append({
                            'id': item.get('Id'),
                            'name': display_name,
                            'size': size,
                            'path': source.get('Path', ''),
                            'lib': lib_name,
                            'resolution': resolution,
                            'codec': codec,
                            'bitrate': bitrate,
                            'type': 'Episode' if ctype == 'tvshows' else 'Movie'
                        })
        
        sys.stdout.write("\r" + " " * 60 + "\r")
        
        # 按大小排序
        large_files.sort(key=lambda x: x['size'], reverse=True)
        
        # TOP N 模式截取
        if scan_mode == 'topn':
            large_files = large_files[:top_n]
        
        if not large_files:
            print(f" {Colors.GREEN}✅ 未发现符合条件的文件。{Colors.RESET}")
            self.pause()
            return
        
        total_size = sum(f['size'] for f in large_files)
        
        # 存储供 Web 使用
        self.web_data['large_files'] = large_files
        
        # 统计信息
        print(f"\n {Colors.RED}⚠️  发现 {len(large_files)} 个文件，共占用 {self.format_size(total_size)}{Colors.RESET}")
        
        # 按分辨率统计
        res_stats = defaultdict(lambda: {'count': 0, 'size': 0})
        for f in large_files:
            res_stats[f['resolution']]['count'] += 1
            res_stats[f['resolution']]['size'] += f['size']
        
        print(f"\n {Colors.BOLD}按分辨率统计:{Colors.RESET}")
        for res in ['4K', '1080P', '720P', 'SD', 'Unknown']:
            if res in res_stats:
                print(f"   {res:>6}: {res_stats[res]['count']:>4} 个, {self.format_size(res_stats[res]['size'])}")
        
        # 显示列表
        print(f"\n {Colors.BOLD}{'#':>3} | {'大小':>10} | {'码率':>8} | {'分辨率':>6} | {'类型':>6} | 名称{Colors.RESET}")
        print(f" {Colors.DIM}{'-'*80}{Colors.RESET}")
        
        for i, f in enumerate(large_files[:50]):
            size_str = self.format_size(f['size'])
            bitrate_str = f"{f['bitrate']:.1f}M" if f['bitrate'] else "N/A"
            res_color = Colors.MAGENTA if f['resolution'] == '4K' else Colors.GREEN if f['resolution'] == '1080P' else Colors.YELLOW
            name_short = f['name'][:30] + '...' if len(f['name']) > 33 else f['name']
            ftype = "剧集" if f['type'] == 'Episode' else "电影"
            print(f" {Colors.CYAN}{i+1:>3}{Colors.RESET} | {Colors.RED}{size_str:>10}{Colors.RESET} | {bitrate_str:>8} | {res_color}{f['resolution']:>6}{Colors.RESET} | {ftype:>6} | {name_short}")
        
        if len(large_files) > 50:
            print(f"\n {Colors.DIM}... 还有 {len(large_files) - 50} 个文件未显示{Colors.RESET}")
        
        # 保存报告
        report_path = os.path.join(self.data_dir, f"large_files_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"🐘 大文件报告\n{'='*60}\n")
                f.write(f"时间: {datetime.now()}\n")
                f.write(f"文件数: {len(large_files)}, 总大小: {self.format_size(total_size)}\n\n")
                f.write(f"按分辨率统计:\n")
                for res in ['4K', '1080P', '720P', 'SD']:
                    if res in res_stats:
                        f.write(f"  {res}: {res_stats[res]['count']} 个, {self.format_size(res_stats[res]['size'])}\n")
                f.write(f"\n{'='*60}\n详细列表:\n\n")
                for item in large_files:
                    bitrate_str = f"{item['bitrate']:.1f} Mbps" if item.get('bitrate') else "N/A"
                    f.write(f"[{self.format_size(item['size'])}] [{item.get('resolution', 'N/A')}] [{bitrate_str}] {item['name']}\n")
                    f.write(f"  路径: {item['path']}\n\n")
            print(f"\n 📄 报告已保存: {report_path}")
        except Exception as e:
            print(f" {Colors.RED}保存报告失败: {e}{Colors.RESET}")
        
        # 提供 Web 预览选项
        preview = self.get_user_input("是否在浏览器中预览? (y/n)", default="n").strip().lower()
        if preview == 'y':
            self.start_web_preview('large_files')
        
        self.pause()

    def run_no_chinese_scanner(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🈯 无中字检测 (增强版)...{Colors.RESET}\n")
        print(f" {Colors.DIM}说明: 检测没有中文字幕/音轨的资源{Colors.RESET}\n")
        
        # 选择扫描范围
        print(f" 请选择扫描范围:")
        print(f"   [1] 仅电影")
        print(f"   [2] 仅剧集")
        print(f"   [3] 全部")
        scope = self.get_user_input("选择", default="1").strip()
        
        # 选择检测模式
        print(f"\n 请选择检测内容:")
        print(f"   {Colors.GREEN}[1] 无中文字幕{Colors.RESET} - 检测没有中文字幕的资源")
        print(f"   {Colors.CYAN}[2] 无中文音轨{Colors.RESET} - 检测没有中文配音的资源")
        print(f"   {Colors.MAGENTA}[3] 两者都无{Colors.RESET} - 检测既无中文字幕也无中文音轨的资源")
        detect_mode = self.get_user_input("选择", default="1").strip()
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: 
            print(f" {Colors.RED}❌ 无法获取媒体库信息。{Colors.RESET}")
            self.pause()
            return
        
        if scope == '1':
            targets = [l for l in libs.get('Items', []) if l.get('CollectionType') == 'movies']
            item_types = 'Movie'
        elif scope == '2':
            targets = [l for l in libs.get('Items', []) if l.get('CollectionType') == 'tvshows']
            item_types = 'Episode'
        else:
            targets = [l for l in libs.get('Items', []) if l.get('CollectionType') in ['movies', 'tvshows']]
            item_types = 'Movie,Episode'
        
        no_cn_items = []
        total_scanned = 0
        
        for lib in targets:
            lib_name = lib.get('Name')
            sys.stdout.write(f" ⏳ 扫描: {lib_name}...                    \r")
            sys.stdout.flush()
            
            params = {
                'ParentId': lib['Id'], 
                'Recursive': 'true', 
                'IncludeItemTypes': item_types, 
                'Fields': 'Path,MediaSources,Name,OriginalLanguage,ProductionLocations,SeriesName,CommunityRating'
            }
            items = self._fetch_all_items("/emby/Items", params, 5000)
            total_scanned += len(items)
            
            for item in items:
                # 根据检测模式进行检查
                has_cn_sub = False
                has_cn_audio = False
                
                media_sources = item.get('MediaSources', [])
                if media_sources:
                    for source in media_sources:
                        for stream in source.get('MediaStreams', []):
                            stype = stream.get('Type')
                            lang = (stream.get('Language') or '').lower()
                            title = (stream.get('Title') or '').lower()
                            display_title = (stream.get('DisplayTitle') or '').lower()
                            
                            is_chinese = lang in ['chi', 'zho', 'chn', 'zh', 'yue', 'wuu']
                            cn_keywords = ['chinese', '中文', '简', '繁', 'chs', 'cht', 'hanzi', '中字', 'zh-cn', 'zh-tw', '国语', '普通话', '粤语', 'cantonese', 'mandarin']
                            for kw in cn_keywords:
                                if kw in title or kw in display_title:
                                    is_chinese = True
                                    break
                            
                            if stype == 'Subtitle' and is_chinese:
                                has_cn_sub = True
                            if stype == 'Audio' and is_chinese:
                                has_cn_audio = True
                
                # 根据检测模式判断是否添加
                should_add = False
                if detect_mode == '1' and not has_cn_sub:  # 无中文字幕
                    should_add = True
                elif detect_mode == '2' and not has_cn_audio:  # 无中文音轨
                    should_add = True
                elif detect_mode == '3' and not has_cn_sub and not has_cn_audio:  # 两者都无
                    should_add = True
                
                if should_add:
                    display_name = item.get('Name', 'Unknown')
                    series = item.get('SeriesName', '')
                    if series:
                        display_name = f"{series} - {display_name}"
                    
                    rating = item.get('CommunityRating', 0)
                    no_cn_items.append({
                        'id': item.get('Id'),
                        'name': display_name,
                        'path': item.get('Path', ''),
                        'lib': lib_name,
                        'rating': rating,
                        'has_sub': has_cn_sub,
                        'has_audio': has_cn_audio
                    })
        
        sys.stdout.write("\r" + " " * 60 + "\r")
        
        print(f"\n {Colors.CYAN}📊 扫描完成: 共 {total_scanned} 个资源{Colors.RESET}")
        
        mode_desc = "无中文字幕" if detect_mode == '1' else "无中文音轨" if detect_mode == '2' else "无中文字幕且无中文音轨"
        
        if not no_cn_items:
            print(f" {Colors.GREEN}✅ 所有资源都有中文内容！{Colors.RESET}")
            self.pause()
            return
        
        # 存储供 Web 使用
        self.web_data['no_chinese'] = no_cn_items
        
        # 按库分组统计
        lib_stats = defaultdict(int)
        for item in no_cn_items:
            lib_stats[item['lib']] += 1
        
        print(f"\n {Colors.RED}⚠️  发现 {len(no_cn_items)} 个{mode_desc}的资源:{Colors.RESET}\n")
        
        for lib_name, count in sorted(lib_stats.items(), key=lambda x: -x[1]):
            print(f"   📁 {lib_name}: {Colors.RED}{count}{Colors.RESET} 个")
        
        # 按评分排序（高分的更值得补字幕）
        no_cn_items.sort(key=lambda x: x.get('rating', 0), reverse=True)
        
        # 显示部分列表
        print(f"\n {Colors.BOLD}高分优先列表 (前30个):{Colors.RESET}")
        print(f" {Colors.DIM}{'-'*70}{Colors.RESET}")
        for i, item in enumerate(no_cn_items[:30]):
            name_short = item['name'][:45] + '...' if len(item['name']) > 48 else item['name']
            rating = item.get('rating', 0)
            rating_str = f"{rating:.1f}" if rating else "N/A"
            status = ""
            if detect_mode == '3':
                status = f"[{'有字幕' if item['has_sub'] else '无字幕'}|{'有配音' if item['has_audio'] else '无配音'}]"
            print(f"   {Colors.CYAN}{i+1:>2}{Colors.RESET}. ⭐{rating_str:>4} | {name_short} {Colors.DIM}{status}{Colors.RESET}")
        
        if len(no_cn_items) > 30:
            print(f"\n {Colors.DIM}... 还有 {len(no_cn_items) - 30} 个未显示{Colors.RESET}")
        
        # 保存报告
        report_path = os.path.join(self.data_dir, f"no_chinese_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"🈯 无中文资源报告\n{'='*60}\n")
                f.write(f"时间: {datetime.now()}\n")
                f.write(f"扫描范围: {item_types}\n")
                f.write(f"检测模式: {mode_desc}\n")
                f.write(f"扫描总数: {total_scanned}\n")
                f.write(f"无中文数: {len(no_cn_items)}\n\n")
                
                # 按评分排序写入
                f.write(f"按评分排序 (高分优先):\n{'='*60}\n")
                for item in no_cn_items:
                    rating = item.get('rating', 0)
                    rating_str = f"⭐{rating:.1f}" if rating else "无评分"
                    f.write(f"  [{rating_str}] {item['name']}\n")
                    if item['path']:
                        f.write(f"    路径: {item['path']}\n")
                
                # 按库分组写入
                f.write(f"\n\n按媒体库分组:\n{'='*60}\n")
                for lib_name in sorted(lib_stats.keys()):
                    f.write(f"\n📁 {lib_name} ({lib_stats[lib_name]} 个)\n{'-'*40}\n")
                    for item in no_cn_items:
                        if item['lib'] == lib_name:
                            f.write(f"  • {item['name']}\n")
            print(f"\n 📄 报告已保存: {report_path}")
        except Exception as e:
            print(f" {Colors.RED}保存报告失败: {e}{Colors.RESET}")
        
        # 提供 Web 预览选项
        preview = self.get_user_input("是否在浏览器中预览? (y/n)", default="n").strip().lower()
        if preview == 'y':
            self.start_web_preview('no_chinese')
        
        self.pause()

    def refresh_library(self):
        """刷新媒体库"""
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🔄 刷新媒体库{Colors.RESET}\n")
        
        libs = self._request("/emby/Library/MediaFolders")
        if not libs:
            print(f" {Colors.RED}❌ 无法获取媒体库信息。{Colors.RESET}")
            self.pause()
            return
        
        all_libs = libs.get('Items', [])
        print(f" 请选择要刷新的媒体库:\n")
        print(f"   [0] 刷新全部媒体库")
        for i, lib in enumerate(all_libs):
            print(f"   [{i+1}] {lib.get('Name')} ({lib.get('CollectionType', 'unknown')})")
        print(f"\n   [q] 取消")
        
        choice = self.get_user_input("选择").strip().lower()
        
        if choice == 'q':
            return
        
        if not choice.isdigit():
            print(f" {Colors.RED}无效选择{Colors.RESET}")
            self.pause()
            return
        
        idx = int(choice)
        
        if idx == 0:
            # 刷新全部
            print(f"\n 🔄 正在刷新全部媒体库...")
            result = self._request("/emby/Library/Refresh", method='POST')
            if result is not None:
                print(f" {Colors.GREEN}✅ 已触发全库刷新！{Colors.RESET}")
            else:
                print(f" {Colors.RED}❌ 刷新失败{Colors.RESET}")
        elif 1 <= idx <= len(all_libs):
            lib = all_libs[idx - 1]
            lib_id = lib.get('Id')
            lib_name = lib.get('Name')
            print(f"\n 🔄 正在刷新: {lib_name}...")
            result = self._request(f"/emby/Items/{lib_id}/Refresh", method='POST')
            if result is not None:
                print(f" {Colors.GREEN}✅ 已触发刷新: {lib_name}{Colors.RESET}")
            else:
                print(f" {Colors.RED}❌ 刷新失败{Colors.RESET}")
        else:
            print(f" {Colors.RED}无效选择{Colors.RESET}")
        
        self.pause()

    # ==================== Web 预览功能 ====================
    def generate_web_html(self, data_type):
        """生成 Web 预览的 HTML 页面"""
        html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Emby Scanner - {title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ 
            text-align: center; 
            margin-bottom: 30px;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.5em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #00ff88; }}
        .stat-label {{ color: #aaa; margin-top: 5px; }}
        .chart-section {{
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
        }}
        .chart-title {{ font-size: 1.3em; margin-bottom: 15px; color: #00d9ff; }}
        .bar-chart {{ display: flex; flex-direction: column; gap: 10px; }}
        .bar-row {{ display: flex; align-items: center; gap: 10px; }}
        .bar-label {{ width: 100px; text-align: right; font-size: 0.9em; }}
        .bar-container {{ flex: 1; background: rgba(255,255,255,0.1); border-radius: 5px; height: 25px; overflow: hidden; }}
        .bar {{ height: 100%; border-radius: 5px; display: flex; align-items: center; padding-left: 10px; font-size: 0.8em; }}
        .bar-4k {{ background: linear-gradient(90deg, #ff00ff, #ff66ff); }}
        .bar-1080p {{ background: linear-gradient(90deg, #00ff88, #66ffaa); }}
        .bar-720p {{ background: linear-gradient(90deg, #ffaa00, #ffcc66); }}
        .bar-sd {{ background: linear-gradient(90deg, #888, #aaa); }}
        .bar-default {{ background: linear-gradient(90deg, #00d9ff, #66e0ff); }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        th {{ background: rgba(0,217,255,0.2); color: #00d9ff; }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        .tag {{ 
            display: inline-block; 
            padding: 3px 8px; 
            border-radius: 5px; 
            font-size: 0.8em;
            margin-right: 5px;
        }}
        .tag-4k {{ background: #ff00ff; }}
        .tag-1080p {{ background: #00ff88; color: #000; }}
        .tag-720p {{ background: #ffaa00; color: #000; }}
        .tag-sd {{ background: #888; }}
        .footer {{ text-align: center; margin-top: 40px; color: #666; font-size: 0.9em; }}
        .footer a {{ color: #00d9ff; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 {title}</h1>
        {content}
        <div class="footer">
            Powered by <a href="https://github.com/huanhq99/emby-scanner">Emby Scanner v4.0</a>
        </div>
    </div>
</body>
</html>'''
        
        content = ""
        title = "Emby Scanner"
        
        if data_type == 'analytics' and 'analytics' in self.web_data:
            title = "媒体库透视分析"
            stats = self.web_data['analytics']
            lib_stats = self.web_data.get('lib_stats', [])
            
            total_hours = stats.get('TotalDuration', 0) / (10000000 * 3600) if stats.get('TotalDuration') else 0
            
            # 统计卡片
            content += '<div class="stats-grid">'
            content += f'<div class="stat-card"><div class="stat-value">{stats.get("TotalCount", 0):,}</div><div class="stat-label">总文件数</div></div>'
            content += f'<div class="stat-card"><div class="stat-value">{stats.get("Movies", 0):,}</div><div class="stat-label">电影</div></div>'
            content += f'<div class="stat-card"><div class="stat-value">{stats.get("Episodes", 0):,}</div><div class="stat-label">剧集</div></div>'
            content += f'<div class="stat-card"><div class="stat-value">{self.format_size(stats.get("TotalSize", 0))}</div><div class="stat-label">总容量</div></div>'
            content += f'<div class="stat-card"><div class="stat-value">{total_hours:.0f}h</div><div class="stat-label">总时长</div></div>'
            content += '</div>'
            
            # 分辨率分布
            content += '<div class="chart-section"><div class="chart-title">🖥️ 分辨率分布</div><div class="bar-chart">'
            total = stats.get('TotalCount', 1)
            for res in ['4K', '1080P', '720P', '480P', 'SD']:
                count = stats.get('Resolution', {}).get(res, 0)
                pct = (count / total * 100) if total > 0 else 0
                bar_class = f"bar-{res.lower().replace('p', '')}" if res in ['4K', '1080P', '720P'] else 'bar-sd'
                content += f'<div class="bar-row"><div class="bar-label">{res}</div><div class="bar-container"><div class="bar {bar_class}" style="width:{max(pct, 2)}%">{count:,} ({pct:.1f}%)</div></div></div>'
            content += '</div></div>'
            
            # 编码分布
            content += '<div class="chart-section"><div class="chart-title">🎞️ 视频编码</div><div class="bar-chart">'
            for codec, count in sorted(stats.get('Codec', {}).items(), key=lambda x: -x[1])[:5]:
                pct = (count / total * 100) if total > 0 else 0
                content += f'<div class="bar-row"><div class="bar-label">{codec}</div><div class="bar-container"><div class="bar bar-default" style="width:{max(pct, 2)}%">{count:,} ({pct:.1f}%)</div></div></div>'
            content += '</div></div>'
            
            # 动态范围
            content += '<div class="chart-section"><div class="chart-title">🌈 动态范围 (HDR)</div><div class="bar-chart">'
            for dr in ['Dolby Vision', 'HDR10+', 'HDR10', 'HLG', 'SDR']:
                count = stats.get('DynamicRange', {}).get(dr, 0)
                pct = (count / total * 100) if total > 0 else 0
                content += f'<div class="bar-row"><div class="bar-label">{dr}</div><div class="bar-container"><div class="bar bar-default" style="width:{max(pct, 2)}%">{count:,} ({pct:.1f}%)</div></div></div>'
            content += '</div></div>'
            
        elif data_type == 'large_files' and 'large_files' in self.web_data:
            title = "大文件列表"
            files = self.web_data['large_files']
            total_size = sum(f['size'] for f in files)
            
            content += '<div class="stats-grid">'
            content += f'<div class="stat-card"><div class="stat-value">{len(files)}</div><div class="stat-label">大文件数</div></div>'
            content += f'<div class="stat-card"><div class="stat-value">{self.format_size(total_size)}</div><div class="stat-label">总占用</div></div>'
            content += '</div>'
            
            content += '<div class="chart-section"><div class="chart-title">📋 文件列表</div>'
            content += '<table><tr><th>#</th><th>名称</th><th>大小</th><th>分辨率</th><th>码率</th></tr>'
            for i, f in enumerate(files[:100]):
                res_class = f"tag-{f.get('resolution', 'sd').lower()}"
                bitrate = f"{f.get('bitrate', 0):.1f} Mbps" if f.get('bitrate') else "N/A"
                name = f['name'][:60] + '...' if len(f['name']) > 60 else f['name']
                content += f'<tr><td>{i+1}</td><td>{name}</td><td>{self.format_size(f["size"])}</td><td><span class="tag {res_class}">{f.get("resolution", "N/A")}</span></td><td>{bitrate}</td></tr>'
            content += '</table></div>'
            
        elif data_type == 'no_chinese' and 'no_chinese' in self.web_data:
            title = "无中文资源列表"
            items = self.web_data['no_chinese']
            
            content += '<div class="stats-grid">'
            content += f'<div class="stat-card"><div class="stat-value">{len(items)}</div><div class="stat-label">无中文资源</div></div>'
            content += '</div>'
            
            content += '<div class="chart-section"><div class="chart-title">📋 资源列表 (按评分排序)</div>'
            content += '<table><tr><th>#</th><th>名称</th><th>评分</th><th>媒体库</th></tr>'
            for i, item in enumerate(items[:100]):
                rating = f"⭐ {item.get('rating', 0):.1f}" if item.get('rating') else "N/A"
                name = item['name'][:50] + '...' if len(item['name']) > 50 else item['name']
                content += f'<tr><td>{i+1}</td><td>{name}</td><td>{rating}</td><td>{item.get("lib", "N/A")}</td></tr>'
            content += '</table></div>'
        
        elif data_type == 'missing' and 'missing' in self.web_data:
            title = "缺集检查报告"
            data = self.web_data['missing']
            details = data.get('details', [])
            
            content += '<div class="stats-grid">'
            content += f'<div class="stat-card"><div class="stat-value">{data.get("total_series", 0):,}</div><div class="stat-label">总剧集数</div></div>'
            content += f'<div class="stat-card"><div class="stat-value" style="color:#ff6b6b">{data.get("total_series_with_missing", 0)}</div><div class="stat-label">缺集剧数</div></div>'
            content += f'<div class="stat-card"><div class="stat-value" style="color:#ffa500">{data.get("total_missing_episodes", 0):,}</div><div class="stat-label">缺集总数</div></div>'
            content += f'<div class="stat-card"><div class="stat-value">{data.get("elapsed", 0):.1f}s</div><div class="stat-label">扫描耗时</div></div>'
            content += '</div>'
            
            # 按缺集数排序
            sorted_details = sorted(details, key=lambda x: x.get('missing_count', 0), reverse=True)
            
            content += '<div class="chart-section"><div class="chart-title">📋 缺集剧集列表 (按缺集数排序)</div>'
            content += '<table><tr><th>#</th><th>剧名</th><th>媒体库</th><th>缺集数</th><th>缺集详情</th></tr>'
            for i, item in enumerate(sorted_details[:100]):
                name = item.get('series', 'Unknown')
                if len(name) > 40:
                    name = name[:40] + '...'
                lib = item.get('lib', 'N/A')
                missing_count = item.get('missing_count', 0)
                # 格式化缺集详情
                detail_parts = []
                for d in item.get('details', [])[:3]:  # 最多显示3季
                    season = d.get('season', 0)
                    missing = d.get('missing', [])
                    if len(missing) > 5:
                        missing_str = ', '.join(map(str, missing[:5])) + f'... (+{len(missing)-5})'
                    else:
                        missing_str = ', '.join(map(str, missing))
                    detail_parts.append(f'S{season}: {missing_str}')
                details_str = ' | '.join(detail_parts)
                if len(item.get('details', [])) > 3:
                    details_str += ' ...'
                content += f'<tr><td>{i+1}</td><td>{name}</td><td>{lib}</td><td style="color:#ff6b6b;font-weight:bold">{missing_count}</td><td style="font-size:0.85em">{details_str}</td></tr>'
            content += '</table></div>'
        
        return html_template.format(title=title, content=content)
    
    def start_web_preview(self, data_type):
        """启动 Web 预览服务器"""
        html_content = self.generate_web_html(data_type)
        
        # 保存 HTML 文件
        html_path = os.path.join(self.data_dir, 'preview.html')
        try:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception as e:
            print(f" {Colors.RED}生成预览失败: {e}{Colors.RESET}")
            return
        
        # 找一个可用端口
        port = 8899
        for p in range(8899, 8999):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(('127.0.0.1', p))
                sock.close()
                port = p
                break
            except:
                continue
        
        # 创建简单的 HTTP 服务器
        class PreviewHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(html_path, 'rb') as f:
                    self.wfile.write(f.read())
            def log_message(self, format, *args):
                pass  # 禁止日志输出
        
        server = HTTPServer(('127.0.0.1', port), PreviewHandler)
        
        # 在后台线程运行服务器
        def serve():
            server.handle_request()  # 只处理一个请求
        
        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        
        url = f"http://127.0.0.1:{port}"
        print(f"\n {Colors.GREEN}🌐 正在打开浏览器预览: {url}{Colors.RESET}")
        
        # 打开浏览器
        try:
            webbrowser.open(url)
        except:
            print(f" {Colors.YELLOW}请手动打开浏览器访问: {url}{Colors.RESET}")
        
        time.sleep(2)  # 等待浏览器加载

    # --- 菜单 ---
    def main_menu(self):
        while True:
            self.clear_screen(); self.print_banner()
            server_status = f"{Colors.GREEN}● 已连接{Colors.RESET}" if self.server_url else f"{Colors.RED}● 未配置{Colors.RESET}"
            print(f" {Colors.DIM}Server: {server_status}   Data: {self.data_dir}\n")
            print(f" {Colors.BOLD}--- 核心维护 ---{Colors.RESET}")
            print(f" {Colors.CYAN}[1]{Colors.RESET} 🚀  重复文件扫描    {Colors.MAGENTA}[5]{Colors.RESET} 🔍  剧集缺集检查")
            print(f"\n {Colors.BOLD}--- 扩展工具 ---{Colors.RESET}")
            print(f" {Colors.BLUE}[6]{Colors.RESET} 🧹  垃圾清理        {Colors.BLUE}[7]{Colors.RESET} 📊  透视分析")
            print(f" {Colors.BLUE}[8]{Colors.RESET} 🐘  大文件筛选      {Colors.BLUE}[9]{Colors.RESET} 🈯  无中字检测")
            print(f" {Colors.BLUE}[r]{Colors.RESET} 🔄  刷新媒体库")
            print(f"\n {Colors.BOLD}--- 系统设置 ---{Colors.RESET}")
            print(f" {Colors.DIM}[2] 配置  [3] 报告  [4] 重置  [0] 退出{Colors.RESET}\n")
            c = self.get_user_input("请选择").strip().lower()
            if c=='1': self.run_scanner() if self.server_url else self.pause()
            elif c=='2': self.init_config() if self.setup_wizard() else None
            elif c=='3': self.view_reports()
            elif c=='4': self.reset_config()
            elif c=='5': self.run_missing_check()
            elif c=='6': self.run_junk_cleaner()
            elif c=='7': self.run_analytics()
            elif c=='8': self.run_large_file_scanner()
            elif c=='9': self.run_no_chinese_scanner()
            elif c=='r': self.refresh_library()
            elif c=='0': sys.exit(0)

    def view_reports(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}📄 查看历史报告{Colors.RESET}\n")
        
        if not os.path.exists(self.data_dir):
            print(f" {Colors.RED}❌ 数据目录不存在。{Colors.RESET}")
            self.pause()
            return
        
        # 查找所有报告文件
        reports = []
        try:
            for f in os.listdir(self.data_dir):
                if f.endswith('.txt'):
                    full_path = os.path.join(self.data_dir, f)
                    mtime = os.path.getmtime(full_path)
                    # 确定报告类型
                    if 'missing' in f:
                        rtype = "🔍 缺集"
                    elif 'report' in f:
                        rtype = "📋 查重"
                    elif 'large' in f:
                        rtype = "🐘 大文件"
                    elif 'chinese' in f:
                        rtype = "🈯 无中文"
                    elif 'clean' in f:
                        rtype = "🧹 清理"
                    else:
                        rtype = "📄 其他"
                    reports.append((f, full_path, mtime, rtype))
        except Exception as e:
            print(f" {Colors.RED}❌ 读取目录失败: {e}{Colors.RESET}")
            self.pause()
            return
        
        if not reports:
            print(f" {Colors.DIM}暂无报告文件。{Colors.RESET}")
            self.pause()
            return
        
        # 按时间排序，最新的在前
        reports.sort(key=lambda x: x[2], reverse=True)
        
        print(f" {Colors.DIM}找到 {len(reports)} 个报告:{Colors.RESET}\n")
        for i, (name, path, mtime, rtype) in enumerate(reports[:15]):  # 显示最近15个
            time_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            print(f"   [{i+1:>2}] {rtype} {name}  {Colors.DIM}({time_str}){Colors.RESET}")
        
        print(f"\n   [0] 返回")
        
        choice = self.get_user_input("选择报告序号查看").strip()
        if not choice.isdigit() or int(choice) == 0:
            return
        
        idx = int(choice) - 1
        if 0 <= idx < len(reports):
            report_path = reports[idx][1]
            self.clear_screen()
            print(f" {Colors.CYAN}📄 {reports[idx][0]}{Colors.RESET}\n")
            print(f" {Colors.DIM}" + "─" * 60 + f"{Colors.RESET}")
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 分页显示，最多显示100行
                    lines = content.split('\n')
                    for line in lines[:100]:
                        print(f" {line}")
                    if len(lines) > 100:
                        print(f"\n {Colors.DIM}... (共 {len(lines)} 行，仅显示前100行){Colors.RESET}")
                        print(f" {Colors.DIM}完整报告: {report_path}{Colors.RESET}")
            except Exception as e:
                print(f" {Colors.RED}❌ 读取失败: {e}{Colors.RESET}")
            print(f" {Colors.DIM}" + "─" * 60 + f"{Colors.RESET}")
        
        self.pause()

    def reset_config(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🔄 重置配置{Colors.RESET}\n")
        print(f" {Colors.DIM}当前配置目录: {self.data_dir}{Colors.RESET}")
        print(f" {Colors.DIM}当前服务器: {self.server_url}{Colors.RESET}\n")
        
        print(f" 请选择操作:")
        print(f"   [1] 仅重置服务器连接配置")
        print(f"   [2] 清空所有数据 (配置+报告)")
        print(f"   [0] 取消\n")
        
        choice = self.get_user_input("选择").strip()
        
        if choice == '1':
            config_file = os.path.join(self.data_dir, 'emby_config.json')
            if os.path.exists(config_file):
                try:
                    os.remove(config_file)
                    self.server_url = ""
                    self.api_key = ""
                    self.headers = {}
                    print(f"\n {Colors.GREEN}✅ 配置已重置。下次启动将重新配置。{Colors.RESET}")
                except Exception as e:
                    print(f"\n {Colors.RED}❌ 删除失败: {e}{Colors.RESET}")
            else:
                print(f"\n {Colors.DIM}配置文件不存在。{Colors.RESET}")
        
        elif choice == '2':
            confirm = self.get_user_input(f"{Colors.RED}确定清空所有数据? 输入 YES 确认{Colors.RESET}").strip()
            if confirm == 'YES':
                try:
                    import shutil
                    if os.path.exists(self.data_dir):
                        shutil.rmtree(self.data_dir)
                    self.server_url = ""
                    self.api_key = ""
                    self.headers = {}
                    print(f"\n {Colors.GREEN}✅ 所有数据已清空。{Colors.RESET}")
                except Exception as e:
                    print(f"\n {Colors.RED}❌ 清空失败: {e}{Colors.RESET}")
            else:
                print(f"\n {Colors.DIM}已取消。{Colors.RESET}")
        
        self.pause()

if __name__ == "__main__":
    try:
        app = EmbyScannerPro()
        app.init_config()
        if not app.server_url: app.setup_wizard()
        app.main_menu()
    except: sys.exit(0)
