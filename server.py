from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import asyncio
import sqlite3

# 修改后的server.py
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import threading
import sqlite3


class FastAPIThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.app = FastAPI()
        self.setup_routes()

    def setup_routes(self):

        # 修改WebSocket路由处理
        @self.app.websocket("/ws/{group_id}")
        async def websocket_endpoint(websocket: WebSocket, group_id: str):
            await manager.connect(websocket, group_id)
            try:
                while True:
                    data = await websocket.receive_text()
                    # 添加消息持久化逻辑
                    msg_data = json.loads(data)
                    with sqlite3.connect('users.db') as conn:
                        c = conn.cursor()
                        c.execute("""INSERT INTO group_messages 
                                  (group_id, user_id, content) 
                                  VALUES (?, ?, ?)""",
                                  (group_id,
                                   msg_data["username"],
                                   msg_data["content"]))
                        conn.commit()
                    # 广播给所有客户端
                    await manager.broadcast(data, group_id)
            except Exception as e:
                manager.disconnect(websocket, group_id)

        # 原有知识库接口
        @self.app.post("/chat/knowledge_base_chat")
        async def chat_endpoint(query: dict):
            # 保留原有知识库处理逻辑
            return {"answer": "示例回答", "status": 200}

    def run(self):
        import uvicorn
        uvicorn.run(self.app, host="0.0.0.0", port=6006)



# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket: WebSocket, group_id: str):
        await websocket.accept()
        if group_id not in self.active_connections:
            self.active_connections[group_id] = []
        self.active_connections[group_id].append(websocket)

    def disconnect(self, websocket: WebSocket, group_id: str):
        if group_id in self.active_connections:
            self.active_connections[group_id].remove(websocket)

    async def broadcast(self, message: str, group_id: str):
        if group_id in self.active_connections:
            for connection in self.active_connections[group_id]:
                await connection.send_text(message)


manager = ConnectionManager()



