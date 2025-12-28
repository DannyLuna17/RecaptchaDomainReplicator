from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class CaptchaHtml:
    """Generated captcha HTML page.

    Attributes:
        filename: Filename for the HTML page.
        content: Full HTML document string.
        path: Absolute/relative file path where the HTML was written, or None if not persisted.
    """

    filename: str
    content: str
    path: str | None


def create_captcha_html(
    download_dir: str,
    website_key: str,
    website_url: str,
    is_invisible: bool = False,
    data_s_value: str | None = None,
    api_domain: str = "google.com",
    is_enterprise: bool = False,
    action: str | None = None,
    persist_html: bool = False,
) -> CaptchaHtml:
    """
    Build an HTML page that renders a ReCAPTCHA widget with the provided parameters.

    Args:
        download_dir (str): Directory to write the HTML file when persistence is enabled.
        website_key (str): ReCAPTCHA sitekey.
        website_url (str): Original page URL.
        is_invisible (bool): Whether to use invisible reCAPTCHA.
        data_s_value (str): Optional data-s value.
        api_domain (str): Domain to load captcha scripts from.
        is_enterprise (bool): Whether this is an enterprise captcha.
        action (str): Action name for invisible/v3.
        persist_html (bool): If True, write the HTML file to disk. Default: False.

    Returns:
        CaptchaHtml: Generated HTML content, with the file path if persisted.
    """
    filename = f"replicated_captcha_{uuid.uuid4()}.html"

    original_domain = urlparse(website_url).netloc if website_url else "unknown"

    api_script = (
        f"//www.{api_domain}/recaptcha/enterprise.js?render=explicit&hl=en"
        if is_enterprise
        else f"//www.{api_domain}/recaptcha/api.js?onload=onRecaptchaLoad&render=explicit&hl=en"
    )

    widget_label = "Invisible" if is_invisible else "Explicit checkbox"
    enterprise_label = "Enterprise" if is_enterprise else "Not enterprise"
    action_row = f'<dt>Action</dt><dd class="mono">{action}</dd>' if action else ""
    stoken_row = f'<dt>stoken</dt><dd class="mono">{data_s_value}</dd>' if data_s_value else ""
    execute_button_html = (
        '<button class="button primary" id="execute-btn" type="button" '
        'onclick="executeInvisibleRecaptcha()" disabled>Execute</button>'
        if is_invisible
        else ""
    )

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ReCAPTCHA replica</title>
    <script src="{api_script}" async defer></script>
    <style>
        :root {{
            color-scheme: light dark;

            --bg: #ffffff;
            --fg: #000000;
            --muted: #666666;
            --border: #eaeaea;
            --card: #ffffff;
            --subtle: #fafafa;
            --radius: 16px;
            --shadow: 0 1px 2px rgba(0, 0, 0, 0.06), 0 18px 42px rgba(0, 0, 0, 0.08);

            --font: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
                Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
            --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
                "Courier New", monospace;

            --success: #0a7f2e;
            --warning: #b45309;
            --danger: #b91c1c;

            --accent: #000000;
            --accent-contrast: #ffffff;
        }}

        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #000000;
                --fg: #ffffff;
                --muted: #a1a1aa;
                --border: #27272a;
                --card: #0a0a0a;
                --subtle: #111111;
                --shadow: none;

                --success: #22c55e;
                --warning: #f59e0b;
                --danger: #ef4444;

                --accent: #ffffff;
                --accent-contrast: #000000;
            }}
        }}

        * {{
            box-sizing: border-box;
        }}

        html,
        body {{
            height: 100%;
        }}

        body {{
            margin: 0;
            font-family: var(--font);
            background: var(--bg);
            color: var(--fg);
            line-height: 1.5;
        }}

        .page {{
            min-height: 100%;
            padding: 28px 16px 64px;
            display: flex;
            justify-content: center;
            align-items: flex-start;
        }}

        .card {{
            width: 100%;
            max-width: 980px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            overflow: hidden;
        }}

        .header {{
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 16px;
            align-items: flex-start;
            justify-content: space-between;
            flex-wrap: wrap;
        }}

        .title {{
            margin: 0;
            font-size: 18px;
            font-weight: 600;
            letter-spacing: -0.01em;
        }}

        .subtitle {{
            margin: 6px 0 0;
            font-size: 13px;
            color: var(--muted);
        }}

        .badges {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
        }}

        .badge {{
            font-size: 12px;
            color: var(--muted);
            background: var(--subtle);
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 4px 10px;
            white-space: nowrap;
        }}

        .content {{
            padding: 24px;
            display: grid;
            gap: 16px;
        }}

        .grid {{
            display: grid;
            gap: 16px;
            grid-template-columns: 1fr;
        }}

        @media (min-width: 900px) {{
            .grid {{
                grid-template-columns: 1fr 1fr;
            }}
        }}

        .panel {{
            background: var(--subtle);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
        }}

        .panel-title {{
            margin: 0 0 10px;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: -0.01em;
        }}

        .panel-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }}

        .panel-head .panel-title {{
            margin: 0;
        }}

        dl.kv {{
            display: grid;
            grid-template-columns: 140px 1fr;
            gap: 8px 12px;
            margin: 0;
        }}

        dl.kv dt {{
            margin: 0;
            font-size: 11px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            line-height: 1.4;
        }}

        dl.kv dd {{
            margin: 0;
            font-size: 13px;
            word-break: break-word;
        }}

        .mono {{
            font-family: var(--mono);
        }}

        .recaptcha-wrap {{
            margin-top: 0;
            padding: 8px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
        }}

        .challenge-row {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: flex-start;
            gap: 12px;
        }}

        .status {{
            margin-top: 10px;
            font-size: 13px;
            color: var(--muted);
        }}

        .status[data-state="success"] {{
            color: var(--success);
        }}

        .status[data-state="warning"] {{
            color: var(--warning);
        }}

        .status[data-state="error"] {{
            color: var(--danger);
        }}

        .error {{
            margin-top: 10px;
            font-size: 13px;
            color: var(--danger);
        }}

        .error:empty {{
            display: none;
        }}

        .actions {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 12px;
        }}

        .challenge-row .actions {{
            margin-top: 0;
        }}

        .button {{
            appearance: none;
            border: 1px solid var(--border);
            background: var(--fg);
            color: var(--card);
            border-radius: 999px;
            padding: 8px 12px;
            font-size: 13px;
            cursor: pointer;
            transition: transform 120ms ease, filter 120ms ease;
        }}

        .button:hover:not(:disabled) {{
            filter: brightness(0.98);
        }}

        .button:active:not(:disabled) {{
            transform: translateY(1px);
        }}

        .button:disabled {{
            opacity: 0.55;
            cursor: not-allowed;
        }}

        .button.primary {{
            background: var(--accent);
            color: var(--accent-contrast);
            border-color: var(--accent);
        }}

        .token {{
            margin: 8px 0 0;
            font-family: var(--mono);
            font-size: 12px;
            line-height: 1.45;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px;
            min-height: 110px;
            max-height: 180px;
            overflow: auto;
            white-space: pre-wrap;
            word-break: break-word;
        }}

        .note {{
            margin: 10px 0 0;
            font-size: 12px;
            color: var(--muted);
        }}

        #copy-feedback:empty {{
            display: none;
        }}
    </style>
    <script>
        var recaptchaWidgetId = null;
        var recaptchaReady = false;
        var isEnterprise = {str(is_enterprise).lower()};
        var isInvisible = {str(is_invisible).lower()};
        var recaptchaAction = {f'"{action}"' if action else "null"};

        function getGrecaptcha() {{
            if (isEnterprise) {{
                return typeof grecaptcha !== 'undefined' && grecaptcha.enterprise
                    ? grecaptcha.enterprise
                    : null;
            }}
            return typeof grecaptcha !== 'undefined' ? grecaptcha : null;
        }}

        function setStatus(message, state) {{
            var el = document.getElementById('status-message');
            if (!el) return;
            el.textContent = message || '';
            if (state) el.dataset.state = state;
        }}

        function setError(message) {{
            var el = document.getElementById('error-message');
            if (!el) return;
            el.textContent = (message || '').toString().trim();
        }}

        function setCopyFeedback(message) {{
            var el = document.getElementById('copy-feedback');
            if (!el) return;
            el.textContent = message || '';
            if (message) {{
                clearTimeout(window._copy_feedback_timer);
                window._copy_feedback_timer = setTimeout(function() {{
                    el.textContent = '';
                }}, 1500);
            }}
        }}

        function onCaptchaSuccess(token) {{
            console.log('Token received:', token.substring(0, 50) + '...');
            document.getElementById('g-recaptcha-response-display').innerText = token;
            setError('');
            setStatus('Token received.', 'success');
        }}

        function onCaptchaError(error) {{
            console.error('reCAPTCHA error:', error);
            setError('reCAPTCHA Error: ' + (error || 'Unknown error'));
            setStatus('reCAPTCHA error.', 'error');
        }}

        function onCaptchaExpired() {{
            console.log('reCAPTCHA expired');
            setStatus('Token expired. Please solve again.', 'warning');
            document.getElementById('g-recaptcha-response-display').innerText = '[Token expired]';
        }}

        function renderRecaptcha() {{
            var gc = getGrecaptcha();
            if (!gc) {{
                console.log('grecaptcha not ready, retrying...');
                setTimeout(renderRecaptcha, 100);
                return;
            }}

            try {{
                var params = {{
                    'sitekey': '{website_key}',
                    'callback': onCaptchaSuccess,
                    'error-callback': onCaptchaError,
                    'expired-callback': onCaptchaExpired
                }};

                if (isInvisible) {{
                    params['size'] = 'invisible';
                }}

                {f"params['stoken'] = '{data_s_value}';" if data_s_value else ""}

                recaptchaWidgetId = gc.render('recaptcha-container', params);
                recaptchaReady = true;

                console.log('reCAPTCHA rendered with widget ID:', recaptchaWidgetId);

                var execBtn = document.getElementById('execute-btn');
                if (execBtn) {{
                    execBtn.disabled = false;
                }}

                if (isInvisible) {{
                    setStatus('Invisible reCAPTCHA loaded. Executing…', 'idle');
                    setTimeout(function() {{
                        executeInvisibleRecaptcha();
                    }}, 1500);
                }} else {{
                    setStatus('reCAPTCHA loaded. Please solve the challenge.', 'idle');
                }}
            }} catch (e) {{
                console.error('Error rendering reCAPTCHA:', e);
                setError('Error rendering reCAPTCHA: ' + e.message);
                setStatus('Failed to render reCAPTCHA.', 'error');
            }}
        }}

        function executeInvisibleRecaptcha() {{
            var gc = getGrecaptcha();
            if (!gc) {{
                setCopyFeedback('reCAPTCHA not loaded yet.');
                return;
            }}

            if (!recaptchaReady || recaptchaWidgetId === null) {{
                setCopyFeedback('Widget not ready yet.');
                return;
            }}

            try {{
                console.log(
                    'Executing invisible reCAPTCHA with widget ID:',
                    recaptchaWidgetId,
                    'action:',
                    recaptchaAction
                );
                setStatus('Executing reCAPTCHA challenge…', 'idle');
                if (recaptchaAction) {{
                    gc.execute(recaptchaWidgetId, {{ action: recaptchaAction }});
                }} else {{
                    gc.execute(recaptchaWidgetId);
                }}
            }} catch (e) {{
                console.error('Error executing reCAPTCHA:', e);
                setError('Error executing reCAPTCHA: ' + e.message);
                setStatus('Failed to execute reCAPTCHA.', 'error');
            }}
        }}

        function resetRecaptcha() {{
            var gc = getGrecaptcha();
            if (gc && recaptchaWidgetId !== null) {{
                gc.reset(recaptchaWidgetId);
                var display = document.getElementById('g-recaptcha-response-display');
                if (display) {{
                    display.innerText = '[No token yet]';
                }}
                setError('');
                setStatus('Reset. Ready to solve again.', 'idle');
            }}
        }}

        function copyToken() {{
            const tokenText = document.getElementById('g-recaptcha-response-display').innerText;
            if (!tokenText || tokenText === '[No token yet]' || tokenText === '[Token expired]') {{
                setCopyFeedback('No token to copy.');
                return;
            }}

            const done = () => setCopyFeedback('Copied to clipboard.');
            const fail = () => setCopyFeedback('Copy failed - select the token and copy manually.');

            if (navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(tokenText).then(done).catch(() => {{
                    try {{
                        var textArea = document.createElement('textarea');
                        textArea.value = tokenText;
                        document.body.appendChild(textArea);
                        textArea.select();
                        document.execCommand('copy');
                        document.body.removeChild(textArea);
                        done();
                    }} catch (e) {{
                        fail();
                    }}
                }});
                return;
            }}

            try {{
                var textArea = document.createElement('textarea');
                textArea.value = tokenText;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                done();
            }} catch (e) {{
                fail();
            }}
        }}

        function initRecaptcha() {{
            var gc = getGrecaptcha();
            if (gc && gc.render) {{
                renderRecaptcha();
            }} else {{
                console.log('Waiting for grecaptcha to load...');
                setTimeout(initRecaptcha, 100);
            }}
        }}

        function onRecaptchaLoad() {{
            console.log('reCAPTCHA API loaded (onload callback)');
            renderRecaptcha();
        }}

        window.onload = function() {{
            if (!recaptchaReady) {{
                setStatus('Loading reCAPTCHA…', 'idle');
            }}
            if (isEnterprise) {{
                initRecaptcha();
            }}
        }}
    </script>
