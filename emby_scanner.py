#!/usr/bin/env python3
"""
Emby媒体库重复检测工具 v3.7 Ultimate Edition (Dual Strategy)
GitHub: https://github.com/huanhq99/emby-scanner
核心功能: 
1. 双重查重模式：
   - [1] 严格体积模式：仅当文件字节数完全一致时，才视为重复。(防误删，最安全)
   - [2] 同集优先模式：只要是【同一集】(SxxExx)，无论体积大小/文件名差异，均视为重复。(专治同集洗版)
2. 智能清理：
   - 剧集：同集模式下，自动保留【体积最大】且【文件名最长】的文件。
   - 电影：自动保留【文件名最长】的文件。
3. 功能全集：登录深度删除 + 手动精选 + 缺集检查 + 媒体库透视。
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
        self.version = "3.7 Ultimate"
        self.github_url = "https://github.com/huanhq99/emby-scanner"
        self.server_url = ""
        self.api_key = ""
        self.headers = {}

        self.user_id = ""
        self.access_token = ""
        self.last_scan_results = {} 
        self.lib_types = {}
        self.scan_mode = "strict" # strict / loose

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
                    self.headers = {'X-Emby-Token': self.api_key, 'Content-Type': 'application/json', 'User-Agent': 'EmbyScannerPro/3.7'}
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

    # --- 其他功能保持不变 ---
    def run_missing_check(self):
        # ... (Include missing check code from v2.9.9) ...
        self.clear_screen(); self.print_banner(); print(f" {Colors.YELLOW}🔍 检查缺集...{Colors.RESET}")
        libs = self._request("/emby/Library/MediaFolders")
        if not libs: return
        target_libs = [l for l in libs.get('Items', []) if l.get('CollectionType') == 'tvshows']
        if not target_libs: print(f" {Colors.RED}❌ 无剧集库。{Colors.RESET}"); self.pause(); return
        print(f"\n {Colors.DIM}┌" + "─"*22 + "┬" + "─"*14 + "┬" + "─"*17 + "┬" + "─"*12 + "┐" + f"{Colors.RESET}")
        print(f" {Colors.BOLD}│ {'媒体库名称':<20} │ {'剧集总数':<12} │ {'缺集统计':<13} │ {'状态':<10} │{Colors.RESET}")
        print(f" {Colors.DIM}├" + "─"*22 + "┼" + "─"*14 + "┼" + "─"*17 + "┼" + "─"*12 + "┤" + f"{Colors.RESET}")
        report_lines = ["🎬 Emby 缺集检测报告", "="*60, f"时间: {datetime.now()}", ""]
        for lib in target_libs:
            lib_name = lib.get('Name')
            sys.stdout.write(f" │ {self.pad_text(lib_name, 22)} ...\r"); sys.stdout.flush()
            params = {'ParentId': lib['Id'], 'Recursive': 'true', 'IncludeItemTypes': 'Series', 'Limit': 1000000}
            series_data = self._request("/emby/Items", params)
            if not series_data: continue
            all_series = series_data.get('Items', []); series_count = len(all_series); lib_missing_count = 0; lib_report_buffer = []
            for series in all_series:
                ep_params = {'ParentId': series['Id'], 'Recursive': 'true', 'IncludeItemTypes': 'Episode', 'Fields': 'ParentIndexNumber,IndexNumber', 'Limit': 10000}
                ep_data = self._request("/emby/Items", ep_params)
                if not ep_data: continue
                season_map = defaultdict(list)
                for ep in ep_data.get('Items', []):
                    s = ep.get('ParentIndexNumber', 1); e = ep.get('IndexNumber')
                    if e is not None: season_map[s].append(e)
                series_missing = []
                for s in sorted(season_map.keys()):
                    if s == 0: continue
                    eps = sorted(set(season_map[s])); max_ep = eps[-1]
                    missing = sorted(list(set(range(1, max_ep + 1)) - set(eps)))
                    if missing:
                        lib_missing_count += len(missing)
                        series_missing.append(f"  - S{s}: 缺 [{', '.join(map(str, missing))}]")
                if series_missing:
                    lib_report_buffer.append(f"📺 {series.get('Name')}"); lib_report_buffer.extend(series_missing); lib_report_buffer.append("")
            if lib_missing_count > 0:
                report_lines.append(f"📁 {lib_name}"); report_lines.extend(lib_report_buffer); report_lines.append("-" * 40)
            status = f"{Colors.YELLOW}有缺集{Colors.RESET}" if lib_missing_count > 0 else f"{Colors.GREEN}完整{Colors.RESET}"
            missing_str = f"{Colors.RED}{lib_missing_count} 集{Colors.RESET}" if lib_missing_count > 0 else "0"
            sys.stdout.write("\r")
            row_str = f" │ {self.pad_text(lib_name, 22)} │ {self.pad_text(str(series_count), 14)} │ {self.pad_text(missing_str, 17)} │ {self.pad_text(status, 12)} │"
            print(row_str)
        print(f" {Colors.DIM}└" + "─"*22 + "┴" + "─"*14 + "┴" + "─"*17 + "┴" + "─"*12 + "┘" + f"{Colors.RESET}")
        try:
            with open(os.path.join(self.data_dir, f"missing_report_{datetime.now().strftime('%Y%m%d')}.txt"), 'w') as f: f.write('\n'.join(report_lines))
        except: pass
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
        self.clear_screen(); self.print_banner(); print(f" {Colors.YELLOW}📊 媒体库透视...{Colors.RESET}")
        params = {'Recursive': 'true', 'IncludeItemTypes': 'Movie,Episode', 'Fields': 'MediaSources,Path'}
        items = self._fetch_all_items("/emby/Items", params, 10000)
        if not items: return
        stats = {'Resolution': defaultdict(int), 'SourceType': defaultdict(int), 'DynamicRange': defaultdict(int), 'ReleaseGroup': defaultdict(int), 'TotalCount':0}
        print("\n 🔄 统计中...")
        for item in items:
            stats['TotalCount'] += 1
            sources = item.get('MediaSources', [])
            if not sources: continue
            source = sources[0]; path = item.get('Path', '').upper(); name = item.get('Name', '').upper()
            if 'REMUX' in path: stats['SourceType']['Remux'] += 1
            else: stats['SourceType']['Other'] += 1
            try:
                fname = os.path.basename(item.get('Path', ''))
                if '-' in fname:
                    group = os.path.splitext(fname)[0].split('-')[-1].strip()
                    if 1 < len(group) < 15 and not group.isdigit(): stats['ReleaseGroup'][group] += 1
            except: pass
            for stream in source.get('MediaStreams', []):
                if stream.get('Type') == 'Video':
                    w = stream.get('Width', 0)
                    if w>=3800: res="4K"
                    elif w>=1900: res="1080P"
                    else: res="SD"
                    stats['Resolution'][res] += 1
                    vr = stream.get('VideoRange', '').upper()
                    if 'HDR' in vr: stats['DynamicRange']['HDR'] += 1
                    break
        print(f"\n {Colors.BOLD}总计: {stats['TotalCount']}{Colors.RESET}"); 
        print(f" 📺 4K: {stats['Resolution']['4K']}"); 
        self.pause()

    def run_large_file_scanner(self):
        self.clear_screen(); self.print_banner(); print(f" {Colors.YELLOW}🐘 大文件筛选...{Colors.RESET}")
        libs = self._request("/emby/Library/MediaFolders"); 
        if not libs: return
        targets = [l for l in libs.get('Items', []) if l.get('CollectionType') == 'movies']
        large = []
        for lib in targets:
            sys.stdout.write(f" ⏳ {lib.get('Name')}...\r"); sys.stdout.flush()
            params = {'ParentId': lib['Id'], 'Recursive': 'true', 'IncludeItemTypes': 'Movie', 'Fields': 'Path,MediaSources,Size'}
            items = self._fetch_all_items("/emby/Items", params)
            for i in items:
                if i.get('Size', 0) > 20*(1024**3): large.append(i)
        print(f"\n {Colors.RED}⚠️  发现 {len(large)} 个 >20GB 文件。{Colors.RESET}"); self.pause()

    def run_no_chinese_scanner(self):
        self.clear_screen(); self.print_banner(); print(f" {Colors.YELLOW}🈯 无中字检测...{Colors.RESET}")
        libs = self._request("/emby/Library/MediaFolders"); 
        if not libs: return
        targets = [l for l in libs.get('Items', []) if l.get('CollectionType') in ['movies', 'tvshows']]
        no_cn = []
        for lib in targets:
            sys.stdout.write(f" ⏳ {lib.get('Name')}...\r"); sys.stdout.flush()
            params = {'ParentId': lib['Id'], 'Recursive': 'true', 'IncludeItemTypes': 'Movie,Episode', 'Fields': 'Path,MediaSources,Name,OriginalLanguage,ProductionLocations'}
            items = self._fetch_all_items("/emby/Items", params, 2000)
            for i in items:
                if not self.has_chinese_content(i): no_cn.append(i.get('Name'))
        print(f"\n {Colors.RED}⚠️  发现 {len(no_cn)} 个无中文资源。{Colors.RESET}"); self.pause()

    # --- 菜单 ---
    def main_menu(self):
        while True:
            self.clear_screen(); self.print_banner()
            server_status = f"{Colors.GREEN}● 已连接{Colors.RESET}" if self.server_url else f"{Colors.RED}● 未配置{Colors.RESET}"
            print(f" {Colors.DIM}Server: {server_status}   Data: {self.data_dir}\n")
            print(f" {Colors.BOLD}--- 核心维护 ---{Colors.RESET}")
            print(f" {Colors.CYAN}[1]{Colors.RESET} 🚀  重复文件扫描 (Dedupe)  {Colors.MAGENTA}[5]{Colors.RESET} 🔍  剧集缺集检查")
            print(f"\n {Colors.BOLD}--- 扩展工具 ---{Colors.RESET}")
            print(f" {Colors.BLUE}[6]{Colors.RESET} 🧹  垃圾清理  {Colors.BLUE}[7]{Colors.RESET} 📊  透视分析  {Colors.BLUE}[8]{Colors.RESET} 🐘  大文件  {Colors.BLUE}[9]{Colors.RESET} 🈯  无中字检测")
            print(f"\n {Colors.BOLD}--- 系统设置 ---{Colors.RESET}")
            print(f" {Colors.DIM}[2] 配置  [3] 报告  [4] 重置  [0] 退出{Colors.RESET}\n")
            c = self.get_user_input("请选择").strip()
            if c=='1': self.run_scanner() if self.server_url else self.pause()
            elif c=='2': self.init_config() if self.setup_wizard() else None
            elif c=='3': self.view_reports()
            elif c=='4': self.reset_config()
            elif c=='5': self.run_missing_check()
            elif c=='6': self.run_junk_cleaner()
            elif c=='7': self.run_analytics()
            elif c=='8': self.run_large_file_scanner()
            elif c=='9': self.run_no_chinese_scanner()
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
