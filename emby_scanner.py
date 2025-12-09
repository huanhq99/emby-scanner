#!/usr/bin/env python3
"""
Emby媒体库重复检测工具 v3.8 Ultimate Edition (Dual Strategy)
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
        self.version = "3.8 Ultimate"
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
        """缺集检查 - 优化版：批量获取所有剧集，减少API请求次数"""
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🔍 检查缺集 (优化版)...{Colors.RESET}")
        
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
        report_lines = ["🎬 Emby 缺集检测报告", "="*60, f"时间: {datetime.now()}", ""]
        
        total_missing_episodes = 0  # 总缺集数
        total_series = 0            # 总剧集数（去重后的 Series）
        total_series_with_missing = 0  # 有缺集的剧数
        
        for lib in target_libs:
            lib_name = lib.get('Name')
            sys.stdout.write(f" │ {self.pad_text(lib_name, 22)} │ 批量加载中...                                    \r")
            sys.stdout.flush()
            
            try:
                # 步骤1: 获取所有剧集列表（Series，不是 Season）
                series_params = {
                    'ParentId': lib['Id'], 
                    'Recursive': 'true', 
                    'IncludeItemTypes': 'Series',  # 只获取 Series，不是 Season
                    'Fields': 'Name', 
                    'Limit': 100000
                }
                series_data = self._request("/emby/Items", series_params)
                if not series_data: 
                    print(f" │ {self.pad_text(lib_name, 22)} │ {self.pad_text('N/A', 12)} │ {self.pad_text('请求失败', 14)} │ {self.pad_text('-', 17)} │ {self.pad_text('❌', 10)} │")
                    continue
                
                all_series = series_data.get('Items', [])
                series_count = len(all_series)
                total_series += series_count
                
                # 创建 Series ID -> Name 映射
                series_map = {s['Id']: s.get('Name', 'Unknown') for s in all_series}
                
                sys.stdout.write(f" │ {self.pad_text(lib_name, 22)} │ 批量获取剧集...                                  \r")
                sys.stdout.flush()
                
                # 步骤2: 一次性批量获取该库下所有 Episode（关键优化！）
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
                
                # 步骤3: 按 SeriesId 分组
                series_episodes = defaultdict(lambda: defaultdict(list))
                for ep in all_episodes:
                    series_id = ep.get('SeriesId')
                    if not series_id:
                        continue
                    season = ep.get('ParentIndexNumber', 1)
                    episode = ep.get('IndexNumber')
                    if episode is not None:
                        series_episodes[series_id][season].append(episode)
                
                # 步骤4: 分析缺集
                lib_missing_episodes = 0  # 该库缺集总数
                lib_series_with_missing = 0  # 该库有缺集的剧数
                lib_report_buffer = []
                
                for series_id, seasons in series_episodes.items():
                    series_name = series_map.get(series_id, 'Unknown')
                    series_missing = []
                    series_missing_count = 0
                    
                    for s in sorted(seasons.keys()):
                        if s == 0 or s is None:
                            continue
                        eps = sorted(set(seasons[s]))
                        if not eps:
                            continue
                        max_ep = eps[-1]
                        missing = sorted(list(set(range(1, max_ep + 1)) - set(eps)))
                        if missing:
                            series_missing_count += len(missing)
                            series_missing.append(f"  - S{s}: 缺 [{', '.join(map(str, missing))}]")
                    
                    if series_missing:
                        lib_missing_episodes += series_missing_count
                        lib_series_with_missing += 1
                        lib_report_buffer.append(f"📺 {series_name} (缺 {series_missing_count} 集)")
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
        print(f" {Colors.YELLOW}📊 媒体库透视...{Colors.RESET}")
        
        params = {'Recursive': 'true', 'IncludeItemTypes': 'Movie,Episode', 'Fields': 'MediaSources,Path'}
        items = self._fetch_all_items("/emby/Items", params, 10000)
        if not items: 
            print(f" {Colors.RED}❌ 无法获取媒体信息。{Colors.RESET}")
            self.pause()
            return
        
        stats = {
            'Resolution': defaultdict(int), 
            'Codec': defaultdict(int),
            'SourceType': defaultdict(int), 
            'DynamicRange': defaultdict(int), 
            'ReleaseGroup': defaultdict(int), 
            'TotalCount': 0,
            'TotalSize': 0
        }
        
        print("\n 🔄 统计中...")
        for item in items:
            stats['TotalCount'] += 1
            sources = item.get('MediaSources', [])
            if not sources: continue
            source = sources[0]
            path = item.get('Path', '').upper()
            
            # 统计大小
            size = source.get('Size', 0)
            if size: stats['TotalSize'] += size
            
            # 统计来源类型
            if 'REMUX' in path: stats['SourceType']['Remux'] += 1
            elif 'BLURAY' in path or 'BLU-RAY' in path: stats['SourceType']['BluRay'] += 1
            elif 'WEB-DL' in path or 'WEBDL' in path: stats['SourceType']['WEB-DL'] += 1
            elif 'WEBRIP' in path: stats['SourceType']['WEBRip'] += 1
            elif 'HDTV' in path: stats['SourceType']['HDTV'] += 1
            else: stats['SourceType']['Other'] += 1
            
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
                    if w >= 3800: res = "4K"
                    elif w >= 1900: res = "1080P"
                    elif w >= 1200: res = "720P"
                    else: res = "SD"
                    stats['Resolution'][res] += 1
                    
                    # 编码
                    codec = stream.get('Codec', 'unknown').upper()
                    if codec in ['HEVC', 'H265']: stats['Codec']['HEVC/H.265'] += 1
                    elif codec in ['AVC', 'H264']: stats['Codec']['AVC/H.264'] += 1
                    elif codec in ['AV1']: stats['Codec']['AV1'] += 1
                    else: stats['Codec']['Other'] += 1
                    
                    # HDR
                    vr = stream.get('VideoRange', '').upper()
                    vrt = stream.get('VideoRangeType', '').upper()
                    if 'DOLBY' in vrt or 'DV' in vrt: stats['DynamicRange']['Dolby Vision'] += 1
                    elif 'HDR10+' in vrt: stats['DynamicRange']['HDR10+'] += 1
                    elif 'HDR' in vr: stats['DynamicRange']['HDR10'] += 1
                    else: stats['DynamicRange']['SDR'] += 1
                    break
        
        # 显示统计结果
        print(f"\n {Colors.BOLD}{'='*50}{Colors.RESET}")
        print(f" {Colors.CYAN}📊 媒体库统计报告{Colors.RESET}")
        print(f" {Colors.BOLD}{'='*50}{Colors.RESET}\n")
        
        print(f" {Colors.BOLD}总览:{Colors.RESET}")
        print(f"   总文件数: {Colors.GREEN}{stats['TotalCount']}{Colors.RESET}")
        print(f"   总容量: {Colors.GREEN}{self.format_size(stats['TotalSize'])}{Colors.RESET}")
        
        print(f"\n {Colors.BOLD}分辨率分布:{Colors.RESET}")
        for res in ['4K', '1080P', '720P', 'SD']:
            count = stats['Resolution'].get(res, 0)
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
            color = Colors.MAGENTA if res == '4K' else Colors.GREEN if res == '1080P' else Colors.RESET
            print(f"   {color}{res:>6}{Colors.RESET}: {bar} {count:>6} ({pct:>5.1f}%)")
        
        print(f"\n {Colors.BOLD}视频编码:{Colors.RESET}")
        for codec, count in sorted(stats['Codec'].items(), key=lambda x: -x[1]):
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            print(f"   {codec:>12}: {count:>6} ({pct:>5.1f}%)")
        
        print(f"\n {Colors.BOLD}动态范围:{Colors.RESET}")
        for dr in ['Dolby Vision', 'HDR10+', 'HDR10', 'SDR']:
            count = stats['DynamicRange'].get(dr, 0)
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            color = Colors.CYAN if 'Dolby' in dr else Colors.YELLOW if 'HDR' in dr else Colors.DIM
            print(f"   {color}{dr:>12}{Colors.RESET}: {count:>6} ({pct:>5.1f}%)")
        
        print(f"\n {Colors.BOLD}来源类型:{Colors.RESET}")
        for src, count in sorted(stats['SourceType'].items(), key=lambda x: -x[1])[:6]:
            pct = (count / stats['TotalCount'] * 100) if stats['TotalCount'] > 0 else 0
            print(f"   {src:>12}: {count:>6} ({pct:>5.1f}%)")
        
        # TOP 制作组
        if stats['ReleaseGroup']:
            print(f"\n {Colors.BOLD}TOP 10 制作组:{Colors.RESET}")
            for group, count in sorted(stats['ReleaseGroup'].items(), key=lambda x: -x[1])[:10]:
                print(f"   {Colors.BLUE}{group:>15}{Colors.RESET}: {count}")
        
        print(f"\n {Colors.BOLD}{'='*50}{Colors.RESET}")
        self.pause()

    def run_large_file_scanner(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🐘 大文件筛选...{Colors.RESET}\n")
        
        # 让用户选择阈值
        threshold_input = self.get_user_input("文件大小阈值 (GB)", default="20").strip()
        try:
            threshold_gb = float(threshold_input)
        except ValueError:
            threshold_gb = 20
        threshold_bytes = threshold_gb * (1024**3)
        
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
                'Fields': 'Path,MediaSources,Size,SeriesName'
            }
            items = self._fetch_all_items("/emby/Items", params)
            
            for item in items:
                sources = item.get('MediaSources', [])
                for source in sources:
                    size = source.get('Size', 0)
                    if size > threshold_bytes:
                        display_name = item.get('Name', 'Unknown')
                        if ctype == 'tvshows':
                            series = item.get('SeriesName', '')
                            if series:
                                display_name = f"{series} - {display_name}"
                        large_files.append({
                            'id': item.get('Id'),
                            'name': display_name,
                            'size': size,
                            'path': source.get('Path', ''),
                            'lib': lib_name
                        })
        
        sys.stdout.write("\r" + " " * 60 + "\r")
        
        if not large_files:
            print(f" {Colors.GREEN}✅ 未发现大于 {threshold_gb}GB 的文件。{Colors.RESET}")
            self.pause()
            return
        
        # 按大小排序
        large_files.sort(key=lambda x: x['size'], reverse=True)
        total_size = sum(f['size'] for f in large_files)
        
        print(f"\n {Colors.RED}⚠️  发现 {len(large_files)} 个 >{threshold_gb}GB 文件，共占用 {self.format_size(total_size)}{Colors.RESET}\n")
        
        # 显示列表
        print(f" {Colors.BOLD}{'序号':>4} | {'大小':>10} | {'媒体库':<12} | 名称{Colors.RESET}")
        print(f" {Colors.DIM}{'-'*70}{Colors.RESET}")
        
        for i, f in enumerate(large_files[:30]):  # 只显示前30个
            size_str = self.format_size(f['size'])
            lib_short = f['lib'][:10] + '..' if len(f['lib']) > 12 else f['lib']
            name_short = f['name'][:35] + '...' if len(f['name']) > 38 else f['name']
            print(f" {Colors.CYAN}{i+1:>4}{Colors.RESET} | {Colors.RED}{size_str:>10}{Colors.RESET} | {lib_short:<12} | {name_short}")
        
        if len(large_files) > 30:
            print(f"\n {Colors.DIM}... 还有 {len(large_files) - 30} 个文件未显示{Colors.RESET}")
        
        # 保存报告
        report_path = os.path.join(self.data_dir, f"large_files_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"🐘 大文件报告 (>{threshold_gb}GB)\n{'='*60}\n")
                f.write(f"时间: {datetime.now()}\n")
                f.write(f"文件数: {len(large_files)}, 总大小: {self.format_size(total_size)}\n\n")
                for item in large_files:
                    f.write(f"[{self.format_size(item['size'])}] {item['name']}\n")
                    f.write(f"  路径: {item['path']}\n\n")
            print(f"\n 📄 报告已保存: {report_path}")
        except Exception as e:
            print(f" {Colors.RED}保存报告失败: {e}{Colors.RESET}")
        
        self.pause()

    def run_no_chinese_scanner(self):
        self.clear_screen()
        self.print_banner()
        print(f" {Colors.YELLOW}🈯 无中字检测...{Colors.RESET}\n")
        print(f" {Colors.DIM}说明: 检测没有中文字幕/音轨的资源{Colors.RESET}\n")
        
        # 选择扫描范围
        print(f" 请选择扫描范围:")
        print(f"   [1] 仅电影")
        print(f"   [2] 仅剧集")
        print(f"   [3] 全部")
        scope = self.get_user_input("选择", default="1").strip()
        
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
                'Fields': 'Path,MediaSources,Name,OriginalLanguage,ProductionLocations,SeriesName'
            }
            items = self._fetch_all_items("/emby/Items", params, 5000)
            total_scanned += len(items)
            
            for item in items:
                if not self.has_chinese_content(item):
                    display_name = item.get('Name', 'Unknown')
                    series = item.get('SeriesName', '')
                    if series:
                        display_name = f"{series} - {display_name}"
                    no_cn_items.append({
                        'id': item.get('Id'),
                        'name': display_name,
                        'path': item.get('Path', ''),
                        'lib': lib_name
                    })
        
        sys.stdout.write("\r" + " " * 60 + "\r")
        
        print(f"\n {Colors.CYAN}📊 扫描完成: 共 {total_scanned} 个资源{Colors.RESET}")
        
        if not no_cn_items:
            print(f" {Colors.GREEN}✅ 所有资源都有中文内容！{Colors.RESET}")
            self.pause()
            return
        
        # 按库分组统计
        lib_stats = defaultdict(int)
        for item in no_cn_items:
            lib_stats[item['lib']] += 1
        
        print(f"\n {Colors.RED}⚠️  发现 {len(no_cn_items)} 个无中文资源:{Colors.RESET}\n")
        
        for lib_name, count in sorted(lib_stats.items(), key=lambda x: -x[1]):
            print(f"   📁 {lib_name}: {Colors.RED}{count}{Colors.RESET} 个")
        
        # 显示部分列表
        print(f"\n {Colors.BOLD}部分列表 (前20个):{Colors.RESET}")
        print(f" {Colors.DIM}{'-'*60}{Colors.RESET}")
        for item in no_cn_items[:20]:
            name_short = item['name'][:50] + '...' if len(item['name']) > 53 else item['name']
            print(f"   • {name_short}")
        
        if len(no_cn_items) > 20:
            print(f"\n {Colors.DIM}... 还有 {len(no_cn_items) - 20} 个未显示{Colors.RESET}")
        
        # 保存报告
        report_path = os.path.join(self.data_dir, f"no_chinese_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"🈯 无中文资源报告\n{'='*60}\n")
                f.write(f"时间: {datetime.now()}\n")
                f.write(f"扫描范围: {item_types}\n")
                f.write(f"扫描总数: {total_scanned}\n")
                f.write(f"无中文数: {len(no_cn_items)}\n\n")
                
                # 按库分组写入
                for lib_name in sorted(lib_stats.keys()):
                    f.write(f"\n📁 {lib_name} ({lib_stats[lib_name]} 个)\n{'-'*40}\n")
                    for item in no_cn_items:
                        if item['lib'] == lib_name:
                            f.write(f"  • {item['name']}\n")
                            if item['path']:
                                f.write(f"    路径: {item['path']}\n")
            print(f"\n 📄 报告已保存: {report_path}")
        except Exception as e:
            print(f" {Colors.RED}保存报告失败: {e}{Colors.RESET}")
        
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
                if f.endswith('.txt') and ('report' in f or 'missing' in f):
                    full_path = os.path.join(self.data_dir, f)
                    mtime = os.path.getmtime(full_path)
                    reports.append((f, full_path, mtime))
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
        for i, (name, path, mtime) in enumerate(reports[:10]):  # 只显示最近10个
            time_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            print(f"   [{i+1}] {name}  {Colors.DIM}({time_str}){Colors.RESET}")
        
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
