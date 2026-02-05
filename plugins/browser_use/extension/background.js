const serverUrl = "http://localhost:8080/api/browser";
let isPolling = false;

async function register() {
    try {
        const response = await fetch(`${serverUrl}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: 'browser_use_ext' })
        });
        return response.ok;
    } catch (e) {
        return false;
    }
}

async function poll() {
    if (isPolling) return;
    isPolling = true;
    try {
        const response = await fetch(`${serverUrl}/poll`);
        if (response.status === 200) {
            const cmd = await response.json();
            if (cmd && cmd.type !== "noop" && cmd.request_id) {
                console.log("Exec:", cmd.type);
                handleCommand(cmd).then(result => {
                    return fetch(`${serverUrl}/respond`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ request_id: cmd.request_id, status: "success", ...result })
                    });
                }).catch(err => {
                    fetch(`${serverUrl}/respond`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ request_id: cmd.request_id, status: "error", message: err.message })
                    });
                });
            }
        }
    } catch (e) {
        console.error("Poll error:", e);
        await new Promise(r => setTimeout(r, 2000)); // Пауза при ошибке сети
    } finally {
        isPolling = false;
        setTimeout(poll, 100);
    }
}

async function handleCommand(command) {
    const action = command.type;
    const params = command.params || {};
    const { tabId, url } = params;

    switch (action) {
        case 'open_url':
            return new Promise((resolve, reject) => {
                chrome.tabs.create({ url: url }, (tab) => {
                    if (chrome.runtime.lastError) {
                        reject(new Error(chrome.runtime.lastError.message));
                    } else {
                        // Сразу возвращаем успех, не дожидаясь загрузки, 
                        // чтобы избежать зависания на 'complete'
                        resolve({ status: 'opened', tabId: tab.id, url: url });
                    }
                });
            });

        case 'get_state':
        case 'batch':
        case 'get_raw_html':
            if (!tabId) throw new Error(`Action ${action} requires tabId`);
            return new Promise((resolve, reject) => {
                chrome.tabs.sendMessage(tabId, { action, data: params }, (response) => {
                    if (chrome.runtime.lastError) {
                        reject(new Error("Content script not ready. Try refreshing the page."));
                    } else {
                        resolve(response);
                    }
                });
            });

        default:
            throw new Error(`Unknown action: ${action}`);
    }
}

register().then(() => poll());