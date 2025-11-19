#!/usr/bin/env python3
"""
Emby媒体库重复检测工具 v6.1 Auto/Manual Dual Mode
GitHub: https://github.com/huanhq99/emby-scanner
核心升级: 
1. 双模式选择：提供【自动批量生成】(保留文件名最长) 和 【手动逐个精选】两种模式。
2. 交互优化：解决逐个确认太繁琐的问题。
3. 安全机制：继续使用 rm 物理删除，防止 Emby 跨库合并误删。
"""

import os
import sys
import json
import time
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
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

# ==================== 主程序类 ====================
class EmbyScannerPro:
    
    def __init__(self):
        self.version = "6.1 Dual-Mode"
        self.github_url = "https://github.com/huanhq99/emby-scanner"
        self.server_url = ""
        self.api_key = ""
        self.headers = {}

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
║             {Colors.RESET}Auto Batch Script | Manual Select | Size-Only{Colors.CYAN}     
╚════════════════════════════════════════════════════════════════╝{Colors.RESET}
        """
        print(banner)

    def get_user_input(self, prompt, default=""):
        full_prompt = f"{Colors.BOLD}{prompt}{Colors.RESET} [{default}]: " if default else f"{Colors.BOLD}{prompt}{Colors.RESET}: "
        try:
            # 使用标准 input，并在之前刷新 stdout 确保提示显示
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

    def _request(self, endpoint, params=None, method='GET'):
        url = f"{self.server_url}{endpoint}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url += f"?{query_string}"
        
        req = urllib.request.Request(url, headers=self.headers, method=method)
        
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
                        'User-Agent': 'EmbyScannerPro/6.1'
                    }
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
            self.clean_menu()
        else:
            print(f"\n{Colors.GREEN}🎉 完美！未发现重复。{Colors.RESET}")
            self.pause()

    # --- 菜单：选择清理模式 ---
    def clean_menu(self):
        print(f"\n{Colors.YELLOW}💡 发现重复文件！请选择操作模式：{Colors.RESET}")
        print(f"   {Colors.BOLD}1.{Colors.RESET} {Colors.GREEN}自动批量模式{Colors.RESET} (推荐) -> 按规则自动保留最佳文件，生成清理脚本")
        print(f"   {Colors.BOLD}2.{Colors.RESET} {Colors.CYAN}手动精选模式{Colors.RESET} -> 逐个查看重复组，手动选择要删除的文件")
        print(f"   {Colors.BOLD}0.{Colors.RESET} 退出")
        
        mode = self.get_user_input("请选择 [1/2/0]").strip()
        
        if mode == '1':
            self.auto_batch_wizard()
        elif mode == '2':
            self.manual_select_wizard()
        else:
            return

    # --- 模式1: 自动批量生成脚本 ---
    def auto_batch_wizard(self):
        libs = list(self.last_scan_results.keys())
        print(f"\n{Colors.CYAN}选择要处理的媒体库:{Colors.RESET}")
        for i, lib in enumerate(libs):
            print(f"  {i+1}. {lib} ({len(self.last_scan_results[lib])} 组重复)")
        
        choice = self.get_user_input("序号 (0=全部处理)").strip()
        target_libs = []
        if choice == '0': target_libs = libs
        elif choice.isdigit() and 0 < int(choice) <= len(libs): target_libs = [libs[int(choice)-1]]
        else: return

        print(f"\n{Colors.YELLOW}正在按规则 [保留文件名最长] 生成脚本...{Colors.RESET}")
        final_delete_list = []
        
        for lib in target_libs:
            groups = self.last_scan_results[lib]
            for group in groups:
                files = group['files']
                # 规则：按文件名长度降序 -> 第一个是最长的（保留），剩下的删除
                sorted_files = sorted(files, key=lambda x: len(os.path.basename(x['path'])), reverse=True)
                
                # 记录要删除的文件
                final_delete_list.extend(sorted_files[1:])

        self.generate_sh(final_delete_list, "auto_batch")

    # --- 模式2: 手动逐个选择 ---
    def manual_select_wizard(self):
        libs = list(self.last_scan_results.keys())
        print(f"\n{Colors.CYAN}选择要手动清理的媒体库:{Colors.RESET}")
        for i, lib in enumerate(libs):
            print(f"  {i+1}. {lib} ({len(self.last_scan_results[lib])} 组重复)")
        
        choice = self.get_user_input("序号").strip()
        target_libs = []
        if choice.isdigit() and 0 < int(choice) <= len(libs): target_libs = [libs[int(choice)-1]]
        else: return

        final_delete_list = []
        for lib in target_libs:
            groups = self.last_scan_results[lib]
            print(f"\n{Colors.BOLD}>>> 正在处理库: {lib}{Colors.RESET}")
            
            for idx, group in enumerate(groups):
                files = group['files']
                size_str = self.format_size(group['size'])
                print(f"\n{Colors.YELLOW}--- [第 {idx+1}/{len(groups)} 组] 体积: {size_str} ---{Colors.RESET}")
                
                for i, f in enumerate(files):
                    fname = os.path.basename(f['path'])
                    print(f"  [{Colors.CYAN}{i+1}{Colors.RESET}] {f['name']} [{f['info']}]")
                    print(f"      📂 {fname}")
                
                print(f"  {Colors.WHITE}[Enter]{Colors.RESET} 跳过")
                user_sel = self.get_user_input(f"输入要{Colors.RED}删除{Colors.RESET}的序号 (如 1)").strip()
                
                if user_sel:
                    try:
                        indices = [int(x.strip()) - 1 for x in user_sel.split(',') if x.strip().isdigit()]
                        for sel_idx in indices:
                            if 0 <= sel_idx < len(files):
                                final_delete_list.append(files[sel_idx])
                                print(f"      {Colors.RED}🔻 已标记删除{Colors.RESET}")
                    except: pass

        self.generate_sh(final_delete_list, "manual_select")

    # --- 通用脚本生成 ---
    def generate_sh(self, delete_list, mode_name):
        if not delete_list:
            print("未选择任何文件。")
            return

        script_content = ["#!/bin/bash", f"# Emby Duplicate Cleaner ({mode_name})", f"# Generated: {datetime.now()}", ""]
        total_cmds = 0
        
        for f in delete_list:
            cmd = f'rm -v "{f["path"]}"'
            script_content.append(cmd)
            total_cmds += 1
            
        sh_name = f"clean_{mode_name}_{datetime.now().strftime('%H%M%S')}.sh"
        sh_path = os.path.join(self.data_dir, sh_name)
        
        try:
            with open(sh_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(script_content))
            os.chmod(sh_path, 0o755)
            print(f"\n{Colors.GREEN}✅ 脚本生成成功！包含 {total_cmds} 个删除指令。{Colors.RESET}")
            print(f"📍 脚本路径: {Colors.BOLD}{sh_path}{Colors.RESET}")
            print(f"👉 请执行: {Colors.YELLOW}bash {sh_path}{Colors.RESET}")
            print(f"\n{Colors.MAGENTA}提示: 执行脚本将物理删除 strm 文件。{Colors.RESET}")
        except Exception as e:
            print(f"❌ 脚本生成失败: {e}")
        
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