</head>
<body>
    <main class="page">
        <section class="card">
            <header class="header">
                <div>
                    <h1 class="title">ReCAPTCHA replica</h1>
                    <p class="subtitle">Solve the challenge to generate a token.</p>
                </div>
            </header>

            <div class="content">
                <div class="grid">
                    <section class="panel">
                        <p class="panel-title">Details</p>
                        <dl class="kv">
                            <dt>Replicating</dt>
                            <dd class="mono">{original_domain}</dd>

                            <dt>Widget</dt>
                            <dd>{widget_label} · {enterprise_label}</dd>

                            <dt>Recaptcha API domain</dt>
                            <dd class="mono">www.{api_domain}</dd>

                            <dt>Website URL</dt>
                            <dd class="mono">{website_url}</dd>

                            <dt>Site key</dt>
                            <dd class="mono">{website_key}</dd>

                            {action_row}
                            {stoken_row}
                        </dl>
                    </section>

                    <section class="panel">
                        <p class="panel-title">Challenge</p>
                        <div class="challenge-row">
                            <div class="recaptcha-wrap">
                                <div id="recaptcha-container"></div>
                            </div>

                            <div class="actions">
                                {execute_button_html}
                                <button
                                    class="button"
                                    type="button"
                                    onclick="resetRecaptcha()"
                                >
                                    Reset
                                </button>
                            </div>
                        </div>

                        <div id="status-message" class="status" data-state="idle">
                            Initializing...
                        </div>
                        <div id="error-message" class="error" aria-live="polite"></div>
                    </section>
                </div>

                <section class="panel">
                    <div class="panel-head">
                        <p class="panel-title">Token</p>
                        <button
                            class="button primary"
                            id="copy-btn"
                            type="button"
                            onclick="copyToken()"
                        >
                            Copy token
                        </button>
                    </div>
                    <pre class="token" id="g-recaptcha-response-display">[No token yet]</pre>
                    <div id="copy-feedback" class="note" aria-live="polite"></div>
                    <p class="note">
                        If you see “Invalid domain for site key”, the site key is domain-restricted.
                        Try enabling domain bypass.
                    </p>
                </section>
            </div>
        </section>
    </main>
</body>
</html>
"""

    # The replicator can serve the HTML from memory,
    # so we don't write to disk unless persistence is enabled.
    html_file_path: str | None = None
    if persist_html:
        os.makedirs(download_dir, exist_ok=True)
        html_file_path = os.path.join(download_dir, filename)
        with open(html_file_path, "w", encoding="utf-8", newline="\n") as file:
            file.write(html_content)

    return CaptchaHtml(filename=filename, content=html_content, path=html_file_path)
