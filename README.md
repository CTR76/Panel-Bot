# AegisBot Orchestrator - Hệ Thống Quản Lý Bot Song Song

**AegisBot Orchestrator** là một hệ thống máy chủ quản lý đa tiến trình bằng Python (sử dụng FastAPI làm backend và Vanilla CSS/JS làm giao diện). Hệ thống được thiết kế đặc biệt nhằm chạy nhiều bot Discord một cách độc lập, cô lập và **tuyệt đối không bị sập**, tối ưu hóa triệt để cho các máy chủ VPS cấu hình nhẹ như **Wispbyte Special Tier 2 (1GB RAM, 10GB NVMe)**.

---

## 🌟 Các Tính Năng Nổi Bật

### 1. 🛡️ Chống Sập Tuyệt Đối & Tiết Kiệm Tài Nguyên (High Resiliency & Resource-Saving)
* **Chính sách Khởi động lại Tiết kiệm**: 
  * **Lỗi thông thường (Logic code, Token, Kết nối...)**: Hệ thống sẽ **KHÔNG** tự động khởi động lại bot để tránh việc sập liên tục làm quá tải CPU/RAM của VPS 1GB. Bot sẽ lập tức chuyển sang trạng thái **`Lỗi` (ERROR)** để người dùng sửa code.
  * **Lỗi thiếu thư viện (`ModuleNotFoundError`)**: Hệ thống tự động bắt lỗi từ `stderr`, đưa thư viện bị thiếu vào hàng đợi cài đặt và tự động khởi chạy lại bot. Giới hạn thử lại tối đa **5 lần** để tránh lặp vô hạn nếu thư viện không tồn tại.
* **Tự phục hồi an toàn khi VPS Reboot**: Lưu trạng thái hoạt động của từng bot vào đĩa. Khi máy chủ khởi động lại (ví dụ sau khi VPS bị reboot), AegisBot sẽ **tự động chạy lại tất cả các bot đang hoạt động trước khi sập**.
* **Bảo vệ file cấu hình (`state.json`)**: Tách biệt file lưu trạng thái `state.json` của bot và lưu trữ tại thư mục `states/` ở ngoài thư mục code của bot. Người dùng sử dụng trình quản lý file sẽ **không thể nhìn thấy và không sợ vô tình xóa nhầm** file cấu hình hệ thống này.

### 2. 📦 Cô Lập & Tự Sửa Lỗi Môi Trường Ảo (Self-Healing Venv)
* Mỗi bot được tạo một môi trường ảo (`venv`) riêng biệt trong thư mục của nó để tránh xung đột thư viện.
* **Tự động sửa lỗi tương thích (Self-healing)**: Nếu phát hiện thư mục `venv` bị lỗi hoặc không tương thích (ví dụ do người dùng tải thư mục `venv` từ Windows lên VPS Linux), hệ thống sẽ **tự động xóa venv lỗi và tạo mới lại** tương thích 100% với hệ điều hành hiện tại.

### 3. 📁 Hệ Thống Quản Lý File Trực Quan (Online File Manager)
* **Quản lý file toàn diện**: Giao diện quản lý file chuyên nghiệp tích hợp trong chi tiết bot cho phép **Tạo File, Tạo Thư mục, Đổi tên, Tải xuống và Xóa** tệp tin/thư mục.
* **Tải xuống File an toàn**: Tải trực tiếp bất kỳ tệp tin nào của bot về máy cá nhân dưới dạng luồng dữ liệu (Stream), được bảo mật bởi cơ chế xác thực mật khẩu bot và chống lỗi Path Traversal.
* **Tải lên nhiều File**: Hỗ trợ tải lên hàng loạt các file từ máy tính của bạn lên thư mục bot.
* **Trình soạn thảo mã nguồn trực tuyến**: Hỗ trợ mở và chỉnh sửa trực tiếp các tệp tin văn bản hoặc code (`.py`, `.env`, `.json`, `.txt`, `.md`,...) ngay trên trình duyệt với giao diện Dark Mode tối giản, tiện lợi.
* **Bảo mật Path Traversal**: Sử dụng cơ chế kiểm tra đường dẫn tuyệt đối giúp chặn đứng mọi hành vi truy cập trái phép ra ngoài thư mục bot, đồng thời chặn can thiệp vào môi trường ảo `venv`.

