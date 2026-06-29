// AegisBot Orchestrator - Frontend Controller

// --- GLOBAL FETCH OVERRIDE FOR PASSWORD AUTH ---
const originalFetch = window.fetch;
window.fetch = async function (url, options = {}) {
    if (!options.headers) {
        options.headers = {};
    }

    let botId = null;
    if (typeof url === 'string') {
        const match = url.match(/\/api\/bots\/([^/]+)/);
        if (match) {
            botId = match[1];
        }
    }

    if (botId) {
        const pwd = sessionStorage.getItem('bot_pwd_' + botId);
        if (pwd) {
            if (options.headers instanceof Headers) {
                options.headers.set('X-Bot-Password', pwd);
            } else {
                options.headers['X-Bot-Password'] = pwd;
            }
        }
    }

    return originalFetch(url, options);
};

// --- HTML ESCAPE FOR XSS PROTECTION ---
function escapeHTML(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// --- ANSI ESCAPE CODES TO HTML CONVERTER ---
function ansiToHTML(text) {
    // Tránh tấn công XSS bằng cách escape HTML trước khi chèn thẻ span
    let escaped = escapeHTML(text);

    // Bản đồ ánh xạ mã ANSI sang màu sắc CSS
    const ansiMap = {
        // Màu thường (30-37)
        '30': 'color: #4b5563; font-weight: 500;', // Gray
        '31': 'color: var(--color-danger); font-weight: 600;', // Red
        '32': 'color: #10b981; font-weight: 500;', // Green
        '33': 'color: var(--color-warning); font-weight: 600;', // Yellow
        '34': 'color: #3b82f6; font-weight: 600;', // Blue
        '35': 'color: #d946ef; font-weight: 500;', // Magenta
        '36': 'color: #06b6d4; font-weight: 500;', // Cyan
        '37': 'color: #f3f4f6;', // White

        // Màu sáng (90-97)
        '90': 'color: #9ca3af;', // Bright gray
        '91': 'color: #f87171; font-weight: 600;', // Bright red
        '92': 'color: #34d399; font-weight: 500;', // Bright green
        '93': 'color: #fbbf24; font-weight: 600;', // Bright yellow
        '94': 'color: #60a5fa; font-weight: 600;', // Bright blue
        '95': 'color: #f472b6; font-weight: 500;', // Bright magenta
        '96': 'color: #22d3ee; font-weight: 500;', // Bright cyan
        '97': 'color: #ffffff; font-weight: 600;', // Bright white

        // Định dạng
        '1': 'font-weight: bold;',
        '3': 'font-style: italic;',
        '4': 'text-decoration: underline;'
    };

    let openSpans = 0;
    const ansiRegex = /\u001b\[([0-9;]*)m/g;

    let result = escaped.replace(ansiRegex, (match, codesStr) => {
        const codes = codesStr.split(';');

        // Lệnh reset (0) hoặc rỗng: đóng toàn bộ các thẻ span đang mở
        if (codes.includes('0') || codesStr === '') {
            let closeTags = '';
            while (openSpans > 0) {
                closeTags += '</span>';
                openSpans--;
            }
            return closeTags;
        }

        // Xây dựng style từ danh sách mã
        let style = '';
        codes.forEach(code => {
            if (ansiMap[code]) {
                style += ansiMap[code] + ' ';
            }
        });

        if (style) {
            openSpans++;
            return `<span style="${style}">`;
        }

        return '';
    });

    // Đóng toàn bộ các thẻ span còn sót lại ở cuối chuỗi
    while (openSpans > 0) {
        result += '</span>';
        openSpans--;
    }

    return result;
}

// --- STATE VARIABLES ---
let bots = [];
let activeBotId = null;
let pendingBotId = null;
let consoleWS = null;
let statsWS = null;
let autoscroll = true;
let isEditMode = false;

// --- DOM ELEMENTS ---
const elBotList = document.getElementById('bot-list');
const elViewDashboard = document.getElementById('view-dashboard');
const elViewBotDetail = document.getElementById('view-bot-detail');
const elViewBotForm = document.getElementById('view-bot-form');

// Detail view elements
const elDetailBotName = document.getElementById('detail-bot-name');
const elDetailBotStatus = document.getElementById('detail-bot-status');
const elConsoleOutput = document.getElementById('console-output');
const elBtnStart = document.getElementById('btn-start');
const elBtnStop = document.getElementById('btn-stop');
const elBtnRestart = document.getElementById('btn-restart');
const elBtnEdit = document.getElementById('btn-edit');
const elBtnDelete = document.getElementById('btn-delete');
const elBtnLockBot = document.getElementById('btn-lock-bot');
const elBtnClearConsole = document.getElementById('btn-clear-console');
const elBtnClearServerLog = document.getElementById('btn-clear-server-log');
const elBtnAutoscroll = document.getElementById('btn-autoscroll');

// Form elements
const elForm = document.getElementById('bot-config-form');
const elFormTitle = document.getElementById('form-title');
const elInputId = document.getElementById('bot-id');
const elInputName = document.getElementById('bot-name');
const elInputEntrypoint = document.getElementById('bot-entrypoint');
const elInputEnv = document.getElementById('bot-env');
const elInputUseEnv = document.getElementById('bot-use-env');
const elInputRequirements = document.getElementById('bot-requirements');
const elInputPassword = document.getElementById('bot-password');
const elDeletePasswordContainer = document.getElementById('delete-password-container');
const elInputClearPassword = document.getElementById('bot-clear-password');
const elBtnFormCancel = document.getElementById('btn-form-cancel');
const elBtnCancelFormTop = document.getElementById('btn-cancel-form');

// Password Verification Modal
const elPasswordModal = document.getElementById('password-modal');
const elConfirmBotPassword = document.getElementById('confirm-bot-password');
const elBtnPasswordCancel = document.getElementById('btn-password-cancel');
const elBtnPasswordSubmit = document.getElementById('btn-password-submit');

// Tabs
const elTabBtns = document.querySelectorAll('.tab-btn');
const elTabContents = document.querySelectorAll('.tab-content');

// File Manager
const elFileManagerWrapper = document.querySelector('.file-manager-wrapper');
const elFileBreadcrumbs = document.getElementById('file-breadcrumbs');
const elFileListBody = document.getElementById('file-list-body');
const elBtnFileNewFile = document.getElementById('btn-file-new-file');
const elBtnFileNewDir = document.getElementById('btn-file-new-dir');
const elBtnFileUploadTrigger = document.getElementById('btn-file-upload-trigger');
const elFileUploadInput = document.getElementById('file-upload-input');
const elBtnFileUploadDirTrigger = document.getElementById('btn-file-upload-dir-trigger');
const elFileUploadDirInput = document.getElementById('file-upload-dir-input');
const elBtnFileRefresh = document.getElementById('btn-file-refresh');

// Bulk Actions
const elChkSelectAll = document.getElementById('chk-select-all');
const elFileBulkActions = document.getElementById('file-bulk-actions');
const elBulkSelectCount = document.getElementById('bulk-select-count');
const elBtnBulkDelete = document.getElementById('btn-bulk-delete');
const elBtnBulkDownload = document.getElementById('btn-bulk-download');
const elBtnBulkMove = document.getElementById('btn-bulk-move');
const elBtnBulkDuplicate = document.getElementById('btn-bulk-duplicate');

// Move File(s) Modal Elements
const elMoveModal = document.getElementById('move-modal');
const elBtnCloseMoveModal = document.getElementById('btn-close-move-modal');
const elBtnMoveUp = document.getElementById('btn-move-up');
const elMoveBreadcrumbs = document.getElementById('move-breadcrumbs');
const elMoveDirList = document.getElementById('move-dir-list');
const elMoveTargetPathDisplay = document.getElementById('move-target-path-display');
const elMovePreviewList = document.getElementById('move-preview-list');
const elBtnMoveCancel = document.getElementById('btn-move-cancel');
const elBtnMoveSubmit = document.getElementById('btn-move-submit');

// File Editor Modal
const elFileEditorModal = document.getElementById('file-editor-modal');
const elFileEditorTitle = document.getElementById('file-editor-title');
const elFileEditorTextarea = document.getElementById('file-editor-textarea');
const elFileEditorStatus = document.getElementById('file-editor-status');
const elBtnCloseEditor = document.getElementById('btn-close-editor');
const elBtnFileEditorCancel = document.getElementById('btn-file-editor-cancel');
const elBtnFileEditorSave = document.getElementById('btn-file-editor-save');

// State cho File Manager
let currentFilePath = "";
let editingFilePath = "";
let currentFilesList = []; // Danh sách file gốc tải từ API

let moveModalCurrentPath = "";
let itemsToMove = []; // Mảng chứa các mục cần di chuyển: [{ path: "...", name: "...", isDir: true/false }]

const elFileSearch = document.getElementById('file-search');
const elFileSortMode = document.getElementById('file-sort-mode');

// System stats widgets
const elCpuWidget = document.getElementById('cpu-widget');
const elRamWidget = document.getElementById('ram-widget');
const elDiskWidget = document.getElementById('disk-widget');

// Toast Notification
const elToast = document.getElementById('toast');
const elToastMessage = document.getElementById('toast-message');

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function initApp() {
    // Event Listeners
    document.getElementById('btn-add-bot-trigger').addEventListener('click', () => showCreateForm());
    elBtnFormCancel.addEventListener('click', () => handleFormCancel());
    elBtnCancelFormTop.addEventListener('click', () => handleFormCancel());
    elForm.addEventListener('submit', handleFormSubmit);

    // Bot control buttons
    elBtnStart.addEventListener('click', () => controlBot('start'));
    elBtnStop.addEventListener('click', () => controlBot('stop'));
    elBtnRestart.addEventListener('click', () => controlBot('restart'));
    elBtnEdit.addEventListener('click', () => loadBotIntoForm(activeBotId));
    elBtnDelete.addEventListener('click', () => deleteBot(activeBotId));
    document.getElementById('btn-back-to-dashboard').addEventListener('click', () => showView('dashboard'));

    if (elBtnLockBot) {
        elBtnLockBot.addEventListener('click', () => {
            if (activeBotId) {
                sessionStorage.removeItem('bot_pwd_' + activeBotId);
                showToast('Đã khóa truy cập bot thành công.', 'success');
                activeBotId = null;
                if (consoleWS) {
                    try { consoleWS.close(); } catch (e) { }
                    consoleWS = null;
                }
                showView('dashboard');
                loadBots();
            }
        });
    }

    // Console actions
    elBtnClearConsole.addEventListener('click', () => {
        elConsoleOutput.textContent = '';
    });
    elBtnClearServerLog.addEventListener('click', () => clearServerLog());
    elBtnAutoscroll.addEventListener('click', () => {
        autoscroll = !autoscroll;
        elBtnAutoscroll.classList.toggle('active', autoscroll);
    });

    elInputUseEnv.addEventListener('change', () => {
        elInputEnv.disabled = !elInputUseEnv.checked;
    });

    // Tab switching (Detail View)
    elTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            elTabBtns.forEach(b => b.classList.remove('active'));
            elTabContents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const tabId = `tab-${btn.dataset.tab}`;
            document.getElementById(tabId).classList.add('active');
            if (btn.dataset.tab === 'files') {
                loadBotFiles();
            }
        });
    });

    // File Manager Events
    elBtnFileNewFile.addEventListener('click', () => createNewItem(false));
    elBtnFileNewDir.addEventListener('click', () => createNewItem(true));
    elBtnFileUploadTrigger.addEventListener('click', () => elFileUploadInput.click());
    elFileUploadInput.addEventListener('change', handleFileUpload);
    elBtnFileUploadDirTrigger.addEventListener('click', () => elFileUploadDirInput.click());
    elFileUploadDirInput.addEventListener('change', handleFileUploadDir);
    elBtnFileRefresh.addEventListener('click', () => {
        if (elFileSearch) elFileSearch.value = ''; // Xóa ô tìm kiếm khi làm mới
        loadBotFiles();
    });

    if (elFileSearch) {
        elFileSearch.addEventListener('input', filterAndRenderFiles);
    }
    if (elFileSortMode) {
        elFileSortMode.addEventListener('change', filterAndRenderFiles);
    }

    // Sự kiện hành động hàng loạt (Bulk Actions)
    if (elChkSelectAll) {
        elChkSelectAll.addEventListener('change', () => {
            const checkboxes = document.querySelectorAll('.chk-file-select');
            checkboxes.forEach(chk => {
                chk.checked = elChkSelectAll.checked;
            });
            updateBulkActions();
        });
    }
    if (elBtnBulkDelete) elBtnBulkDelete.addEventListener('click', handleBulkDelete);
    if (elBtnBulkDownload) elBtnBulkDownload.addEventListener('click', handleBulkDownload);
    if (elBtnBulkMove) elBtnBulkMove.addEventListener('click', handleBulkMove);
    if (elBtnBulkDuplicate) elBtnBulkDuplicate.addEventListener('click', handleBulkDuplicate);

    // Sự kiện Modal di chuyển (Move File(s))
    if (elBtnCloseMoveModal) elBtnCloseMoveModal.addEventListener('click', closeMoveModal);
    if (elBtnMoveCancel) elBtnMoveCancel.addEventListener('click', closeMoveModal);
    if (elBtnMoveUp) elBtnMoveUp.addEventListener('click', handleMoveModalUp);
    if (elBtnMoveSubmit) elBtnMoveSubmit.addEventListener('click', submitMoveModal);

    // Password Modal Events
    if (elBtnPasswordCancel) elBtnPasswordCancel.addEventListener('click', closePasswordModal);
    if (elBtnPasswordSubmit) elBtnPasswordSubmit.addEventListener('click', submitConfirmPassword);
    if (elConfirmBotPassword) {
        elConfirmBotPassword.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') submitConfirmPassword();
        });
    }

    // Drag & Drop for File Manager
    if (elFileManagerWrapper) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            elFileManagerWrapper.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            elFileManagerWrapper.addEventListener(eventName, () => {
                elFileManagerWrapper.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            elFileManagerWrapper.addEventListener(eventName, () => {
                elFileManagerWrapper.classList.remove('dragover');
            }, false);
        });

        elFileManagerWrapper.addEventListener('drop', async e => {
            const dt = e.dataTransfer;

            // Hỗ trợ kéo thả cả thư mục (duyệt cây đệ quy)
            if (dt.items && dt.items.length > 0) {
                const files = [];
                const promises = [];

                for (let i = 0; i < dt.items.length; i++) {
                    const item = dt.items[i];
                    if (item.kind === 'file') {
                        const entry = item.webkitGetAsEntry();
                        if (entry) {
                            promises.push(traverseFileTree(entry, "", files));
                        }
                    }
                }

                await Promise.all(promises);
                if (files.length > 0) {
                    uploadFileList(files);
                }
            } else {
                // Fallback nếu không hỗ trợ DataTransferItem
                const files = dt.files;
                if (files && files.length > 0) {
                    uploadFileList(files);
                }
            }
        }, false);
    }

    // Editor Modal Events
    elBtnCloseEditor.addEventListener('click', closeEditor);
    elBtnFileEditorCancel.addEventListener('click', closeEditor);
    elBtnFileEditorSave.addEventListener('click', saveEditedFile);

    // Sự kiện tìm kiếm bot
    const elBotSearch = document.getElementById('bot-search');
    if (elBotSearch) {
        elBotSearch.addEventListener('input', () => {
            renderBotList();
        });
    }

    // Khởi động
    loadBots();
    connectStatsWS();

    // Tự động làm mới danh sách bot sau mỗi 5 giây để cập nhật trạng thái
    setInterval(loadBots, 5000);
}

