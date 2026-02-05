let serverUrl = "http://localhost:3000"; // Default
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
            console.warn("Poll failed, re-registering...");
            await register();
            return;
        }
        const commands = await response.json();
        for (const cmd of commands) {
            await handleCommand(cmd);
        }
    } catch (e) {
        console.error("Poll error:", e);
        await register(); // Сразу вызываем register при падении fetch
    } finally {
        isPolling = false;
    }
}

// Keep-alive via alarms
chrome.alarms.create('keepAlive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'keepAlive') {
        poll();
    }
});

async function handleCommand(command) {
    switch (command.action) {
        case 'open_url':
            return new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    chrome.tabs.onUpdated.removeListener(listener);
                    reject(new Error("Timeout waiting for tab update"));
                }, 15000); // 15 sec timeout

                const listener = (tabId, changeInfo, tab) => {
                    if (tabId === command.tabId && changeInfo.status === 'complete') {
                        clearTimeout(timeout);
                        chrome.tabs.onUpdated.removeListener(listener);
                        resolve({ status: 'complete', url: tab.url });
                    }
                };

                chrome.tabs.onUpdated.addListener(listener);
                chrome.tabs.update(command.tabId, { url: command.url });
            });
        // ... другие команды
    }
}

// Initial registration
register();
