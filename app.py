# -*- coding: utf-8 -*-
"""
Jianpenghuo Aesthetic Education Comprehensive Analysis Platform V2.0
Engineered from the "Jianpeng Companion" rural education revitalization project
(Dalian University of Technology) core achievements.

V2.0 updates:
1. Five-dimension model upgraded to "De, Zhi, Ti, Mei, Lao" (morality, intellect,
   physique, aesthetics, labor) - consistent with national "五育并举" policy.
2. Region analysis switched to official open-data search mode: input a place name,
   official statistics and auto-generated diagnosis & countermeasures appear.
3. Redundant pages merged; a cleaner, more advanced interactive UI.
"""
import io
import json
import os
import re
import random
import sqlite3
import time
from datetime import datetime

from flask import (Flask, render_template, request, jsonify, session,
                   redirect, url_for)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'system.db')
DB_VERSION = 2

# ==================== Config dictionaries ====================
# All Chinese texts are centralized here; business code only uses English keys.
I18N = {
    # five dimensions (De Zhi Ti Mei Lao)
    'dim_moral': '品德',
    'dim_intel': '智育',
    'dim_phys': '体育',
    'dim_aest': '美育',
    'dim_labor': '劳动',
    'dim_letter': ['德', '智', '体', '美', '劳'],
    # stages
    'stage_1': '学期初',
    'stage_2': '学期中',
    'stage_3': '学期末',
    # work categories
    'cat_paint': '绘画',
    'cat_music': '音乐',
    'cat_calligraphy': '书法',
    'cat_handcraft': '手工',
    'cat_dance': '舞蹈',
    'cat_other': '其他',
    # score levels
    'lv_excellent': '优秀',
    'lv_good': '良好',
    'lv_fair': '需提升',
    'lv_concern': '需关注',
    # guide levels
    'lv_high': '优势',
    'lv_mid': '良好',
    'lv_low': '待提升',
    # region status / level
    'st_ok': '达标',
    'st_approx': '接近',
    'st_fail': '未达标',
    'region_lv1': '优质',
    'region_lv2': '良好',
    'region_lv3': '基本达标',
    'region_lv4': '待改善',
    # misc
    'not_evaluated': '未评价',
    'gender_male': '男',
    'gender_female': '女',
    'unassigned_class': '未分班',
}

DIM_KEYS = ['dim_moral', 'dim_intel', 'dim_phys', 'dim_aest', 'dim_labor']
STAGE_KEYS = ['stage_1', 'stage_2', 'stage_3']
CAT_KEYS = ['cat_paint', 'cat_music', 'cat_calligraphy',
            'cat_handcraft', 'cat_dance', 'cat_other']
LEVELS = [(85, 'lv_excellent'), (70, 'lv_good'), (60, 'lv_fair'), (0, 'lv_concern')]
AI_ALPHA = 0.5  # final_score = alpha * ai_score + (1-alpha) * teacher_score

# API response messages
MSG = {
    'login_required': '请先登录',
    'phone_invalid': '手机号格式不正确，需为11位大陆手机号',
    'phone_invalid_short': '手机号格式不正确',
    'code_sent': '验证码已发送（演示模式：{code}，5分钟内有效）',
    'code_sent_prod': '验证码已发送至您的手机（生产模式，5分钟内有效）',
    'pwd_short': '密码长度至少6位',
    'code_wrong': '验证码错误或已过期，请重新获取',
    'phone_registered': '该手机号已注册，请直接登录',
    'register_ok': '注册成功，已自动登录',
    'login_fail': '手机号或密码错误',
    'login_ok': '登录成功',
    'logout_ok': '已退出登录',
    'not_login': '未登录',
    'name_empty': '学生姓名不能为空',
    'add_ok': '添加成功',
    'deleted': '已删除',
    'select_student': '请先选择学生',
    'dims_saved': '五育评价已保存',
    'work_need': '请选择学生并填写作品标题',
    'work_saved': '作品评价已保存',
    'student_not_found': '学生不存在',
    'data_incomplete': '该生五育数据不完整，请先在"综合评价"录入',
    'param_error': '参数错误',
    'region_ok': '已检索到该地区官方统计信息',
    'region_empty': '请输入要分析的地区名称',
    'region_not_found': '暂未收录该地区的官方统计数据，可尝试：{hint}',
}

# Personalized comment templates
COMMENT = {
    'sep': '；',
    'space': ' ',
    'dim_high': '【{dim}】表现突出（{score:.1f}分），是班级中的榜样，希望继续保持这份热爱',
    'dim_good': '【{dim}】发展良好（{score:.1f}分），基础扎实，仍有提升空间',
    'dim_mid': '【{dim}】尚有潜力（{score:.1f}分），建议增加练习与参与机会',
    'dim_low': '【{dim}】需要关注（{score:.1f}分），请老师与家长共同引导',
    'tip_mid': '{dim}方面建议多参与课堂活动、加强日常练习',
    'tip_low': '{dim}方面建议家校协同，制定阶段提升小目标',
    'head_total': '综合评定为{lv}（{total:.1f}分）。',
    'advice_tips': '专项指导意见：{tips}',
    'advice_none': '五育发展均衡，建议持续拓展艺术特长，向更高水平迈进。',
    'work_ok': 'AI评分与教师评分较为一致，评估信度高',
    'work_gap': 'AI评分与教师评分存在差异，建议结合课堂观察复核',
    'work_head': '该{category}作品综合评级为{lv}（{final:.1f}分）。{gap}。',
}

# Family cooperation advice templates
FAMILY = {
    'low': '{dim}：请家长配合落实每日小目标，多用肯定式沟通，避免横向比较',
    'high': '{dim}：提供展示平台（作品上墙、上台表演），让特长持续发光',
    'mid': '{dim}：每周与孩子聊一次课堂收获，鼓励其主动参与',
}