// --- NAVIGATION ---
function showView(viewName) {
    // Ẩn tất cả các view
    elViewDashboard.classList.remove('active');
    elViewBotDetail.classList.remove('active');
    elViewBotForm.classList.remove('active');

    // Ngắt kết nối Console WS nếu rời khỏi trang chi tiết bot
    if (viewName !== 'bot-detail' && consoleWS) {
        consoleWS.close();
        consoleWS = null;
    }

    // Hiển thị view mong muốn
    if (viewName === 'dashboard') {
        elViewDashboard.classList.add('active');
        activeBotId = null;
        // Bỏ active của các item trong sidebar
        document.querySelectorAll('.bot-item').forEach(item => item.classList.remove('active'));
    } else if (viewName === 'bot-detail') {
        elViewBotDetail.classList.add('active');
    } else if (viewName === 'bot-form') {
        elViewBotForm.classList.add('active');
    }
}

// --- SYSTEM STATS (WEBSOCKET) ---
function connectStatsWS() {
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/system/stats/ws`;

        statsWS = new WebSocket(wsUrl);

        statsWS.onmessage = (event) => {
            const stats = JSON.parse(event.data);
            updateStatsUI(stats);
        };

        statsWS.onclose = () => {
            // Tự động kết nối lại sau 5 giây nếu mất kết nối
            setTimeout(connectStatsWS, 5000);
        };
    } catch (error) {
        console.error("Lỗi khởi tạo WebSocket Stats:", error);
    }
}

function updateStatsUI(stats) {
    // CPU
    const cpuBar = elCpuWidget.querySelector('.progress-bar');
    const cpuVal = elCpuWidget.querySelector('.stat-value');
    cpuBar.style.width = `${stats.cpu}%`;
    cpuVal.textContent = `${stats.cpu}%`;

    // RAM
    const ramBar = elRamWidget.querySelector('.progress-bar');
    const ramVal = elRamWidget.querySelector('.stat-value');
    ramBar.style.width = `${stats.ram.percent}%`;
    ramVal.textContent = `${stats.ram.used} / ${stats.ram.total} GB (${stats.ram.percent}%)`;

    // Đổi màu thanh RAM nếu quá cao (trên VPS 1GB)
    if (stats.ram.percent > 85) {
        ramBar.style.background = 'var(--color-danger)';
    } else if (stats.ram.percent > 70) {
        ramBar.style.background = 'var(--color-warning)';
    } else {
        ramBar.style.background = 'var(--gradient-primary)';
    }

    // Disk
    const diskBar = elDiskWidget.querySelector('.progress-bar');
    const diskVal = elDiskWidget.querySelector('.stat-value');
    diskBar.style.width = `${stats.disk.percent}%`;
    diskVal.textContent = `${stats.disk.used} / ${stats.disk.total} GB (${stats.disk.percent}%)`;
}

let initialLoadTimeout = null;

async function loadBots() {
    try {
        const response = await fetch(`/api/bots?t=${Date.now()}`);
        if (!response.ok) throw new Error(`Mã lỗi HTTP: ${response.status}`);

        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("text/html")) {
            // Tự động dọn dẹp Cache Storage trong nền
            if ('caches' in window) {
                caches.keys().then(names => {
                    for (let name of names) {
                        caches.delete(name);
                    }
                }).catch(() => { });
            }
            throw new Error("Backend trả về trang HTML (Lỗi cấu hình Nginx/Proxy hoặc chưa chạy Backend).");
        }

        bots = await response.json();
        renderBotList();

        // Cập nhật trạng thái hiển thị của bot hiện tại nếu đang ở trang chi tiết
        if (activeBotId) {
            const currentBot = bots.find(b => b.id === activeBotId);
            if (currentBot) {
                updateBotDetailUI(currentBot);
            } else {
                // Bot hiện tại đã bị xóa nóng ngoài hệ thống
                showToast('Cảnh báo: Bot hiện tại đã bị xóa khỏi hệ thống trên VPS!', 'danger');
                activeBotId = null;
                if (consoleWS) {
                    try { consoleWS.close(); } catch (e) { }
                    consoleWS = null;
                }
                showView('dashboard');
            }
        }
    } catch (error) {
        console.error("Lỗi tải danh sách bot:", error);

        // Hiển thị thông báo lỗi trực tiếp lên danh sách bot để người dùng biết
        elBotList.innerHTML = `
            <div class="loading-placeholder" style="color: var(--color-danger); flex-direction: column; text-align: center; gap: 0.5rem; padding: 1.2rem 1rem; width: 100%;">
                <i class="fa-solid fa-circle-exclamation" style="font-size: 1.5rem;"></i>
                <span style="font-weight: 600; font-size: 0.9rem;">Lỗi tải danh sách Bot</span>
                <span style="font-size: 0.75rem; color: var(--color-text-muted); max-width: 260px; line-height: 1.4; word-break: break-word; margin-bottom: 0.3rem;">
                    ${escapeHTML(error.message)}
                </span>
                <button class="btn btn-secondary btn-sm" id="btn-clear-cache-reload" style="font-size: 0.75rem; padding: 0.35rem 0.7rem; display: inline-flex; align-items: center; gap: 0.3rem;">
                    <i class="fa-solid fa-rotate"></i> Xóa Cache & Tải Lại
                </button>
            </div>
        `;

        // Gắn sự kiện cho nút xóa cache và tải lại
        const btnReload = document.getElementById('btn-clear-cache-reload');
        if (btnReload) {
            btnReload.addEventListener('click', () => {
                if ('caches' in window) {
                    caches.keys().then(names => {
                        for (let name of names) {
                            caches.delete(name);
                        }
                    }).catch(() => { });
                }
                // Tải lại trang kèm tham số chống cache tĩnh
                const url = new URL(window.location.href);
                url.searchParams.set('nocache', Date.now());
                window.location.href = url.toString();
            });
        }

        // Nếu mất kết nối, âm thầm thử lại sau 3 giây
        if (initialLoadTimeout) clearTimeout(initialLoadTimeout);
        initialLoadTimeout = setTimeout(loadBots, 3000);
    }
}

function renderBotList() {
    const elBotSearch = document.getElementById('bot-search');
    const query = elBotSearch ? elBotSearch.value.trim().toLowerCase() : '';

    // Lọc danh sách bot theo tên hoặc ID
    const filteredBots = bots.filter(bot =>
        bot.name.toLowerCase().includes(query) ||
        bot.id.toLowerCase().includes(query)
    );

    if (bots.length === 0) {
        elBotList.innerHTML = `
            <div class="loading-placeholder">
                <i class="fa-solid fa-folder-open"></i> Chưa có bot nào được tạo.
            </div>
        `;
        return;
    }

    if (filteredBots.length === 0) {
        elBotList.innerHTML = `
            <div class="loading-placeholder">
                <i class="fa-solid fa-magnifying-glass"></i> Không tìm thấy bot phù hợp.
            </div>
        `;
        return;
    }

    elBotList.innerHTML = '';
    filteredBots.forEach(bot => {
        const item = document.createElement('div');
        item.className = `bot-item ${bot.id === activeBotId ? 'active' : ''}`;
        item.dataset.id = bot.id;

        item.innerHTML = `
            <div class="bot-item-info">
                <span class="bot-item-name">${escapeHTML(bot.name)}</span>
                <span class="bot-item-id">${escapeHTML(bot.id)}</span>
            </div>
            <div class="status-indicator status-${escapeHTML(bot.status)}" title="${escapeHTML(bot.status)}"></div>
        `;

        item.addEventListener('click', () => selectBot(bot.id));
        elBotList.appendChild(item);
    });
}

function selectBot(botId) {
    const bot = bots.find(b => b.id === botId);
    if (!bot) return;

    // Kiểm tra mật khẩu truy cập
    if (bot.has_password) {
        const pwd = sessionStorage.getItem('bot_pwd_' + botId);
        if (!pwd) {
            pendingBotId = botId;
            elConfirmBotPassword.value = '';
            elPasswordModal.classList.add('active');
            setTimeout(() => elConfirmBotPassword.focus(), 100);
            return;
        }
    }

    activeBotId = botId;

    // Highlight sidebar item
    document.querySelectorAll('.bot-item').forEach(item => {
        item.classList.toggle('active', item.dataset.id === botId);
    });

    // Reset tab về console
    elTabBtns.forEach(b => b.classList.remove('active'));
    elTabContents.forEach(c => c.classList.remove('active'));
    document.querySelector('[data-tab="console"]').classList.add('active');
    document.getElementById('tab-console').classList.add('active');
    currentFilePath = "";

    if (bot) {
        showView('bot-detail');
        updateBotDetailUI(bot);
        connectConsoleWS(botId);
    }
}

function updateBotDetailUI(bot) {
    elDetailBotName.textContent = bot.name;

    // Trạng thái hiển thị
    elDetailBotStatus.className = `status-badge ${bot.status}`;
    let statusText = bot.status;
    if (bot.status === 'RUNNING') statusText = 'Đang chạy';
    else if (bot.status === 'STOPPED') statusText = 'Đã dừng';
    else if (bot.status === 'INSTALLING') statusText = 'Đang cài thư viện';
    else if (bot.status === 'STARTING') statusText = 'Đang khởi chạy';
    else if (bot.status === 'ERROR') statusText = 'Lỗi';
    else if (bot.status === 'CRASHED') statusText = 'Bị sập';

    elDetailBotStatus.textContent = statusText;

    // Hiện nút Khóa lại nếu bot có mật khẩu
    if (elBtnLockBot) {
        elBtnLockBot.style.display = bot.has_password ? 'inline-flex' : 'none';
    }

    // Bật/Tắt các nút điều khiển phù hợp với trạng thái
    if (bot.status === 'RUNNING') {
        elBtnStart.disabled = true;
        elBtnStop.disabled = false;
        elBtnRestart.disabled = false;
    } else if (bot.status === 'STOPPED' || bot.status === 'ERROR' || bot.status === 'CRASHED') {
        elBtnStart.disabled = false;
        elBtnStop.disabled = true;
        elBtnRestart.disabled = true;
    } else { // STARTING, INSTALLING
        elBtnStart.disabled = true;
        elBtnStop.disabled = false;  // Cho phép dừng khi đang cài
        elBtnRestart.disabled = true;
    }
}

// --- CONSOLE REAL-TIME (WEBSOCKET) ---
function connectConsoleWS(botId) {
    if (consoleWS) {
        consoleWS.close();
    }

    elConsoleOutput.textContent = '[Hệ thống] Đang kết nối luồng Log...\n';

    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const pwd = sessionStorage.getItem('bot_pwd_' + botId) || '';
        const wsUrl = `${protocol}//${window.location.host}/api/bots/${botId}/console/ws?password=${encodeURIComponent(pwd)}`;

        consoleWS = new WebSocket(wsUrl);

        consoleWS.onmessage = (event) => {
            // Chuyển đổi mã ANSI sang HTML có màu sắc
            const htmlLog = ansiToHTML(event.data);
            // Sử dụng insertAdjacentHTML để append HTML cực nhanh, không gây giật lag
            elConsoleOutput.insertAdjacentHTML('beforeend', htmlLog);

            // Tự động cuộn xuống cuối nếu bật autoscroll
            if (autoscroll) {
                elConsoleOutput.scrollTop = elConsoleOutput.scrollHeight;
            }
        };

        consoleWS.onerror = (err) => {
            elConsoleOutput.textContent += '\n[Hệ thống Lỗi] Lỗi kết nối WebSocket Console.\n';
        };

        consoleWS.onclose = () => {
            elConsoleOutput.textContent += '\n[Hệ thống] Luồng Log đã đóng.\n';
        };
    } catch (error) {
        elConsoleOutput.textContent += `\n[Hệ thống Lỗi] Không thể khởi tạo kết nối WebSocket Console: ${error.message}\n`;
    }
}

