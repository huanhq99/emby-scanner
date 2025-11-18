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
    
    def setup_virtualenv(self):
        """设置虚拟环境"""
        print("\n🚀 设置虚拟环境...")
        
        if os.path.exists(self.venv_path):
            print("✅ 虚拟环境已存在")
            return True
        
        try:
            print("创建虚拟环境中...")
            result = subprocess.run([
                sys.executable, "-m", "venv", self.venv_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 虚拟环境创建成功")
                return True
            else:
                print(f"❌ 虚拟环境创建失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 虚拟环境设置失败: {e}")
            return False
    
    def install_dependencies(self):
        """安装依赖"""
        print("\n📦 安装依赖包...")
        
        pip_path = os.path.join(self.venv_path, "bin", "pip")
        if os.name == 'nt':
            pip_path = os.path.join(self.venv_path, "Scripts", "pip.exe")
        
        try:
            result = subprocess.run([
                pip_path, "install", "requests"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 依赖安装成功")
                return True
            else:
                print(f"❌ 依赖安装失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 依赖安装失败: {e}")
            return False
    
    def show_server_examples(self):
        """显示服务器地址示例"""
        print("\n💡 服务器地址示例:")
        print("  - 本地服务器: http://192.168.1.100:8096")
        print("  - 本地服务器: http://localhost:8096") 
        print("  - 远程服务器: https://your-domain.com")
        print("  - 远程服务器: https://emby.example.com")
        print("  - 默认端口: 8096 (HTTP) 或 8920 (HTTPS)")
    
    def show_api_help(self):
        """显示API密钥获取帮助"""
        print("\n📋 如何获取API密钥:")
        print("1. 登录Emby网页管理界面")
        print("2. 点击右上角用户图标 → 下拉菜单选择「高级」")
        print("3. 在左侧菜单选择「API密钥」")
        print("4. 点击「新建API密钥」按钮")
        print("5. 输入描述（如：扫描工具），点击「确定」")
        print("6. 复制生成的API密钥")
    
    def get_emby_config(self):
        """获取Emby配置"""
        print("\n⚙️  Emby服务器配置")
        print("=" * 50)
        
        self.show_server_examples()
        
        while True:
            self.server_url = self.get_user_input("\n请输入Emby服务器地址").strip()
            if not self.server_url:
                print("❌ 服务器地址不能为空")
                continue
            
            if not self.server_url.startswith(('http://', 'https://')):
                self.server_url = 'http://' + self.server_url
                print(f"💡 已自动添加协议: {self.server_url}")
            
            if '://' not in self.server_url:
                print("❌ 服务器地址格式不正确")
                continue
                
            break
        
        self.show_api_help()
        
        while True:
            self.api_key = self.get_user_input("\n请输入API密钥").strip()
            if not self.api_key:
                print("❌ API密钥不能为空")
                continue
                
            if len(self.api_key) < 10:
                confirm = input("⚠️  API密钥似乎过短，是否继续？(y/n): ").lower()
                if confirm != 'y':
                    continue
            
            break
        
        print("\n🔗 测试服务器连接...")
        if self.test_connection():
            print("✅ 连接成功！配置验证通过")
            return True
        else:
            print("❌ 连接测试失败")
            retry = input("\n是否重新配置？(y/n): ").lower()
            if retry == 'y':
                return self.get_emby_config()
            return False
    
    def test_connection(self):
        """测试Emby连接"""
        try:
            headers = {'X-Emby-Token': self.api_key}
            response = requests.get(f"{self.server_url}/emby/System/Info", 
                                  headers=headers, timeout=15)
            
            if response.status_code == 200:
                system_info = response.json()
                server_name = system_info.get('ServerName', '未知')
                version = system_info.get('Version', '未知')
                print(f"✅ 连接成功!")
                print(f"   服务器名称: {server_name}")
                print(f"   Emby版本: {version}")
                return True
            else:
                print(f"❌ 服务器返回错误: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            print("❌ 连接超时（15秒），请检查服务器地址和网络")
            return False
        except requests.exceptions.ConnectionError:
            print("❌ 无法连接到服务器，请检查地址和端口")
            return False
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    def save_config(self):
        """保存配置到文件"""
        config = {
            'server_url': self.server_url,
            'api_key': self.api_key,
            'last_updated': datetime.now().isoformat(),
            'version': self.version
        }
        
        config_file = os.path.join(self.script_dir, 'emby_config.json')
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ 配置保存失败: {e}")
            return False
    
    def load_config(self):
        """从文件加载配置"""
        config_file = os.path.join(self.script_dir, 'emby_config.json')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.server_url = config.get('server_url', '')
                self.api_key = config.get('api_key', '')
                return True
            except:
                pass
        return False

    # ========================= 扫描功能 =========================
    
    def get_libraries(self):
        """获取所有媒体库"""
        try:
            headers = {'X-Emby-Token': self.api_key}
            response = requests.get(f"{self.server_url}/emby/Library/MediaFolders", 
                                  headers=headers, timeout=30)
            response.raise_for_status()
            return response.json().get('Items', [])
        except Exception as e:
            print(f"❌ 获取媒体库失败: {e}")
            return []
    
    def run_scanner(self):
        """运行扫描器"""
        print("\n🚀 开始扫描媒体库...")
        print("正在连接服务器，请等待...")
        
        libraries = self.get_libraries()
        if not libraries:
            print("❌ 未找到任何媒体库")
            input("\n按回车键返回主菜单...")
            return
        
        print(f"✅ 找到 {len(libraries)} 个媒体库")
        
        # 生成报告文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"emby_library_report_{timestamp}.txt"
        report_path = os.path.join(self.script_dir, report_file)
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("Emby媒体库扫描报告\n")
                f.write("=" * 60 + "\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"服务器: {self.server_url}\n")
                f.write(f"媒体库数量: {len(libraries)}\n\n")
                
                for library in libraries:
                    f.write(f"媒体库: {library['Name']}\n")
                    f.write(f"ID: {library['Id']}\n\n")
            
            print(f"\n✅ 扫描完成！")
            print(f"📄 报告文件: {report_file}")
            print(f"📍 文件位置: {self.script_dir}/")
            print("\n💡 查看报告方法:")
            print(f"1. 主菜单 → 查看扫描报告")
            print(f"2. 命令: cat '{report_path}'")
            print(f"3. 命令: nano '{report_path}'")
                
        except Exception as e:
            print(f"❌ 生成报告失败: {e}")
        
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
                print(f"   时间: {time_str} | 大小: {size_kb:.1f}KB")
            
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
                    action = input("回车下一页，q退出，f查看文件路径: ").lower()
                    if action == 'q':
                        break
                    elif action == 'f':
                        print(f"\n📁 报告文件完整路径: {file_path}")
                        print("💡 你可以用以下命令查看:")
                        print(f"   cat '{file_path}'")
                        print(f"   nano '{file_path}'")
                        input("\n按回车继续...")
                    else:
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
        print(f"当前目录: {self.script_dir}")
        
        if self.server_url:
            print(f"服务器: {self.server_url}")
        
        # 检查报告文件
        reports = [f for f in os.listdir(self.script_dir) 
                  if f.startswith("emby_library_report_") and f.endswith(".txt")]
        print(f"报告文件: {len(reports)} 个")
        
        if reports:
            latest = max(reports, key=lambda f: os.path.getctime(os.path.join(self.script_dir, f)))
            print(f"最新报告: {latest}")
        
        input("\n按回车键返回主菜单...")
    
    def show_help(self):
        """显示帮助信息"""
        self.clear_screen()
        self.print_banner()
        print("""
📖 使用指南

🎯 主要功能:
- 扫描Emby媒体库信息
- 生成详细扫描报告
- 查看历史扫描记录

📁 文件位置说明:
- 配置文件: 当前目录/emby_config.json
- 扫描报告: 当前目录/emby_library_report_时间戳.txt

🔍 查看报告方法:
1. 在主菜单中选择「查看扫描报告」
2. 使用命令查看具体文件
3. 报告会显示完整文件路径

💡 温馨提示:
- 首次使用需要配置服务器
- 报告文件保存在脚本同一目录
""")
        input("\n按回车键返回主菜单...")
    
    def setup_wizard(self):
        """设置向导"""
        self.clear_screen()
        self.print_banner()
        
        print("欢迎使用Emby媒体库重复检测工具！")
        print("本向导将引导您完成初始设置。")
        print("=" * 50)
        
        if not self.check_python():
            input("\n按回车键退出...")
            return False
        
        if not self.setup_virtualenv():
            input("\n按回车键退出...")
            return False
        
        if not self.install_dependencies():
            input("\n按回车键退出...")
            return False
        
        if not self.get_emby_config():
            input("\n按回车键退出...")
            return False
        
        if self.save_config():
            print("✅ 配置已保存到本地文件")
        else:
            print("⚠️  配置保存失败，下次需要重新输入")
        
        print("\n🎉 初始设置完成！")
        input("\n按回车键进入主菜单...")
        return True
    
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
                print("配置状态: ❌ 未配置")
            
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
