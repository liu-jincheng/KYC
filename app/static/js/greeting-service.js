/**
 * 生日祝福生成 & 历史记录管理 - 共享模块
 * 用于 dashboard.html 和 customer_detail.html
 *
 * 使用方式:
 *   const gs = new GreetingService({ getCustomerId: () => someId });
 *   gs.init();
 */

class GreetingService {
    constructor(options = {}) {
        // getCustomerId: 返回当前客户 ID 的函数
        this.getCustomerId = options.getCustomerId || (() => null);
        this.MAX_HISTORY_ITEMS = 10;
        this.modal = null;
    }

    // ---- 初始化 ----
    init() {
        const genBtn = document.getElementById('generateGreetingBtn') || document.getElementById('doGenerateGreetingBtn');
        if (genBtn) genBtn.addEventListener('click', () => this.generate());

        const copyBtn = document.getElementById('copyGreetingBtn');
        if (copyBtn) copyBtn.addEventListener('click', () => this.copyResult());

        const clearBtn = document.getElementById('clearHistoryBtn');
        if (clearBtn) clearBtn.addEventListener('click', () => this.clearAll());
    }

    // ---- localStorage key ----
    _key() {
        return `birthday_greetings_history_${this.getCustomerId()}`;
    }

    // ---- 打开 Modal ----
    open(customerName) {
        if (customerName) {
            const nameEl = document.getElementById('greetingCustomerName');
            if (nameEl) nameEl.textContent = customerName;
        }

        const style = document.getElementById('greetingStyle');
        if (style) style.value = '商务专业';

        this._hide('greetingResultArea');
        this._hide('greetingLoading');
        this._hide('greetingError');

        const result = document.getElementById('greetingResult');
        if (result) result.textContent = '';

        const copyOk = document.getElementById('copySuccess');
        if (copyOk) copyOk.style.display = 'none';

        this.loadHistory();

        if (!this.modal) {
            this.modal = new bootstrap.Modal(document.getElementById('birthdayGreetingModal'));
        }
        this.modal.show();
    }

    // ---- 流式生成祝福 ----
    async generate() {
        const style = document.getElementById('greetingStyle').value;
        const resultEl = document.getElementById('greetingResult');
        const genBtn = document.getElementById('generateGreetingBtn') || document.getElementById('doGenerateGreetingBtn');

        this._show('greetingLoading');
        this._show('greetingResultArea');
        resultEl.textContent = '';
        this._hide('greetingError');
        if (genBtn) genBtn.disabled = true;

        const statusText = document.getElementById('greetingStatusText');
        if (statusText) statusText.textContent = 'AI 正在生成祝福语...';

        resultEl.classList.add('streaming-cursor');
        let accumulated = '';

        try {
            const response = await fetch('/api/ai/generate-birthday-greeting/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
                body: JSON.stringify({ customer_id: this.getCustomerId(), style })
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                while (buffer.includes('\n')) {
                    const idx = buffer.indexOf('\n');
                    const line = buffer.slice(0, idx).trim();
                    buffer = buffer.slice(idx + 1);

                    if (!line.startsWith('data: ')) continue;
                    const dataStr = line.slice(6);
                    if (!dataStr || dataStr === '[DONE]') continue;

                    try {
                        const data = JSON.parse(dataStr);
                        if (data.type === 'content' && data.content) {
                            accumulated += data.content;
                            resultEl.textContent = accumulated;
                            resultEl.scrollTop = resultEl.scrollHeight;
                        } else if (data.type === 'done') {
                            resultEl.classList.remove('streaming-cursor');
                            this._hide('greetingLoading');
                            if (data.full_content) {
                                resultEl.textContent = data.full_content;
                                accumulated = data.full_content;
                            }
                            if (accumulated) this.saveToHistory(style, accumulated);
                        } else if (data.type === 'error') {
                            resultEl.classList.remove('streaming-cursor');
                            this._showError(data.message || '生成失败，请重试');
                            if (!accumulated) this._hide('greetingResultArea');
                        }
                    } catch (_) { /* skip parse errors */ }
                }
            }

            resultEl.classList.remove('streaming-cursor');
        } catch (error) {
            console.error('生成祝福失败:', error);
            resultEl.classList.remove('streaming-cursor');
            this._showError('网络错误，请检查连接后重试');
            if (!accumulated) this._hide('greetingResultArea');
        } finally {
            this._hide('greetingLoading');
            if (genBtn) genBtn.disabled = false;
        }
    }