// --- BOT ACTIONS ---
async function controlBot(action) {
    if (!activeBotId) return;

    try {
        const response = await fetch(`/api/bots/${activeBotId}/${action}`, {
            method: 'POST'
        });
        const data = await response.json();

        if (response.ok) {
            showToast(data.message, 'success');
            await loadBots();
            // Khởi tạo lại kết nối WebSocket để cập nhật luồng log mới nhất
            connectConsoleWS(activeBotId);
        } else {
            showToast(data.detail || 'Thao tác thất bại.', 'danger');
        }
    } catch (error) {
        showToast('Lỗi kết nối máy chủ!', 'danger');
    }
}

async function clearServerLog() {
    if (!activeBotId) return;
    if (!confirm('Bạn có chắc chắn muốn dọn sạch toàn bộ tệp tin Log của Bot này trên Server?')) {
        return;
    }

    try {
        const response = await fetch(`/api/bots/${activeBotId}/logs/clear`, {
            method: 'POST'
        });
        const data = await response.json();

        if (response.ok) {
            elConsoleOutput.textContent = '[Hệ thống] Đã dọn sạch tệp tin log của Bot trên Server.\n';
            showToast(data.message, 'success');
        } else {
            showToast(data.detail || 'Không thể dọn log.', 'danger');
        }
    } catch (error) {
        showToast('Lỗi kết nối máy chủ!', 'danger');
    }
}

