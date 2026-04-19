
const SERVER_URL = "http://127.0.0.1:8085";
// Глобальное состояние целевой вкладки
let targetTabId = null;

async function sendCDP(tabId, method, params = {}) {
    return new Promise((resolve, reject) => {
        chrome.debugger.sendCommand({ tabId }, method, params, (res) => {
            if (chrome.runtime.lastError) {
                reject(new Error(chrome.runtime.lastError.message));
            } else {
                resolve(res);
            }
        });
    });
}

async function attachDebugger(tabId) {
    return new Promise((resolve) => {
        chrome.debugger.getTargets((targets) => {
            let target = targets.find(t => t.tabId === tabId);
            if (target && target.attached) {
                resolve();
            } else {
                chrome.debugger.attach({ tabId }, "1.3", () => {
                    if (chrome.runtime.lastError) console.error(chrome.runtime.lastError);
                    resolve();
                });
            }
        });
    });
}

async function detachDebugger(tabId) {
    return new Promise((resolve) => {
        chrome.debugger.detach({ tabId }, () => {
            resolve();
        });
    });
}

async function executeAction(tabId, action) {
    if (action.action === "click") {
        let exp = `
            (() => {
                let el = null;
                if ("${action.selector}".startsWith("//")) {
                    el = document.evaluate("${action.selector}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                } else {
                    el = document.querySelector("${action.selector}");
                }
                if (!el) return null;
                el.scrollIntoView({block: 'center', behavior: 'instant'});
                let rect = el.getBoundingClientRect();
                return { x: rect.left + rect.width/2, y: rect.top + rect.height/2 };
            })()
        `;
        let evalRes = await sendCDP(tabId, "Runtime.evaluate", { expression: exp, returnByValue: true });
        
        if (!evalRes.result || !evalRes.result.value) {
            throw new Error("Element not found: " + action.selector);
        }
        
        let coords = evalRes.result.value;
        await sendCDP(tabId, "Input.dispatchMouseEvent", { type: "mouseMoved", x: coords.x, y: coords.y });
        await sendCDP(tabId, "Input.dispatchMouseEvent", { type: "mousePressed", x: coords.x, y: coords.y, button: "left", clickCount: 1 });
        await sendCDP(tabId, "Input.dispatchMouseEvent", { type: "mouseReleased", x: coords.x, y: coords.y, button: "left", clickCount: 1 });
        
    } else if (action.action === "type") {
        if (action.selector) {
            await executeAction(tabId, { action: "click", selector: action.selector });
            await new Promise(r => setTimeout(r, 100));
        }
        for (let char of action.text) {
            await sendCDP(tabId, "Input.dispatchKeyEvent", { type: "char", text: char });
        }
    } else if (action.action === "press") {
         await sendCDP(tabId, "Input.dispatchKeyEvent", { type: "keyDown", commands: [action.key] });
         await sendCDP(tabId, "Input.dispatchKeyEvent", { type: "keyUp", commands: [action.key] });
    }
    await new Promise(r => setTimeout(r, 300));
}

async function handleCommand(commandData) {
    let msgId = commandData.message_id;
    let result = { status: "success" };
    
    try {
        // Умный поиск вкладки
        if (!targetTabId) {
            let tabs = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tabs.length) throw new Error("No active tab found");
            targetTabId = tabs[0].id;
        } else {
            try {
                await chrome.tabs.get(targetTabId); // Проверяем, жива ли вкладка
            } catch(e) {
                let tabs = await chrome.tabs.query({ active: true, currentWindow: true });
                if (!tabs.length) throw new Error("Target tab closed and no active tab found");
                targetTabId = tabs[0].id;
            }
        }

        if (commandData.action === "navigate") {
            await chrome.tabs.update(targetTabId, { url: commandData.url, active: true });
            await new Promise(resolve => {
                let listener = (tId, info) => {
                    if (tId === targetTabId && info.status === 'complete') {
                        chrome.tabs.onUpdated.removeListener(listener);
                        resolve();
                    }
                };
                chrome.tabs.onUpdated.addListener(listener);
                setTimeout(() => {
                    chrome.tabs.onUpdated.removeListener(listener);
                    resolve();
                }, 10000);
            });
            result.message = "Navigated to " + commandData.url;
            
        } else if (commandData.action === "execute_actions") {
            await attachDebugger(targetTabId);
            try {
                for (let action of commandData.actions) {
                    await executeAction(targetTabId, action);
                }
                result.message = "Actions executed successfully";
            } finally {
                // Гарантированно отключаем дебаггер даже при ошибке
                await detachDebugger(targetTabId);
            }
        }
    } catch (e) {
        result = { status: "error", message: e.message };
    }

    result.message_id = msgId;
    
    try {
        await fetch(SERVER_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(result)
        });
    } catch (e) {
        console.error("Failed to send response back to server:", e);
    }
}

async function pollServer() {
    let backoff = 1000;
    while (true) {
        try {
            let res = await fetch(SERVER_URL, { method: "GET" });
            if (res.ok) {
                backoff = 1000; // Сбрасываем backoff при успехе
                let data = await res.json();
                if (data.status === "command") {
                    await handleCommand(data.data);
                }
            } else {
                throw new Error("Server returned " + res.status);
            }
        } catch (e) {
            // Увеличиваем задержку до максимума 10 секунд
            backoff = Math.min(backoff * 1.5, 10000);
            await new Promise(r => setTimeout(r, backoff));
        }
    }
}

pollServer();
