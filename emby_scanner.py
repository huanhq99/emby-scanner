#!/usr/bin/env python3
"""
Emby媒体库重复检测工具
GitHub: https://github.com/huanhq99/emby-scanner
"""

import os
import sys
import subprocess
import requests
import json
from collections import defaultdict
from datetime import datetime

class EmbyScannerSetup:
    """环境设置和交互界面"""
    
    def __init__(self):
        self.server_url = ""
        self.api_key = ""
        self.venv_path = os.path.expanduser("~/emby-scanner-env")
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.version = "2.0"
        self.github_url = "https://github.com/huanhq99/emby-scanner"
        
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_banner(self):
        """打印横幅"""
        banner = f"""
╔════════════════════════════════════════════════════════════════╗
║                Emby媒体库重复检测工具 v{self.version}              
║                GitHub: {self.github_url}               
╚════════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    def print_menu(self, title, options):
        """打印菜单"""
        print(f"\n{title}")
        print("=" * 50)
        for key, value in options.items():
            print(f"  {key}. {value}")
        print("-" * 50)
    
    def get_user_input(self, prompt, default=""):
        """获取用户输入"""
        if default:
            user_input = input(f"{prompt} [{default}]: ").strip()
            return user_input if user_input else default
        else:
            return input(f"{prompt}: ").strip()
    
    def check_python(self):
        """检查Python环境"""
        print("\n🔍 检查Python环境...")
        if sys.version_info < (3, 6):
            print("❌ 需要Python 3.6或更高版本")
            return False
        print(f"✅ Python版本: {sys.version.split()[0]}")
        return True
    
    # ...（中间的所有方法保持不变）...

    def run_scanner(self):
        """运行扫描器"""
        print("\n🚀 开始扫描媒体库...")
        print("正在连接服务器，请等待...")
        
        # 运行真正的扫描功能
        report_path = self.run_real_scanner()
        
        if report_path:
            print(f"\n✅ 扫描完成！")
            print(f"📄 报告文件: {report_path}")
            print("\n💡 如何查看报告:")
            print(f"1. 文件位置: {report_path}")
            print(f"2. 查看命令: cat '{report_path}'")
            print(f"3. 或者在主菜单中选择「查看扫描报告」")
        else:
            print("❌ 扫描失败")
        
        input("\n按回车键返回主菜单...")
    
    def show_reports(self):
        """显示报告文件"""
        self.clear_screen()
        self.print_banner()
        print("\n📊 扫描报告列表")
        print("=" * 50)
        
        reports = []
        for file in os.listdir(self.script_dir):
            if file.startswith("emby_library_report_") and file.endswith(".txt"):
                file_path = os.path.join(self.script_dir, file)
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                file_size = os.path.getsize(file_path)
                reports.append((file, file_time, file_size))
        
        if not reports:
            print("暂无扫描报告")
            print("请先运行扫描功能生成报告")
        else:
            reports.sort(key=lambda x: x[1], reverse=True)
            
            print(f"找到 {len(reports)} 个报告文件:")
            for i, (report, report_time, size) in enumerate(reports[:10], 1):
                time_str = report_time.strftime("%Y-%m-%d %H:%M")
                size_kb = size / 1024
                print(f"{i}. {report}")
                print(f"   生成时间: {time_str} | 大小: {size_kb:.1f}KB")
            
            choice = input("\n输入报告编号查看，或按回车返回: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(reports):
                self.view_report(reports[int(choice)-1][0])
        
        input("\n按回车键返回主菜单...")
    
    def view_report(self, filename):
        """查看报告内容"""
        file_path = os.path.join(self.script_dir, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            page_size = 20
            current_page = 0
            
            while current_page * page_size < len(lines):
                self.clear_screen()
                print(f"📄 报告文件: {filename}")
                print(f"📍 文件路径: {file_path}")
                print(f"📄 页码: {current_page + 1}/{(len(lines)-1)//page_size + 1}")
                print("=" * 70)
                
                start = current_page * page_size
                end = min((current_page + 1) * page_size, len(lines))
                
                for i, line in enumerate(lines[start:end], start + 1):
                    print(f"{i:3d}. {line}")
                
                print("=" * 70)
                if end < len(lines):
                    action = input("回车看下一页，q退出，f查看文件路径: ").lower()
                    if action == 'q':
                        break
                    elif action == 'f':
                        print(f"\n📁 报告文件完整路径: {file_path}")
                        print("💡 你可以用以下命令查看:")
                        print(f"   cat '{file_path}'")
                        print(f"   nano '{file_path}'")
                        input("\n按回车继续...")
                    current_page += 1
                else:
                    print(f"\n📁 报告文件完整路径: {file_path}")
                    input("已到报告末尾，按回车返回...")
                    break
                    
        except Exception as e:
            print(f"❌ 读取报告失败: {e}")
            input("按回车键继续...")
    
    def show_system_info(self):
        """显示系统信息"""
        self.clear_screen()
        self.print_banner()
        
        print("🔧 系统信息")
        print("=" * 50)
        print(f"工具版本: v{self.version}")
        print(f"Python版本: {sys.version.split()[0]}")
        print(f"脚本目录: {self.script_dir}")
        
        if self.server_url:
            print(f"服务器地址: {self.server_url}")
        
        # 检查配置文件
        config_file = os.path.join(self.script_dir, 'emby_config.json')
        if os.path.exists(config_file):
            config_time = datetime.fromtimestamp(os.path.getctime(config_file))
            print(f"配置时间: {config_time.strftime('%Y-%m-%d %H:%M')}")
        
        # 检查报告文件
        reports = [f for f in os.listdir(self.script_dir) 
                  if f.startswith("emby_library_report_") and f.endswith(".txt")]
        print(f"扫描报告数量: {len(reports)} 个")
        
        if reports:
            latest_report = max(reports, key=lambda f: os.path.getctime(os.path.join(self.script_dir, f)))
            report_time = datetime.fromtimestamp(os.path.getctime(os.path.join(self.script_dir, latest_report)))
            print(f"最新报告: {latest_report}")
            print(f"生成时间: {report_time.strftime('%Y-%m-%d %H:%M')}")
        
        input("\n按回车键返回主菜单...")
    
    def show_help(self):
        """显示帮助信息"""
        self.clear_screen()
        self.print_banner()
        print("""