async function deleteBot(botId) {
    if (!confirm(`Bạn có chắc chắn muốn XÓA HOÀN TOÀN bot "${botId}"? Tất cả code nguồn, file .env và venv sẽ bị xóa vĩnh viễn.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/bots/${botId}`, {
            method: 'DELETE'
        });
        const data = await response.json();

        if (response.ok) {
            showToast('Đã xóa bot thành công.', 'success');
            showView('dashboard');
            loadBots();
        } else {
            showToast(data.detail || 'Xóa bot thất bại.', 'danger');
        }
    } catch (error) {
        showToast('Lỗi kết nối máy chủ!', 'danger');
    }
}

// --- FORM CREATE / EDIT ---
function showCreateForm() {
    isEditMode = false;
    elFormTitle.textContent = 'Thêm Bot Mới';
    elInputId.value = '';
    elInputId.disabled = false;
    elInputName.value = '';
    elInputEntrypoint.value = 'bot.py';
    elInputUseEnv.checked = true;
    elInputEnv.disabled = false;
    elInputEnv.value = 'DISCORD_TOKEN=your_token_here\nPREFIX=! \n';
    elInputRequirements.value = 'discord.py\npython-dotenv\n';
    elInputPassword.value = '';
    elInputPassword.placeholder = 'Để trống nếu không muốn đặt mật khẩu';
    if (elDeletePasswordContainer) elDeletePasswordContainer.style.display = 'none';
    if (elInputClearPassword) elInputClearPassword.checked = false;

    showView('bot-form');
}

function handleFormCancel() {
    if (isEditMode && activeBotId) {
        selectBot(activeBotId);
    } else {
        showView('dashboard');
    }
}

async function loadBotIntoForm(botId) {
    try {
        const response = await fetch(`/api/bots/${botId}/config`);
        if (!response.ok) throw new Error('Không thể lấy cấu hình bot.');

        const data = await response.json();

        isEditMode = true;
        elFormTitle.textContent = `Chỉnh Sửa Bot: ${data.name}`;
        elInputId.value = data.id;
        elInputId.disabled = true; // Không cho sửa ID vì nó tương ứng với tên thư mục
        elInputName.value = data.name;
        elInputEntrypoint.value = data.entrypoint || 'bot.py';
        elInputUseEnv.checked = data.use_env !== false; // mặc định là true
        elInputEnv.disabled = !elInputUseEnv.checked;
        elInputEnv.value = data.env;
        elInputRequirements.value = data.requirements || '';
        elInputPassword.value = '';
        elInputPassword.placeholder = 'Nhập để thay đổi mật khẩu truy cập';

        // Hiện phần xóa mật khẩu nếu bot hiện tại đang có mật khẩu
        const currentBot = bots.find(b => b.id === botId);
        if (currentBot && currentBot.has_password) {
            if (elDeletePasswordContainer) elDeletePasswordContainer.style.display = 'flex';
        } else {
            if (elDeletePasswordContainer) elDeletePasswordContainer.style.display = 'none';
        }
        if (elInputClearPassword) elInputClearPassword.checked = false;

        showView('bot-form');
    } catch (error) {
        showToast(error.message, 'danger');
    }
}

