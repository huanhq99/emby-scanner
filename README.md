# Emby媒体库重复检测工具

一个简单易用的Emby媒体库重复内容检测工具，具有友好的交互式界面。

##  ✨ 功能特性

-  🎯 **智能重复检测**：基于TMDB ID和文件大小智能识别重复内容
-  🖥️ **交互式界面**：数字菜单选择，小白也能轻松使用
-  🔧 **自动环境配置**：自动创建Python虚拟环境并安装依赖
-  💾 **配置持久化**：一次配置，永久使用
-  📊 **详细报告**：自动生成带时间戳的文本报告
-  🔄 **配置验证**：连接测试确保配置正确

##  快速开始

### 方法一：直接下载运行
```bash
# 下载脚本
wget https://raw.githubusercontent.com/huanhq99/emby-scanner/main/emby_scanner.py

# 运行脚本
python3 emby_scanner.py

方法二：克隆仓库（推荐）
# 克隆项目
git clone https://github.com/huanhq99/emby-scanner.git
cd emby-scanner

# 运行脚本
python3 emby_scanner.py

📋 使用指南
首次使用流程
运行脚本：python3 emby_scanner.py
环境配置：脚本自动设置Python虚拟环境
服务器配置：按照提示输入Emby服务器信息
开始扫描：在主菜单中选择扫描选项
查看报告：扫描完成后查看生成的报告
主菜单功能
🚀 开始扫描媒体库：执行重复内容检测
⚙️ 重新配置服务器：修改服务器设置
📊 查看扫描报告：浏览历史扫描结果
🔧 系统信息：查看运行环境信息
📖 使用指南：查看帮助文档
⚙️ 配置说明
Emby服务器地址格式
本地服务器示例：
http://192.168.1.100:8096
http://localhost:8096

远程服务器示例：
https://your-domain.com
https://emby.example.com:8920
API密钥获取步骤
登录Emby网页管理界面
点击右上角用户图标 → 选择「高级」
左侧菜单选择「API密钥」
点击「新建API密钥」
输入描述信息，点击「确定」
复制生成的API密钥
📊 报告示例
Emby媒体库重复检测报告
========================================
扫描时间: 2024-01-01 12:00:00
服务器: https://your-emby-server.com

📁 媒体库: 电影
项目数量: 1250
总大小: 2.1 TB

🔴 TMDB ID重复 (3组):
    TMDB-ID: 12345
    重复数量: 2个版本
    总大小: 15.3 GB

📁 媒体库: 电视剧  
项目数量: 500
总大小: 3.5 TB

✅ 未发现重复资源

❓ 常见问题
Q: 运行脚本时提示"command not found"
A: 系统未安装Python3，请安装Python 3.6或更高版本：
# Ubuntu/Debian
sudo apt update && sudo apt install python3

# CentOS/RHEL
sudo yum install python3
Q: 连接Emby服务器失败
A: 检查以下项目：

服务器地址是否正确（包含http://或https://）
API密钥是否有读取媒体库的权限
网络连接是否正常
服务器防火墙设置
Q: 扫描过程很慢
A: 这是正常现象，大型媒体库扫描需要时间：

电影库：约1-2分钟/千部电影
电视剧库：约2-3分钟/百部剧集
Q: 如何重新配置服务器？
A: 在主菜单中选择「重新配置服务器」选项，或删除本地的emby_config.json文件重新运行。

Q: 报告文件保存在哪里？
A: 报告文件保存在脚本同一目录下，文件名格式：emby_library_report_年月日_时分秒.txt

🐛 问题反馈
如果你遇到问题，请按以下步骤反馈：

查看错误信息截图
提供你的系统信息（Python版本、操作系统）
描述问题的具体表现
在GitHub Issues中提交问题
Issue模板：
## 问题描述
[详细描述遇到的问题]

## 复现步骤
1. 
2. 
3. 

## 预期行为
[期望的正常表现]

## 实际行为
[实际遇到的异常]

## 环境信息
- 操作系统: [如Ubuntu 20.04]
- Python版本: [如Python 3.8.10]
- Emby版本: [如4.7.11.0]
🤝 贡献指南
我们欢迎各种形式的贡献！

代码贡献
Fork本仓库
创建特性分支：git checkout -b feature/新功能
提交更改：git commit -m '添加新功能'
推送到分支：git push origin feature/新功能
提交Pull Request
功能建议
如果你有新的功能想法，欢迎在Issues中提出！

文档改进
发现文档问题或可以改进的地方？欢迎提交PR！

📝 更新日志
v2.0 (当前版本)
✅ 全新的交互式界面
✅ 自动环境配置
✅ 配置持久化存储
✅ 连接测试验证
✅ 分页报告查看器
v1.0
基础扫描功能
简单重复检测
⭐ 支持项目
如果这个工具对你有帮助，请考虑：

给个Star ⭐ - 让更多人看到这个项目
分享给朋友 👥 - 帮助更多Emby用户
提交反馈 💡 - 帮助改进工具
贡献代码 🔧 - 一起完善功能
📄 许可证
MIT License - 详见 LICENSE 文件

🔗 相关链接
Emby官方网站
Python官方网站
GitHub仓库
注意: 本工具仅供个人学习使用，请遵守相关法律法规和Emby的使用条款。
