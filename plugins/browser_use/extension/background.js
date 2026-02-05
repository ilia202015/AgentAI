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
        console.error("Registration failed:", e);
        return false;
    }
}

async function poll() {
    if (isPolling) return;
    isPolling = true;
    try {
        const response = await fetch(`${serverUrl}/poll`);
        if (!response.ok) {
            console.warn("Poll failed, re-registering in 5s...");
            setTimeout(poll, 5000);
            return;
        }
        
        const cmd = await response.json();
        
        // В bridge.py пустой ответ - это {type: "noop"}
        if (cmd && cmd.type !== "noop" && cmd.request_id) {
            console.log("Received command:", cmd);
            try {
                const result = await handleCommand(cmd);
                // ВАЖНО: шлем на /respond и включаем request_id
                await fetch(`${serverUrl}/respond`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        request_id: cmd.request_id, 
                        status: "success",
                        ...result 
                    })
                });
            } catch (cmdError) {
                console.error("Command error:", cmdError);
                await fetch(`${serverUrl}/respond`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        request_id: cmd.request_id, 
                        status: "error", 
                        message: cmdError.message 
                    })
                });
            }
        }
    } catch (e) {
        console.error("Poll error:", e);
    } finally {
        isPolling = false;
        // Рекурсивный вызов для Long Polling
        setTimeout(poll, 100); 
    }
}

// Keep-alive via alarms (as backup)
if (chrome.alarms) {
    chrome.alarms.create('keepAlive', { periodInMinutes: 1 });
    chrome.alarms.onAlarm.addListener((alarm) => {
        if (alarm.name === 'keepAlive' && !isPolling) poll();
    });
}

async function handleCommand(command) {
    // В bridge.py тип команды в поле 'type', параметры в 'params'
    const action = command.type;
    const params = command.params || {};
    const { tabId, url } = params;

    switch (action) {
        case 'open_url':
            return new Promise((resolve, reject) => {
                chrome.tabs.create({ url: url }, (tab) => {
                    const listener = (updatedTabId, changeInfo, updatedTab) => {
                        if (updatedTabId === tab.id && changeInfo.status === 'complete') {
                            chrome.tabs.onUpdated.removeListener(listener);
                            resolve({ status: 'complete', tabId: tab.id, url: updatedTab.url });
                        }
                    };
                    chrome.tabs.onUpdated.addListener(listener);
                });
                // Таймаут безопасности
                setTimeout(() => reject(new Error("Tab load timeout")), 20000);
            });

        case 'get_state':
        case 'batch':
        case 'get_raw_html':
            if (!tabId) throw new Error(`Action ${action} requires tabId`);
            return new Promise((resolve, reject) => {
                chrome.tabs.sendMessage(tabId, { action, data: params }, (response) => {
                    if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
                    else resolve(response);
                });
            });

        default:
            throw new Error(`Unknown action: ${action}`);
    }
}

// Start
register().then(() => poll());