async function handleFormSubmit(e) {
    if (e) e.preventDefault();

    const payload = {
        id: elInputId.value.trim(),
        name: elInputName.value.trim(),
        entrypoint: elInputEntrypoint.value.trim().replace(/\\/g, '/') || 'bot.py',
        env: elInputEnv.value,
        use_env: elInputUseEnv.checked,
        requirements: elInputRequirements.value,
        is_edit: isEditMode,
        password: elInputPassword.value.trim(),
        clear_password: elInputClearPassword ? elInputClearPassword.checked : false
    };

    if (!payload.id || !payload.name) {
        showToast('Vui lòng điền đầy đủ ID và Tên Bot.', 'warning');
        return;
    }

    try {
        const response = await fetch('/api/bots', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (response.ok) {
            showToast(data.message, 'success');

            // Nếu đổi mật khẩu mới hoặc xóa mật khẩu, xóa thông tin đã lưu trong session để buộc khóa lại
            if (payload.password || payload.clear_password) {
                sessionStorage.removeItem('bot_pwd_' + payload.id);
                // Đóng websocket console nếu đang mở cho bot này
                if (activeBotId === payload.id && consoleWS) {
                    try { consoleWS.close(); } catch (e) { }
                    consoleWS = null;
                }
            }

            await loadBots();
            selectBot(payload.id);
        } else {
            showToast(data.detail || 'Lưu cấu hình thất bại.', 'danger');
        }
    } catch (error) {
        showToast('Lỗi kết nối máy chủ!', 'danger');
    }
}

// ==========================================
// FILE MANAGER LOGIC
// ==========================================

async function loadBotFiles(keepSearch = false) {
    if (!activeBotId) return;

    // Mặc định dọn dẹp ô tìm kiếm khi chuyển thư mục
    if (!keepSearch && elFileSearch) {
        elFileSearch.value = '';
    }

    try {
        const response = await fetch(`/api/bots/${activeBotId}/files?path=${encodeURIComponent(currentFilePath)}&t=${Date.now()}`);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Không thể tải danh sách file.');
        }

        currentFilesList = await response.json();
        renderBreadcrumbs();
        filterAndRenderFiles();
    } catch (error) {
        showToast(`Lỗi: ${error.message}`, 'danger');
    }
}

function filterAndRenderFiles() {
    let files = [...currentFilesList];

    // 1. Lọc theo từ khóa tìm kiếm
    const query = elFileSearch ? elFileSearch.value.trim().toLowerCase() : '';
    if (query) {
        files = files.filter(f => f.name.toLowerCase().includes(query));
    }

    // 2. Sắp xếp file/thư mục
    const sortMode = elFileSortMode ? elFileSortMode.value : 'name_asc';
    files.sort((a, b) => {
        // Thư mục luôn được ưu tiên xếp lên đầu
        if (a.is_dir && !b.is_dir) return -1;
        if (!a.is_dir && b.is_dir) return 1;

        // Cùng là thư mục hoặc cùng là file thì so sánh theo tiêu chí
        switch (sortMode) {
            case 'name_asc':
                return a.name.localeCompare(b.name, 'vi', { sensitivity: 'base' });
            case 'name_desc':
                return b.name.localeCompare(a.name, 'vi', { sensitivity: 'base' });
            case 'size_asc':
                return (a.is_dir ? 0 : a.size) - (b.is_dir ? 0 : b.size);
            case 'size_desc':
                return (b.is_dir ? 0 : b.size) - (a.is_dir ? 0 : a.size);
            case 'time_desc':
                return b.mtime - a.mtime;
            case 'time_asc':
                return a.mtime - b.mtime;
            default:
                return a.name.localeCompare(b.name, 'vi', { sensitivity: 'base' });
        }
    });

    renderFileList(files);
}

function renderBreadcrumbs() {
    elFileBreadcrumbs.innerHTML = '';

    // Nút Home gốc
    const rootCrumb = document.createElement('span');
    rootCrumb.className = 'crumb-link';
    rootCrumb.innerHTML = '<i class="fa-solid fa-house"></i> Gốc';
    rootCrumb.addEventListener('click', () => {
        currentFilePath = "";
        loadBotFiles();
    });
    elFileBreadcrumbs.appendChild(rootCrumb);

    if (!currentFilePath) return;

    const parts = currentFilePath.split('/').filter(p => p);
    let cumulativePath = "";

    parts.forEach((part, index) => {
        // Dấu ngăn cách
        const separator = document.createElement('span');
        separator.textContent = ' / ';
        elFileBreadcrumbs.appendChild(separator);

        cumulativePath += (index === 0 ? '' : '/') + part;
        const currentCrumbPath = cumulativePath;

        const crumb = document.createElement('span');
        if (index === parts.length - 1) {
            crumb.textContent = part;
            crumb.style.color = 'var(--color-text-main)';
        } else {
            crumb.className = 'crumb-link';
            crumb.textContent = part;
            crumb.addEventListener('click', () => {
                currentFilePath = currentCrumbPath;
                loadBotFiles();
            });
        }
        elFileBreadcrumbs.appendChild(crumb);
    });
}

function renderFileList(files) {
    elFileListBody.innerHTML = '';
    
    // Đặt lại trạng thái chọn tất cả và ẩn thanh hành động hàng loạt
    if (elChkSelectAll) elChkSelectAll.checked = false;
    if (elFileBulkActions) elFileBulkActions.style.display = 'none';

    // Nếu đang ở thư mục con, hiện nút quay lại thư mục cha
    if (currentFilePath) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td></td>
            <td colspan="4" class="file-name-cell" style="color: var(--color-primary);">
                <i class="fa-solid fa-arrow-turn-up fa-rotate-270"></i> .. (Thư mục cha)
            </td>
        `;
        tr.addEventListener('click', () => {
            const parts = currentFilePath.split('/').filter(p => p);
            parts.pop();
            currentFilePath = parts.join('/');
            loadBotFiles();
        });
        elFileListBody.appendChild(tr);
    }

    if (files.length === 0 && !currentFilePath) {
        elFileListBody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; padding: 2rem; color: var(--color-text-muted);">
                    Thư mục trống.
                </td>
            </tr>
        `;
        return;
    }

    files.forEach(file => {
        const tr = document.createElement('tr');

        // Dung lượng và thời gian
        const sizeStr = file.is_dir ? '-' : formatBytes(file.size);
        const mtimeStr = formatDate(file.mtime);

        // Icon tương ứng
        let iconClass = 'fa-regular fa-file';
        if (file.is_dir) {
            iconClass = 'fa-solid fa-folder';
        } else {
            const ext = file.name.split('.').pop().toLowerCase();
            if (['py', 'js', 'css', 'html', 'json', 'env', 'txt', 'md', 'sh', 'log'].includes(ext)) {
                if (ext === 'log') {
                    iconClass = 'fa-regular fa-file-lines';
                } else {
                    iconClass = 'fa-regular fa-file-code';
                }
            }
        }

        const relativePath = currentFilePath ? `${currentFilePath}/${file.name}` : file.name;

        const downloadBtnHtml = file.is_dir ? '' : `
            <button class="btn btn-secondary btn-sm btn-download" style="padding: 0.2rem 0.5rem; margin-right: 0.3rem;" title="Tải file về máy"><i class="fa-solid fa-download"></i></button>
        `;

        tr.innerHTML = `
            <td style="text-align: center; width: 40px;">
                <input type="checkbox" class="chk-file-select" data-path="${escapeHTML(relativePath)}" data-name="${escapeHTML(file.name)}" data-isdir="${file.is_dir}" style="cursor: pointer;">
            </td>
            <td>
                <div class="file-name-cell">
                    <i class="${escapeHTML(iconClass)}"></i>
                    <span>${escapeHTML(file.name)}</span>
                </div>
            </td>
            <td><span class="file-size">${escapeHTML(sizeStr)}</span></td>
            <td><span class="file-mtime">${escapeHTML(mtimeStr)}</span></td>
            <td style="text-align: right; white-space: nowrap;">
                ${downloadBtnHtml}
                <button class="btn btn-secondary btn-sm btn-move" style="padding: 0.2rem 0.5rem; margin-right: 0.3rem;" title="Di chuyển"><i class="fa-solid fa-arrows-up-down-left-right"></i></button>
                <button class="btn btn-secondary btn-sm btn-duplicate" style="padding: 0.2rem 0.5rem; margin-right: 0.3rem;" title="Nhân bản (Tạo bản sao)"><i class="fa-regular fa-copy"></i></button>
                <button class="btn btn-secondary btn-sm btn-rename" style="padding: 0.2rem 0.5rem; margin-right: 0.3rem;" title="Đổi tên"><i class="fa-solid fa-pen"></i></button>
                <button class="btn btn-danger-outline btn-sm btn-delete" style="padding: 0.2rem 0.5rem;" title="Xóa"><i class="fa-solid fa-trash-can"></i></button>
            </td>
        `;

        // Ngăn sự kiện mở file khi bấm vào checkbox
        const chk = tr.querySelector('.chk-file-select');
        if (chk) {
            chk.addEventListener('click', (e) => {
                e.stopPropagation();
                updateBulkActions();
            });
        }

        // Sự kiện click vào hàng để mở file/thư mục
        const nameCell = tr.querySelector('.file-name-cell');
        nameCell.addEventListener('click', (e) => {
            if (file.is_dir) {
                currentFilePath = relativePath;
                loadBotFiles();
            } else {
                editFile(relativePath, file.name);
            }
        });

        // Sự kiện tải xuống tệp
        if (!file.is_dir) {
            tr.querySelector('.btn-download').addEventListener('click', (e) => {
                e.stopPropagation();
                downloadFile(relativePath, file.name);
            });
        }

        // Sự kiện di chuyển
        tr.querySelector('.btn-move').addEventListener('click', (e) => {
            e.stopPropagation();
            openMoveModal([{ path: relativePath, name: file.name, isDir: file.is_dir }]);
        });

        // Sự kiện nhân bản
        tr.querySelector('.btn-duplicate').addEventListener('click', (e) => {
            e.stopPropagation();
            duplicateItem(relativePath, file.name);
        });

        // Sự kiện đổi tên
        tr.querySelector('.btn-rename').addEventListener('click', (e) => {
            e.stopPropagation();
            renameItem(relativePath, file.name);
        });

        // Sự kiện xóa
        tr.querySelector('.btn-delete').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteItem(relativePath, file.name);
        });

        elFileListBody.appendChild(tr);
    });
}

