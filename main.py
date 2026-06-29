import os
import shutil
import asyncio
import hmac
import hashlib
import base64
import json
import time
import urllib.request
import urllib.parse
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File, Header, Query, Request, Cookie
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

from orchestrator import BotProcessManager
from utils import get_system_stats

# Khởi tạo tiến trình quản lý bot
manager = BotProcessManager(base_dir="bots")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động các luồng giám sát khi server chạy
    await manager.start_background_tasks()
    yield
    # Dừng tất cả các bot và luồng giám sát khi server tắt
    await manager.stop_background_tasks()

app = FastAPI(title="Discord Bot Manager Server", lifespan=lifespan)

# --- Cấu hình bảo mật và Xác thực ---
AUTH_CONFIG_FILE = "panel_auth.json"

def load_auth_config():
    if not os.path.exists(AUTH_CONFIG_FILE):
        default_config = {
            "users": [
                {
                    "username": "admin",
                    "email": "trancuong2674@gmail.com",
                    "password": "cuongpanelbots2000@"
                }
            ]
        }
        with open(AUTH_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        return default_config
    try:
        with open(AUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Cảnh báo] Không thể đọc file cấu hình bảo mật: {e}")
        return {
            "users": [
                {
                    "username": "admin",
                    "email": "trancuong2674@gmail.com",
                    "password": "cuongpanelbots2000@"
                }
            ]
        }

# Khóa bí mật dùng để ký Session Cookie
from dotenv import load_dotenv
load_dotenv()
JWT_SECRET = os.environ.get("JWT_SECRET", "aegisbot_panel_secret_session_key_2026")

# Ký và xác minh session token
def sign_data(data: dict) -> str:
    serialized = json.dumps(data).encode('utf-8')
    signature = hmac.new(JWT_SECRET.encode('utf-8'), serialized, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(serialized + signature).decode('utf-8')

def verify_data(signed_str: str) -> Optional[dict]:
    if not signed_str:
        return None
    try:
        decoded = base64.urlsafe_b64decode(signed_str.encode('utf-8'))
        serialized = decoded[:-32]
        signature = decoded[-32:]
        expected_sig = hmac.new(JWT_SECRET.encode('utf-8'), serialized, hashlib.sha256).digest()
        if hmac.compare_digest(signature, expected_sig):
            return json.loads(serialized.decode('utf-8'))
    except:
        pass
    return None

# Middleware kiểm tra quyền truy cập (cho tất cả HTTP ngoại trừ login/callback/static)
@app.middleware("http")
async def check_auth_middleware(request: Request, call_next):
    path = request.url.path
    if path == "/login" or path.startswith("/api/auth") or path.startswith("/static"):
        return await call_next(request)
        
    session_token = request.cookies.get("session_token")
    data = verify_data(session_token)
    
    if not data:
        if path == "/":
            return RedirectResponse(url="/login")
        return JSONResponse(status_code=401, content={"detail": "Chưa đăng nhập hoặc phiên làm việc đã hết hạn."})
        
    if data:
        config = load_auth_config()
        users = config.get("users", [])
        
        allowed_usernames = [u.get("username", "").strip().lower() for u in users if u.get("username")]
        allowed_emails = [u.get("email", "").strip().lower() for u in users if u.get("email")]
        
        session_username = data.get("username", "").strip().lower()
        session_email = data.get("email", "").strip().lower()
        
        has_access = False
        if session_username and session_username in allowed_usernames:
            has_access = True
        elif session_email and session_email in allowed_emails:
            has_access = True
            
        if not has_access:
            if path == "/":
                return RedirectResponse(url="/login?error=unauthorized")
            return JSONResponse(status_code=401, content={"detail": "Tài khoản không có quyền truy cập."})
            
    return await call_next(request)

# Tạo thư mục static và templates nếu chưa có
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Model cho API tạo bot
class BotCreateSchema(BaseModel):
    id: str
    name: str
    code: str = None
    env: str
    use_env: bool = True
    entrypoint: str = "bot.py"
    requirements: str = ""
    is_edit: bool = False
    password: str = ""
    clear_password: bool = False

@app.get("/", response_class=HTMLResponse)
async def read_index():
    """Trả về trang chủ quản lý (đã được middleware bảo vệ)."""
    index_path = os.path.join("templates", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h2>Chưa tìm thấy giao diện index.html trong thư mục templates!</h2>")

# --- CÁC ENDPOINT XÁC THỰC VÀ ĐĂNG NHẬP ---

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Trả về trang đăng nhập."""
    login_path = os.path.join("templates", "login.html")
    if os.path.exists(login_path):
        return FileResponse(login_path)
    return HTMLResponse("<h2>Chưa tìm thấy giao diện login.html trong thư mục templates!</h2>")

class LoginSchema(BaseModel):
    username_or_email: str
    password: str

@app.post("/api/auth/login")
async def login(payload: LoginSchema, request: Request):
    now = time.time()
    config = load_auth_config()
    
    users = config.get("users", [])
    submitted_identifier = payload.username_or_email.strip().lower()
    
    # Tìm cặp username/email và mật khẩu trùng khớp
    user_match = None
    for u in users:
        u_username = u.get("username", "").strip().lower()
        u_email = u.get("email", "").strip().lower()
        if submitted_identifier == u_username or submitted_identifier == u_email:
            user_match = u
            break
            
    if user_match and payload.password == user_match.get("password"):
        # Cấp session token
        session_token = sign_data({
            "username": user_match.get("username", ""),
            "email": user_match.get("email", ""),
            "logged_in_at": now
        })
        response = JSONResponse(content={"status": "success", "message": "Đăng nhập thành công."})
        response.set_cookie(
            "session_token", 
            session_token, 
            httponly=True, 
            secure=False,  # Cho phép chạy trên HTTP không có SSL (ví dụ sau proxy)
            samesite="lax",
            max_age=86400 * 7
        )
        return response
    else:
        raise HTTPException(
            status_code=400, 
            detail="Tên đăng nhập/Email hoặc mật khẩu không chính xác."
        )

@app.get("/api/auth/logout")
async def logout():
    """Đăng xuất, xóa cookie phiên và chuyển hướng về login."""
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_token")
    return response

# --- API CỦA HỆ THỐNG ---

@app.get("/api/system/stats")
async def system_stats():
    """Lấy thông số RAM, CPU, Disk hiện tại."""
    return get_system_stats()

def verify_bot_access(
    bot_id: str, 
    x_bot_password: Optional[str] = Header(None), 
    password: Optional[str] = Query(None)
):
    """Xác minh quyền truy cập bot bằng mật khẩu."""
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    bot_info = manager.active_bots[bot_id]
    expected_password = bot_info.get("password", "")
    
    if expected_password:
        provided_password = x_bot_password or password
        if provided_password != expected_password:
            raise HTTPException(
                status_code=401, 
                detail="Mật khẩu truy cập bot không chính xác hoặc chưa được cung cấp."
            )

@app.get("/api/bots")
async def list_bots():
    """Lấy danh sách tất cả các bot và trạng thái."""
    bots_list = []
    for bot_id, info in list(manager.active_bots.items()):
        bots_list.append({
            "id": bot_id,
            "name": info["name"],
            "status": info["status"],
            "restarts": info["restarts"],
            "error_msg": info["error_msg"],
            "has_password": bool(info.get("password", ""))
        })
    return bots_list

@app.post("/api/bots")
async def create_or_update_bot(bot_data: BotCreateSchema):
    """Tạo mới hoặc chỉnh sửa cấu hình một bot."""
    # Validate bot_id chỉ chứa chữ và số, gạch dưới để tránh path traversal
    if not bot_data.id.isalnum() and "_" not in bot_data.id and "-" not in bot_data.id:
        raise HTTPException(status_code=400, detail="Bot ID chỉ được chứa chữ cái, số, gạch dưới hoặc gạch nối.")
        
    # Chống tạo trùng bot
    if not bot_data.is_edit:
        if bot_data.id in manager.active_bots or os.path.exists(os.path.join(manager.base_dir, bot_data.id)):
            raise HTTPException(status_code=400, detail="Mã ID Bot này đã tồn tại! Vui lòng chọn ID khác.")
        
    # Xử lý code tùy chọn
    code_content = bot_data.code
    if code_content is None:
        if bot_data.is_edit and bot_data.id in manager.active_bots:
            # Đọc lại code hiện tại của bot để tránh ghi đè trống
            paths = manager.get_bot_paths(bot_data.id)
            if os.path.exists(paths["code"]):
                try:
                    with open(paths["code"], "r", encoding="utf-8") as f:
                        code_content = f.read()
                except:
                    code_content = ""
            else:
                code_content = ""
        else:
            # Tạo code mặc định khi tạo mới bot
            code_content = f"# Bot: {bot_data.name}\nprint('Khởi động Bot thành công!')\n"

    password_val = bot_data.password
    if bot_data.is_edit:
        if bot_data.clear_password:
            password_val = ""
        elif not password_val:
            password_val = manager.active_bots[bot_data.id].get("password", "")

    success = await manager.create_bot(
        bot_id=bot_data.id,
        bot_name=bot_data.name,
        code=code_content,
        env_content=bot_data.env,
        requirements_content=bot_data.requirements,
        use_env=bot_data.use_env,
        entrypoint=bot_data.entrypoint,
        is_edit=bot_data.is_edit,
        password=password_val
    )
    if success:
        return {"status": "success", "message": f"Đã lưu bot {bot_data.name} thành công."}
    raise HTTPException(status_code=500, detail="Không thể tạo hoặc cập nhật bot.")

@app.delete("/api/bots/{bot_id}")
async def delete_bot(bot_id: str, _ = Depends(verify_bot_access)):
    """Xóa hoàn toàn bot khỏi hệ thống."""
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
    success = await manager.delete_bot(bot_id)
    if success:
        return {"status": "success", "message": "Đã xóa bot thành công."}
    raise HTTPException(status_code=500, detail="Không thể xóa bot.")

@app.post("/api/bots/{bot_id}/start")
async def start_bot(bot_id: str, _ = Depends(verify_bot_access)):
    """Bật bot."""
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
    success = await manager.start_bot(bot_id)
    if success:
        return {"status": "success", "message": "Yêu cầu khởi chạy bot đã được gửi."}
    raise HTTPException(status_code=500, detail="Không thể bật bot.")

@app.post("/api/bots/{bot_id}/stop")
async def stop_bot(bot_id: str, _ = Depends(verify_bot_access)):
    """Tắt bot."""
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
    success = await manager.stop_bot(bot_id)
    if success:
        return {"status": "success", "message": "Đã gửi yêu cầu tắt bot."}
    raise HTTPException(status_code=500, detail="Không thể tắt bot.")

@app.post("/api/bots/{bot_id}/restart")
async def restart_bot(bot_id: str, _ = Depends(verify_bot_access)):
    """Khởi động lại bot."""
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
    success = await manager.restart_bot(bot_id)
    if success:
        return {"status": "success", "message": "Đã gửi yêu cầu khởi động lại bot."}
    raise HTTPException(status_code=500, detail="Không thể khởi động lại bot.")

@app.post("/api/bots/{bot_id}/logs/clear")
async def clear_bot_logs(bot_id: str, _ = Depends(verify_bot_access)):
    """Dọn sạch file log của bot một cách an toàn khi bot không chạy."""
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    bot_info = manager.active_bots[bot_id]
    if bot_info["status"] == "RUNNING":
        raise HTTPException(status_code=400, detail="Không thể dọn log khi bot đang hoạt động!")
        
    paths = manager.get_bot_paths(bot_id)
    log_path = paths["log"]
    
    try:
        # Giải phóng log file handle nếu đang được lưu trữ
        log_file_handle = bot_info.get("log_file_handle")
        if log_file_handle:
            try:
                log_file_handle.close()
            except:
                pass
            bot_info["log_file_handle"] = None
            
        # Làm trống tệp log
        if os.path.exists(log_path):
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("")
        return {"status": "success", "message": "Đã dọn sạch tệp tin log của Bot."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi dọn dẹp log: {str(e)}")

@app.get("/api/bots/{bot_id}/config")
async def get_bot_config(bot_id: str, _ = Depends(verify_bot_access)):
    """Lấy nội dung code và env hiện tại của bot để chỉnh sửa."""
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    paths = manager.get_bot_paths(bot_id)
    code_content = ""
    env_content = ""
    requirements_content = ""
    
    if os.path.exists(paths["code"]):
        with open(paths["code"], "r", encoding="utf-8") as f:
            code_content = f.read()
            
    if os.path.exists(paths["env"]):
        with open(paths["env"], "r", encoding="utf-8") as f:
            env_content = f.read()
            
    if os.path.exists(paths["requirements"]):
        with open(paths["requirements"], "r", encoding="utf-8") as f:
            requirements_content = f.read()
            
    return {
        "id": bot_id,
        "name": manager.active_bots[bot_id]["name"],
        "code": code_content,
        "env": env_content,
        "requirements": requirements_content,
        "use_env": manager.active_bots[bot_id].get("use_env", True),
        "entrypoint": manager.active_bots[bot_id].get("entrypoint", "bot.py")
    }

# --- WEBSOCKETS CHO REAL-TIME UPDATE ---

@app.websocket("/api/system/stats/ws")
async def system_stats_websocket(websocket: WebSocket, session_token: Optional[str] = Cookie(None)):
    """WebSocket gửi thông số hệ thống (RAM, CPU, Disk) liên tục mỗi 2 giây."""
    if not session_token or not verify_data(session_token):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        while True:
            stats = get_system_stats()
            await websocket.send_json(stats)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket Stats Lỗi: {e}")

@app.websocket("/api/bots/{bot_id}/console/ws")
async def bot_console_websocket(websocket: WebSocket, bot_id: str, password: Optional[str] = None, session_token: Optional[str] = Cookie(None)):
    """WebSocket stream log thời gian thực của bot lên Terminal giả lập trên Web."""
    if not session_token or not verify_data(session_token):
        await websocket.close(code=1008)
        return
        
    if bot_id not in manager.active_bots:
        await websocket.close(code=4004)
        return
        
    # Xác minh mật khẩu nếu bot có mật khẩu
    bot_info = manager.active_bots[bot_id]
    expected_password = bot_info.get("password", "")
    if expected_password and password != expected_password:
        await websocket.close(code=4001, reason="Mật khẩu truy cập bot không chính xác.")
        return
        
    await websocket.accept()
    paths = manager.get_bot_paths(bot_id)
    
    # 1. Gửi 100 dòng log cũ trước
    initial_logs = manager.get_bot_logs(bot_id, max_lines=100)
    await websocket.send_text(initial_logs)
    
    # 2. Theo dõi và stream các dòng log mới
    try:
        # Nếu chưa có file log, đợi file được tạo
        for _ in range(20):
            if os.path.exists(paths["log"]):
                break
            await asyncio.sleep(0.5)
            
        if not os.path.exists(paths["log"]):
            await websocket.send_text("[Hệ thống] Chưa tìm thấy file log.\n")

        async def receive_loop():
            """Vòng lặp nhận dữ liệu để phát hiện ngắt kết nối từ client."""
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass

        async def send_loop():
            """Vòng lặp đọc và gửi log thời gian thực."""
            with open(paths["log"], "r", encoding="utf-8", errors="ignore") as f:
                # Nhảy đến cuối file để chỉ đọc các log mới phát sinh
                f.seek(0, os.SEEK_END)
                while True:
                    if bot_id not in manager.active_bots:
                        break
                    line = f.readline()
                    if line:
                        await websocket.send_text(line)
                    else:
                        await asyncio.sleep(0.3)

        # Chạy song song cả hai tác vụ. Nếu một trong hai tác vụ kết thúc (ví dụ: client đóng tab),
        # tác vụ còn lại sẽ bị hủy bỏ một cách an toàn.
        recv_task = asyncio.create_task(receive_loop())
        send_task = asyncio.create_task(send_loop())
        
        await asyncio.wait(
            [recv_task, send_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Hủy bỏ tác vụ còn lại để tránh rò rỉ tài nguyên
        recv_task.cancel()
        send_task.cancel()
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(f"\n[Hệ thống Lỗi] Mất kết nối WebSocket Log: {e}\n")
        except:
            pass

def safe_resolve_path(bot_id: str, relative_path: str) -> str:
    """Giải quyết đường dẫn tương đối của bot và kiểm tra an toàn chống Path Traversal."""
    bot_paths = manager.get_bot_paths(bot_id)
    bot_dir = os.path.abspath(bot_paths["dir"])
    
    # Giải quyết đường dẫn tương đối thành tuyệt đối
    target_path = os.path.abspath(os.path.join(bot_dir, relative_path.lstrip("/")))
    
    # Đảm bảo target_path nằm nghiêm ngặt bên trong bot_dir
    # (nghĩa là bot_dir phải là tiền tố của target_path)
    if not target_path.startswith(bot_dir):
        raise HTTPException(status_code=403, detail="Cảnh báo bảo mật: Không được phép truy cập thư mục ngoài phạm vi bot!")
        
    # Ngăn cản tác động vào thư mục ảo venv
    venv_dir = os.path.abspath(bot_paths["venv"])
    if target_path == venv_dir or target_path.startswith(venv_dir + os.sep):
        raise HTTPException(status_code=403, detail="Không được phép thao tác trên thư mục venv!")
        
    return target_path

# 1. API: Lấy danh sách file/thư mục
@app.get("/api/bots/{bot_id}/files")
async def list_bot_files(bot_id: str, path: str = "", _ = Depends(verify_bot_access)):
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    target_dir = safe_resolve_path(bot_id, path)
    if not os.path.exists(target_dir):
        raise HTTPException(status_code=404, detail="Đường dẫn không tồn tại.")
    if not os.path.isdir(target_dir):
        raise HTTPException(status_code=400, detail="Đường dẫn không phải là thư mục.")
        
    files_list = []
    try:
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            is_dir = os.path.isdir(item_path)
            size = os.path.getsize(item_path) if not is_dir else 0
            mtime = os.path.getmtime(item_path)
            
            # Ẩn thư mục venv để tránh gây rối mắt và bảo vệ môi trường ảo
            if item == "venv":
                continue
                
            files_list.append({
                "name": item,
                "is_dir": is_dir,
                "size": size,
                "mtime": mtime
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đọc thư mục: {str(e)}")
        
    # Sắp xếp thư mục lên trước, tệp tin sau
    files_list.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return files_list

# 2. API: Lấy nội dung file văn bản
@app.get("/api/bots/{bot_id}/files/content")
async def get_bot_file_content(bot_id: str, path: str, _ = Depends(verify_bot_access)):
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    target_file = safe_resolve_path(bot_id, path)
    if not os.path.exists(target_file):
        raise HTTPException(status_code=404, detail="Tệp tin không tồn tại.")
    if os.path.isdir(target_file):
        raise HTTPException(status_code=400, detail="Đường dẫn là thư mục, không phải tệp tin.")
        
    # Giới hạn kích thước file đọc trực tuyến (tối đa 5MB)
    MAX_VIEW_SIZE = 5 * 1024 * 1024  # 5MB
    if os.path.getsize(target_file) > MAX_VIEW_SIZE:
        raise HTTPException(
            status_code=400, 
            detail="Tệp tin quá lớn (vượt quá 5MB). Vui lòng sử dụng tính năng Tải xuống (Download) để xem nội dung."
        )
        
    # Chỉ cho phép đọc các file dạng văn bản hoặc code
    allowed_extensions = ['.py', '.env', '.txt', '.json', '.md', '.js', '.css', '.html', '.yaml', '.yml', '.ini', '.cfg', '.log']
    _, ext = os.path.splitext(target_file.lower())
    # Nếu file không có extension (như .env) hoặc nằm trong danh sách cho phép
    if ext not in allowed_extensions and os.path.basename(target_file) != ".env":
        raise HTTPException(status_code=400, detail="Định dạng tệp tin này không được hỗ trợ chỉnh sửa trực tuyến.")
        
    try:
        with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đọc tệp tin: {str(e)}")

@app.get("/api/bots/{bot_id}/files/download")
async def download_bot_file(bot_id: str, path: str, _ = Depends(verify_bot_access)):
    """Tải tệp tin của bot về máy client."""
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    target_file = safe_resolve_path(bot_id, path)
    if not os.path.exists(target_file):
        raise HTTPException(status_code=404, detail="Tệp tin không tồn tại.")
    if os.path.isdir(target_file):
        raise HTTPException(status_code=400, detail="Không thể tải xuống thư mục.")
        
    return FileResponse(
        path=target_file,
        filename=os.path.basename(target_file),
        media_type="application/octet-stream"
    )

# Model lưu nội dung file
class SaveFileSchema(BaseModel):
    path: str
    content: str

# 3. API: Lưu nội dung file văn bản
@app.post("/api/bots/{bot_id}/files/content")
async def save_bot_file_content(bot_id: str, payload: SaveFileSchema, _ = Depends(verify_bot_access)):
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    target_file = safe_resolve_path(bot_id, payload.path)
    
    # Tạo thư mục cha nếu chưa có (đề phòng)
    os.makedirs(os.path.dirname(target_file), exist_ok=True)
    
    try:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(payload.content)
        return {"status": "success", "message": "Đã lưu tệp tin thành công."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi ghi tệp tin: {str(e)}")

# Model tạo file/thư mục
class CreateItemSchema(BaseModel):
    path: str
    is_dir: bool

# 4. API: Tạo mới file hoặc thư mục
@app.post("/api/bots/{bot_id}/files/create")
async def create_bot_file_or_dir(bot_id: str, payload: CreateItemSchema, _ = Depends(verify_bot_access)):
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    target_path = safe_resolve_path(bot_id, payload.path)
    if os.path.exists(target_path):
        raise HTTPException(status_code=400, detail="Tệp tin hoặc thư mục đã tồn tại.")
        
    try:
        if payload.is_dir:
            os.makedirs(target_path, exist_ok=True)
            msg = "Đã tạo thư mục thành công."
        else:
            # Tạo thư mục cha nếu chưa có
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("")
            msg = "Đã tạo tệp tin thành công."
        return {"status": "success", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo tệp tin/thư mục: {str(e)}")

# Model đổi tên
class RenameItemSchema(BaseModel):
    path: str
    new_name: str

# 5. API: Đổi tên file hoặc thư mục
@app.post("/api/bots/{bot_id}/files/rename")
async def rename_bot_file_or_dir(bot_id: str, payload: RenameItemSchema, _ = Depends(verify_bot_access)):
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    old_path = safe_resolve_path(bot_id, payload.path)
    if not os.path.exists(old_path):
        raise HTTPException(status_code=404, detail="Đường dẫn gốc không tồn tại.")
        
    # Trích xuất thư mục cha và tạo đường dẫn mới
    parent_dir = os.path.dirname(old_path)
    new_path = os.path.join(parent_dir, payload.new_name)
    
    # Kiểm tra an toàn cho đường dẫn mới
    new_path = safe_resolve_path(bot_id, os.path.relpath(new_path, manager.get_bot_paths(bot_id)["dir"]))
    
    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="Tên mới đã tồn tại.")
        
    try:
        os.rename(old_path, new_path)
        return {"status": "success", "message": "Đã đổi tên thành công."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đổi tên: {str(e)}")

# Model xóa
class DeleteItemSchema(BaseModel):
    path: str

# 6. API: Xóa file hoặc thư mục
@app.post("/api/bots/{bot_id}/files/delete")
async def delete_bot_file_or_dir(bot_id: str, payload: DeleteItemSchema, _ = Depends(verify_bot_access)):
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    target_path = safe_resolve_path(bot_id, payload.path)
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="Đường dẫn cần xóa không tồn tại.")
        
    try:
        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        else:
            os.remove(target_path)
        return {"status": "success", "message": "Đã xóa thành công."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa: {str(e)}")

# Model di chuyển file/thư mục
class MoveItemSchema(BaseModel):
    path: str
    new_path: str

# API: Di chuyển file hoặc thư mục
@app.post("/api/bots/{bot_id}/files/move")
async def move_bot_file_or_dir(bot_id: str, payload: MoveItemSchema, _ = Depends(verify_bot_access)):
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    src_path = safe_resolve_path(bot_id, payload.path)
    dest_path = safe_resolve_path(bot_id, payload.new_path)
    
    if not os.path.exists(src_path):
        raise HTTPException(status_code=404, detail="Tệp tin hoặc thư mục nguồn không tồn tại.")
    if os.path.exists(dest_path):
        raise HTTPException(status_code=400, detail="Tệp tin hoặc thư mục đích đã tồn tại.")
        
    # Tạo thư mục cha của đường dẫn đích nếu chưa tồn tại
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    try:
        shutil.move(src_path, dest_path)
        return {"status": "success", "message": "Đã di chuyển thành công."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi di chuyển: {str(e)}")

# Model nhân bản file
class DuplicateItemSchema(BaseModel):
    path: str

# API: Nhân bản file hoặc thư mục
@app.post("/api/bots/{bot_id}/files/duplicate")
async def duplicate_bot_file_or_dir(bot_id: str, payload: DuplicateItemSchema, _ = Depends(verify_bot_access)):
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    src_path = safe_resolve_path(bot_id, payload.path)
    if not os.path.exists(src_path):
        raise HTTPException(status_code=404, detail="Tệp tin hoặc thư mục gốc không tồn tại.")
        
    dir_name = os.path.dirname(src_path)
    base_name = os.path.basename(src_path)
    
    if os.path.isdir(src_path):
        new_base = f"{base_name}_copy"
        dest_path = os.path.join(dir_name, new_base)
        counter = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dir_name, f"{new_base} ({counter})")
            counter += 1
        try:
            shutil.copytree(src_path, dest_path)
            return {"status": "success", "message": f"Đã sao chép thư mục thành công thành '{os.path.basename(dest_path)}'."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi sao chép thư mục: {str(e)}")
    else:
        name_part, ext_part = os.path.splitext(base_name)
        new_base = f"{name_part}_copy{ext_part}"
        dest_path = os.path.join(dir_name, new_base)
        counter = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dir_name, f"{name_part}_copy ({counter}){ext_part}")
            counter += 1
        try:
            shutil.copy2(src_path, dest_path)
            return {"status": "success", "message": f"Đã nhân bản tệp tin thành công thành '{os.path.basename(dest_path)}'."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi nhân bản tệp tin: {str(e)}")

# 7. API: Upload nhiều file cùng lúc
@app.post("/api/bots/{bot_id}/files/upload")
async def upload_bot_files(bot_id: str, path: str = "", files: List[UploadFile] = File(...), _ = Depends(verify_bot_access)):
    if bot_id not in manager.active_bots:
        raise HTTPException(status_code=404, detail="Không tìm thấy bot.")
        
    target_dir = safe_resolve_path(bot_id, path)
    # Tự động tạo thư mục đích nếu chưa có (để hỗ trợ upload cấu trúc thư mục con)
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể tạo thư mục tải lên: {str(e)}")
        
    uploaded_count = 0
    try:
        for file in files:
            # Lọc tên file chống Path Traversal từ client gửi lên
            filename = os.path.basename(file.filename)
            if not filename:
                continue
            file_dest = os.path.join(target_dir, filename)
            
            # Kiểm tra an toàn đích đến
            file_dest = safe_resolve_path(bot_id, os.path.relpath(file_dest, manager.get_bot_paths(bot_id)["dir"]))
            
            with open(file_dest, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_count += 1
            
        return {"status": "success", "message": f"Đã tải lên thành công {uploaded_count} tệp tin."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải lên file: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    # Tự động lấy cổng được cấp từ Wispbyte/Pterodactyl (PORT hoặc SERVER_PORT)
    port = int(os.environ.get("PORT", os.environ.get("SERVER_PORT", 9079)))
    print(f"[Hệ thống] Khởi chạy máy chủ trên cổng: {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
