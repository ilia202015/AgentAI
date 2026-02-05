function isVisible(el) {
    if (!el.offsetParent && el.tagName !== 'BODY') return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

function getInteractiveElements() {
    const all = document.querySelectorAll('*');
    const interactive = [];
    all.forEach(el => {
        if (!isVisible(el)) return;

        const style = window.getComputedStyle(el);
        const isStandard = ['BUTTON', 'A', 'INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);
        const isPointer = style.cursor === 'pointer';

        if (isStandard || isPointer) {
            let text = el.innerText || el.value || '';
            
            // SVG processing
            const svg = el.querySelector('svg');
            if (svg) {
                const label = svg.getAttribute('aria-label') || svg.className.baseVal || 'Graphic';
                text += ` [Icon: ${label}]`;
            }

            interactive.push({
                tagName: el.tagName,
                text: text.trim().substring(0, 50),
                id: el.id.substring(0, 40),
                className: el.className.toString().substring(0, 40),
                rect: el.getBoundingClientRect()
            });
        }
    });
    return interactive;
}

function getCleanHTML() {
    const clone = document.documentElement.cloneNode(true);
    const walk = document.createTreeWalker(clone, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let n;
    while (n = walk.nextNode()) {
        if (n.nodeType === Node.TEXT_NODE) {
            if (n.textContent.length > 500) {
                n.textContent = n.textContent.substring(0, 500) + '...';
            }
        } else if (n.tagName === 'IFRAME') {
            const id = n.id || 'frame-' + Math.random().toString(36).substr(2, 5);
            const src = n.src || 'about:blank';
            const placeholder = document.createElement('iframe');
            placeholder.id = id;
            placeholder.src = src;
            placeholder.innerText = '[Internal Content]';
            n.parentNode.replaceChild(placeholder, n);
        }
    }
    return clone.outerHTML;
}

async function executeSingleAction(action) {
    const el = document.querySelector(action.selector);
    if (!el && action.action !== 'js_exec') return { error: 'Element not found' };

    switch (action.action) {
        case 'hover':
            el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
            el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
            el.dispatchEvent(new MouseEvent('mousemove', { bubbles: true }));
            return { status: 'hovered' };
        
        case 'js_exec':
            try {
                const res = new Function(action.text)();
                return { status: 'executed', result: res };
            } catch (e) {
                return { error: e.message };
            }

        case 'get_text':
            return { text: el.innerText }; // БЕЗ ОБРЕЗКИ

        case 'type':
            el.value = action.text;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return { status: 'typed' };
        
        // ... другие действия (click и т.д.)
    }
}