# Individual growth advice (five-dimension, De Zhi Ti Mei Lao)
DIM_ADVICE = {
    'dim_moral': {
        'high': '品德表现突出，建议担任班级服务岗或小队干部，在服务他人中进一步锻炼责任担当；可引导参与学校志愿活动，发挥榜样示范作用。',
        'mid': '品德发展基础良好，建议通过每周一件好事记录、值日组长等小岗位锻炼，强化诚信友善与责任意识。',
        'low': '品德发展需重点关注，建议家校协同营造正向榜样环境：教师在日常中及时肯定微小的善行，家长通过家务分工、诚信约定等小事培养责任感，建立每周沟通反馈。',
        'act': ['设立班级小岗位（如图书管理员）并每周反馈', '记录"每周一件好事"成长日志', '家长陪伴参与一次社区志愿服务']},
    'dim_intel': {
        'high': '学习能力突出，建议拓展学科阅读与思维挑战（如趣味数学、科学小实验），尝试担任学习小组组长，带动同伴共同进步。',
        'mid': '学业基础扎实，建议制定"错题本+每日一题"计划，加强薄弱学科专项训练，每两周复盘一次学习效果。',
        'low': '学业水平需重点帮扶，建议：教师利用课后服务开展结对辅导；制定小步子学习目标（每日完成基础练习）；家长营造固定学习时段，减少干扰；及时肯定每一次进步。',
        'act': ['建立错题本，每周复习一遍', '每天完成1道基础提升题', '与学习伙伴结对，每周互查作业']},
    'dim_phys': {
        'high': '身体素质良好，建议保持每日运动习惯，可加入学校体育社团或兴趣队，注意劳逸结合与用眼卫生。',
        'mid': '身体素质良好，建议增加户外活动时间（每天至少1小时），规律作息，控制电子产品使用时长。',
        'low': '体质健康需关注，建议：保障充足睡眠（小学生10小时）；每天安排30分钟以上户外运动；如有情绪困扰及时与心理老师沟通；家长减少学业加压，多安排亲子运动。',
        'act': ['每天户外运动30-60分钟', '21:00前完成作业、保证睡眠', '每周1次亲子运动或户外活动']},
    'dim_aest': {
        'high': '艺术天赋突出，建议加入学校艺术社团（合唱/绘画/书法），鼓励参加校级及以上展演，让特长被看见。',
        'mid': '艺术素养有较好基础，建议每周固定1-2次艺术练习（绘画、歌唱、手工等），多欣赏优秀作品提升审美。',
        'low': '艺术素养需激发兴趣，建议：从孩子喜欢的艺术形式入手（涂鸦、动画、儿歌）；提供简便材料随时可创作；多参加班级美育活动获得成功体验；教师及时展示其作品增强信心。',
        'act': ['每周完成1幅画或1件手工作品', '每月学唱1首新歌或欣赏1部艺术短片', '作品在班级展示角展出']},
    'dim_labor': {
        'high': '劳动实践能力强，建议参与校内劳动基地、社区服务或家务劳动规划，将劳动体验写成观察日记，锻炼动手与责任意识。',
        'mid': '劳动实践参与较好，建议增加劳动机会：参与校园值周、班级卫生责任区、家庭家务分工等，每次劳动后做口头或书面分享。',
        'low': '劳动实践参与不足，建议从低门槛活动开始：班级值日组长、校园环保行动、整理书包书桌；家长周末安排家务分工；教师安排同伴带领参与，逐步建立劳动习惯。',
        'act': ['每天承担1项固定家务（整理书桌/洗碗/扫地）', '每学期参加2次以上集体劳动实践活动', '完成1份劳动实践记录（画或文字）']},
}
ADVICE_LEVELS = {'high': (85, 101), 'mid': (70, 85), 'low': (0, 70)}
# ==================== Official open region statistics ====================
# Data sources: official government statistical bulletins & education bureaus.
# Every record keeps its real source and year; target values follow national or
# provincial reference standards and are clearly labelled as "reference targets".
REGION_STATS = {
    'nanle': {
        'names': ['南乐县', '河南南乐', '南乐', '濮阳南乐', '河南省濮阳市南乐县'],
        'full_name': '河南省濮阳市南乐县',
        'level': '县（区）级',
        'year_range': '2019-2026',
        'source': '南乐县人民政府、濮阳市人民政府、河南省教育厅、濮阳市教育局',
        'summary': '全国义务教育优质均衡发展县（教育部认定）、省"五育"并举实验区、省义务教育阶段课后服务示范区。',
        'indicators': [
            {'key': 'schools', 'name': '各级各类学校数', 'value': 212, 'unit': '所', 'year': 2021,
             'source': '南乐县人民政府·社会发展情况综述', 'kind': 'scale', 'target': None,
             'note': '小学182所（公办149、民办33）、初中22所、高中5所、职业学校1所'},
            {'key': 'kindergarten', 'name': '幼儿园数', 'value': 208, 'unit': '所', 'year': 2021,
             'source': '南乐县人民政府·社会发展情况综述', 'kind': 'scale', 'target': None,
             'note': '各级各类幼儿园208所'},
            {'key': 'teachers', 'name': '专任教师数', 'value': 6800, 'unit': '人', 'year': 2019,
             'source': '濮阳日报·南乐县教育报道', 'kind': 'scale', 'target': None,
             'note': '含市级以上骨干教师458人、省市级学科带头人154人'},
            {'key': 'students', 'name': '在校学生与幼儿数', 'value': 123000, 'unit': '人', 'year': 2019,
             'source': '濮阳日报·南乐县教育报道', 'kind': 'scale', 'target': None,
             'note': '在校学生和幼儿12.3万人'},
            {'key': 'quality_balance', 'name': '义务教育优质均衡创建', 'value': 100, 'unit': '%', 'year': 2026,
             'source': '濮阳市人民政府（全国义务教育优质均衡发展县）', 'kind': 'quality', 'target': 100,
             'note': '2017年认定为义务教育基本均衡县，后获评全国义务教育优质均衡发展县；新增优质学位2万余个'},
            {'key': 'edu_group', 'name': '教育集团覆盖率', 'value': 92.3, 'unit': '%', 'year': 2026,
             'source': '濮阳市人民政府', 'kind': 'quality', 'target': 100,
             'note': '组建21个教育集团，覆盖学校132所，覆盖率92.3%，有效扩大优质教育资源覆盖面'},
            {'key': 'five_edu', 'name': '“五育”并举推进', 'value': 95, 'unit': '%', 'year': 2026,
             'source': '濮阳市人民政府（省"五育"并举实验区）', 'kind': 'quality', 'target': 100,
             'note': '创新"一体两翼 六点支撑"五育培养模式，设立舞蹈、戏曲、美术等社团2000余个'},
            {'key': 'edu_input', 'name': '教育支出占公共财政支出比', 'value': 30, 'unit': '%', 'year': 2019,
             'source': '河南省教育厅', 'kind': 'quality', 'target': 30,
             'note': '近三年教育投入超10亿元，教育投入年均增长30.8%，教育优先保障'},
        ],
    },
    'liangshan': {
        'names': ['凉山州', '凉山', '四川凉山', '凉山彝族自治州'],
        'full_name': '四川省凉山彝族自治州',
        'level': '市（州）级',
        'year_range': '2023-2025',
        'source': '凉山州人民政府、凉山州统计局、凉山州教育和体育局',
        'summary': '全国脱贫攻坚与乡村教育振兴重点地区，控辍保学与义务教育均衡成效显著，九年义务教育巩固率大幅提升。',
        'indicators': [
            {'key': 'schools', 'name': '各级各类学校数（不含幼儿园）', 'value': 911, 'unit': '所', 'year': 2025,
             'source': '凉山州2025年国民经济和社会发展统计公报', 'kind': 'scale', 'target': None,
             'note': '小学725所、初中126所等；另有教学点308个'},
            {'key': 'students', 'name': '在校学生数', 'value': 1015000, 'unit': '人', 'year': 2025,
             'source': '凉山州2025年国民经济和社会发展统计公报', 'kind': 'scale', 'target': None,
             'note': '其中少数民族学生74.6万人'},
            {'key': 'teachers', 'name': '专任教师数', 'value': 58000, 'unit': '人', 'year': 2025,
             'source': '凉山州2025年国民经济和社会发展统计公报', 'kind': 'scale', 'target': None,
             'note': '义务教育阶段专任教师4.22万人（小学2.77万、初中1.45万，2024年教体局口径）'},
            {'key': 'enroll_rate', 'name': '小学学龄儿童入学率', 'value': 99.29, 'unit': '%', 'year': 2025,
             'source': '凉山州2025年国民经济和社会发展统计公报', 'kind': 'quality', 'target': 100,
             'note': '2024年为99.74%，入学保障持续巩固'},
            {'key': 'retention', 'name': '九年义务教育巩固率', 'value': 96.92, 'unit': '%', 'year': 2024,
             'source': '凉山州人民政府（控辍保学成效）', 'kind': 'quality', 'target': 100,
             'note': '由2020年的82.85%大幅提升至96.92%；残疾适龄儿童入学率97.57%'},
            {'key': 'school_infra', 'name': '近三年教育投入与办学改善', 'value': 79, 'unit': '亿元', 'year': 2024,
             'source': '凉山州人民政府', 'kind': 'scale', 'target': None,
             'note': '累计投入79亿元，新建改扩建学校443所，新增学位4万余个、寄宿制床位9万余个'},
            {'key': 'preschool', 'name': '学前三年毛入园率', 'value': 89.7, 'unit': '%', 'year': 2024,
             'source': '凉山教育事业发展纪实（2024）', 'kind': 'quality', 'target': 95,
             'note': '学前教育普及普惠持续推进'},
        ],
    },
}