// --- MOVE MODAL LOGIC ---
function openMoveModal(items) {
    itemsToMove = items;
    moveModalCurrentPath = currentFilePath;
    if (elMoveModal) elMoveModal.classList.add('active');
    renderMoveModalNavigation();
}

function closeMoveModal() {
    if (elMoveModal) elMoveModal.classList.remove('active');
    itemsToMove = [];
}

function handleMoveModalUp() {
    const parts = moveModalCurrentPath.split('/').filter(p => p);
    parts.pop();
    moveModalCurrentPath = parts.join('/');
    renderMoveModalNavigation();
}

async function renderMoveModalNavigation() {
    elMoveDirList.innerHTML = '';
    
    // Render breadcrumbs
    elMoveBreadcrumbs.innerHTML = '<span style="color: #6366f1; cursor: pointer; font-weight: 500;"><i class="fa-solid fa-house"></i> Gốc</span>';
    elMoveBreadcrumbs.querySelector('span').addEventListener('click', () => {
        moveModalCurrentPath = "";
        renderMoveModalNavigation();
    });
    
    if (moveModalCurrentPath) {
        const parts = moveModalCurrentPath.split('/').filter(p => p);
        let cumulative = "";
        parts.forEach(part => {
            cumulative += (cumulative ? '/' : '') + part;
            const currentPartPath = cumulative;
            
            const separator = document.createElement('span');
            separator.textContent = ' / ';
            separator.style.color = '#475569';
            elMoveBreadcrumbs.appendChild(separator);
            
            const span = document.createElement('span');
            span.textContent = part;
            span.style.cursor = 'pointer';
            span.style.fontWeight = '500';
            span.addEventListener('click', () => {
                moveModalCurrentPath = currentPartPath;
                renderMoveModalNavigation();
            });
            elMoveBreadcrumbs.appendChild(span);
        });
    }
    
    // Cập nhật target path display
    const rootDisplayName = `/${activeBotId}/`;
    elMoveTargetPathDisplay.textContent = rootDisplayName + (moveModalCurrentPath ? moveModalCurrentPath + '/' : '');
    
    // Fetch thư mục con
    try {
        const response = await fetch(`/api/bots/${activeBotId}/files?path=${encodeURIComponent(moveModalCurrentPath)}&t=${Date.now()}`);
        if (!response.ok) throw new Error("Không thể tải danh sách thư mục.");
        
        const items = await response.json();
        const directories = items.filter(item => item.is_dir);
        
        if (directories.length === 0) {
            elMoveDirList.innerHTML = `
                <div style="text-align: center; padding: 1.5rem; color: #475569; font-size: 0.8rem; font-style: italic;">
                    Không có thư mục con nào.
                </div>
            `;
        } else {
            directories.forEach(dir => {
                // Kiểm tra xem thư mục này có nằm trong danh sách các mục đang bị di chuyển không
                const isBeingMoved = itemsToMove.some(item => item.path === (moveModalCurrentPath ? `${moveModalCurrentPath}/${dir.name}` : dir.name));
                
                const dirDiv = document.createElement('div');
                dirDiv.className = 'move-dir-item';
                if (isBeingMoved) {
                    dirDiv.style.opacity = '0.4';
                    dirDiv.style.pointerEvents = 'none';
                    dirDiv.title = 'Không thể di chuyển vào thư mục đang được chọn.';
                }
                
                dirDiv.innerHTML = `
                    <div class="move-dir-item-left">
                        <i class="fa-solid fa-folder"></i>
                        <span>${escapeHTML(dir.name)}</span>
                    </div>
                    <div class="move-dir-item-right">
                        <i class="fa-solid fa-chevron-right"></i>
                    </div>
                `;
                
                if (!isBeingMoved) {
                    dirDiv.addEventListener('click', () => {
                        moveModalCurrentPath = moveModalCurrentPath ? `${moveModalCurrentPath}/${dir.name}` : dir.name;
                        renderMoveModalNavigation();
                    });
                }
                
                elMoveDirList.appendChild(dirDiv);
            });
        }
    } catch (e) {
        elMoveDirList.innerHTML = `
            <div style="text-align: center; padding: 1.5rem; color: var(--color-danger); font-size: 0.8rem;">
                Lỗi tải danh sách thư mục.
            </div>
        `;
    }
    
    // Render preview di chuyển
    elMovePreviewList.innerHTML = '';
    itemsToMove.forEach(item => {
        const itemDiv = document.createElement('div');
        itemDiv.style.display = 'flex';
        itemDiv.style.alignItems = 'center';
        itemDiv.style.gap = '0.5rem';
        itemDiv.style.fontSize = '0.8rem';
        itemDiv.style.marginTop = '0.2rem';
        
        const iconClass = item.isDir ? 'fa-solid fa-folder' : 'fa-regular fa-file';
        const iconColor = item.isDir ? '#3b82f6' : '#9ca3af';
        const newFullPath = rootDisplayName + (moveModalCurrentPath ? moveModalCurrentPath + '/' : '') + item.name;
        
        itemDiv.innerHTML = `
            <i class="${iconClass}" style="color: ${iconColor};"></i>
            <span style="color: #9ca3af; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; max-width: 180px;">${escapeHTML(item.name)}</span>
            <i class="fa-solid fa-arrow-right" style="color: #475569; font-size: 0.75rem;"></i>
            <span style="color: #10b981; font-weight: 500; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; flex: 1;">${escapeHTML(newFullPath)}</span>
        `;
        elMovePreviewList.appendChild(itemDiv);
    });
}