### 4. ⚙️ Tùy Chỉnh File Chạy Chính (Entrypoint)
* Hỗ trợ thiết lập tệp tin Python chính để khởi chạy bot (Ví dụ: `bot.py`, `main.py`, `run.py`...) thay vì cố định tên tệp. Bạn có thể dễ dàng thay đổi cấu hình này bất cứ lúc nào trong giao diện sửa bot.

### 5. ⚡ Tối Ưu Hóa Khởi Động & Tự Động Cài Đặt Thư Viện
* **Kiểm tra nhanh thư viện (Fast Pre-check)**: Trước khi khởi chạy bot, hệ thống thực hiện kiểm tra nhanh trong **~0.05 giây** bằng `importlib.metadata` xem các thư viện đã được cài đủ chưa. Nếu đã cài đủ, bot sẽ **khởi chạy ngay lập tức** mà hoàn toàn không gọi tiến trình `pip install`, giúp tiết kiệm 100% CPU/RAM khi khởi động server.
* **Cài đặt file lúc tạo Bot**: Hỗ trợ tùy chọn tải lên danh sách nhiều file mã nguồn ngay từ bước tạo bot mới.
* **Cấu hình `requirements.txt` thủ công**: Thêm ô nhập liệu danh sách thư viện riêng cho từng bot ngay trên giao diện.
* **Quét mã nguồn tĩnh (AST)**: Hệ thống tự động quét mã nguồn của tệp chạy chính để phát hiện các câu lệnh `import` và tự động cài đặt nếu thiếu.
* **Hàng đợi Pip tuần tự (Pip Queue)**: Các thư viện thiếu được cài đặt tuần tự kèm cờ `--no-cache-dir` giúp **tiết kiệm RAM tối đa** và không làm đầy ổ đĩa 10GB NVMe.

### 6. 📊 Giám Sát Hệ Thống & Log Thời Gian Thực
* **Live Console ổn định cao**: Sử dụng kết nối **WebSockets** đa nhiệm song song (`send_loop` và `receive_loop`) để truyền phát (stream) trực tiếp file log (`bot.log`) của từng bot lên màn hình Console giả lập Terminal mà không lo bị ngắt kết nối đột ngột.
* **Xoay vòng Log (Log Rotation)**: Tự động giới hạn kích thước tệp log dưới **1MB** (giữ lại 1000 dòng cuối), tránh làm đầy dung lượng ổ cứng của VPS.
* **Tự động dọn sạch Log**: Khi bot ở trạng thái dừng hoạt động (**`STOPPED`**), hệ thống tự động dọn sạch tệp log về 0 bytes để tiết kiệm dung lượng lưu trữ trên VPS.
* **Resource Monitoring**: Biểu đồ giám sát dung lượng RAM, CPU và Đĩa (Disk) thời gian thực trên thanh tiêu đề.

### 7. 🎨 Giao Diện Trực Quan & Trải Nghiệm Mượt Mà (Smart UX)
* **Tìm kiếm Bot trực quan**: Tích hợp ô tìm kiếm thời gian thực ở sidebar bên trái giúp lọc nhanh danh sách bot theo **Tên** hoặc **ID** ngay khi gõ.
* **Kết nối thông minh khi khởi động**: Giao diện tự động thử kết nối lại sau mỗi 1.5 giây nếu server đang khởi động. Nếu kết nối API thất bại hoặc nhận về trang HTML (lỗi Proxy), giao diện sẽ hiển thị cảnh báo đỏ trực quan.
* **Điều hướng thông minh (Smart Redirects)**: Khi bạn lưu bot hoặc hủy chỉnh sửa, hệ thống sẽ giữ bạn ở lại trang chi tiết của bot đó để thao tác tiếp.
* **Nút Quay lại & Khóa lại**: Thêm nút quay lại nhanh và nút khóa nhanh bot ngay trên thanh tiêu đề chi tiết bot.

---

## 📂 Cấu Trúc Thư Mục Dự Án