# Analysis templates for region search
REGION = {
    'sep': '、',
    'weak_item': '{name}（达成度{score:.0f}%）',
    'ok_head': '当前{name}教育发展综合指数为{index}，评级{level}。各项质量指标总体达标，建议保持投入强度，在优质均衡与特色发展上进一步突破。',
    'weak_head': '当前{name}教育发展综合指数为{index}，评级{level}。主要短板集中在：{weak}。',
    'weak_tail': '建议优先补齐师资配置与办学条件短板，再通过课程建设与活动育人提升实际效果。',
    'strong': '相对优势维度：{names}。',
    'data_note': '以上数据均来自{source}（{year}），供分析与决策参考；目标值为国家/省级参考标准。',
}

# Suggestion rules: keyword -> countermeasure text (auto composed from shortboards)
SUGGEST = {
    'quality': '质量短板：优先对照国家义务教育优质均衡标准逐项补差，重点提升{items}对应指标的达标率。',
    'teacher': '师资配置：建议加大音体美劳等紧缺学科教师招聘与"县管校聘"改革力度，推动城乡教师轮岗交流。',
    'balance': '均衡发展：深化集团化办学与结对帮扶，推动优质学位扩容和薄弱学校改造，缩小校际差距。',
    'labor': '劳动教育：落实每周劳动教育课时，建设校内劳动实践基地，联合家庭开展家务劳动清单化管理。',
    'aesthetic': '美育提升：开齐开足美育课程，依托社团与展演平台（如戏曲、舞蹈、美术社团）培养学生艺术素养。',
    'fund': '经费保障：保持教育投入优先，重点向乡村小规模学校和寄宿制学校倾斜，落实生均公用经费标准。',
}

# Seed demo data
SEED = {
    'school_name': '河南南乐中心小学',
    'classes': ['六年级一班', '六年级二班', '五年级一班'],
    'names': ['李小雨', '王浩然', '张梓萱', '刘子墨', '陈思远', '杨欣怡',
              '赵一鸣', '孙梦琪', '周宇航', '吴佳慧', '郑博文', '林可欣'],
    'base_scores': [86, 82, 88, 74, 69, 91, 78, 84, 63, 80, 72, 76],
    'work_titles': {'cat_paint': '我的家乡', 'cat_music': '童声合唱', 'cat_calligraphy': '硬笔楷书',
                    'cat_handcraft': '纸艺灯笼', 'cat_dance': '课间操', 'cat_other': '手抄报'},
}


