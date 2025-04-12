from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import asyncio
import sqlite3

app = FastAPI()

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


# WebSocket路由
@app.websocket("/ws/{group_id}")
async def websocket_endpoint(websocket: WebSocket, group_id: str):
    await manager.connect(websocket, group_id)
    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            user_id = msg_data.get("user_id")
            with sqlite3.connect('users.db') as conn:
                c = conn.cursor()
                # 修改SQL插入语句，增加msg_id字段
                c.execute("""INSERT INTO group_messages 
                          (group_id, user_id, content, msg_id) 
                          VALUES (?, ?, ?, ?)""",
                          (group_id,
                           msg_data["user_id"],
                           msg_data["content"],
                           msg_data["msg_id"]))
                conn.commit()
            await manager.broadcast(data, group_id)
    except Exception as e:
        manager.disconnect(websocket, group_id)

# 原有知识库接口
@app.post("/chat/knowledge_base_chat")
async def chat_endpoint(query: dict):
    # 保留原有知识库处理逻辑
    return {"answer": "示例回答", "status": 200}


if __name__ == "__main__":
    uvicorn.run(app="server:app", host="0.0.0.0", port=6006, reload=True)