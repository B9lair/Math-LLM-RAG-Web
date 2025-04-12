import streamlit as st
import requests
import json
import sqlite3
from datetime import datetime
import random
import string
import os

def get_user_info(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT nickname, role, avatar_path FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return {
        "nickname": result[0],
        "role": result[1],
        "avatar": result[2]
    } if result else None



def generate_unique_invite_code():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    while True:
        invite_code = ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=6
        ))
        c.execute("SELECT id FROM group_chats WHERE invite_code = ?", (invite_code,))
        if not c.fetchone():
            conn.close()
            return invite_code

# 数据库初始化函数
def init_chat_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # 创建对话表
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT NOT NULL,
                  title TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(user_id) REFERENCES users(username))''')

    # 创建消息表
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  conversation_id INTEGER NOT NULL,
                  role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(conversation_id) REFERENCES conversations(id))''')

    # 创建群聊表
    c.execute('''CREATE TABLE IF NOT EXISTS group_chats
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      title TEXT NOT NULL,
                      invite_code TEXT NOT NULL,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # 创建用户群聊关联表
    c.execute('''CREATE TABLE IF NOT EXISTS user_group_chats
                     (user_id TEXT NOT NULL,
                      group_chat_id INTEGER NOT NULL,
                      FOREIGN KEY(user_id) REFERENCES users(username),
                      FOREIGN KEY(group_chat_id) REFERENCES group_chats(id))''')


    conn.commit()
    conn.close()

# 初始化数据库
init_chat_db()


# 确保用户已登录且会话状态正确初始化
if "username" not in st.session_state or not st.session_state.get("authenticated", False):
    st.switch_page("app.py")  # 强制跳转回登录页面

# 确保username属性存在
if "username" not in st.session_state:
    st.session_state.username = None  # 初始化默认值

# 获取用户昵称
def get_user_nickname(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT nickname FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# 初始化页面配置
st.set_page_config(
    page_title="智能数学学习平台",
    page_icon="📚",
    layout="wide"  # 修改为wide以支持左右侧边栏
)



# 初始化会话状态（保存对话历史）
if "history" not in st.session_state:
    st.session_state.history = []

if "current_group" in st.session_state:
    # 如果检测到残留的群聊状态
    del st.session_state.current_group
    st.session_state.history = []
    st.experimental_rerun()

# 页面标题
st.title("📚 智能数学学习平台")
st.caption("基于本地数学知识库的智能问答系统")

st.markdown("""
<style>
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

if "show_right_content" not in st.session_state:
    st.session_state.show_right_content = False

# 左侧边栏配置参数
with st.sidebar:

    st.markdown("""
        <style>
            /* 侧边栏容器样式 */
            [data-testid="stSidebar"] {
                border: 2px solid #E6E6FA !important;
                border-radius: 15px !important;
                box-shadow: 3px 3px 10px rgba(230,230,250,0.5) !important;
            }
            /* 标题装饰线 */
            .sidebar-title {
                border-bottom: 2px solid #E6E6FA !important;
                padding-bottom: 20px !important;
            }
        </style>
        """, unsafe_allow_html=True)

    st.markdown("""
        <style>
            .sidebar-title {
                font-size: 24px !important;
                font-weight: 600;
                margin-bottom: 20px;
                padding-bottom: 10px;
            }
        </style>
        <div class="sidebar-title">📚 学习导航</div>
        """, unsafe_allow_html=True)

    if not st.session_state.show_right_content:
        # 新建对话按钮
        if st.button("+ 新建对话"):
            # 创建新对话记录
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("INSERT INTO conversations (user_id, title) VALUES (?, ?)",
                      (st.session_state.username, f"对话-{datetime.now().strftime('%m-%d %H:%M')}"))
            new_conv_id = c.lastrowid
            conn.commit()
            conn.close()

            # 重置当前会话
            st.session_state.current_conv = new_conv_id
            st.session_state.history = []
            st.experimental_rerun()

        # 新增删除当前对话按钮
        if st.button("删除当前对话"):
            if "current_conv" in st.session_state:
                # 删除数据库记录
                conn = sqlite3.connect('users.db')
                c = conn.cursor()

                try:
                    # 先删除关联消息
                    c.execute("DELETE FROM messages WHERE conversation_id = ?",
                              (st.session_state.current_conv,))
                    # 再删除对话
                    c.execute("DELETE FROM conversations WHERE id = ?",
                              (st.session_state.current_conv,))
                    conn.commit()

                    # 清除会话状态（但不创建新对话）
                    del st.session_state.current_conv
                    st.session_state.history = []
                    st.success("对话已删除")

                except sqlite3.Error as e:
                    conn.rollback()
                    st.error(f"删除失败: {str(e)}")
                finally:
                    conn.close()

                st.experimental_rerun()

        # 自定义带滚动条的对话历史容器
        st.markdown("""
                <style>
                    .history-container {
                        border: 1px solid rgba(49, 51, 63, 0.2);
                        border-radius: 8px;
                        padding: 10px;
                        max-height: 60vh;
                        overflow-y: auto;
                        margin-bottom: 15px;
                    }
                    /* 自定义滚动条样式 */
                    .history-container::-webkit-scrollbar {
                        width: 8px;
                    }
                    .history-container::-webkit-scrollbar-track {
                        background: #f1f1f1;
                        border-radius: 4px;
                    }
                    .history-container::-webkit-scrollbar-thumb {
                        background: #888;
                        border-radius: 4px;
                    }
                    .history-container::-webkit-scrollbar-thumb:hover {
                        background: #555;
                    }
                </style>
            """, unsafe_allow_html=True)

        # 原始左侧边栏内容
        st.header("历史对话记录")

        # 使用新的包裹方式
        with st.container():
            st.markdown('<div class="history-wrapper">', unsafe_allow_html=True)

            # 创建独立的历史列表容器
            history_list = st.container()

            with history_list:
                # 获取当前用户的对话历史
                conn = sqlite3.connect('users.db')
                c = conn.cursor()
                c.execute("SELECT id, title FROM conversations WHERE user_id = ? ORDER BY created_at DESC",
                          (st.session_state.username,))
                conversations = c.fetchall()
                conn.close()

                # 显示对话历史
                for conv in conversations:
                    conv_id, title = conv
                    # 为每个对话创建点击区域
                    if st.button(title, key=f"conv_{conv_id}"):
                        # 加载选中对话的历史记录
                        conn = sqlite3.connect('users.db')
                        c = conn.cursor()
                        c.execute("SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY timestamp",
                                  (conv_id,))
                        messages = [{"role": role, "content": content} for role, content in c.fetchall()]
                        conn.close()

                        st.session_state.current_conv = conv_id
                        st.session_state.history = messages
                        st.experimental_rerun()

            st.markdown('</div>', unsafe_allow_html=True)

        # 修改后的按钮布局
        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("退出登录", key="logout_left"):
                st.session_state.authenticated = False
                st.session_state.username = None
                st.switch_page("app.py")
        with col2:
            if st.button("切换侧边栏", key="toggle_left"):
                st.session_state.show_right_content = True
                st.experimental_rerun()

    else:
        # 显示右侧边栏内容
        st.header("用户信息")

        # 在用户信息显示部分修改
        st.markdown("""
        <style>
            .user-card {
                display: flex;
                align-items: center;
                gap: 15px;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 10px;
                margin-bottom: 20px;
            }
            .avatar {
                width: 60px;
                height: 60px;
                border-radius: 50%;
                object-fit: cover;
            }
            .user-info {
                flex: 1;
            }
        </style>
        """, unsafe_allow_html=True)

        user_info = get_user_info(st.session_state.username)
        if user_info:
            avatar_path = os.path.join(os.getcwd(), user_info['avatar'])
            st.markdown(f"""
            <div class="user-card">
                <img src="{avatar_path}" class="avatar">
                <div class="user-info">
                    <h3 style="margin:0;font-size:18px">{user_info['nickname']}</h3>
                    <p style="margin:0;color:#666">{user_info['role']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)


        # 在侧边栏的群聊管理部分
        st.header("群聊管理")

        # 初始化表单显示状态
        if "show_group_form" not in st.session_state:
            st.session_state.show_group_form = False

        # 新建群聊按钮逻辑
        if st.button("+ 新建群聊", key="new_group_sidebar"):
            st.session_state.show_group_form = not st.session_state.show_group_form

        # 显示创建群聊表单
        if st.session_state.show_group_form:
            with st.form(key="group_creation_form", clear_on_submit=True):
                st.subheader("创建新群聊")
                group_name = st.text_input(
                    "群聊名称",
                    value=f"数学群聊-{datetime.now().strftime('%m-%d')}",
                    help="请输入不超过20个字符的群聊名称"
                )

                # 双列布局按钮
                col1, col2 = st.columns([1, 1])  # 等宽比例
                with col1:
                    submit = st.form_submit_button("✅ 创建")
                with col2:
                    if st.form_submit_button("❌ 取消"):
                        st.session_state.show_group_form = False
                        st.experimental_rerun()

                if submit:
                    if len(group_name) > 20:
                        st.error("群聊名称不能超过20个字符")
                    else:
                        # 生成唯一邀请码
                        invite_code = generate_unique_invite_code()

                        conn = sqlite3.connect('users.db')
                        c = conn.cursor()
                        try:
                            c.execute("INSERT INTO group_chats (title, invite_code) VALUES (?, ?)",
                                      (group_name, invite_code))
                            group_chat_id = c.lastrowid
                            c.execute("INSERT INTO user_group_chats (user_id, group_chat_id) VALUES (?, ?)",
                                      (st.session_state.username, group_chat_id))
                            conn.commit()

                            # 更新会话状态
                            st.session_state.current_group = {
                                "id": group_chat_id,
                                "name": group_name,
                                "invite_code": invite_code
                            }

                            # 清除可能存在的旧群聊历史状态
                            for key in list(st.session_state.keys()):
                                if key.startswith("history_loaded_"):
                                    del st.session_state[key]

                            st.session_state.show_group_form = False
                            st.switch_page("pages/group_chat.py")

                        except sqlite3.Error as e:
                            conn.rollback()
                            st.error(f"创建失败: {str(e)}")
                        finally:
                            conn.close()



        # 获取群聊列表数据
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT group_chats.id, group_chats.title FROM group_chats "
                    "JOIN user_group_chats ON group_chats.id = user_group_chats.group_chat_id "
                    "WHERE user_group_chats.user_id = ?", (st.session_state.username,))
        group_chats = c.fetchall()
        conn.close()

        st.header("群聊列表")
        # 显示群聊列表（修改后的代码）
        for group_chat in group_chats:
            group_chat_id, group_title = group_chat
            if st.button(group_title, key=f"group_side_{group_chat_id}"):
                # 获取完整的群聊信息
                conn = sqlite3.connect('users.db')
                c = conn.cursor()
                c.execute("SELECT title, invite_code FROM group_chats WHERE id = ?", (group_chat_id,))
                group_info = c.fetchone()
                conn.close()

                if group_info:
                    # 保存到会话状态
                    st.session_state.current_group = {
                        "id": group_chat_id,
                        "name": group_info[0],
                        "invite_code": group_info[1]
                    }
                    # 跳转到群聊页面
                    st.switch_page("pages/group_chat.py")

        # 输入邀请码加入群聊
        invite_code = st.text_input("输入邀请码加入群聊")
        if st.button("加入群聊"):
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            try:
                c.execute("SELECT id FROM group_chats WHERE invite_code = ?", (invite_code,))
                result = c.fetchone()
                if result:
                    group_chat_id = result[0]
                    # 检查是否已加入
                    c.execute("SELECT 1 FROM user_group_chats WHERE user_id = ? AND group_chat_id = ?",
                              (st.session_state.username, group_chat_id))
                    if not c.fetchone():
                        c.execute("INSERT INTO user_group_chats (user_id, group_chat_id) VALUES (?, ?)",
                                  (st.session_state.username, group_chat_id))
                        conn.commit()
                        st.success("成功加入群聊")
                    else:
                        st.warning("您已在群聊中")

                    # 更新群聊状态
                    c.execute("SELECT title, invite_code FROM group_chats WHERE id = ?", (group_chat_id,))
                    group_info = c.fetchone()

                    st.session_state.current_group = {
                        "id": group_chat_id,
                        "name": group_info[0],
                        "invite_code": group_info[1]
                    }
                    st.experimental_rerun()
                else:
                    st.error("邀请码无效")
            except sqlite3.IntegrityError:
                st.error("操作失败：邀请码已失效")
            finally:
                conn.close()

        # 修改后的按钮布局
        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("退出登录", key="logout_right"):
                st.session_state.authenticated = False
                st.session_state.username = None
                st.switch_page("app.py")
        with col2:
            if st.button("切换侧边栏", key="toggle_right"):
                st.session_state.show_right_content = False
                st.experimental_rerun()

# 添加CSS样式优化按钮间距
st.markdown("""
<style>
    div[data-testid="column"] {
        gap: 0.5rem;
    }
    button {
        width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)



# 对话展示区域
with st.container():
    if "current_conv" in st.session_state:  # 新增判断
        for msg in st.session_state.history:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["content"])
            else:
                st.chat_message("assistant").write(msg["content"])
    else:
        st.info("👋 欢迎使用！请输入第一个问题开始新对话")

# 用户输入区域

# 用户输入区域
if prompt := st.chat_input("请输入您的问题..."):
    # 确保当前对话存在（新增逻辑）
    if "current_conv" not in st.session_state:
        # 创建新对话（仅在首次提问时）
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("BEGIN TRANSACTION")  # 开启事务

        try:
            # 创建对话记录
            c.execute("INSERT INTO conversations (user_id, title) VALUES (?, ?)",
                      (st.session_state.username, f"对话-{datetime.now().strftime('%m-%d %H:%M')}"))
            new_conv_id = c.lastrowid

            # 插入用户消息
            c.execute("INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                      (new_conv_id, "user", prompt))

            conn.commit()

            # 更新会话状态
            st.session_state.current_conv = new_conv_id
            st.session_state.history = [{"role": "user", "content": prompt}]

            # 立即处理AI响应（新增部分）
            # 构造请求参数
            payload = {
                "query": prompt,
                "knowledge_base_name": "math",
                "top_k": 3,
                "score_threshold": 0.85,
                "history": [],
                "stream": True,
                "model_name": "chatglm3-6b",
                "temperature": 0.3,
                "max_tokens": 0,
                "prompt_name": "default"
            }

            # 显示加载状态和占位符
            response_placeholder = st.empty()
            full_answer = ""

            # 发送流式请求
            with requests.post(
                    "http://127.0.0.1:6006/chat/knowledge_base_chat",
                    json=payload,
                    stream=True
            ) as response:

                # 处理流式响应
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data: "):
                                try:
                                    json_str = decoded_line.split("data: ")[1]
                                    data = json.loads(json_str)
                                    answer_chunk = data.get("answer", "")
                                    full_answer += answer_chunk
                                    # 实时更新回答
                                    with response_placeholder.container():
                                        st.markdown(full_answer + "▌")
                                except json.JSONDecodeError:
                                    st.error("数据解析失败")
                else:
                    full_answer = f"请求失败（状态码 {response.status_code}）"

            # 保存AI回复到数据库（使用新连接）
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                      (new_conv_id, "assistant", full_answer))
            conn.commit()

            # 更新会话历史
            st.session_state.history.append({"role": "assistant", "content": full_answer})

        except Exception as e:
            conn.rollback()
            st.error(f"操作失败: {str(e)}")
        finally:
            if conn:
                conn.close()

    else:

        # 保存用户消息到数据库
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                  (st.session_state.current_conv, "user", prompt))
        conn.commit()

        # 添加用户问题到历史记录
        st.session_state.history.append({"role": "user", "content": prompt})

        # 显示用户输入
        with st.chat_message("user"):
            st.write(prompt)

        # 构造请求参数
        payload = {
            "query": prompt,
            "knowledge_base_name": "math",
            "top_k": 3,
            "score_threshold": 0.85,
            "history": st.session_state.history[:-1],  # 不包含当前问题
            "stream": True,  # 必须设置为True
            "model_name": "chatglm3-6b",
            "temperature": 0.3,
            "max_tokens": 0,
            "prompt_name": "default"
        }

        # 显示加载状态和占位符
        response_placeholder = st.empty()
        full_answer = ""

        try:
            # 发送流式请求
            with requests.post(
                    "http://127.0.0.1:7861/chat/knowledge_base_chat",
                    json=payload,
                    stream=True
            ) as response:

                # 处理流式响应
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')

                            # 解析SSE格式数据
                            if decoded_line.startswith("data: "):
                                try:
                                    json_str = decoded_line.split("data: ")[1]
                                    data = json.loads(json_str)
                                    answer_chunk = data.get("answer", "")
                                    full_answer += answer_chunk

                                    # 实时更新回答
                                    with response_placeholder.container():
                                        st.markdown(full_answer + "▌")

                                except json.JSONDecodeError:
                                    st.error("数据解析失败")
                else:
                    full_answer = f"请求失败（状态码 {response.status_code}）"

        except requests.exceptions.ConnectionError:
            full_answer = "无法连接到服务端，请检查接口地址！"
        except Exception as e:
            full_answer = f"接口异常：{str(e)}"

        # 最终显示完整回答
        with response_placeholder.container():
            st.markdown(full_answer)

            # 保存助手回复到数据库
            c.execute("INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                    (st.session_state.current_conv, "assistant", full_answer))
            conn.commit()
            conn.close()

            # 更新会话历史
            st.session_state.history.append({"role": "user", "content": prompt})
            st.session_state.history.append({"role": "assistant", "content": full_answer})