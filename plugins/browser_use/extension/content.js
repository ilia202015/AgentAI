
// content.js - отвечает ТОЛЬКО за построение DOM дерева и генерацию локаторов.
// Не выполняет действий на странице (за это отвечает background.js через CDP).

function generateSelector(el) {
    if (el.tagName.toLowerCase() == "html") return "html";
    
    // Приоритет 1: ID
    if (el.id) return "#" + CSS.escape(el.id);
    
    // Приоритет 2: Атрибуты тестирования
    let dataTest = el.getAttribute("data-test") || el.getAttribute("data-testid") || el.getAttribute("data-qa");
    if (dataTest) return `[${el.hasAttribute('data-testid') ? 'data-testid' : (el.hasAttribute('data-test') ? 'data-test' : 'data-qa')}="${CSS.escape(dataTest)}"]`;

    // Приоритет 3: Class (если классы не похожи на автосгенерированные)
    if (el.className && typeof el.className === 'string') {
        let classes = el.className.split(/\s+/).filter(c => c && !/[0-9]/.test(c));
        if (classes.length > 0) {
            let selector = "." + classes.map(c => CSS.escape(c)).join(".");
            // Проверяем уникальность
            try {
                if (document.querySelectorAll(selector).length === 1) return selector;
            } catch(e) {}
        }
    }
    
    // Fallback: строим путь от родителя
    if (el.parentNode && el.parentNode.nodeType === 1) {
        let siblings = Array.from(el.parentNode.children).filter(e => e.tagName === el.tagName);
        let path = generateSelector(el.parentNode);
        if (siblings.length > 1) {
            let index = siblings.indexOf(el) + 1;
            return `${path} > ${el.tagName.toLowerCase()}:nth-of-type(${index})`;
        } else {
             return `${path} > ${el.tagName.toLowerCase()}`;
        }
    }
    
    return el.tagName.toLowerCase();
}

function getInteractiveElements() {
    const elements = document.querySelectorAll('button, a, input, select, textarea, [role="button"], [tabindex]:not([tabindex="-1"])');
    const result = [];
    
    elements.forEach((el, index) => {
        // Проверяем видимость
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden' && window.getComputedStyle(el).display !== 'none') {
            
            let text = el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '';
            text = text.trim().replace(/\n/g, ' ').substring(0, 50);
            
            result.push({
                id: index,
                tag: el.tagName.toLowerCase(),
                text: text,
                selector: generateSelector(el),
                type: el.type || undefined
            });
        }
    });
    return result;
}

// Этот метод может быть вызван из background.js через chrome.scripting.executeScript
// если понадобится получить срез DOM дерева.
window.agentGetDOMContext = function() {
    return {
        url: window.location.href,
        title: document.title,
        interactive_elements: getInteractiveElements()
    };
}