async function submitMoveModal() {
    if (itemsToMove.length === 0) return;
    
    let successCount = 0;
    let failCount = 0;
    
    // Vô hiệu hóa nút bấm trong quá trình xử lý
    elBtnMoveSubmit.disabled = true;
    elBtnMoveSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Moving...';
    
    const movePromises = itemsToMove.map(async item => {
        const newPath = moveModalCurrentPath ? `${moveModalCurrentPath}/${item.name}` : item.name;
        if (item.path === newPath) return; // Bỏ qua nếu trùng
        
        try {
            const response = await fetch(`/api/bots/${activeBotId}/files/move`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: item.path, new_path: newPath })
            });
            if (response.ok) {
                successCount++;
            } else {
                failCount++;
            }
        } catch (e) {
            failCount++;
        }
    });
    
    await Promise.all(movePromises);
    
    elBtnMoveSubmit.disabled = false;
    elBtnMoveSubmit.innerHTML = '<i class="fa-solid fa-folder-open"></i> Move Here';
    
    if (failCount === 0) {
        showToast(`Đã di chuyển thành công ${successCount} mục.`, 'success');
    } else {
        showToast(`Đã di chuyển ${successCount} mục. Thất bại ${failCount} mục.`, 'warning');
    }
    
    closeMoveModal();
    loadBotFiles(true);
}

// Nhân bản file hoặc thư mục đơn lẻ
async function duplicateItem(path, name) {
    try {
        const response = await fetch(`/api/bots/${activeBotId}/files/duplicate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path })
        });
        
        const data = await response.json();
        if (response.ok) {
            showToast(data.message, 'success');
            loadBotFiles();
        } else {
            showToast(data.detail || 'Nhân bản thất bại.', 'danger');
        }
    } catch (error) {
        showToast('Lỗi kết nối máy chủ!', 'danger');
    }
}

// Di chuyển hàng loạt
function handleBulkMove() {
    const checkedBoxes = document.querySelectorAll('.chk-file-select:checked');
    if (checkedBoxes.length === 0) return;
    
    const items = Array.from(checkedBoxes).map(chk => ({
        path: chk.dataset.path,
        name: chk.dataset.name,
        isDir: chk.dataset.isdir === 'true'
    }));
    
    openMoveModal(items);
}

// Nhân bản hàng loạt
async function handleBulkDuplicate() {
    const checkedBoxes = document.querySelectorAll('.chk-file-select:checked');
    if (checkedBoxes.length === 0) return;
    
    let successCount = 0;
    let failCount = 0;
    
    const duplicatePromises = Array.from(checkedBoxes).map(async chk => {
        try {
            const response = await fetch(`/api/bots/${activeBotId}/files/duplicate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: chk.dataset.path })
            });
            if (response.ok) {
                successCount++;
            } else {
                failCount++;
            }
        } catch (e) {
            failCount++;
        }
    });
    
    await Promise.all(duplicatePromises);
    
    if (failCount === 0) {
        showToast(`Đã nhân bản thành công ${successCount} mục.`, 'success');
    } else {
        showToast(`Đã nhân bản ${successCount} mục. Thất bại ${failCount} mục.`, 'warning');
    }
    
    loadBotFiles(true);
}

// Cập nhật trạng thái hiển thị thanh hành động hàng loạt
function updateBulkActions() {
    const checkboxes = document.querySelectorAll('.chk-file-select');
    const checkedBoxes = document.querySelectorAll('.chk-file-select:checked');
    const count = checkedBoxes.length;
    
    if (count > 0) {
        if (elFileBulkActions) elFileBulkActions.style.display = 'flex';
        if (elBulkSelectCount) elBulkSelectCount.textContent = count;
    } else {
        if (elFileBulkActions) elFileBulkActions.style.display = 'none';
    }
    
    // Đồng bộ nút "Chọn tất cả"
    if (elChkSelectAll) {
        elChkSelectAll.checked = checkboxes.length > 0 && count === checkboxes.length;
    }
}

// Xử lý xóa hàng loạt
async function handleBulkDelete() {
    const checkedBoxes = document.querySelectorAll('.chk-file-select:checked');
    if (checkedBoxes.length === 0) return;
    
    const items = [];
    checkedBoxes.forEach(chk => {
        items.push({
            path: chk.dataset.path,
            name: chk.dataset.name
        });
    });
    
    const confirmMsg = `Bạn có chắc chắn muốn xóa ${items.length} mục đã chọn?\nHành động này không thể hoàn tác!`;
    if (!confirm(confirmMsg)) return;
    
    let successCount = 0;
    let failCount = 0;
    
    // Thực hiện xóa song song qua Promise.all
    const deletePromises = items.map(async item => {
        try {
            const response = await fetch(`/api/bots/${activeBotId}/files/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: item.path })
            });
            if (response.ok) {
                successCount++;
            } else {
                failCount++;
            }
        } catch (e) {
            failCount++;
        }
    });
    
    await Promise.all(deletePromises);
    
    if (failCount === 0) {
        showToast(`Đã xóa thành công ${successCount} mục.`, 'success');
    } else {
        showToast(`Đã xóa ${successCount} mục. Thất bại ${failCount} mục.`, 'warning');
    }
    
    loadBotFiles(true); // Tải lại danh sách file và giữ lại trạng thái tìm kiếm
}

// Xử lý tải xuống hàng loạt
function handleBulkDownload() {
    const checkedBoxes = document.querySelectorAll('.chk-file-select:checked');
    if (checkedBoxes.length === 0) return;
    
    let fileCount = 0;
    checkedBoxes.forEach(chk => {
        const isDir = chk.dataset.isdir === 'true';
        if (!isDir) {
            fileCount++;
            // Tránh việc trình duyệt chặn tải xuống hàng loạt bằng cách đặt độ trễ (delay) nhỏ
            setTimeout(() => {
                downloadFile(chk.dataset.path, chk.dataset.name);
            }, fileCount * 250); // Cách nhau 250ms
        }
    });
    
    if (fileCount === 0) {
        showToast('Không có tệp tin nào được chọn để tải xuống (không hỗ trợ tải xuống thư mục).', 'warning');
    } else {
        showToast(`Đang chuẩn bị tải xuống ${fileCount} tệp tin...`, 'success');
    }
}

// Tải xuống file
function downloadFile(relativePath, fileName) {
    const pwd = sessionStorage.getItem('bot_pwd_' + activeBotId) || '';
    const url = `/api/bots/${activeBotId}/files/download?path=${encodeURIComponent(relativePath)}&password=${encodeURIComponent(pwd)}`;

    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('vi-VN');
}

// Tạo file/thư mục mới
async function createNewItem(isDir) {
    const title = isDir ? 'Tạo Thư mục mới' : 'Tạo File mới';
    const placeholder = isDir ? 'Tên thư mục...' : 'Tên file (ví dụ: config.json)...';
    const name = prompt(`${title}\nNhập tên cần tạo:`);

    if (!name || !name.trim()) return;

    const relativePath = currentFilePath ? `${currentFilePath}/${name.trim()}` : name.trim();

    try {
        const response = await fetch(`/api/bots/${activeBotId}/files/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: relativePath, is_dir: isDir })
        });

        const data = await response.json();
        if (response.ok) {
            showToast(data.message, 'success');
            loadBotFiles();
        } else {
            showToast(data.detail || 'Tạo thất bại.', 'danger');
        }
    } catch (error) {
        showToast('Lỗi kết nối máy chủ!', 'danger');
    }
}

// Đổi tên file/thư mục
async function renameItem(relativePath, oldName) {
    const newName = prompt(`Đổi tên tệp/thư mục: ${oldName}\nNhập tên mới:`, oldName);
    if (!newName || !newName.trim() || newName.trim() === oldName) return;

    try {
        const response = await fetch(`/api/bots/${activeBotId}/files/rename`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: relativePath, new_name: newName.trim() })
        });

        const data = await response.json();
        if (response.ok) {
            showToast(data.message, 'success');
            loadBotFiles();
        } else {
            showToast(data.detail || 'Đổi tên thất bại.', 'danger');
        }
    } catch (error) {
        showToast('Lỗi kết nối máy chủ!', 'danger');
    }
}