# ==================== Application ====================
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
app.secret_key = 'jianpenghuo-aesthetic-2026-v2-secret'

SMS_CODES = {}


# ==================== Database ====================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    # V2 migration: if a V1 database exists, back it up and rebuild with new schema/semantics
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            ver = conn.execute('SELECT value FROM meta WHERE key=?', ('db_version',)).fetchone()
            conn.close()
            if ver and int(ver[0]) >= DB_VERSION:
                return
        except Exception:
            pass
        bak = DB_PATH + '.v1_backup.db'
        try:
            os.replace(DB_PATH, bak)
        except OSError:
            os.remove(DB_PATH)
    conn = get_db()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        gender TEXT NOT NULL, grade_class TEXT NOT NULL,
        school TEXT DEFAULT '', created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS dim_scores(
        student_id INTEGER NOT NULL, dim INTEGER NOT NULL,
        stage INTEGER NOT NULL, score REAL NOT NULL,
        PRIMARY KEY(student_id, dim, stage))''')
    c.execute('''CREATE TABLE IF NOT EXISTS works(
        id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
        title TEXT NOT NULL, category TEXT NOT NULL,
        completeness REAL, creativity REAL, technique REAL,
        ai_score REAL, teacher_score REAL, final_score REAL,
        created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL, created_at TEXT, last_login TEXT)''')
    c.execute('INSERT OR REPLACE INTO meta(key, value) VALUES (?,?)', ('db_version', str(DB_VERSION)))
    conn.commit()
    # Seed demo data on first run
    if c.execute('SELECT COUNT(*) FROM students').fetchone()[0] == 0:
        _seed_demo(c)
    if c.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
        c.execute('INSERT OR IGNORE INTO users(phone, password_hash, created_at) VALUES (?,?,?)',
                  ('13800000000', generate_password_hash('123456'),
                   datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()


def _seed_demo(c):
    """Seed demo data: 12 students in 3 classes with improving five-dim trends and works."""
    rng = random.Random(2026)
    schools = SEED['school_name']
    classes = SEED['classes']
    names = SEED['names']
    base = SEED['base_scores']
    titles = {k: SEED['work_titles'][k] for k in CAT_KEYS}
    for i, name in enumerate(names):
        c.execute('INSERT INTO students(name, gender, grade_class, school, created_at) VALUES (?,?,?,?,?)',
                  (name, I18N['gender_female'] if i % 2 else I18N['gender_male'], classes[i % 3], schools,
                   datetime.now().strftime('%Y-%m-%d')))
        sid = c.lastrowid
        b = base[i]
        for dim in range(5):
            # Scores float around the baseline and rise across stages
            for stage in range(3):
                s = b + (dim - 2) * rng.uniform(1, 4) + stage * rng.uniform(1.5, 3.5)
                s = max(45, min(98, s))
                c.execute('INSERT INTO dim_scores(student_id, dim, stage, score) VALUES (?,?,?,?)',
                          (sid, dim + 1, stage + 1, round(s, 1)))
        # 1-2 works per student
        for k in range(1 + (i % 2)):
            cat = rng.choice(CAT_KEYS)
            comp = round(rng.uniform(6, 10), 1)
            crea = round(rng.uniform(5, 10), 1)
            tech = round(rng.uniform(5, 10), 1)
            ai = ai_work_score(comp, crea, tech)
            tch = round(ai + rng.uniform(-8, 8), 1)
            tch = max(40, min(98, tch))
            fin = round(AI_ALPHA * ai + (1 - AI_ALPHA) * tch, 1)
            c.execute('''INSERT INTO works(student_id, title, category, completeness, creativity, technique,
                         ai_score, teacher_score, final_score, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                      (sid, titles[cat], cat, comp, crea, tech, ai, tch, fin,
                       datetime.now().strftime('%Y-%m-%d %H:%M')))

# ==================== Core algorithms ====================
def ai_work_score(completeness, creativity, technique):
    """AI objective scoring: 40% completeness + 35% creativity + 25% technique (0-10 -> 0-100)."""
    return round(40 * completeness / 10 + 35 * creativity / 10 + 25 * technique / 10, 1)


def work_final_score(ai, teacher, alpha=AI_ALPHA):
    """Human-AI dual assessment: final = alpha*AI + (1-alpha)*teacher."""
    return round(alpha * ai + (1 - alpha) * teacher, 1)


def level_of(score):
    for th, name in LEVELS:
        if score >= th:
            return I18N[name]
    return I18N['lv_concern']


def student_avg_score(conn, sid, stage=None):
    """Student average score of latest stage (with data) across five dims."""
    if stage is None:
        row = conn.execute('SELECT MAX(stage) s FROM dim_scores WHERE student_id=?', (sid,)).fetchone()
        stage = row['s'] if row and row['s'] else 1
    rows = conn.execute('SELECT score FROM dim_scores WHERE student_id=? AND stage=?', (sid, stage)).fetchall()
    if not rows:
        return None, stage
    return round(sum(r['score'] for r in rows) / len(rows), 1), stage


