import streamlit as st
import requests
import json
import sqlite3
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="智能数学学习平台",
    page_icon="📚",
    layout="wide"
)

# 隐藏自动生成的侧边栏导航
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📚 智能数学学习平台")
st.caption("基于本地数学知识库的智能问答系统")

# 数据库初始化函数（添加调用）
def init_chat_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS group_messages
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 group_id INTEGER NOT NULL,
                 user_id TEXT NOT NULL,
                 content TEXT NOT NULL,
                 timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY(group_id) REFERENCES group_chats(id))''')
    conn.commit()
    conn.close()


# 初始化数据库（新增调用）
init_chat_db()

# 初始化群聊状态（添加路径检查）
if "current_group" not in st.session_state:
    st.switch_page("app.py")  # 跳回首页如果直接访问
else:
    # 验证群聊ID有效性
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM group_chats WHERE id = ?",
             (st.session_state.current_group["id"],))
    if not c.fetchone():
        del st.session_state.current_group
        st.switch_page("pages/single_chat.py")
    conn.close()

# 添加群聊ID变化检测
if "last_group_id" not in st.session_state:
    st.session_state.last_group_id = None

if st.session_state.last_group_id != st.session_state.current_group["id"]:
    # 清除旧群聊的历史状态
    for key in list(st.session_state.keys()):
        if key.startswith("history_loaded_"):
            del st.session_state[key]
    st.session_state.last_group_id = st.session_state.current_group["id"]

# 加载群聊历史记录（使用群聊ID标识状态）
current_group_id = st.session_state.current_group["id"]
history_key = f"history_loaded_{current_group_id}"

if not st.session_state.get(history_key, False):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("""SELECT user_id, content FROM group_messages 
               WHERE group_id = ? ORDER BY timestamp""",
              (current_group_id,))
    messages = c.fetchall()
    conn.close()

    # 转换并重置历史记录
    st.session_state.history = [
        {"role": "user", "content": f"{user}: {msg}"} for user, msg in messages
    ]
    st.session_state[history_key] = True  # 标记当前群聊历史已加载

# 侧边栏信息显示（保持不变）
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
                padding-bottom: 10px !important;
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

    st.subheader(f"群聊名称: {st.session_state.current_group['name']}")
    st.markdown(f"**邀请码**: `{st.session_state.current_group['invite_code']}`")

    # 退出群聊按钮
    if st.button("退出群聊"):
        # 清除所有群聊相关状态
        keys_to_remove = ["current_group", "last_group_id"]
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
        # 强制创建新对话
        st.session_state.pop("current_conv", None)
        st.session_state.history = []
        st.switch_page("pages/single_chat.py")



# 消息展示区域（修改展示逻辑）
with st.container():
    for msg in st.session_state.history:
        # 使用精确前缀判断
        role = "assistant" if msg["content"].startswith("助手:") else "user"
        st.chat_message(role).write(msg["content"])

# 用户输入处理（修改保存逻辑）
if prompt := st.chat_input("请输入您的问题..."):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("BEGIN TRANSACTION")

        # 插入用户消息（始终保存）
        c.execute("""INSERT INTO group_messages (group_id, user_id, content)
                   VALUES (?, ?, ?)""",
                  (st.session_state.current_group["id"],
                   st.session_state.username,
                   prompt))

        # 检查是否以@数学开头
        if prompt.startswith("@数学"):
            # 提取有效问题内容（去除@数学前缀）
            query = prompt[len("@数学"):].strip()

            # 构造AI请求
            payload = {
                "query": query,  # 使用处理后的查询内容
                "knowledge_base_name": "math",
                "top_k": 3,
                "score_threshold": 0.85,
                "history": [msg for msg in st.session_state.history if msg["role"] == "user"],
                "stream": True,
                "model_name": "chatglm3-6b",
                "temperature": 0.3
            }

            # 处理AI响应
            full_answer = ""
            try:
                with requests.post("http://127.0.0.1:7861/chat/knowledge_base_chat",
                                   json=payload, stream=True, timeout=30) as response:
                    if response.status_code == 200:
                        for line in response.iter_lines():
                            if line and line.startswith(b'data: '):
                                data = json.loads(line.decode('utf-8')[6:])
                                full_answer += data.get("answer", "")
            except requests.exceptions.Timeout:
                full_answer = "请求超时，请稍后再试"
            except Exception as e:
                full_answer = f"请求异常：{str(e)}"
                raise

            # 保存AI回复到数据库
            c.execute("""INSERT INTO group_messages (group_id, user_id, content)
                    VALUES (?, ?, ?)""",
                      (st.session_state.current_group["id"],
                       "assistant",
                       full_answer))

            # 更新会话历史
            st.session_state.history.extend([
                {"role": "user", "content": f"{st.session_state.username}: {prompt}"},
                {"role": "assistant", "content": f"助手: {full_answer}"}
            ])
        else:
            # 仅更新用户消息历史
            st.session_state.history.append(
                {"role": "user", "content": f"{st.session_state.username}: {prompt}"}
            )

        conn.commit()

    except Exception as e:
        conn.rollback()
        st.error(f"操作失败: {str(e)}")
    finally:
        if conn:
            conn.close()
    st.experimental_rerun()