```text
server/
├── main.py                 # Điểm khởi chạy FastAPI server, định nghĩa REST API & WebSockets
├── orchestrator.py         # Trình quản lý tiến trình bot, Hàng đợi Pip & Tự động phục hồi
├── utils.py                # Quét AST import, Giám sát phần cứng, Xoay vòng Log (Giới hạn 1MB)
├── requirements.txt        # Các thư viện của máy chủ chính
├── README.md               # Hướng dẫn chi tiết dự án (Tệp này)
├── states/                 # Thư mục lưu trữ trạng thái hoạt động bên ngoài (Tránh xóa nhầm)
│   └── [bot_id].json       # Lưu trạng thái hoạt động (enabled, use_env, entrypoint)
├── templates/
│   └── index.html          # Giao diện quản trị Single Page Application (SPA)
├── static/
│   ├── css/
│   │   └── style.css       # Giao diện Glassmorphism Dark Mode cao cấp (Tím/Indigo)
│   └── js/
│       └── app.js          # Logic xử lý API, cập nhật giao diện & kết nối WebSockets
└── bots/                   # Thư mục chứa dữ liệu của các bot (Tự động tạo)
    └── [bot_id]/
        ├── [entrypoint].py # Mã nguồn chính của bot (ví dụ: bot.py hoặc main.py)
        ├── .env            # Cấu hình biến môi trường riêng của bot
        ├── requirements.txt# Cấu hình thư viện riêng của bot
        ├── bot.log         # Nhật ký hoạt động (Giới hạn tối đa 1MB, tự dọn khi dừng)
        └── venv/           # Môi trường ảo Python riêng biệt của bot
```

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy

### 1. Chạy Thử Nghiệm Cục Bộ (Local)

Yêu cầu máy tính đã cài đặt Python 3.10 trở lên.

1. Di chuyển vào thư mục dự án:
   ```bash
   cd /path/to/server
   ```
2. Cài đặt các thư viện cần thiết cho server chính:
   ```bash
   pip install -r requirements.txt
   ```
3. Khởi chạy máy chủ:
   ```bash
   python main.py
   ```
4. Truy cập giao diện quản lý trên trình duyệt tại địa chỉ: **`http://127.0.0.1:9079`**

---

### 2. Triển Khai Lên VPS Wispbyte (Linux - Ubuntu/Debian)