def gen_comment(scores):
    """Personalized comment rule engine: comments + targeted advice by score bands."""
    parts = []
    tips = []
    for idx, dim_key in enumerate(DIM_KEYS):
        dim = I18N[dim_key]
        s = scores[idx]
        if s >= 85:
            parts.append(COMMENT['dim_high'].format(dim=dim, score=s))
        elif s >= 70:
            parts.append(COMMENT['dim_good'].format(dim=dim, score=s))
        elif s >= 60:
            parts.append(COMMENT['dim_mid'].format(dim=dim, score=s))
            tips.append(COMMENT['tip_mid'].format(dim=dim))
        else:
            parts.append(COMMENT['dim_low'].format(dim=dim, score=s))
            tips.append(COMMENT['tip_low'].format(dim=dim))
    total = round(sum(scores) / len(scores), 1)
    lv = level_of(total)
    head = COMMENT['head_total'].format(lv=lv, total=total)
    if tips:
        advice = COMMENT['advice_tips'].format(tips=COMMENT['sep'].join(tips))
    else:
        advice = COMMENT['advice_none']
    return head + COMMENT['space'].join(parts) + advice


def gen_work_comment(ai, teacher, final, category):
    lv = level_of(final)
    gap = COMMENT['work_ok'] if abs(ai - teacher) <= 8 else COMMENT['work_gap']
    return COMMENT['work_head'].format(category=category, lv=lv, final=final, gap=gap)


# ==================== Individual growth guide (rule engine) ====================
def _advice_level(score):
    if score >= 85:
        return 'high'
    if score >= 70:
        return 'mid'
    return 'low'


def gen_guide(scores):
    """Generate personalized growth guide: diagnosis + actions + shortboard plan + family cooperation."""
    total = round(sum(scores) / len(scores), 1)
    dims_out = []
    for i, dim_key in enumerate(DIM_KEYS):
        dim = I18N[dim_key]
        letter = I18N['dim_letter'][i]
        s = scores[i]
        lv = _advice_level(s)
        level_name = I18N['lv_high'] if lv == 'high' else (I18N['lv_mid'] if lv == 'mid' else I18N['lv_low'])
        dims_out.append({'dim': dim, 'letter': letter, 'dim_key': dim_key, 'score': s, 'level': lv,
                         'level_name': level_name,
                         'advice': DIM_ADVICE[dim_key][lv], 'acts': DIM_ADVICE[dim_key]['act']})
    # Shortboard (lowest dim) and strength (highest dim)
    low = min(dims_out, key=lambda x: x['score'])
    high = max(dims_out, key=lambda x: x['score'])
    # Next-stage targets: shortboard dim = current + 8 (cap 95), total = current + 3
    low_target = min(95, round(low['score'] + 8))
    total_target = min(98, round(total + 3))
    family = []
    for d in dims_out:
        family.append(FAMILY[d['level']].format(dim=d['dim']))
    return {
        'total': total,
        'level': level_of(total),
        'dims': dims_out,
        'low_dim': {'name': low['dim'], 'letter': low['letter'], 'score': low['score'], 'target': low_target},
        'high_dim': {'name': high['dim'], 'letter': high['letter'], 'score': high['score']},
        'total_target': total_target,
        'family': family,
    }


# ==================== Region analysis (official open data search) ====================
def _find_region(query):
    q = re.sub(r'\s+', '', str(query or '').strip())
    if not q:
        return None
    for key, rec in REGION_STATS.items():
        for nm in rec['names']:
            if q == nm or q in nm or nm in q:
                return key
    return None


def region_analysis(rec):
    """Build region analysis from official statistics record."""
    items = []
    weak, strong = [], []
    for ind in rec['indicators']:
        item = dict(ind)
        if ind['kind'] == 'quality' and ind.get('target'):
            item['score'] = round(min(100, ind['value'] / ind['target'] * 100), 1)
            if item['score'] >= 90:
                item['status'] = I18N['st_ok']
                strong.append(item)
            elif item['score'] >= 70:
                item['status'] = I18N['st_approx']
            else:
                item['status'] = I18N['st_fail']
                weak.append(item)
        else:
            item['score'] = None
            item['status'] = '—'
        items.append(item)
    quality_items = [x for x in items if x['kind'] == 'quality' and x.get('score') is not None]
    index = round(sum(x['score'] for x in quality_items) / len(quality_items), 1) if quality_items else 0
    if index >= 85:
        level, tag = I18N['region_lv1'], 't1'
    elif index >= 70:
        level, tag = I18N['region_lv2'], 't2'
    elif index >= 60:
        level, tag = I18N['region_lv3'], 't3'
    else:
        level, tag = I18N['region_lv4'], 't4'
    name = rec['full_name']
    if weak:
        weak_txt = REGION['sep'].join(REGION['weak_item'].format(name=x['name'], score=x['score'])
                                      for x in weak[:4])
        diag = REGION['weak_head'].format(name=name, index=index, level=level, weak=weak_txt)
        diag += REGION['weak_tail']
    else:
        diag = REGION['ok_head'].format(name=name, index=index, level=level)
    if strong:
        diag += REGION['strong'].format(names=REGION['sep'].join(x['name'] for x in strong[:3]))
    # Auto countermeasures from shortboards
    suggestions = []
    if weak:
        suggestions.append(SUGGEST['quality'].format(items=REGION['sep'].join(x['name'] for x in weak[:3])))
    if any('teacher' in x['key'] for x in items):
        suggestions.append(SUGGEST['teacher'])
    if any('balance' in x['key'] or 'group' in x['key'] for x in items):
        suggestions.append(SUGGEST['balance'])
    if any('labor' in x['key'] for x in items):
        suggestions.append(SUGGEST['labor'])
    if any('aest' in x['key'] or 'five' in x['key'] for x in items):
        suggestions.append(SUGGEST['aesthetic'])
    if any('fund' in x['key'] or 'input' in x['key'] for x in items):
        suggestions.append(SUGGEST['fund'])
    if not suggestions:
        suggestions = [SUGGEST['balance'], SUGGEST['teacher']]
    return {
        'full_name': rec['full_name'], 'level': rec['level'],
        'year_range': rec['year_range'], 'source': rec['source'],
        'summary': rec['summary'],
        'items': items, 'index': index, 'level': level, 'tag': tag,
        'diag': diag, 'suggestions': suggestions[:5],
        'data_note': REGION['data_note'].format(source=rec['source'], year=rec['year_range']),
    }


