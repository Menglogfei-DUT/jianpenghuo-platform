# 碱蓬火智能美育综合分析平台 V2.0 — 部署指南

## 一、本地运行
双击 `启动系统.bat`，浏览器访问 http://127.0.0.1:5001
演示账号：13800000000 / 123456
服务监听 0.0.0.0:5001（局域网内其他电脑可输入 本机IP:5001 访问）

## 二、部署到公网（换台电脑在浏览器输入网址即可访问）

本平台为 Flask + SQLite + ECharts 应用，代码已推送至
GitHub：https://github.com/Menglogfei-DUT/jianpenghuo-platform
仓库已备好 `requirements.txt`、`wsgi.py`（WSGI 入口）、`runtime.txt`。

### 方案 B：PythonAnywhere（免费、免绑卡，本次采用方案）

1. 注册免费 Beginner 账号：https://www.pythonanywhere.com/registration/register/beginner/
   注册用户名即公网子域前缀，最终网址为 https://<用户名>.pythonanywhere.com
2. 顶部打开 **Consoles → Bash**（或已存在的 Bash console），执行克隆：
   ```bash
   git clone https://github.com/Menglogfei-DUT/jianpenghuo-platform.git
   ```
3. 安装依赖（系统 Python 已自带 numpy/pandas，缺失包会自动补装）：
   ```bash
   pip install --user -r jianpenghuo-platform/requirements.txt
   ```
4. 顶部 **Web 标签 → Add a new web app**：
   - 点 **Manual configuration**（不要选 Flask 样板）
   - Python 版本选最新的 3.11（界面上可选版本为准）
5. 在 Web 标签的 **Code** 区域点开 **WSGI configuration file**，
   把默认内容替换为（注意把 `<用户名>` 换成你的实际用户名）：
   ```python
   import os, sys
   project_home = '/home/<用户名>/jianpenghuo-platform'
   if project_home not in sys.path:
       sys.path.insert(0, project_home)
   os.chdir(project_home)
   from wsgi import application
   ```
6. 在 **Static files** 区域添加一条映射：
   - URL：`/static/`
   - Directory：`/home/<用户名>/jianpenghuo-platform/static/`
7. 保存后点绿色 **Reload** 按钮，访问
   https://<用户名>.pythonanywhere.com 即可。

注意：
- 免费 Beginner 账号只能创建 1 个 Web App；SQLite 库 `data/system.db`
  首次访问时由 `init_db()` 自动创建并写入演示种子数据，位于项目目录内、持久保存。
- 免费账号 90 天不登录会被清理；出站网络走官方白名单（github.com、pypi.org 在列）。
- 免费层不支持自定义域名、不跑常驻后台进程；本平台为短请求 Web 应用，不受影响。
- 公网对外使用时建议在 Web 标签 **Security → Environment** 增加环境变量
  `SMS_DEMO=0`，关闭注册验证码回显；如需真实短信需自行接入短信平台。

### 方案 A：Render.com（备选；免费层需绑卡做身份验证，仅验证不扣费）

1. 注册/登录 https://render.com （用 GitHub 账号直接登录）
2. New + → Web Service → 连接 GitHub 仓库 `Menglogfei-DUT/jianpenghuo-platform`
3. 配置（仓库内配置文件可被自动识别）：
   - Name：jianpenghuo；Environment：Python 3
   - Build Command：`pip install -r requirements.txt`
   - Start Command：`gunicorn app:app`
   - Instance Type：Free
4. 创建后等待 3-5 分钟，获得 https://jianpenghuo.onrender.com
5. 免费实例约 15 分钟无访问休眠（唤醒约 30 秒）；重启后 SQLite 重置为种子数据。
6. 创建免费服务前 Render 会要求添加银行卡完成身份验证，可后续删除支付方式。

## 三、公网访问注意事项
- 本地运行数据与公网实例相互独立；SQLite 文件位于 `data/system.db`。
- 修改代码后：本地调试通过 → git commit / push → PythonAnywhere 端在 Bash 执行
  `cd jianpenghuo-platform && git pull`，再到 Web 标签点 **Reload**。

## 四、V2.0 功能清单
- 手机号注册/登录（绑定手机号，验证码演示模式）
- 总览看板：五育雷达图、等级分布、三阶段趋势
- 学生档案：信息管理 + 数字成长档案（五育×三阶段矩阵、评语、作品记录）
- 综合评价：德智体美劳 × 学期初/中/末 评价矩阵，自动均分、评级、评语
- 作品评价：AI 评分（完成度40%+创意性35%+技法25%）+ 教师评分 人机协同
- 成长指南：五育短板诊断、提升目标、行动清单、家校协作建议
- 区域分析：输入地名自动检索官方统计数据（内置南乐县、凉山州），
  自动生成综合指数、评级、短板诊断与对策建议
- 报告导出：A4 打印版成长档案（可另存为 PDF）
