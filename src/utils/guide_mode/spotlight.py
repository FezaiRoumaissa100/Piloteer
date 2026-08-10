def get_spotlight_js(description: str) -> str:
    """
    Returns the JavaScript snippet to inject a non-intrusive orange spotlight 
    (halo) and a Driver.js-style popup card with the given description.
    """
    safe_description = description.replace("'", "\\'").replace('"', '\\"')

    return """
    (element) => {
        const rect = element.getBoundingClientRect();

        // --- HALO ---
        const halo = document.createElement('div');
        halo.id = 'piloteer-halo';
        halo.style.cssText = `
            position: fixed;
            top: ${rect.top - 4}px;
            left: ${rect.left - 4}px;
            width: ${rect.width + 8}px;
            height: ${rect.height + 8}px;
            border: 2px solid #ff9900;
            box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.6), 0 0 15px 5px rgba(255, 153, 0, 0.8) inset, 0 0 15px 5px rgba(255, 153, 0, 0.8);
            border-radius: 4px;
            z-index: 99998;
            pointer-events: none;
            transition: all 0.3s ease;
        `;
        document.body.appendChild(halo);

        // --- POPUP CARD ---
        const popup = document.createElement('div');
        popup.id = 'piloteer-popup';

        const POPUP_WIDTH = 320;
        const ARROW_SIZE = 10;
        const MARGIN = 12;

        // Smart positioning: show below if element is in top half, above if in bottom half
        const spaceBelow = window.innerHeight - rect.bottom;
        const showBelow = spaceBelow > 120 || rect.top < window.innerHeight / 2;

        // Horizontal: align with element, keep within viewport
        let leftPos = rect.left + rect.width / 2 - POPUP_WIDTH / 2;
        leftPos = Math.max(MARGIN, Math.min(leftPos, window.innerWidth - POPUP_WIDTH - MARGIN));

        // Arrow horizontal offset relative to popup
        const arrowCenter = (rect.left + rect.width / 2) - leftPos;
        const arrowClamp = Math.max(16, Math.min(arrowCenter, POPUP_WIDTH - 16));

        const topPos    = showBelow ? rect.bottom + ARROW_SIZE + 4 : rect.top - ARROW_SIZE - 4;
        const arrowTop  = showBelow ? `-${ARROW_SIZE}px` : 'auto';
        const arrowBot  = showBelow ? 'auto' : `-${ARROW_SIZE}px`;
        const arrowBorder = showBelow
            ? `transparent transparent #ffffff transparent`
            : `#ffffff transparent transparent transparent`;

        popup.style.cssText = `
            position: fixed;
            top: ${showBelow ? topPos : 'auto'}px;
            bottom: ${showBelow ? 'auto' : window.innerHeight - rect.top + ARROW_SIZE + 4 + 'px'};
            left: ${leftPos}px;
            width: ${POPUP_WIDTH}px;
            background: #ffffff;
            color: #1a1a1a;
            padding: 14px 16px;
            border-radius: 10px;
            z-index: 99999;
            font-size: 14px;
            line-height: 1.5;
            white-space: normal;
            word-wrap: break-word;
            border: 1px solid rgba(0,0,0,0.1);
            box-shadow: 0 8px 24px rgba(0,0,0,0.18), 0 2px 6px rgba(0,0,0,0.1);
            pointer-events: none;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            animation: piloteer-fadein 0.2s ease;
        `;

        // Arrow element
        const arrow = document.createElement('div');
        arrow.style.cssText = `
            position: absolute;
            left: ${arrowClamp}px;
            top: ${arrowTop};
            bottom: ${arrowBot};
            transform: translateX(-50%%);
            width: 0;
            height: 0;
            border-width: ${ARROW_SIZE}px;
            border-style: solid;
            border-color: ${arrowBorder};
        `;

        // Fade-in animation
        const style = document.createElement('style');
        style.textContent = `@keyframes piloteer-fadein { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }`;
        document.head.appendChild(style);

        popup.innerText = '%s';
        popup.appendChild(arrow);
        document.body.appendChild(popup);
    }
    """ % safe_description


def get_cleanup_js() -> str:
    """
    Returns the JavaScript snippet to remove the spotlight elements.
    """
    return "() => { document.getElementById('piloteer-halo')?.remove(); document.getElementById('piloteer-popup')?.remove(); }"
