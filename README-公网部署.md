# 碱蓬火智能美育综合分析平台 V2.0 — 部署指南

## 一、本地运行（已有）
双击 `启动系统.bat`，浏览器访问 http://127.0.0.1:5001
演示账号：13800000000 / 123456
服务监听 0.0.0.0:5001（局域网内其他电脑可输入 本机IP:5001 访问）

## 二、部署到公网（换台电脑在浏览器输入网址即可访问）

本平台为 Flask + SQLite 应用，推荐以下两种免费方案：

### 方案 A：Render.com（推荐，全程网页操作，免费层可用）
1. 准备一个 GitHub 账号；把整个 `碱蓬火智能美育综合分析平台` 文件夹作为仓库推送到 GitHub
   （仓库名建议：jianpenghuo-platform）
2. 注册/登录 https://render.com （用 GitHub 账号直接登录）
3. 首页点 New + → Web Service → 连接你的 GitHub 仓库
4. 自动识别配置（仓库中已备好 requirements.txt / runtime.txt / Procfile）：
   - Name：jianpenghuo
   - Environment：Python
   - Build Command：pip install -r requirements.txt
   - Start Command：gunicorn app:app
   - Instance Type：Free
5. 点 Create Web Service，等待 3-5 分钟部署完成
6. 完成后获得公网地址，形如 https://jianpenghuo.onrender.com —— 任何电脑浏览器输入即可访问

注意：
- 免费实例约 15 分钟无访问会休眠，再次访问自动唤醒（首次约 30 秒）
- 免费实例重启后 SQLite 演示数据会重置为种子数据，属正常现象
- 生产环境请关闭验证码泄露：Settings → Environment 添加环境变量 `SMS_DEMO=0`，
  此时注册页不再回显验证码（如需真实短信，需自行接入短信平台）

### 方案 B：PythonAnywhere（数据持久，适合长期使用）
1. 注册 https://www.pythonanywhere.com （免费账号）
2. Web 标签 → Add a new web app → Manual configuration → Python 3.11
3. 用 Files 标签上传 app.py、templates/、static/ 全部文件
4. 在 Bash 控制台执行：pip install flask gunicorn
5. Web 标签修改 WSGI 配置指向你的 app.py（flask_app = app）
6. 保存并 Reload，获得公网地址 https://你的用户名.pythonanywhere.com

## 三、公网访问后的注意事项
- 开放注册默认开启（演示验证码）。对外公开访问时务必设置环境变量 `SMS_DEMO=0`
  或在 /api/register 前增加管理员审核，防止无关人员注册占用数据
- SQLite 数据库文件位于 data/system.db；本地运行数据与公网实例相互独立
- 如需修改端口：本地运行改 app.py 中 app.run(host='0.0.0.0', port=5001)

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