📖 使用指南

🎯 主要功能:
- 智能检测重复的电影和电视剧
- 基于TMDB ID识别重复内容
- 自动生成详细扫描报告

📁 文件位置说明:
- 配置文件: 脚本目录/emby_config.json
- 扫描报告: 脚本目录/emby_library_report_时间戳.txt
- 虚拟环境: ~/emby-scanner-env/

🔍 查看报告的方法:
1. 在主菜单中选择「查看扫描报告」
2. 使用命令: cat 报告文件名.txt
3. 报告文件保存在脚本同一目录下

💡 温馨提示:
- 首次使用需要配置服务器信息
- 大型媒体库扫描需要一些时间
- 报告文件会显示完整的文件路径
""")
        input("\n按回车键返回主菜单...")
    
    def main_menu(self):
        """主菜单"""
        while True:
            self.clear_screen()
            self.print_banner()
            
            if self.server_url and self.api_key:
                display_url = self.server_url
                if len(display_url) > 35:
                    display_url = display_url[:32] + "..."
                print(f"当前服务器: {display_url}")
                print("配置状态: ✅ 已配置")
            else:
                print("配置状态:  ❌ 未配置")
            
            menu_options = {
                "1": "🚀 开始扫描媒体库",
                "2": "⚙️  重新配置服务器",
                "3": "📊 查看扫描报告", 
                "4": "🔧 系统信息",
                "5": "📖 使用指南",
                "0": "🚪 退出程序"
            }
            
            self.print_menu("主菜单", menu_options)
            
            choice = input("请输入选项 [0-5]: ").strip()
            
            if choice == "1":
                if not self.server_url or not self.api_key:
                    print("❌ 请先配置服务器信息")
                    input("按回车键继续...")
                    continue
                self.run_scanner()
            elif choice == "2":
                if self.setup_wizard():
                    self.load_config()
            elif choice == "3":
                self.show_reports()
            elif choice == "4":
                self.show_system_info()
            elif choice == "5":
                self.show_help()
            elif choice == "0":
                print("\n👋 感谢使用！")
                print(f"项目地址: {self.github_url}")
                break
            else:
                print("❌ 无效选择，请重新输入")
                input("按回车键继续...")

def main():
    """主函数"""
    setup = EmbyScannerSetup()
    
    # 尝试加载现有配置
    setup.load_config()
    
    # 如果未配置，运行设置向导
    if not setup.server_url or not setup.api_key:
        if not setup.setup_wizard():
            return
    
    # 显示主菜单
    setup.main_menu()

if __name__ == "__main__":
    main()