// Xóa file/thư mục
async function deleteItem(relativePath, name) {
    if (!confirm(`Bạn có chắc chắn muốn xóa "${name}"?\nHành động này không thể hoàn tác!`)) return;

    try {
        const response = await fetch(`/api/bots/${activeBotId}/files/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: relativePath })
        });

        const data = await response.json();
        if (response.ok) {
            showToast(data.message, 'success');
            loadBotFiles();
        } else {
            showToast(data.detail || 'Xóa thất bại.', 'danger');
        }
    } catch (error) {
        showToast('Lỗi kết nối máy chủ!', 'danger');
    }
}

// Mở trình soạn thảo file
async function editFile(relativePath, name) {
    try {
        const response = await fetch(`/api/bots/${activeBotId}/files/content?path=${encodeURIComponent(relativePath)}&t=${Date.now()}`);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Không thể đọc nội dung file.');
        }

        const data = await response.json();
        editingFilePath = relativePath;
        elFileEditorTitle.textContent = `Đang chỉnh sửa: ${name}`;
        elFileEditorTextarea.value = data.content;
        elFileEditorStatus.textContent = `Đường dẫn: ${relativePath}`;
        elFileEditorModal.classList.add('active');
    } catch (error) {
        showToast(`Không hỗ trợ định dạng hoặc lỗi: ${error.message}`, 'warning');
    }
}

function closeEditor() {
    elFileEditorModal.classList.remove('active');
    editingFilePath = "";
    elFileEditorTextarea.value = "";
}

async function saveEditedFile() {
    if (!activeBotId || !editingFilePath) return;

    const content = elFileEditorTextarea.value;
    elBtnFileEditorSave.disabled = true;
    elBtnFileEditorSave.textContent = 'Đang lưu...';

    try {
        const response = await fetch(`/api/bots/${activeBotId}/files/content`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: editingFilePath, content: content })
        });

        const data = await response.json();
        if (response.ok) {
            showToast(data.message, 'success');
            closeEditor();
            loadBotFiles();
        } else {
            showToast(data.detail || 'Lưu tệp tin thất bại.', 'danger');
        }
    } catch (error) {
        showToast('Lỗi kết nối máy chủ!', 'danger');
    } finally {
        elBtnFileEditorSave.disabled = false;
        elBtnFileEditorSave.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Lưu Thay Đổi';
    }
}

// Xử lý tải lên file từ input chọn file
async function handleFileUpload(e) {
    const files = e.target.files;
    if (files.length === 0) return;
    await uploadFileList(files);
    elFileUploadInput.value = ''; // Reset input chọn file
}

// Xử lý tải lên thư mục từ input thư mục
async function handleFileUploadDir(e) {
    const files = e.target.files;
    if (files.length === 0) return;
    await uploadFileList(files);
    elFileUploadDirInput.value = ''; // Reset input chọn thư mục
}

// Hàm tải lên danh sách file dùng chung (hỗ trợ kéo thả, chọn file, chọn thư mục và tự động nhóm)
async function uploadFileList(files) {
    showToast('Đang chuẩn bị tải lên...', 'info');

    // Nhóm các file theo thư mục tương đối
    const groups = {};
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const relPath = file.webkitRelativePath || "";
        let dirPart = "";
        if (relPath && relPath.includes('/')) {
            dirPart = relPath.substring(0, relPath.lastIndexOf('/'));
        }

        if (!groups[dirPart]) {
            groups[dirPart] = [];
        }
        groups[dirPart].push(file);
    }

    const totalGroups = Object.keys(groups).length;
    let uploadedGroups = 0;

    showToast(`Đang tải lên ${files.length} tệp tin...`, 'info');

    for (const [dirPart, fileList] of Object.entries(groups)) {
        const formData = new FormData();
        fileList.forEach(file => {
            formData.append('files', file);
        });

        // Đường dẫn đích trên server
        const targetPath = currentFilePath ? (dirPart ? `${currentFilePath}/${dirPart}` : currentFilePath) : dirPart;

        try {
            const response = await fetch(`/api/bots/${activeBotId}/files/upload?path=${encodeURIComponent(targetPath)}`, {
                method: 'POST',
                body: formData
            });
            if (response.ok) {
                uploadedGroups++;
            }
        } catch (error) {
            console.error(`Lỗi tải lên nhóm thư mục ${dirPart}:`, error);
        }
    }

    if (uploadedGroups === totalGroups) {
        showToast('Tải lên toàn bộ tệp tin thành công!', 'success');
    } else {
        showToast(`Tải lên hoàn thành (${uploadedGroups}/${totalGroups} nhóm thư mục thành công).`, 'warning');
    }
    loadBotFiles();
}

// --- UTILITIES ---
function showToast(message, type = 'info') {
    elToastMessage.textContent = message;

    // Thiết lập màu sắc toast dựa trên loại
    elToast.style.borderColor = 'var(--color-primary)';
    if (type === 'success') elToast.style.borderColor = 'var(--color-success)';
    if (type === 'danger') elToast.style.borderColor = 'var(--color-danger)';
    if (type === 'warning') elToast.style.borderColor = 'var(--color-warning)';

    elToast.classList.add('show');

    setTimeout(() => {
        elToast.classList.remove('show');
    }, 4000);
}

// Hàm đệ quy duyệt cây thư mục khi kéo thả
function traverseFileTree(item, path, fileList) {
    return new Promise((resolve) => {
        if (item.isFile) {
            item.file((file) => {
                // Gán đường dẫn tương đối giả lập vào file object để hàm uploadFileList xử lý đồng bộ
                Object.defineProperty(file, 'webkitRelativePath', {
                    value: path ? `${path}/${file.name}` : file.name,
                    writable: false
                });
                fileList.push(file);
                resolve();
            });
        } else if (item.isDirectory) {
            const dirReader = item.createReader();
            const readEntries = () => {
                dirReader.readEntries(async (entries) => {
                    if (entries.length === 0) {
                        resolve();
                    } else {
                        const promises = [];
                        for (let i = 0; i < entries.length; i++) {
                            const newPath = path ? `${path}/${item.name}` : item.name;
                            promises.push(traverseFileTree(entries[i], newPath, fileList));
                        }
                        await Promise.all(promises);
                        readEntries(); // Đọc tiếp phòng trường hợp thư mục có cực kỳ nhiều file
                    }
                }, () => resolve());
            };
            readEntries();
        } else {
            resolve();
        }
    });
}

// --- PASSWORD CONFIRM MODAL ACTIONS ---
async function submitConfirmPassword() {
    const pwd = elConfirmBotPassword.value;
    if (!pwd) {
        showToast('Vui lòng nhập mật khẩu.', 'warning');
        return;
    }

    // Thử gọi API config để kiểm tra mật khẩu (sử dụng originalFetch để tránh vòng lặp)
    try {
        const response = await originalFetch(`/api/bots/${pendingBotId}/config`, {
            headers: {
                'X-Bot-Password': pwd
            }
        });

        if (response.ok) {
            // Đúng mật khẩu! Lưu vào sessionStorage
            sessionStorage.setItem('bot_pwd_' + pendingBotId, pwd);
            elPasswordModal.classList.remove('active');

            const targetBotId = pendingBotId;
            pendingBotId = null;
            selectBot(targetBotId);
        } else {
            showToast('Mật khẩu truy cập bot không chính xác!', 'danger');
            elConfirmBotPassword.value = '';
            elConfirmBotPassword.focus();
        }
    } catch (error) {
        showToast('Lỗi kết nối kiểm tra mật khẩu!', 'danger');
    }
}

function closePasswordModal() {
    elPasswordModal.classList.remove('active');
    pendingBotId = null;
}

// Hàm toggle ẩn/hiện mật khẩu
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    const icon = btn.querySelector('i');
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    }
}

// Đăng ký toàn cục để gọi từ onclick trong HTML
window.togglePasswordVisibility = togglePasswordVisibility;
