import os
import sys
import subprocess
import asyncio
import logging
import shutil
import re
import json
from typing import Dict, Any, List
from utils import parse_imports, get_external_packages, rotate_log_file

# Cấu hình logging cho orchestrator
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Orchestrator")

class BotProcessManager:
    def __init__(self, base_dir: str = "bots"):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs("states", exist_ok=True)
        
        # Thiết lập người dùng chạy bot bảo mật trên Linux
        self.runner_user = None
        if os.name != "nt" and os.getuid() == 0:
            self._setup_secure_runner()
            
        # Lưu trữ thông tin chạy của các bot
        self.active_bots: Dict[str, Dict[str, Any]] = {}
        
        # Hàng đợi cài đặt pip (asyncio.Queue)
        self.pip_queue = asyncio.Queue()
        
        # Hủy bỏ nhiệm vụ chạy ngầm nếu cần
        self.monitor_task = None
        self.pip_worker_task = None
        
        # Tải danh sách bot hiện có từ ổ đĩa
        self._load_existing_bots()

    def _setup_secure_runner(self):
        """Tạo người dùng hệ thống bảo mật aegisbot_runner và phân quyền thư mục."""
        import pwd
        try:
            pwd.getpwnam("aegisbot_runner")
            self.runner_user = "aegisbot_runner"
        except KeyError:
            try:
                subprocess.run(["useradd", "-r", "-s", "/bin/false", "aegisbot_runner"], check=True)
                self.runner_user = "aegisbot_runner"
                logger.info("Đã tạo người dùng hệ thống bảo mật 'aegisbot_runner'.")
            except Exception as e:
                logger.error(f"Không thể tạo người dùng 'aegisbot_runner': {e}")
                
        if self.runner_user:
            try:
                user_info = pwd.getpwnam(self.runner_user)
                uid = user_info.pw_uid
                gid = user_info.pw_gid
                
                # Phân quyền sở hữu thư mục bots và các thư mục con cho aegisbot_runner
                os.chown(self.base_dir, uid, gid)
                os.chmod(self.base_dir, 0o770)
                for root, dirs, files in os.walk(self.base_dir):
                    for d in dirs:
                        path = os.path.join(root, d)
                        os.chown(path, uid, gid)
                        os.chmod(path, 0o770)
                    for f in files:
                        path = os.path.join(root, f)
                        os.chown(path, uid, gid)
                        os.chmod(path, 0o660)
                logger.info(f"Đã phân quyền sở hữu thư mục {self.base_dir} cho {self.runner_user}")
            except Exception as e:
                logger.error(f"Lỗi phân quyền thư mục bots: {e}")

    def get_subprocess_kwargs(self) -> dict:
        """Trả về cấu hình chạy tiến trình con với quyền hạn hạn chế trên Linux."""
        kwargs = {}
        if self.runner_user and os.name != "nt":
            if sys.version_info >= (3, 9):
                kwargs["user"] = self.runner_user
            else:
                import pwd
                uid = pwd.getpwnam(self.runner_user).pw_uid
                kwargs["preexec_fn"] = lambda: os.setuid(uid)
        return kwargs

    def _load_existing_bots(self):
        """Quét thư mục bots để tải các bot đã tồn tại và dọn dẹp các file state mồ côi."""
        if not os.path.exists(self.base_dir):
            return
            
        for bot_id in os.listdir(self.base_dir):
            bot_path = os.path.join(self.base_dir, bot_id)
            if os.path.isdir(bot_path):
                # Đọc tên bot từ file cấu hình hoặc mặc định là bot_id
                bot_name = bot_id
                
                # Đọc trạng thái đã lưu (mặc định là tắt)
                enabled = False
                use_env = True
                entrypoint = "bot.py"
                password = ""
                state_file = os.path.join("states", f"{bot_id}.json")
                if os.path.exists(state_file):
                    try:
                        with open(state_file, "r", encoding="utf-8") as sf:
                            state_data = json.load(sf)
                            enabled = state_data.get("enabled", False)
                            use_env = state_data.get("use_env", True)
                            entrypoint = state_data.get("entrypoint", "bot.py").replace('\\', '/').strip().strip('/')
                            if not entrypoint:
                                entrypoint = "bot.py"
                            password = state_data.get("password", "")
                            bot_name = state_data.get("name", bot_id)
                    except Exception as e:
                        logger.error(f"Lỗi khi đọc file trạng thái của {bot_id}: {e}")

                # Đọc cấu hình hoặc đặt mặc định
                self.active_bots[bot_id] = {
                    "process": None,
                    "status": "STOPPED",
                    "restarts": 0,
                    "name": bot_name,
                    "error_msg": "",
                    "enabled": enabled,
                    "use_env": use_env,
                    "entrypoint": entrypoint,
                    "password": password
                }
                logger.info(f"Đã tải cấu hình bot từ ổ đĩa: {bot_id} ({bot_name}), trạng thái lưu: {'Bật' if enabled else 'Tắt'}, dùng .env: {use_env}, file chạy: {entrypoint}, có mật khẩu: {bool(password)}")

        # Tối ưu hiệu năng: Đối chiếu và dọn dẹp các file JSON mồ côi trong states/
        states_dir = "states"
        if os.path.exists(states_dir):
            for state_filename in os.listdir(states_dir):
                if state_filename.endswith(".json"):
                    bot_id = state_filename[:-5]
                    bot_dir = os.path.join(self.base_dir, bot_id)
                    if not os.path.exists(bot_dir) or not os.path.isdir(bot_dir):
                        state_file_path = os.path.join(states_dir, state_filename)
                        try:
                            os.remove(state_file_path)
                            logger.info(f"Đã dọn dẹp tệp trạng thái mồ côi: {state_file_path} (Do thư mục bot không tồn tại)")
                        except Exception as e:
                            logger.error(f"Lỗi khi xóa file trạng thái mồ côi {state_file_path}: {e}")

    def _save_bot_state(self, bot_id: str, enabled: bool, use_env: bool = None, entrypoint: str = None, password: str = None, bot_name: str = None):
        """Lưu trạng thái kích hoạt và cấu hình của bot vào đĩa để khôi phục khi sập/reboot."""
        state_file = os.path.join("states", f"{bot_id}.json")
        if use_env is None:
            use_env = self.active_bots[bot_id].get("use_env", True)
        if entrypoint is None:
            entrypoint = self.active_bots[bot_id].get("entrypoint", "bot.py")
        entrypoint = entrypoint.replace('\\', '/').strip().strip('/')
        if not entrypoint:
            entrypoint = "bot.py"
        if password is None:
            password = self.active_bots[bot_id].get("password", "")
        if bot_name is None:
            bot_name = self.active_bots[bot_id].get("name", bot_id)
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({
                    "name": bot_name,
                    "enabled": enabled, 
                    "use_env": use_env,
                    "entrypoint": entrypoint,
                    "password": password
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Lỗi khi lưu file trạng thái của {bot_id}: {e}")

    def get_bot_paths(self, bot_id: str) -> Dict[str, str]:
        """Trả về các đường dẫn liên quan đến bot."""
        bot_dir = os.path.join(self.base_dir, bot_id)
        venv_dir = os.path.join(bot_dir, "venv")
        
        # Xác định đường dẫn thực thi dựa trên Hệ điều hành
        if os.name == "nt":  # Windows
            python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
            pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")
        else:  # Linux / macOS (Wispbyte VPS chạy Linux)
            python_exe = os.path.join(venv_dir, "bin", "python")
            pip_exe = os.path.join(venv_dir, "bin", "pip")
            
        entrypoint = "bot.py"
        if bot_id in self.active_bots:
            entrypoint = self.active_bots[bot_id].get("entrypoint", "bot.py")
            
        return {
            "dir": bot_dir,
            "venv": venv_dir,
            "python": python_exe,
            "pip": pip_exe,
            "code": os.path.join(bot_dir, entrypoint),
            "env": os.path.join(bot_dir, ".env"),
            "requirements": os.path.join(bot_dir, "requirements.txt"),
            "log": os.path.join(bot_dir, "bot.log")
        }

    async def start_background_tasks(self):
        """Khởi động các tác vụ giám sát chạy ngầm."""
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        self.pip_worker_task = asyncio.create_task(self._pip_queue_worker())
        logger.info("Đã khởi động các tiến trình giám sát và hàng đợi cài đặt.")
        
        # Tự động khôi phục các bot đã được bật trước khi server sập/reboot
        for bot_id, info in list(self.active_bots.items()):
            if info.get("enabled", False):
                logger.info(f"Tự động khôi phục chạy bot: {bot_id}")
                asyncio.create_task(self.start_bot(bot_id))

    async def stop_background_tasks(self):
        """Dừng các tác vụ chạy ngầm khi tắt server."""
        if self.monitor_task:
            self.monitor_task.cancel()
        if self.pip_worker_task:
            self.pip_worker_task.cancel()
        
        # Dừng tất cả các bot đang chạy nhưng giữ nguyên trạng thái enabled để khôi phục khi bật lại
        for bot_id in list(self.active_bots.keys()):
            await self.stop_bot(bot_id, keep_enabled=True)

    async def create_bot(self, bot_id: str, bot_name: str, code: str, env_content: str, requirements_content: str = "", use_env: bool = True, entrypoint: str = "bot.py", is_edit: bool = False, password: str = "") -> bool:
        """Tạo mới hoặc cập nhật một bot."""
        # Chuẩn hóa entrypoint (chuyển \ thành / và loại bỏ khoảng trắng, gạch chéo dư thừa)
        entrypoint = entrypoint.replace('\\', '/').strip().strip('/')
        if not entrypoint:
            entrypoint = "bot.py"

        # Cập nhật trạng thái trong bộ nhớ trước để get_bot_paths lấy đúng entrypoint mới
        if bot_id not in self.active_bots:
            self.active_bots[bot_id] = {
                "process": None,
                "status": "STOPPED",
                "restarts": 0,
                "name": bot_name,
                "error_msg": "",
                "enabled": False,
                "use_env": use_env,
                "entrypoint": entrypoint,
                "password": password
            }
        else:
            self.active_bots[bot_id]["name"] = bot_name
            self.active_bots[bot_id]["use_env"] = use_env
            self.active_bots[bot_id]["entrypoint"] = entrypoint
            self.active_bots[bot_id]["password"] = password

        paths = self.get_bot_paths(bot_id)
        os.makedirs(paths["dir"], exist_ok=True)
        
        # Ghi mã nguồn python (Chỉ áp dụng khi tạo mới bot, không tạo/ghi file khi sửa cấu hình)
        if not is_edit:
            # Tự động tạo thư mục cha của file chạy chính nếu cần
            os.makedirs(os.path.dirname(paths["code"]), exist_ok=True)
            with open(paths["code"], "w", encoding="utf-8") as f:
                f.write(code)
            
        # Ghi file .env
        with open(paths["env"], "w", encoding="utf-8") as f:
            f.write(env_content)
            
        # Ghi file requirements.txt
        with open(paths["requirements"], "w", encoding="utf-8") as f:
            f.write(requirements_content)
            
        # Khởi tạo file log nếu chưa có
        if not os.path.exists(paths["log"]):
            with open(paths["log"], "w", encoding="utf-8") as f:
                f.write(f"--- Khởi tạo Bot: {bot_name} ---\n")
                
        # Lưu trạng thái cấu hình xuống đĩa
        self._save_bot_state(bot_id, self.active_bots[bot_id]["enabled"], use_env, entrypoint, password)
            
        logger.info(f"Đã ghi file cấu hình cho bot: {bot_id} (Ghi code: {not is_edit})")
        return True

    async def delete_bot(self, bot_id: str) -> bool:
        """Xóa hoàn toàn một bot khỏi hệ thống."""
        await self.stop_bot(bot_id)
        paths = self.get_bot_paths(bot_id)
        
        # Xóa khỏi danh sách active_bots trước để giải phóng các luồng đọc log (WebSockets)
        if bot_id in self.active_bots:
            del self.active_bots[bot_id]
            
        # Xóa tệp trạng thái lưu trữ bên ngoài
        state_file = os.path.join("states", f"{bot_id}.json")
        if os.path.exists(state_file):
            try:
                os.remove(state_file)
            except Exception as e:
                logger.error(f"Không thể xóa tệp trạng thái của bot {bot_id}: {e}")
            
        # Đợi một chút để các WebSocket loop thực sự thoát và đóng file handle
        await asyncio.sleep(0.2)
        
        if os.path.exists(paths["dir"]):
            # Xóa thư mục bot bằng hàm retry để tránh trễ giải phóng file của OS
            success = await self._delete_dir_with_retry(paths["dir"])
            return success
            
        return True

    async def _delete_dir_with_retry(self, dir_path: str, retries: int = 5, delay: float = 0.3) -> bool:
        """Thử xóa thư mục nhiều lần để tránh lỗi khóa tệp trễ trên Windows/Linux."""
        for i in range(retries):
            try:
                # rmtree chạy đồng bộ, đưa vào thread để tránh block
                await asyncio.to_thread(shutil.rmtree, dir_path)
                logger.info(f"Đã xóa thành công thư mục: {dir_path}")
                return True
            except Exception as e:
                logger.warning(f"Thử xóa thư mục {dir_path} lần {i+1} thất bại: {e}. Thử lại sau {delay}s...")
                await asyncio.sleep(delay)
        
        # Nếu vẫn thất bại sau nhiều lần thử, dùng ignore_errors làm phương án cuối
        try:
            await asyncio.to_thread(shutil.rmtree, dir_path, ignore_errors=True)
        except:
            pass
        return not os.path.exists(dir_path)

    async def start_bot(self, bot_id: str) -> bool:
        """Kích hoạt chạy bot."""
        if bot_id not in self.active_bots:
            return False
            
        bot_info = self.active_bots[bot_id]
        bot_info["enabled"] = True
        self._save_bot_state(bot_id, True)
        
        if bot_info["status"] in ["RUNNING", "INSTALLING"]:
            return True  # Đang chạy hoặc đang cài đặt rồi
            
        bot_info["status"] = "STARTING"
        bot_info["restarts"] = 0
        bot_info["install_attempts"] = 0  # Reset số lần thử cài đặt khi bật thủ công
        bot_info["error_msg"] = ""
        
        # Đưa vào quy trình khởi chạy
        asyncio.create_task(self._launch_bot_sequence(bot_id))
        return True

    async def stop_bot(self, bot_id: str, keep_enabled: bool = False) -> bool:
        """Dừng tiến trình của bot."""
        if bot_id not in self.active_bots:
            return False
            
        bot_info = self.active_bots[bot_id]
        if not keep_enabled:
            bot_info["enabled"] = False
            self._save_bot_state(bot_id, False)
        
        proc = bot_info["process"]
        bot_info["status"] = "STOPPED"
        
        # Đóng file log handle để giải phóng khóa tệp (đặc biệt trên Windows)
        log_file_handle = bot_info.get("log_file_handle")
        if log_file_handle:
            try:
                log_file_handle.close()
            except:
                pass
            bot_info["log_file_handle"] = None
        
        if proc:
            try:
                # Gửi tín hiệu dừng
                if os.name == "nt":
                    proc.terminate()
                else:
                    proc.terminate()
                
                # Chờ tiến trình kết thúc trong tối đa 3 giây
                for _ in range(30):
                    if proc.poll() is not None:
                        break
                    await asyncio.sleep(0.1)
                
                if proc.poll() is None:
                    proc.kill()  # Buộc dừng nếu không phản hồi
                    
                logger.info(f"Đã dừng tiến trình bot: {bot_id}")
            except Exception as e:
                logger.error(f"Lỗi khi dừng bot {bot_id}: {e}")
            finally:
                bot_info["process"] = None
                
        return True

    async def restart_bot(self, bot_id: str) -> bool:
        """Khởi động lại bot."""
        await self.stop_bot(bot_id)
        return await self.start_bot(bot_id)

    async def _launch_bot_sequence(self, bot_id: str):
        """Quy trình chuẩn bị môi trường và khởi chạy bot."""
        paths = self.get_bot_paths(bot_id)
        bot_info = self.active_bots[bot_id]
        
        # 1. Tạo venv nếu chưa tồn tại hoặc bị lỗi (ví dụ copy từ Windows sang Linux)
        venv_exists = os.path.exists(paths["venv"])
        python_exists = os.path.exists(paths["python"])
        
        if venv_exists and not python_exists:
            logger.warning(f"Phát hiện venv của bot {bot_id} không tương thích hoặc lỗi (thiếu file thực thi python). Đang tự động xóa và tạo lại...")
            try:
                shutil.rmtree(paths["venv"])
                venv_exists = False
            except Exception as e:
                logger.error(f"Không thể xóa venv lỗi của bot {bot_id}: {e}")
        
        if not venv_exists:
            bot_info["status"] = "INSTALLING"
            with open(paths["log"], "a", encoding="utf-8") as log_f:
                log_f.write("[Hệ thống] Đang tạo môi trường ảo venv (Có thể mất 10-30 giây)...\n")
            
            # Tạo venv
            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "venv", paths["venv"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **self.get_subprocess_kwargs()
                )
                await proc.wait()
                if proc.returncode != 0:
                    raise Exception(f"Tiến trình venv thoát với mã {proc.returncode}")
            except Exception as e:
                bot_info["status"] = "ERROR"
                bot_info["enabled"] = False
                self._save_bot_state(bot_id, False)
                bot_info["error_msg"] = f"Lỗi tạo venv: {str(e)}"
                with open(paths["log"], "a", encoding="utf-8") as log_f:
                    log_f.write(f"[Hệ thống Lỗi] Không thể tạo venv: {e}\n")
                    log_f.write("[Hệ thống Hướng Dẫn] Lỗi này thường do VPS của bạn thiếu gói python3-venv.\n")
                    log_f.write("Hãy chạy lệnh sau trên terminal của VPS (SSH) để cài đặt rồi thử lại:\n")
                    log_f.write("    sudo apt update && sudo apt install python3-venv -y\n")
                return

        # 2. Đọc các thư viện từ requirements.txt của người dùng
        user_packages = []
        if os.path.exists(paths["requirements"]):
            try:
                with open(paths["requirements"], "r", encoding="utf-8") as req_f:
                    for line in req_f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            user_packages.append(line)
            except Exception as e:
                logger.error(f"Lỗi khi đọc file requirements.txt của {bot_id}: {e}")

        # 3. Quét các thư viện cần thiết bằng AST
        imports = parse_imports(paths["code"])
        ast_packages = get_external_packages(imports)
        
        # Trộn hai danh sách thư viện và lọc trùng lặp thông minh
        merged_packages = list(user_packages)
        
        # Trích xuất tên gốc của user_packages để so sánh
        user_package_bases = set()
        for pkg in user_packages:
            match = re.match(r"^([a-zA-Z0-9_\-\.]+)", pkg)
            if match:
                user_package_bases.add(match.group(1).lower().replace("-", "_"))
                
        # Chỉ thêm các gói phát hiện bằng AST nếu người dùng chưa khai báo thủ công
        for pkg in ast_packages:
            pkg_base = pkg.lower().replace("-", "_")
            if pkg_base not in user_package_bases:
                merged_packages.append(pkg)
        
        # Cập nhật thông tin log
        with open(paths["log"], "a", encoding="utf-8") as log_f:
            log_f.write(f"[Hệ thống] Danh sách thư viện cần cài đặt: {', '.join(merged_packages) if merged_packages else 'Không có'}\n")
            
        if merged_packages:
            # Kiểm tra xem các thư viện đã được cài đặt đầy đủ trong venv chưa
            packages_installed = False
            clean_packages = [re.split(r'[<>=~!]', pkg)[0].strip() for pkg in merged_packages if pkg]
            clean_packages = [p for p in clean_packages if p]
            
            try:
                # Chạy kiểm tra nhanh bằng cách gọi python trong venv
                proc = await asyncio.create_subprocess_exec(
                    paths["python"], "-c", 
                    "import sys, importlib.metadata; [importlib.metadata.version(p) for p in sys.argv[1:]]",
                    *clean_packages,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **self.get_subprocess_kwargs()
                )
                await proc.wait()
                if proc.returncode == 0:
                    packages_installed = True
            except Exception as e:
                logger.error(f"Lỗi khi kiểm tra nhanh thư viện của bot {bot_id}: {e}")
                
            if not packages_installed:
                # Gửi các gói cần cài đặt vào Hàng đợi cài đặt Pip
                bot_info["status"] = "INSTALLING"
                await self.pip_queue.put((bot_id, merged_packages))
            else:
                # Đã cài đủ, khởi chạy ngay lập tức
                await self._run_bot_process(bot_id)
        else:
            # Không cần cài đặt gì, khởi chạy ngay
            await self._run_bot_process(bot_id)

    async def _run_bot_process(self, bot_id: str):
        """Khởi chạy thực sự tiến trình Python của bot."""
        paths = self.get_bot_paths(bot_id)
        bot_info = self.active_bots[bot_id]
        
        # Đảm bảo bot vẫn ở trạng thái muốn chạy
        if bot_info["status"] == "STOPPED":
            return
            
        # Mở file log để ghi đè/nối tiếp stdout và stderr
        log_file = open(paths["log"], "a", encoding="utf-8", buffering=1)
        bot_info["log_file_handle"] = log_file
        log_file.write(f"\n[Hệ thống] --- KHỞI CHẠY BOT --- (Lần thử {bot_info['restarts'] + 1})\n")
        
        try:
            # Thiết lập môi trường chạy với file .env của bot
            env = os.environ.copy()
            # Đọc .env thủ công và đưa vào môi trường của tiến trình con nếu được kích hoạt
            if bot_info.get("use_env", True) and os.path.exists(paths["env"]):
                with open(paths["env"], "r", encoding="utf-8") as env_f:
                    for line in env_f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            env[k.strip()] = v.strip()
            
            # Khởi chạy tiến trình con dùng python trong venv
            # Chạy ở chế độ unbuffered (-u) để log xuất hiện ngay lập tức
            proc = subprocess.Popen(
                [paths["python"], "-u", paths["code"]],
                stdout=log_file,
                stderr=log_file,
                cwd=paths["dir"],
                env=env,
                text=True,
                **self.get_subprocess_kwargs()
            )
            
            bot_info["process"] = proc
            bot_info["status"] = "RUNNING"
            logger.info(f"Đã khởi chạy bot {bot_id} (PID: {proc.pid})")
        except Exception as e:
            bot_info["status"] = "ERROR"
            bot_info["error_msg"] = f"Lỗi khởi chạy tiến trình: {str(e)}"
            log_file.write(f"[Hệ thống Lỗi] Lỗi khởi chạy: {e}\n")
            log_file.close()

    async def _pip_queue_worker(self):
        """Hàng đợi chạy Pip tuần tự giúp tiết kiệm RAM cực độ trên VPS 1GB."""
        while True:
            try:
                bot_id, packages = await self.pip_queue.get()
                
                # Kiểm tra xem bot có bị xóa hoặc dừng trong lúc đợi không
                if bot_id not in self.active_bots or self.active_bots[bot_id]["status"] == "STOPPED":
                    self.pip_queue.task_done()
                    continue
                    
                bot_info = self.active_bots[bot_id]
                paths = self.get_bot_paths(bot_id)
                
                bot_info["status"] = "INSTALLING"
                
                with open(paths["log"], "a", encoding="utf-8") as log_f:
                    log_f.write(f"[Hệ thống] Đang cài đặt thư viện tuần tự (Tránh nghẽn RAM VPS): {', '.join(packages)}\n")
                    log_f.flush()
                
                # Chạy pip install từng gói một hoặc gộp chung với cờ tối ưu hóa
                # Cờ --no-cache-dir giúp giảm thiểu dung lượng đĩa NVMe và giảm RAM sử dụng của pip
                cmd = [paths["pip"], "install", "--no-cache-dir"] + packages
                
                try:
                    # Mở file log để pip ghi tiến trình vào đó cho người dùng theo dõi
                    with open(paths["log"], "a", encoding="utf-8") as log_f:
                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=log_f,
                            stderr=log_f,
                            **self.get_subprocess_kwargs()
                        )
                        await proc.wait()
                        
                    with open(paths["log"], "a", encoding="utf-8") as log_f:
                        if proc.returncode == 0:
                            log_f.write("[Hệ thống] Cài đặt thư viện thành công!\n")
                            # Chạy bot sau khi cài đặt thành công
                            await self._run_bot_process(bot_id)
                        else:
                            bot_info["status"] = "ERROR"
                            bot_info["enabled"] = False
                            self._save_bot_state(bot_id, False)
                            bot_info["error_msg"] = "Lỗi cài đặt thư viện (Kiểm tra Log)"
                            log_f.write(f"[Hệ thống Lỗi] Lệnh pip thất bại với mã thoát {proc.returncode}\n")
                except Exception as e:
                    bot_info["status"] = "ERROR"
                    bot_info["enabled"] = False
                    self._save_bot_state(bot_id, False)
                    bot_info["error_msg"] = f"Lỗi chạy pip: {str(e)}"
                    with open(paths["log"], "a", encoding="utf-8") as log_f:
                        log_f.write(f"[Hệ thống Lỗi] Lỗi khi chạy lệnh cài đặt: {e}\n")
                        
                self.pip_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Lỗi trong Pip Queue Worker: {e}")
                await asyncio.sleep(1)

    async def _monitor_loop(self):
        """Vòng lặp giám sát các tiến trình bot chạy ngầm, tự động phục hồi nếu sập và dọn dẹp nóng nếu thư mục bị xóa."""
        while True:
            try:
                await asyncio.sleep(4)  # Kiểm tra mỗi 4 giây
                
                for bot_id, bot_info in list(self.active_bots.items()):
                    # Kiểm tra nóng: Nếu thư mục bot đã bị xóa (ví dụ xóa thủ công qua FTP/CMD)
                    bot_dir = os.path.join(self.base_dir, bot_id)
                    if not os.path.exists(bot_dir) or not os.path.isdir(bot_dir):
                        logger.warning(f"Phát hiện thư mục của bot {bot_id} đã bị xóa hoặc không tồn tại. Tiến hành dọn dẹp trạng thái nóng...")
                        # Dừng tiến trình của bot
                        if bot_info["process"] is not None:
                            try:
                                bot_info["process"].terminate()
                                bot_info["process"].wait(timeout=2)
                            except:
                                try:
                                    bot_info["process"].kill()
                                except:
                                    pass
                        # Giải phóng log file handle nếu có
                        log_file_handle = bot_info.get("log_file_handle")
                        if log_file_handle:
                            try:
                                log_file_handle.close()
                            except:
                                pass
                        # Xóa file cấu hình trạng thái của bot tương ứng
                        state_file = os.path.join("states", f"{bot_id}.json")
                        if os.path.exists(state_file):
                            try:
                                os.remove(state_file)
                            except Exception as e:
                                logger.error(f"Không thể xóa file trạng thái mồ côi {state_file}: {e}")
                        # Xóa khỏi bộ nhớ active_bots
                        self.active_bots.pop(bot_id, None)
                        continue
                    paths = self.get_bot_paths(bot_id)
                    
                    # Tự động dọn dẹp log nếu bot không chạy (trạng thái STOPPED)
                    if bot_info["status"] == "STOPPED":
                        if os.path.exists(paths["log"]):
                            if os.path.getsize(paths["log"]) > 50:  # Hơn 50 bytes mới dọn dẹp để tránh ghi liên tục
                                try:
                                    with open(paths["log"], "w", encoding="utf-8") as f:
                                        f.write("--- Nhật ký trống (Bot đã dừng) ---\n")
                                except Exception as e:
                                    logger.error(f"Lỗi khi tự động dọn log cho bot {bot_id}: {e}")
                                    
                    # Tự động xoay vòng log file nếu vượt quá 1MB để tiết kiệm bộ nhớ VPS
                    rotate_log_file(paths["log"], max_size_bytes=1 * 1024 * 1024)
                    
                    # Chỉ giám sát các bot được đánh dấu là đang chạy (RUNNING)
                    if bot_info["status"] != "RUNNING":
                        continue
                        
                    proc = bot_info["process"]
                    
                    if proc is None:
                        continue
                        
                    # Kiểm tra xem tiến trình đã kết thúc chưa
                    exit_code = proc.poll()
                    if exit_code is not None:
                        # Bot đã bị dừng hoặc crash!
                        logger.warning(f"Phát hiện bot {bot_id} đã dừng với mã thoát: {exit_code}")
                        bot_info["process"] = None
                        
                        # Đóng file log handle để giải phóng khóa tệp
                        log_file_handle = bot_info.get("log_file_handle")
                        if log_file_handle:
                            try:
                                log_file_handle.close()
                            except:
                                pass
                            bot_info["log_file_handle"] = None
                        
                        # 1. Đọc log cuối để phân tích nguyên nhân sập
                        has_import_error = False
                        missing_module = None
                        
                        if os.path.exists(paths["log"]):
                            try:
                                with open(paths["log"], "r", encoding="utf-8", errors="ignore") as log_f:
                                    # Lọc lấy 30 dòng cuối
                                    lines = log_f.readlines()[-30:]
                                    log_content = "".join(lines)
                                    
                                    # Tìm lỗi ModuleNotFoundError
                                    match = re.search(r"ModuleNotFoundError:\s+No\s+module\s+named\s+'([^']+)'", log_content)
                                    if match:
                                        has_import_error = True
                                        missing_module = match.group(1)
                            except Exception as e:
                                logger.error(f"Không thể đọc log phân tích lỗi cho bot {bot_id}: {e}")
                        
                        # 2. Xử lý lỗi thiếu thư viện đột xuất lúc chạy (Runtime)
                        if has_import_error and missing_module:
                            install_attempts = bot_info.get("install_attempts", 0) + 1
                            bot_info["install_attempts"] = install_attempts
                            
                            if install_attempts <= 5:
                                with open(paths["log"], "a", encoding="utf-8") as log_f:
                                    log_f.write(f"[Hệ thống Phát Hiện] Bot sập do thiếu thư viện: '{missing_module}' (Lần thử {install_attempts}/5). Đang tải và cài đặt...\n")
                                
                                # Đưa vào hàng đợi cài đặt
                                bot_info["status"] = "INSTALLING"
                                from utils import IMPORT_TO_PACKAGE_MAP
                                package_name = IMPORT_TO_PACKAGE_MAP.get(missing_module, missing_module)
                                await self.pip_queue.put((bot_id, [package_name]))
                            else:
                                bot_info["status"] = "ERROR"
                                bot_info["enabled"] = False
                                self._save_bot_state(bot_id, False)
                                bot_info["error_msg"] = f"Cài đặt thư viện thất bại 5 lần ('{missing_module}')"
                                with open(paths["log"], "a", encoding="utf-8") as log_f:
                                    log_f.write(f"[Hệ thống Lỗi] Đã thử cài đặt thư viện '{missing_module}' 5 lần nhưng vẫn thất bại. Dừng tự động cài đặt và đặt trạng thái về Tắt để tiết kiệm tài nguyên.\n")
                            
                        # 3. Xử lý khi bot dừng bình thường (Mã thoát 0) hoặc sập (Mã thoát khác 0)
                        elif exit_code == 0:
                            bot_info["status"] = "STOPPED"
                            bot_info["enabled"] = False
                            self._save_bot_state(bot_id, False)
                            bot_info["error_msg"] = ""
                            with open(paths["log"], "a", encoding="utf-8") as log_f:
                                log_f.write("[Hệ thống] Bot đã dừng bình thường với mã thoát 0.\n")
                        else:
                            bot_info["status"] = "ERROR"
                            bot_info["enabled"] = False
                            self._save_bot_state(bot_id, False)
                            bot_info["error_msg"] = f"Bot dừng đột ngột (Mã thoát: {exit_code})"
                            with open(paths["log"], "a", encoding="utf-8") as log_f:
                                log_f.write(f"[Hệ thống Lỗi] Phát hiện bot sập đột ngột với mã thoát {exit_code} (Không phải lỗi thiếu thư viện). AegisBot sẽ KHÔNG tự động khởi động lại và đặt trạng thái về Tắt để tiết kiệm tài nguyên VPS.\n")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Lỗi trong vòng lặp giám sát: {e}")

    async def _delayed_restart(self, bot_id: str, delay: int):
        """Khởi động lại bot sau một khoảng thời gian chờ."""
        await asyncio.sleep(delay)
        if bot_id in self.active_bots and self.active_bots[bot_id]["status"] == "STARTING":
            await self._run_bot_process(bot_id)
            
    def get_bot_logs(self, bot_id: str, max_lines: int = 150) -> str:
        """Đọc log hiện tại của bot."""
        paths = self.get_bot_paths(bot_id)
        if not os.path.exists(paths["log"]):
            return "Chưa có file log."
            
        try:
            with open(paths["log"], "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                return "".join(lines[-max_lines:])
        except Exception as e:
            return f"Không thể đọc log: {e}"
