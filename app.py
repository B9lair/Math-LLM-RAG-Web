import streamlit as st
import sqlite3
from passlib.hash import pbkdf2_sha256
import re


# 初始化数据库
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, 
                  nickname TEXT NOT NULL,  -- 确保存在该字段
                  phone TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  role TEXT NOT NULL)''')
    conn.commit()
    conn.close()


# 验证用户登录
def verify_user(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    result = c.fetchone()
    conn.close()
    if result and pbkdf2_sha256.verify(password, result[0]):
        return True
    return False


# 注册新用户
def register_user(username, nickname, phone, password, role):
    try:
        # 验证手机号格式
        if not re.match(r'^1[3-9]\d{9}$', phone):
            return "invalid_phone"

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        hashed = pbkdf2_sha256.hash(password)
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                  (username, nickname, phone, hashed, role))
        conn.commit()
        conn.close()
        return "success"
    except sqlite3.IntegrityError as e:
        if "users.username" in str(e):
            return "username_exists"
        elif "users.phone" in str(e):
            return "phone_exists"
        return "error"


# 初始化页面配置
st.set_page_config(
    page_title="智能数学学习平台",
    page_icon="📚",
    layout="centered",
)

# 隐藏侧边栏
hide_sidebar_css = """
    <style>
        section[data-testid="stSidebar"] {
            display: none !important;
        }
    </style>
"""
st.markdown(hide_sidebar_css, unsafe_allow_html=True)

# 初始化数据库和会话状态
init_db()
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# 页面标题
st.title("用户登录/注册")

# 登录注册切换
tab1, tab2 = st.tabs(["登录", "注册"])

with tab1:
    with st.form("登录表单"):
        login_user = st.text_input("用户名")
        login_pass = st.text_input("密码", type="password")
        login_submitted = st.form_submit_button("登录")

        if login_submitted:
            if verify_user(login_user, login_pass):
                st.session_state.authenticated = True
                st.session_state.username = login_user
                st.success("登录成功！")
                st.switch_page("pages/single_chat.py")
            else:
                st.error("用户名或密码错误")

with tab2:
    with st.form("注册表单"):
        reg_nickname = st.text_input("昵称")  # 新增昵称字段
        reg_user = st.text_input("用户名（用于登录）")
        reg_phone = st.text_input("手机号")
        reg_pass = st.text_input("密码", type="password")
        reg_role = st.selectbox("身份", ["学生", "老师"])

        reg_submitted = st.form_submit_button("注册")

        if reg_submitted:
            # 前端验证
            error_messages = []
            if len(reg_user) < 4:
                error_messages.append("用户名至少需要4个字符")
            if len(reg_nickname) < 2:  # 新增昵称验证
                error_messages.append("昵称至少需要2个字符")
            if len(reg_pass) < 6:
                error_messages.append("密码至少需要6个字符")
            if not reg_phone.isdigit() or len(reg_phone) != 11:
                error_messages.append("请输入有效的11位手机号")

            if error_messages:
                for error in error_messages:
                    st.error(error)
            else:
                # 修正参数，添加nickname
                result = register_user(reg_user, reg_nickname, reg_phone, reg_pass, reg_role)
                if result == "success":
                    st.success("注册成功！请登录")
                elif result == "username_exists":
                    st.error("用户名已存在")
                elif result == "phone_exists":
                    st.error("手机号已注册")
                elif result == "invalid_phone":
                    st.error("手机号格式不正确")
                else:
                    st.error("注册失败，请稍后重试")