    // ---- 复制结果 ----
    async copyResult() {
        const text = document.getElementById('greetingResult').textContent;
        await this._copyText(text);
        const ok = document.getElementById('copySuccess');
        if (ok) {
            ok.style.display = 'inline';
            setTimeout(() => { ok.style.display = 'none'; }, 2000);
        }
    }

    // ---- 历史记录 ----
    getHistory() {
        try {
            const data = localStorage.getItem(this._key());
            return data ? JSON.parse(data) : [];
        } catch (_) { return []; }
    }

    saveToHistory(style, content) {
        const history = this.getHistory();
        history.unshift({
            id: `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            style, content,
            timestamp: Date.now()
        });
        if (history.length > this.MAX_HISTORY_ITEMS) history.pop();
        try {
            localStorage.setItem(this._key(), JSON.stringify(history));
            this.loadHistory();
        } catch (_) {}
    }

    loadHistory() {
        const history = this.getHistory();
        const list = document.getElementById('greetingHistoryList');
        const badge = document.getElementById('historyCount');
        const actions = document.getElementById('historyActions');

        if (badge) badge.textContent = history.length;

        if (history.length === 0) {
            if (list) list.innerHTML = '<p class="text-muted text-center py-2 mb-0">暂无历史记录</p>';
            if (actions) actions.style.display = 'none';
            return;
        }

        if (actions) actions.style.display = 'block';

        let html = '';
        history.forEach(item => {
            const date = new Date(item.timestamp);
            const timeStr = date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
            const snippet = item.content.length > 60 ? item.content.substring(0, 60) + '...' : item.content;

            html += `
                <div class="list-group-item list-group-item-action p-2" data-history-id="${item.id}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1" style="cursor:pointer;" onclick="window._greetingService.useHistory('${item.id}')">
                            <div class="d-flex gap-2 mb-1">
                                <span class="badge bg-info">${item.style}</span>
                                <small class="text-muted">${timeStr}</small>
                            </div>
                            <p class="mb-0 small text-muted" style="white-space:pre-wrap;">${snippet}</p>
                        </div>
                        <div class="btn-group btn-group-sm ms-2">
                            <button type="button" class="btn btn-outline-success btn-sm" onclick="window._greetingService.copyHistory('${item.id}')" title="复制">
                                <i class="bi bi-clipboard"></i>
                            </button>
                            <button type="button" class="btn btn-outline-danger btn-sm" onclick="window._greetingService.deleteHistory('${item.id}')" title="删除">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>`;
        });
        if (list) list.innerHTML = html;
    }

    useHistory(id) {
        const item = this.getHistory().find(h => h.id === id);
        if (!item) return;
        document.getElementById('greetingResult').textContent = item.content;
        this._show('greetingResultArea');
        const style = document.getElementById('greetingStyle');
        if (style) style.value = item.style;
    }

    async copyHistory(id) {
        const item = this.getHistory().find(h => h.id === id);
        if (!item) return;
        await this._copyText(item.content);
        const btn = document.querySelector(`[data-history-id="${id}"] .btn-outline-success`);
        if (btn) {
            const orig = btn.innerHTML;
            btn.innerHTML = '<i class="bi bi-check"></i>';
            setTimeout(() => { btn.innerHTML = orig; }, 1500);
        }
    }

    deleteHistory(id) {
        let history = this.getHistory().filter(h => h.id !== id);
        localStorage.setItem(this._key(), JSON.stringify(history));
        this.loadHistory();
    }

    clearAll() {
        if (confirm('确定要清空所有历史记录吗？')) {
            localStorage.removeItem(this._key());
            this.loadHistory();
        }
    }

    // ---- 工具方法 ----
    async _copyText(text) {
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(text);
            } else {
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.style.cssText = 'position:fixed;left:-9999px';
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
            }
        } catch (e) {
            console.error('复制失败:', e);
        }
    }

    _show(id) {
        const el = document.getElementById(id);
        if (el) el.style.display = 'block';
    }

    _hide(id) {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    }

    _showError(msg) {
        const el = document.getElementById('greetingError');
        if (el) {
            el.textContent = msg;
            el.style.display = 'block';
        }
    }
}