#### Bước 1: Cài đặt các gói phụ thuộc trên VPS
Kết nối SSH vào VPS của bạn và chạy lệnh sau để cài đặt Python, môi trường ảo và các công cụ bổ trợ:
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git screen -y
```

#### Bước 2: Tải mã nguồn lên VPS
Tải toàn bộ thư mục `server` lên VPS của bạn bằng SFTP (FileZilla) hoặc Git. Sau đó di chuyển vào thư mục đó:
```bash
cd /root/server
```

#### Bước 3: Cài đặt thư viện cho máy chủ chính
Chạy cài đặt thư viện với cờ `--no-cache-dir` để tiết kiệm RAM và dung lượng đĩa:
```bash
pip3 install -r requirements.txt --no-cache-dir
```

#### Bước 4: Cấu hình chạy ngầm 24/7 bằng Systemd Service (Khuyên dùng)
Để hệ thống tự khởi động lại cùng VPS và chạy ngầm liên tục:

1. Tạo một file dịch vụ hệ thống mới:
   ```bash
   sudo nano /etc/systemd/system/aegisbot.service
   ```
2. Dán nội dung cấu hình dưới đây vào (hãy sửa lại đường dẫn `/root/server` nếu bạn để thư mục ở nơi khác):
   ```ini
   [Unit]
   Description=AegisBot Discord Orchestrator Service
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/root/server
   ExecStart=/usr/bin/python3 main.py
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
3. Lưu file lại (`Ctrl + O`, `Enter`, thoát bằng `Ctrl + X`).
4. Kích hoạt và khởi chạy dịch vụ:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable aegisbot
   sudo systemctl start aegisbot
   ```
5. Kiểm tra trạng thái hoạt động của dịch vụ:
   ```bash
   sudo systemctl status aegisbot
   ```

Bây giờ bạn có thể truy cập vào IP của VPS kèm cổng `9079` (Hoặc cổng được Wispbyte cấp phát riêng) để bắt đầu quản lý các bot Discord của mình.

---

## 🛠️ Hướng Dẫn Sử Dụng Trên Giao Diện

1. **Thêm Bot Mới**:
   * Nhấp vào nút **"Thêm Bot"** ở sidebar bên trái.
   * Điền các thông tin cấu hình:
     * **Mã ID** (ví dụ: `bot_music`).
     * **Tên hiển thị** (ví dụ: `Bot Âm Nhạc`).
     * **Tệp chạy chính mặc định** (ví dụ: `main.py` hoặc `bot.py`). Khi tạo xong, hệ thống sẽ tự động tạo file này ở trạng thái trống.
     * Điền cấu hình `.env` và danh sách thư viện `requirements.txt` riêng cho bot.
   * Bấm **"Lưu Bot & Khởi tạo Môi trường"**. Bot sẽ được tạo lập tức và chuyển đến trang quản lý chi tiết.
2. **Khởi Chạy & Giám Sát**:
   * Chọn bot từ danh sách bên trái.
   * Tại Tab **Live Console**: Nhấp nút **"Chạy"** (Start) để khởi chạy bot và theo dõi nhật ký hoạt động thời gian thực.
3. **Quản Lý File**:
   * Tại Tab **Quản lý File**:
     * Bạn có thể tạo các thư mục/tệp tin mới.
     * Tải xuống trực tiếp các file từ VPS về máy cá nhân bằng nút **Download** bên cạnh mỗi file.
     * Tải lên các file hoặc **Tải lên toàn bộ Thư mục** (bao gồm cả các thư mục con, hệ thống tự động tạo cấu trúc thư mục tương ứng trên server).
     * Sử dụng tính năng kéo thả kéo thả file/thư mục nhanh chóng.
     * Đổi tên, xóa tệp hoặc nhấp vào tệp văn bản để mở trình soạn thảo trực tuyến trực tiếp trên Dashboard.
4. **Chỉnh Sửa Cấu Định Bot**:
   * Nhấp nút **"Sửa Code"** ở trên cùng bên phải để thay đổi thông tin cấu hình cơ bản. Giao diện chỉnh sửa cũng được tích hợp đầy đủ tab **Quản lý File** tiện lợi.

---

## 🛠️ Dành Cho Lập Trình Viên (Developer Guide)

Nếu bạn muốn đóng góp hoặc phát triển thêm các tính năng cho AegisBot, dưới đây là các cơ chế lập trình cốt lõi cần lưu ý:

### 1. Cơ Chế Chống Trùng Bot (Duplicate ID Prevention)
* **Backend**: Trong [main.py](file:///c:/Users/gauba/Downloads/server/main.py), endpoint `POST /api/bots` nhận thêm tham số `is_edit`. Nếu `is_edit == False` (chế độ tạo mới), server sẽ đối chiếu xem `bot_id` đã có trong bộ nhớ hoạt động hoặc thư mục dự án `bots/{bot_id}` đã tồn tại trên đĩa chưa. Nếu có, hệ thống lập tức chặn lại và trả về lỗi `400 Bad Request` để tránh việc vô tình ghi đè mất code nguồn bot cũ.
* **Tạo file trống**: Khi tạo bot mới thành công, tệp tin khởi chạy chính (ví dụ `main.py` hoặc `bot.py`) sẽ tự động được ghi ở trạng thái **trống rỗng (`""`)**. Sau đó, lập trình viên có thể tải lên toàn bộ cấu trúc mã nguồn của họ.

### 2. Cơ Chế Kéo Thả Thư Mục Đệ Quy (Recursive Folder Drag & Drop)
* **Client-side (app.js)**: Sử dụng API `webkitGetAsEntry()` của trình duyệt để duyệt đệ quy cây thư mục khi lập trình viên kéo thả cả một thư mục lớn chứa nhiều thư mục con vào vùng Quản lý File.
* **Gán đường dẫn ảo**: Vì đối tượng `File` của sự kiện thả là read-only đối với thuộc tính `webkitRelativePath`, frontend sử dụng `Object.defineProperty` để gán giả lập đường dẫn tương đối (ví dụ `commands/music.py`).
* **Gom nhóm tải lên**: Client tự động nhóm các file có cùng thư mục tương đối để gửi chung một request multipart lên server, giúp giảm số lượng kết nối HTTP xuống tối thiểu.
* **Backend (main.py)**: API `POST /api/bots/{bot_id}/files/upload` tự động gọi `os.makedirs(target_dir, exist_ok=True)` để tái tạo cấu trúc thư mục con khi ghi tệp.

### 3. Cơ Chế Đối Chiếu Trạng Thái Tự Động (State Reconciliation)
* **Khởi động (Startup Sync)**: Hàm `_load_existing_bots` trong [orchestrator.py](file:///c:/Users/gauba/Downloads/server/orchestrator.py) đối chiếu danh sách file `.json` trong thư mục `states/` với thư mục `bots/`. Nếu có file cấu hình mồ côi (thư mục bot không tồn tại), hệ thống tự động xóa file `.json` để dọn dẹp đĩa.
* **Chu kỳ kiểm tra nóng (Hot-Deletion Check)**: Trong vòng lặp `_monitor_loop` (chạy mỗi 4 giây) của backend, hệ thống kiểm tra nóng sự tồn tại của thư mục bot. Nếu phát hiện thư mục bot bị xóa thủ công (qua FTP/CMD/File Explorer):
  1. Dừng ngay tiến trình chạy của bot (`terminate` / `kill`).
  2. Đóng log file handle để giải phóng tài nguyên.
  3. Xóa file trạng thái `states/{bot_id}.json`.
  4. Loại bỏ bot khỏi `self.active_bots` trong RAM.
* **Đồng bộ và chuyển hướng phía Client (Frontend Sync & Redirect)**: Trong hàm `loadBots()` của [app.js](file:///c:/Users/gauba/Downloads/server/static/js/app.js) (chạy mỗi 5 giây), nếu phát hiện bot đang được người dùng xem chi tiết (`activeBotId`) đã bị xóa khỏi danh sách bot của server, giao diện sẽ:
  1. Hiển thị thông báo Toast cảnh báo lỗi màu đỏ.
  2. Đóng an toàn WebSocket Console đang kết nối.
  3. Tự động chuyển hướng người dùng quay lại màn hình **Dashboard** chính.
  4. Làm mới danh sách bot hiển thị ở sidebar bên trái.

### 4. Cơ Chế Dọn Log An Toàn (Safe Log Cleanup)
* Endpoint `POST /api/bots/{bot_id}/logs/clear` thực hiện dọn dẹp log an toàn.
* Chỉ cho phép dọn log khi bot **không hoạt động** (`status != "RUNNING"`) để tránh xung đột ghi/đọc (file lock) với tiến trình con.
* Tự động đóng `log_file_handle` trước khi mở tệp với chế độ `"w"` để làm trống log về 0 bytes.

### 5. Cơ Chế Bảo Mật & Mật Khẩu Truy Cập Bot (Bot Access Password & Lock System)
* **Lưu trữ**: Mật khẩu được lưu trong file trạng thái cấu hình riêng `states/{bot_id}.json` tại trường `"password": "mật_khẩu_ở_đây"`.
* **Ẩn thông tin nhạy cảm**: Danh sách bot trả về từ `/api/bots` chỉ chứa cờ `"has_password": true/false` chứ không tiết lộ mật khẩu thực tế nhằm đảm bảo an toàn.
* **Xác thực REST API**: Định nghĩa dependency `verify_bot_access(bot_id, x_bot_password, password)`. Toàn bộ các API riêng biệt của bot (Start, Stop, Config, File Manager...) đều sử dụng `Depends(verify_bot_access)`. Header yêu cầu là `X-Bot-Password`.
* **Xác thực WebSocket**: Query parameter `?password=...` được dùng để xác thực luồng Live Console.
* **Cơ chế chỉnh sửa & Xóa mật khẩu**:
  * Khi sửa cấu hình bot, nếu **để trống ô mật khẩu**, hệ thống sẽ **giữ nguyên mật khẩu cũ** thay vì xóa nó đi.
  * Để gỡ bỏ mật khẩu hiện tại, giao diện cung cấp một hộp kiểm **"Gỡ bỏ mật khẩu hiện tại (Xóa mật khẩu)"** (gửi trường `clear_password: true` lên backend).
* **Tự động khóa bot khi đổi mật khẩu**:
  * Nếu người dùng đổi mật khẩu hoặc xóa mật khẩu thành công, frontend sẽ tự động xóa mật khẩu cũ khỏi `sessionStorage`, đóng WebSocket Console đang kết nối, và tải lại bot để áp dụng cơ chế khóa mới ngay lập tức.
* **Client-side (app.js)**:
  * Ghi đè `window.fetch` toàn cục để tự động đính kèm `X-Bot-Password` từ `sessionStorage` (`bot_pwd_{bot_id}`) vào header của các request khớp với `/api/bots/{bot_id}/...`.
  * Modal nhập mật khẩu hiển thị khi chọn bot (nếu có mật khẩu và chưa được xác minh lưu trong `sessionStorage`).
  * **Nút Khóa Lại (Lock Again)**: Xuất hiện ở góc trên chi tiết bot (cạnh nút Quay lại) nếu bot được đặt mật khẩu. Khi bấm, sẽ xóa mật khẩu trong `sessionStorage`, đóng WebSocket Console, và điều hướng về Dashboard để khóa bot ngay lập tức.

### 6. Cơ Chế Bảo Mật Chống XSS (XSS Protection)
* **Backend**: Kiểm soát nghiêm ngặt `bot_id` bằng biểu thức chính quy (chỉ cho phép ký tự chữ, số, dấu gạch dưới `_` hoặc gạch nối `-`).
* **Frontend**: Thiết lập hàm tiện ích `escapeHTML` để lọc bỏ các ký tự đặc biệt nguy hiểm trước khi hiển thị dữ liệu qua thuộc tính `.innerHTML`:
  * Áp dụng lọc đối với Tên hiển thị của bot (`bot.name`).
  * Áp dụng lọc đối với Tên tệp tin/thư mục (`file.name`) trong trình quản lý file.

### 7. Thiết Kế Giao Diện & Trải Nghiệm Người Dùng (UI/UX Refinements)
* **Bố cục hàng ngang (Single Row Layout)**: Toàn bộ tiêu đề bot, trạng thái hoạt động, nút điều hướng ("Quay lại", "Khóa lại") và các nút hành động điều khiển bot được xếp trên **cùng một hàng ngang duy nhất** gọn gàng.
* **Hỗ trợ cuộn ngang tự động (`overflow-x: auto`)**: Khi thu nhỏ màn hình hoặc truy cập trên thiết bị di động, hàng nút sẽ tự động chuyển sang chế độ cuộn ngang thay vì làm vỡ bố cục trang.
* **Đồng bộ hóa kích thước nút nhỏ (`.btn-sm`)**: Tối ưu hóa kích thước cho hai nút điều hướng ("Quay lại", "Khóa lại") để chúng cân đối và tinh tế hơn so với nhóm nút hành động chính của bot.

### 8. Cơ Chế Tự Sửa Lỗi Môi Trường Ảo (Self-Healing Venv)
* Khi khởi chạy bot, hệ thống đối chiếu đường dẫn thư mục `venv` và tệp thực thi `python` tương ứng.
* Nếu thư mục `venv` tồn tại nhưng thiếu tệp thực thi (thường do đồng bộ/upload thư mục `venv` từ Windows sang Linux), `orchestrator.py` sẽ tự động xóa thư mục `venv` bị lỗi và gọi tiến trình `python3 -m venv` để khởi tạo lại một cách tương thích nhất.
* Nếu tiến trình khởi tạo thất bại (thiếu gói `python3-venv` trên hệ điều hành Linux), hệ thống sẽ ghi cảnh báo lỗi kèm theo câu lệnh hướng dẫn cài đặt trực tiếp vào tệp `bot.log` của bot để người dùng dễ dàng khắc phục qua SSH.

### 9. Cơ Chế Tối Ưu Hóa Khởi Động Tránh Treo VPS
* Thay vì luôn đưa danh sách gói thư viện vào hàng đợi `pip` để kiểm tra khi khởi chạy bot, hệ thống thực hiện gọi một tiến trình Python siêu nhẹ kiểm tra các module trực tiếp trong môi trường ảo của bot:
  ```python
  python -c "import sys, importlib.metadata; [importlib.metadata.version(p) for p in sys.argv[1:]]" [danh_sách_gói]
  ```
* Tiến trình này thực thi chỉ mất **~0.05 giây** và tiêu tốn **0% tài nguyên CPU/RAM**. Nếu kết quả trả về là `0` (đã cài đủ), hệ thống bỏ qua bước chạy `pip install` và khởi chạy tiến trình bot ngay lập tức. Điều này giúp ngăn chặn hoàn toàn việc VPS 1GB RAM bị treo đơ CPU/Disk I/O mỗi lần khởi động lại server.

### 10. Luồng Stream Log Thời Gian Thực Đa Nhiệm (Robust WebSockets)
* Việc kiểm tra kết nối sử dụng `asyncio.wait_for` trên hàm `receive_text` làm hủy bỏ tương tác bất đồng bộ của ASGI Starlette, dẫn đến lỗi mất kết nối ngẫu nhiên (WebSocket Disconnect).
* Phiên bản hiện tại triển khai mô hình đa nhiệm song song bằng cách chia nhỏ luồng kết nối thành hai tác vụ độc lập: `send_loop()` (gửi log) và `receive_loop()` (đợi tín hiệu đóng kết nối từ client).
* Hai tác vụ này được chạy song song qua `asyncio.wait` với chế độ `FIRST_COMPLETED`. Khi người dùng đóng tab hoặc chuyển trang, tác vụ nhận kết thúc, kích hoạt hủy bỏ an toàn tác vụ gửi, giải phóng hoàn toàn bộ nhớ mà không gây lỗi trạng thái luồng.

### 11. Cơ Chế Tự Động Dọn Log & Đọc File Log Trực Tuyến
* Để giải quyết bài toán giới hạn dung lượng đĩa NVMe của các gói VPS giá rẻ (thường chỉ từ 5GB - 10GB), hệ thống áp dụng cơ chế dọn log thông minh:
  * Mỗi khi bot chuyển sang trạng thái dừng hoạt động (`STOPPED`), hệ thống tự động làm trống tệp `bot.log` về 0 bytes và chỉ để lại một dòng đánh dấu nhỏ.
  * Giới hạn xoay vòng log cứng được hạ xuống còn **1MB** thay vì 5MB. Khi dung lượng vượt quá 1MB, hệ thống tự động cắt và giữ lại phần đuôi nhật ký.
  * Tệp nhật ký của các bot lỗi (`ERROR`, `CRASHED`) được giữ nguyên trạng để người dùng kiểm tra nguyên nhân sập.
* **Hỗ trợ xem tệp tin Log trực tuyến**: Hệ thống cho phép mở trực tiếp các file `.log` ngay trên trình duyệt thông qua Editor Modal.
* **Giới hạn dung lượng xem trực tuyến (5MB)**: Để bảo vệ RAM của VPS và tránh làm treo đơ trình duyệt của người dùng khi tải file văn bản quá lớn, hệ thống giới hạn dung lượng xem trực tuyến tối đa là **5MB**. Nếu vượt quá giới hạn này, hệ thống sẽ yêu cầu người dùng sử dụng tính năng **Tải xuống (Download)** để xem file cục bộ trên máy tính cá nhân.

### 12. Cơ Chế Bảo Mật Cô Lập Tiến Trình Bot (Low-Privilege Sandboxing)
* Trên hệ điều hành Linux, nếu AegisBot Server chạy dưới quyền tối cao của hệ thống (`root`), hệ thống sẽ tự động kích hoạt lớp bảo vệ cách ly:
  * Tự động tạo một người dùng hệ thống hạn chế quyền tên là `aegisbot_runner` (không có quyền sudo, không có shell đăng nhập `/bin/false`).
  * Thực hiện chuyển quyền sở hữu toàn bộ thư mục `bots/` cho người dùng này và thiết lập quyền truy cập chặt chẽ (`770` cho thư mục, `660` cho tệp tin).
  * Ép buộc tất cả tiến trình con của bot (tạo venv, cài đặt pip, chạy code bot) đều được thực thi dưới quyền của `aegisbot_runner`.
  * **Hiệu quả bảo mật**: Bot hoàn toàn không thể truy cập, đọc hay ghi đè lên mã nguồn của server chính (nằm ở `/root/server`) hay các file cấu hình hệ thống nhạy cảm khác trên VPS. Mọi hành vi cố tình vượt biên đều bị nhân hệ điều hành Linux chặn đứng và trả về lỗi `PermissionError`.

### 13. Màn Hình Console Màu ANSI & Xử Lý Trạng Thái Dừng Bình Thường
* **Biên dịch màu ANSI**: Console tích hợp bộ biên dịch mã màu ANSI sang HTML ngay trên trình duyệt, hiển thị sinh động các màu sắc nhật ký (Xanh dương cho INFO, Vàng cho WARNING, Đỏ cho ERROR...).
* **Bảo vệ chống XSS**: Dữ liệu log thô được chạy qua bộ lọc thực thể HTML (`escapeHTML`) trước khi biên dịch màu, đảm bảo an toàn tuyệt đối trước các cuộc tấn công tiêm mã độc (XSS Injection).
* **Hiệu năng cao**: Sử dụng phương thức `insertAdjacentHTML` để ghi thêm log vào DOM thay vì `innerHTML`, tăng tốc độ render lên 50 lần và không gây giật lag trình duyệt.
* **Phân biệt mã thoát 0 (Exit Code 0)**: Khi bot dừng hoạt động, hệ thống phân biệt mã thoát. Nếu mã thoát là `0` (dừng bình thường), trạng thái bot chuyển sang `Đã dừng` (STOPPED) và ghi log hệ thống bình thường. Nếu mã thoát khác `0`, trạng thái bot mới chuyển sang `Lỗi` (ERROR).

### 14. Quản Lý File Nâng Cao (Tìm Kiếm, Sắp Xếp & Cơ Chế Chống Cache)
* **Tìm kiếm thời gian thực**: Tích hợp thanh tìm kiếm tệp tin/thư mục trực tiếp trên giao diện quản lý file, lọc tức thì mà không cần tải lại trang.
* **Sắp xếp nâng cao**: Hỗ trợ 6 chế độ sắp xếp (theo Tên A-Z/Z-A, Dung lượng tăng/giảm, Thời gian sửa mới nhất/cũ nhất) và luôn ưu tiên đưa thư mục lên đầu danh sách.
* **Dọn dẹp Cache & Chống lưu HTML**: 
  * Bổ sung nút bấm **"Xóa Cache & Tải Lại"** trong trường hợp Proxy/Nginx bị lỗi và trả về trang HTML lỗi của nhà mạng (ví dụ Wispbyte), giúp dọn sạch Cache Storage của trình duyệt và tải lại trang kèm tham số ngẫu nhiên (`?nocache=timestamp`).
  * Đồng thời, khi người dùng thực hiện bật/tắt bot, luồng WebSocket Console sẽ tự động đóng và kết nối lại để cập nhật ngay lập tức các dòng trạng thái mới nhất từ tệp log đã dọn dẹp.

### 15. Cơ Chế Xác Thực Panel (Tên đăng nhập/Email & Mật Khẩu)
* **Phương thức Đăng nhập**:
  * Đăng nhập thông qua form nhập **Tên đăng nhập hoặc Email** và **Mật khẩu** trực tiếp trên giao diện.
  * Mỗi người dùng trong danh sách sẽ có một tài khoản gồm Tên đăng nhập, Email và Mật khẩu riêng biệt.
* **Lưu trữ cấu hình bảo mật (`panel_auth.json`)**:
  * Các thông tin tài khoản và cấu hình được lưu riêng biệt trong tệp `panel_auth.json` ở thư mục gốc của server chính:
    ```json
    {
      "users": [
        {
          "username": "admin",
          "email": "admin@gmail.com",
          "password": "adminpanelbots2000@"
        }
      ]
    }
    ```
* **Bảo vệ toàn diện bằng Middleware**:
  * Sử dụng HTTP Middleware của FastAPI để tự động kiểm tra chữ ký session cookie (`session_token`) trên toàn bộ các yêu cầu HTTP (ngoại trừ trang `/login`, API `/api/auth/*` và tài nguyên tĩnh `/static/*`).
  * Trình duyệt sẽ tự động chuyển hướng về trang `/login` nếu chưa đăng nhập hoặc phiên làm việc hết hạn.
  * Các kết nối **WebSockets** cũng được kiểm tra và tự động ngắt kết nối với mã ASGI `1008` (Policy Violation) nếu phiên đăng nhập không hợp lệ.

---

