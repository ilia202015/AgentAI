let serverUrl = "http://localhost:8080/api/browser";
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

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000); 

    try {
        const response = await fetch(`${serverUrl}/poll`, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (response.status === 200) {
            const cmd = await response.json();
            if (cmd && cmd.type !== "noop" && cmd.request_id) {
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
        } else {
            await register();
            await new Promise(r => setTimeout(r, 2000));
        }
    } catch (e) {
        await register();
        await new Promise(r => setTimeout(r, 5000)); 
    } finally {
        isPolling = false;
        setTimeout(poll, 200);
    }
}

async function handleCommand(command) {
    const action = command.type;
    const params = command.params || {};
    
    // Auto-resolve tabId if missing
    let tabId = params.tabId;
    if (!tabId && action !== 'open_url') {
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tabs.length > 0) tabId = tabs[0].id;
    }

    switch (action) {
        case 'open_url':
            return new Promise((resolve, reject) => {
                chrome.tabs.create({ url: params.url }, (tab) => {
                    if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
                    else resolve({ status: 'opened', tabId: tab.id, url: params.url });
                });
            });

        case 'list_tabs':
            const allTabs = await chrome.tabs.query({});
            return { tabs: allTabs.map(t => ({ id: t.id, title: t.title, url: t.url, active: t.active })) };

        case 'screenshot':
            const dataUrl = await chrome.tabs.captureVisibleTab(null, { format: 'png' });
            return { images: [dataUrl.split(',')[1]] };

        case 'batch':
            if (!tabId) throw new Error("No active tab found for batch actions");
            const results = await chrome.tabs.sendMessage(tabId, { action: 'batch', data: params });
            
            // Check if any command in batch was 'screenshot' (client-side extension)
            // But actually we can handle it here if we want a full screenshot
            for (let i=0; i < params.commands.length; i++) {
                if (params.commands[i].type === 'screenshot') {
                    const screenshot = await chrome.tabs.captureVisibleTab(null, { format: 'png' });
                    results.results[i] = { status: 'success', images: [screenshot.split(',')[1]] };
                }
            }
            return results;

        case 'get_state':
        case 'get_raw_html':
            if (!tabId) throw new Error(`Action ${action} requires tabId`);
            return await chrome.tabs.sendMessage(tabId, { action, data: params });

        default:
            throw new Error(`Unknown action: ${action}`);
    }
}

chrome.alarms.create('keepAlive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'keepAlive' && !isPolling) poll();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "SET_SERVER_URL") {
        if (serverUrl !== message.url) {
            serverUrl = message.url;
            register().then(() => { if (!isPolling) poll(); });
        }
    }
});

register().then(() => poll());