# ==================== User authentication ====================
PHONE_RE = re.compile(r'^1[3-9]\d{9}$')


@app.route('/login')
def page_login():
    return render_template('login.html')


@app.route('/register')
def page_register():
    return render_template('login.html')


@app.before_request
def require_login():
    p = request.path
    if p.startswith('/static') or p == '/favicon.ico':
        return None
    if p in ('/login', '/register'):
        return None
    if p.startswith('/api/'):
        if p in ('/api/login', '/api/register', '/api/send_code'):
            return None
        if 'user' not in session:
            return jsonify({'ok': False, 'msg': MSG['login_required']}), 401
        return None
    if 'user' not in session:
        return redirect(url_for('page_login'))
    return None


@app.route('/api/send_code', methods=['POST'])
def api_send_code():
    d = request.get_json(force=True)
    phone = str(d.get('phone', '')).strip()
    if not PHONE_RE.match(phone):
        return jsonify({'ok': False, 'msg': MSG['phone_invalid']})
    code = str(random.randint(100000, 999999))
    SMS_CODES[phone] = {'code': code, 'expire': time.time() + 300}
    if os.environ.get('SMS_DEMO', '0') == '1':
        return jsonify({'ok': True, 'msg': MSG['code_sent'].format(code=code), 'demo_code': code})
    return jsonify({'ok': True, 'msg': MSG['code_sent_prod']})


@app.route('/api/register', methods=['POST'])
def api_register():
    d = request.get_json(force=True)
    phone = str(d.get('phone', '')).strip()
    code = str(d.get('code', '')).strip()
    password = d.get('password', '')
    if not PHONE_RE.match(phone):
        return jsonify({'ok': False, 'msg': MSG['phone_invalid_short']})
    if len(password) < 6:
        return jsonify({'ok': False, 'msg': MSG['pwd_short']})
    rec = SMS_CODES.get(phone)
    if not rec or rec['code'] != code or rec['expire'] < time.time():
        return jsonify({'ok': False, 'msg': MSG['code_wrong']})
    conn = get_db()
    if conn.execute('SELECT id FROM users WHERE phone=?', (phone,)).fetchone():
        conn.close()
        return jsonify({'ok': False, 'msg': MSG['phone_registered']})
    conn.execute('INSERT INTO users(phone, password_hash, created_at) VALUES (?,?,?)',
                 (phone, generate_password_hash(password), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    SMS_CODES.pop(phone, None)
    session['user'] = phone
    return jsonify({'ok': True, 'msg': MSG['register_ok']})


@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.get_json(force=True)
    phone = str(d.get('phone', '')).strip()
    password = d.get('password', '')
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE phone=?', (phone,)).fetchone()
    if not row or not check_password_hash(row['password_hash'], password):
        conn.close()
        return jsonify({'ok': False, 'msg': MSG['login_fail']})
    conn.execute('UPDATE users SET last_login=? WHERE id=?',
                 (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), row['id']))
    conn.commit()
    conn.close()
    session['user'] = phone
    return jsonify({'ok': True, 'msg': MSG['login_ok']})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('user', None)
    return jsonify({'ok': True, 'msg': MSG['logout_ok']})


@app.route('/api/me')
def api_me():
    if 'user' in session:
        return jsonify({'ok': True, 'phone': session['user']})
    return jsonify({'ok': False, 'msg': MSG['not_login']})


# ==================== Pages ====================
@app.route('/')
def index():
    return render_template('index.html', dims=[I18N[k] for k in DIM_KEYS],
                           letters=I18N['dim_letter'], active='index')


@app.route('/students')
def page_students():
    return render_template('students.html', dims=[I18N[k] for k in DIM_KEYS],
                           stages=[I18N[k] for k in STAGE_KEYS], letters=I18N['dim_letter'], active='students')


@app.route('/dims')
def page_dims():
    return render_template('dims.html', dims=[I18N[k] for k in DIM_KEYS],
                           stages=[I18N[k] for k in STAGE_KEYS], letters=I18N['dim_letter'], active='dims')


@app.route('/works')
def page_works():
    return render_template('works.html', categories=[I18N[k] for k in CAT_KEYS], active='works')


@app.route('/guide')
def page_guide():
    return render_template('guide.html', dims=[I18N[k] for k in DIM_KEYS],
                           letters=I18N['dim_letter'], active='guide')


@app.route('/region')
def page_region():
    return render_template('region.html', active='region')


@app.route('/report')
def page_report():
    return render_template('report.html', active='report')

# ==================== API: students ====================
@app.route('/api/students', methods=['GET'])
def api_students():
    conn = get_db()
    rows = conn.execute('SELECT * FROM students ORDER BY id').fetchall()
    out = []
    for r in rows:
        d = dict(r)
        avg, stage = student_avg_score(conn, r['id'])
        d['avg_score'] = avg
        d['stage'] = stage
        d['level'] = level_of(avg) if avg is not None else I18N['not_evaluated']
        cnt = conn.execute('SELECT COUNT(*) n FROM works WHERE student_id=?', (r['id'],)).fetchone()['n']
        d['work_count'] = cnt
        out.append(d)
    conn.close()
    return jsonify({'ok': True, 'data': out})


@app.route('/api/students', methods=['POST'])
def api_students_add():
    d = request.get_json(force=True)
    name = str(d.get('name', '')).strip()
    if not name:
        return jsonify({'ok': False, 'msg': MSG['name_empty']})
    conn = get_db()
    conn.execute('INSERT INTO students(name, gender, grade_class, school, created_at) VALUES (?,?,?,?,?)',
                 (name, str(d.get('gender', I18N['gender_male'])).strip() or I18N['gender_male'],
                  str(d.get('grade_class', '')).strip() or I18N['unassigned_class'],
                  str(d.get('school', '')).strip(),
                  datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'msg': MSG['add_ok']})


@app.route('/api/students/<int:sid>', methods=['DELETE'])
def api_students_del(sid):
    conn = get_db()
    conn.execute('DELETE FROM students WHERE id=?', (sid,))
    conn.execute('DELETE FROM dim_scores WHERE student_id=?', (sid,))
    conn.execute('DELETE FROM works WHERE student_id=?', (sid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'msg': MSG['deleted']})


# ==================== API: five dims (De Zhi Ti Mei Lao) ====================
@app.route('/api/dim_scores', methods=['GET'])
def api_dim_scores():
    sid = request.args.get('student_id', type=int)
    conn = get_db()
    rows = conn.execute('SELECT * FROM dim_scores WHERE student_id=? ORDER BY dim, stage', (sid,)).fetchall()
    conn.close()
    data = {}
    for r in rows:
        data[f'{r["dim"]}_{r["stage"]}'] = r['score']
    return jsonify({'ok': True, 'data': data})


@app.route('/api/dim_scores', methods=['POST'])
def api_dim_scores_save():
    d = request.get_json(force=True)
    sid = d.get('student_id')
    sid = int(sid) if sid else None
    scores = d.get('scores', {})  # {'dim_stage': score}
    if not sid:
        return jsonify({'ok': False, 'msg': MSG['select_student']})
    conn = get_db()
    for k, v in scores.items():
        try:
            dim, stage = map(int, k.split('_'))
        except Exception:
            continue
        v = float(v)
        v = max(0, min(100, v))
        conn.execute('''INSERT INTO dim_scores(student_id, dim, stage, score) VALUES (?,?,?,?)
                        ON CONFLICT(student_id, dim, stage) DO UPDATE SET score=excluded.score''',
                     (sid, dim, stage, v))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'msg': MSG['dims_saved']})


