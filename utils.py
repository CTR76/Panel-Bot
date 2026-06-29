import ast
import os
import sys
import psutil
import shutil

# Bản đồ ánh xạ từ tên import trong Python sang tên package trên PyPI
IMPORT_TO_PACKAGE_MAP = {
    "discord": "discord.py",
    "dotenv": "python-dotenv",
    "PIL": "Pillow",
    "bs4": "beautifulsoup4",
    "mysql": "mysql-connector-python",
    "pg": "psycopg2",
    "yaml": "pyyaml",
    "google": "google-api-python-client",
    "twitchio": "twitchio",
    "youtube_dl": "youtube_dl",
    "yt_dlp": "yt-dlp",
}

def parse_imports(file_path: str) -> set:
    """Quét mã nguồn của bot để tìm tất cả các thư viện được import."""
    if not os.path.exists(file_path):
        return set()
        
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
            
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Lấy phần tên gốc trước dấu chấm (ví dụ: os.path -> os)
                    root_name = alias.name.split(".")[0]
                    imports.add(root_name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_name = node.module.split(".")[0]
                    imports.add(root_name)
    except Exception as e:
        print(f"Lỗi khi parse file {file_path}: {e}")
        
    return imports

def get_external_packages(import_names: set) -> set:
    """Lọc bỏ thư viện chuẩn của Python và trả về danh sách gói cần cài đặt."""
    # Lấy danh sách thư viện chuẩn của Python (chỉ có từ Python 3.10+)
    stdlib = getattr(sys, "stdlib_module_names", set())
    if not stdlib:
        # Fallback cho các phiên bản Python cũ hơn
        import sysconfig
        stdlib = set(sysconfig.get_python_lib(standard_lib=True))
        
    external_packages = set()
    for name in import_names:
        # Bỏ qua thư viện chuẩn và các module nội bộ (bắt đầu bằng dấu chấm hoặc cùng thư mục)
        if name in stdlib or name in sys.builtin_module_names or name == "":
            continue
            
        # Ánh xạ tên import sang tên package trên PyPI nếu có
        package_name = IMPORT_TO_PACKAGE_MAP.get(name, name)
        external_packages.add(package_name)
        
    return external_packages

def get_system_stats() -> dict:
    """Lấy thông số RAM, CPU và Disk của hệ thống."""
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        
        # RAM
        virtual_mem = psutil.virtual_memory()
        ram_total = virtual_mem.total
        ram_used = virtual_mem.used
        ram_percent = virtual_mem.percent
        
        # Disk
        disk_usage = psutil.disk_usage("/")
        disk_total = disk_usage.total
        disk_used = disk_usage.used
        disk_percent = disk_usage.percent
        
        return {
            "cpu": cpu_percent,
            "ram": {
                "total": round(ram_total / (1024 ** 3), 2), # GB
                "used": round(ram_used / (1024 ** 3), 2),   # GB
                "percent": ram_percent
            },
            "disk": {
                "total": round(disk_total / (1024 ** 3), 2), # GB
                "used": round(disk_used / (1024 ** 3), 2),   # GB
                "percent": disk_percent
            }
        }
    except Exception as e:
        print(f"Lỗi khi lấy thông số hệ thống: {e}")
        return {
            "cpu": 0,
            "ram": {"total": 0, "used": 0, "percent": 0},
            "disk": {"total": 0, "used": 0, "percent": 0}
        }

def rotate_log_file(log_path: str, max_size_bytes: int = 1 * 1024 * 1024):
    """Giới hạn kích thước file log để tránh đầy ổ đĩa. 
    Nếu vượt quá max_size_bytes, giữ lại khoảng 1000 dòng cuối cùng."""
    if not os.path.exists(log_path):
        return
        
    try:
        if os.path.getsize(log_path) > max_size_bytes:
            # Đọc khoảng 1000 dòng cuối cùng
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            
            keep_lines = lines[-1000:] if len(lines) > 1000 else lines
            
            # Ghi đè lại file log với các dòng đã giữ
            with open(log_path, "w", encoding="utf-8") as f:
                f.writelines(keep_lines)
                f.write("\n--- [Hệ thống tự động xoay vòng Log để tiết kiệm dung lượng] ---\n")
    except Exception as e:
        print(f"Lỗi khi xoay vòng file log {log_path}: {e}")
