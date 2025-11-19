#!/usr/bin/env python3
"""
Emby媒体库重复检测工具 v6.0 Manual-Select Edition
GitHub: https://github.com/huanhq99/emby-scanner
核心升级: 
1. 手动精选模式：针对重复组，逐一列出详情，用户手动输入序号选择删除对象。
2. 解决合并误删：放弃 API 删除，改用物理路径 rm 删除，完美避开 Emby 跨库合并导致的"连坐"问题。
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
        self.version = "6.0 Manual-Select"
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
║             {Colors.RESET}Manual Select | Safe for Merged Items | Size-Only{Colors.CYAN}     
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
        self.get_user_input(f"\n按 {Colors.GREEN}回车键{Colors.RESET} 继续...")

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
                        'User-Agent': 'EmbyScannerPro/6.0'
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
        # if container: info.append(container) # 简化显示
        video_streams = [s for s in stream.get('MediaStreams', []) if s.get('Type') == 'Video']
        if video_streams:
            v = video_streams[0]
            width = v.get('Width')
            if width:
                if width >= 3800: res = "4K"
                elif width >= 1900: res = "1080P"
                elif width >= 1200: res = "720P"
                else: res = "SD"
                # 颜色高亮分辨率，方便选择
                if res == "4K": res = f"{Colors.MAGENTA}4K{Colors.RESET}"
                elif res == "1080P": res = f"{Colors.GREEN}1080P{Colors.RESET}"
                info.append(res)
            codec = v.get('Codec', '').upper()
            if codec: info.append(codec)
        
        # 增加 HDR/DV 检测
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

    # --- v6.0 核心：手动选择向导 ---
    def manual_select_wizard(self):
        print(f"\n{Colors.YELLOW}💡 发现重复文件！进入手动选择模式。{Colors.RESET}")
        print(f"   说明: 您将逐个查看重复组，并手动输入序号选择要{Colors.RED}【删除】{Colors.RESET}的文件。")
        
        libs = list(self.last_scan_results.keys())
        print(f"\n{Colors.CYAN}选择要清理的媒体库:{Colors.RESET}")
        for i, lib in enumerate(libs):
            print(f"  {i+1}. {lib} ({len(self.last_scan_results[lib])} 组重复)")
        
        choice = self.get_user_input("序号 (0=全部)").strip()
        target_libs = []
        if choice == '0': target_libs = libs
        elif choice.isdigit() and 0 < int(choice) <= len(libs): target_libs = [libs[int(choice)-1]]
        else: return

        final_delete_list = []

        for lib in target_libs:
            groups = self.last_scan_results[lib]
            print(f"\n{Colors.BOLD}>>> 正在处理库: {lib}{Colors.RESET}")
            
            for idx, group in enumerate(groups):
                files = group['files']
                size_str = self.format_size(group['size'])
                
                print(f"\n{Colors.YELLOW}--- [第 {idx+1}/{len(groups)} 组] 体积: {size_str} ---{Colors.RESET}")
                
                # 列出该组所有文件
                for i, f in enumerate(files):
                    # 提取简短文件名以便阅读
                    fname = os.path.basename(f['path'])
                    print(f"  [{Colors.CYAN}{i+1}{Colors.RESET}] {f['name']} [{f['info']}]")
                    print(f"      📂 {fname}")
                
                print(f"  {Colors.WHITE}[s]{Colors.RESET} 跳过此组")
                
                user_sel = self.get_user_input(f"请输入要{Colors.RED}删除{Colors.RESET}的序号 (多选逗号隔开, 如 1,3)").strip().lower()
                
                if user_sel == 's' or user_sel == '':
                    print("已跳过。")
                    continue
                
                try:
                    # 解析用户输入 "1, 3" -> [0, 2]
                    selected_indices = [int(x.strip()) - 1 for x in user_sel.split(',') if x.strip().isdigit()]
                    
                    for sel_idx in selected_indices:
                        if 0 <= sel_idx < len(files):
                            file_to_del = files[sel_idx]
                            final_delete_list.append(file_to_del)
                            print(f"      {Colors.RED}🔻 已标记删除: {os.path.basename(file_to_del['path'])}{Colors.RESET}")
                except:
                    print("输入无效，跳过此组。")

        if not final_delete_list:
            print("\n未选择任何文件。")
            return

        # 生成脚本
        print(f"\n{Colors.YELLOW}正在生成清理脚本...{Colors.RESET}")
        script_content = ["#!/bin/bash", "# Emby Duplicate Cleaner (Manual Select)", f"# Generated: {datetime.now()}", ""]
        
        total_cmds = 0
        for f in final_delete_list:
            # 使用 rm 命令精准删除文件路径
            # 增加 -f 强制删除，不提示
            cmd = f'rm -v "{f["path"]}"'
            script_content.append(cmd)
            total_cmds += 1
            
        sh_name = f"clean_manual_{datetime.now().strftime('%H%M%S')}.sh"
        sh_path = os.path.join(self.data_dir, sh_name)
        
        try:
            with open(sh_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(script_content))
            os.chmod(sh_path, 0o755)
            print(f"\n{Colors.GREEN}✅ 脚本生成成功！包含 {total_cmds} 个删除指令。{Colors.RESET}")
            print(f"📍 脚本路径: {Colors.BOLD}{sh_path}{Colors.RESET}")
            print(f"👉 请执行: {Colors.YELLOW}bash {sh_path}{Colors.RESET}")
            print(f"\n{Colors.MAGENTA}提示: 执行脚本后，strm 文件会被物理删除。请等待 Emby 自动扫描或手动触发扫描以更新媒体库。{Colors.RESET}")
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