# ==================== API: works (AI + teacher dual assessment) ====================
@app.route('/api/works', methods=['GET'])
def api_works():
    conn = get_db()
    rows = conn.execute('''SELECT w.*, s.name, s.grade_class FROM works w
                           JOIN students s ON s.id = w.student_id ORDER BY w.id DESC''').fetchall()
    conn.close()
    return jsonify({'ok': True, 'data': [dict(r) for r in rows]})


@app.route('/api/works', methods=['POST'])
def api_works_add():
    d = request.get_json(force=True)
    sid = d.get('student_id')
    sid = int(sid) if sid else None
    title = str(d.get('title', '')).strip()
    category = str(d.get('category', I18N['cat_paint'])).strip()
    if not sid or not title:
        return jsonify({'ok': False, 'msg': MSG['work_need']})
    comp = float(d.get('completeness', 7))
    crea = float(d.get('creativity', 7))
    tech = float(d.get('technique', 7))
    ai = ai_work_score(comp, crea, tech)
    tch = float(d.get('teacher_score', ai))
    fin = work_final_score(ai, tch)
    conn = get_db()
    conn.execute('''INSERT INTO works(student_id, title, category, completeness, creativity, technique,
                     ai_score, teacher_score, final_score, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                 (sid, title, category, comp, crea, tech, ai, tch, fin,
                  datetime.now().strftime('%Y-%m-%d %H:%M')))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'msg': MSG['work_saved'], 'ai_score': ai,
                    'final_score': fin, 'comment': gen_work_comment(ai, tch, fin, category)})


@app.route('/api/ai_score', methods=['POST'])
def api_ai_score():
    d = request.get_json(force=True)
    comp = float(d.get('completeness', 7))
    crea = float(d.get('creativity', 7))
    tech = float(d.get('technique', 7))
    ai = ai_work_score(comp, crea, tech)
    return jsonify({'ok': True, 'ai_score': ai})


@app.route('/api/works/<int:wid>', methods=['DELETE'])
def api_works_del(wid):
    conn = get_db()
    conn.execute('DELETE FROM works WHERE id=?', (wid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'msg': MSG['deleted']})


# ==================== API: growth archive ====================
@app.route('/api/profile/<int:sid>')
def api_profile(sid):
    conn = get_db()
    stu = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
    if not stu:
        conn.close()
        return jsonify({'ok': False, 'msg': MSG['student_not_found']})
    rows = conn.execute('SELECT * FROM dim_scores WHERE student_id=? ORDER BY stage, dim', (sid,)).fetchall()
    works = conn.execute('SELECT * FROM works WHERE student_id=? ORDER BY id DESC', (sid,)).fetchall()
    conn.close()
    matrix = {stage: [None] * 5 for stage in range(3)}
    for r in rows:
        matrix[r['stage'] - 1][r['dim'] - 1] = r['score']
    stage_avg = []
    for st in range(3):
        vals = [v for v in matrix[st] if v is not None]
        stage_avg.append(round(sum(vals) / len(vals), 1) if vals else None)
    latest = stage_avg[2] if stage_avg[2] is not None else next((v for v in reversed(stage_avg) if v is not None), None)
    comments = {}
    for st in range(3):
        vals = matrix[st]
        if all(v is not None for v in vals):
            comments[st + 1] = gen_comment(vals)
    return jsonify({'ok': True, 'data': {
        'student': dict(stu),
        'matrix': matrix,
        'stage_avg': stage_avg,
        'latest_avg': latest,
        'level': level_of(latest) if latest is not None else I18N['not_evaluated'],
        'works': [dict(w) for w in works],
        'comments': comments,
    }})


@app.route('/report/print/<int:sid>')
def report_print(sid):
    conn = get_db()
    stu = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
    if not stu:
        conn.close()
        return MSG['student_not_found'], 404
    rows = conn.execute('SELECT * FROM dim_scores WHERE student_id=? ORDER BY stage, dim', (sid,)).fetchall()
    works = conn.execute('SELECT * FROM works WHERE student_id=? ORDER BY id DESC', (sid,)).fetchall()
    conn.close()
    matrix = {stage: [None] * 5 for stage in range(3)}
    for r in rows:
        matrix[r['stage'] - 1][r['dim'] - 1] = r['score']
    stage_avg = []
    for st in range(3):
        vals = [v for v in matrix[st] if v is not None]
        stage_avg.append(round(sum(vals) / len(vals), 1) if vals else None)
    dim_avg = []
    for dm in range(5):
        vals = [matrix[st][dm] for st in range(3) if matrix[st][dm] is not None]
        dim_avg.append(round(sum(vals) / len(vals), 1) if vals else None)
    latest = stage_avg[2] if stage_avg[2] is not None else next((v for v in reversed(stage_avg) if v is not None), None)
    comments = {}
    for st in range(3):
        vals = matrix[st]
        if all(v is not None for v in vals):
            comments[st + 1] = gen_comment(vals)
    return render_template('report_print.html', stu=stu, dims=[I18N[k] for k in DIM_KEYS],
                           letters=I18N['dim_letter'],
                           datetime_now=datetime.now().strftime('%Y-%m-%d'),
                           stages=[I18N[k] for k in STAGE_KEYS],
                           matrix=matrix, stage_avg=stage_avg, dim_avg=dim_avg, latest=latest,
                           level=level_of(latest) if latest is not None else I18N['not_evaluated'],
                           works=works, comments=comments)


# ==================== API: growth guide ====================
@app.route('/api/guide/<int:sid>')
def api_guide(sid):
    conn = get_db()
    stu = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
    if not stu:
        conn.close()
        return jsonify({'ok': False, 'msg': MSG['student_not_found']})
    avg, stage = student_avg_score(conn, sid)
    rows = conn.execute('SELECT score FROM dim_scores WHERE student_id=? AND stage=?', (sid, stage)).fetchall()
    conn.close()
    if not rows or len(rows) < 5:
        return jsonify({'ok': False, 'msg': MSG['data_incomplete']})
    scores = [r['score'] for r in rows]
    guide = gen_guide(scores)
    guide['student'] = dict(stu)
    guide['stage'] = I18N[STAGE_KEYS[stage - 1]]
    return jsonify({'ok': True, 'data': guide})


# ==================== API: region search (official data) ====================
@app.route('/api/region/search', methods=['GET'])
def api_region_search():
    q = request.args.get('q', '')
    if not str(q).strip():
        return jsonify({'ok': False, 'msg': MSG['region_empty']})
    key = _find_region(q)
    if not key:
        hint = REGION['sep'].join(rec['names'][0] for rec in REGION_STATS.values())
        return jsonify({'ok': False, 'msg': MSG['region_not_found'].format(hint=hint)})
    data = region_analysis(REGION_STATS[key])
    data['matched'] = REGION_STATS[key]['names'][0]
    return jsonify({'ok': True, 'msg': MSG['region_ok'], 'data': data})


@app.route('/api/region/list', methods=['GET'])
def api_region_list():
    out = [{'name': rec['names'][0], 'full': rec['full_name']} for rec in REGION_STATS.values()]
    return jsonify({'ok': True, 'data': out})


# ==================== API: statistics ====================
@app.route('/api/stats/overview')
def api_stats_overview():
    conn = get_db()
    n_stu = conn.execute('SELECT COUNT(*) n FROM students').fetchone()['n']
    n_cls = conn.execute('SELECT COUNT(DISTINCT grade_class) n FROM students').fetchone()['n']
    n_work = conn.execute('SELECT COUNT(*) n FROM works').fetchone()['n']
    rows = conn.execute('SELECT id FROM students').fetchall()
    avgs, levels = [], {I18N[name]: 0 for _, name in LEVELS}
    for r in rows:
        avg, _ = student_avg_score(conn, r['id'])
        if avg is not None:
            avgs.append(avg)
            levels[level_of(avg)] += 1
    # Five-dim averages (latest stage)
    dim_avg = []
    for dim in range(5):
        row = conn.execute('''SELECT AVG(s.score) a FROM dim_scores s
                              JOIN (SELECT student_id, MAX(stage) st FROM dim_scores GROUP BY student_id) m
                                ON m.student_id = s.student_id AND m.st = s.stage
                              WHERE s.dim=?''', (dim + 1,)).fetchone()
        dim_avg.append(round(row['a'], 1) if row['a'] else 0)
    # Three-stage school-wide average trend
    stage_trend = []
    for st in range(3):
        row = conn.execute('SELECT AVG(score) a FROM dim_scores WHERE stage=?', (st + 1,)).fetchone()
        stage_trend.append(round(row['a'], 1) if row['a'] else 0)
    conn.close()
    return jsonify({'ok': True, 'data': {
        'n_stu': n_stu, 'n_cls': n_cls, 'n_work': n_work,
        'avg_total': round(sum(avgs) / len(avgs), 1) if avgs else 0,
        'levels': levels, 'dim_avg': dim_avg, 'stage_trend': stage_trend,
    }})


@app.route('/api/stats/class_compare')
def api_stats_class_compare():
    conn = get_db()
    rows = conn.execute('SELECT DISTINCT grade_class FROM students').fetchall()
    out = []
    for cls in rows:
        cls_name = cls['grade_class']
        stus = conn.execute('SELECT id FROM students WHERE grade_class=?', (cls_name,)).fetchall()
        dim_sum = [0.0] * 5
        n = 0
        for r in stus:
            avg, stage = student_avg_score(conn, r['id'])
            if avg is None:
                continue
            n += 1
            drow = conn.execute('SELECT score FROM dim_scores WHERE student_id=? AND stage=?', (r['id'], stage)).fetchall()
            for i, dr in enumerate(drow):
                dim_sum[i] += dr['score']
        if n:
            out.append({'name': cls_name, 'n': n,
                        'dims': [round(x / n, 1) for x in dim_sum],
                        'avg': round(sum(dim_sum) / n / 5, 1)})
    conn.close()
    return jsonify({'ok': True, 'data': out})


# Initialize the database on import so WSGI servers (e.g. PythonAnywhere)
# receive a ready-to-serve app. init_db() is idempotent.
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)