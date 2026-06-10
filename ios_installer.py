from nicegui import ui, app


IOS_BANNER_CSS = """
<style>
  .ios-install-banner {
    display: none;
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 10000;
    background: var(--paper, #FBF8F3);
    border-top: 2px solid var(--brass-soft, #D9C79B);
    box-shadow: 0 -4px 20px rgba(0,0,0,0.15);
    padding: 20px 20px calc(env(safe-area-inset-bottom, 0px) + 20px) 20px;
    transform: translateY(100%);
    transition: transform 0.35s cubic-bezier(0.2, 0.8, 0.2, 1);
  }
  .ios-install-banner.visible { display: block; }
  .ios-install-banner.visible.shown { transform: translateY(0); }

  .ios-banner-shell { max-width: 480px; margin: 0 auto; }
  .ios-banner-title {
    font-family: 'Playfair Display', 'Cormorant Garamond', serif;
    font-size: 1.4rem;
    color: var(--ink, #023e8a);
    text-align: center;
    margin-bottom: 6px;
    letter-spacing: 0.01em;
  }
  .ios-banner-sub {
    font-family: 'Cormorant Garamond', serif;
    font-size: 1.05rem;
    color: var(--ink-deep, #021f4d);
    text-align: center;
    margin-bottom: 14px;
    line-height: 1.4;
  }
  .ios-banner-step {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--paper-2, #F5EFE3);
    border: 1px solid var(--brass-soft, #D9C79B);
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 8px;
    font-family: 'Cormorant Garamond', serif;
    font-size: 1rem;
    color: var(--ink-deep, #021f4d);
  }
  .ios-banner-step-num {
    font-weight: 700;
    color: var(--brass, #A07A2E);
    font-size: 1.05rem;
    min-width: 18px;
  }
  .ios-banner-step-text { flex: 1; }
  .ios-banner-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    color: var(--brass, #A07A2E);
    flex-shrink: 0;
  }
  .ios-banner-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 14px;
    gap: 12px;
  }
  .ios-banner-actions .q-btn.ios-banner-ok {
    background: var(--paper, #FBF8F3) !important;
    color: var(--brass, #A07A2E) !important;
    border: 1px solid var(--brass, #A07A2E) !important;
    border-radius: 50px !important;
    padding: 10px 22px !important;
    font-family: 'Cormorant Garamond', serif !important;
    font-size: 1rem !important;
    letter-spacing: 0.03em !important;
    text-transform: none !important;
    transition: background-color 0.2s, color 0.2s !important;
  }
  .ios-banner-actions .q-btn.ios-banner-ok:hover {
    background: var(--brass, #A07A2E) !important;
    color: var(--paper, #FBF8F3) !important;
  }
  .ios-banner-actions .q-btn.ios-banner-skip {
    background: transparent !important;
    color: var(--ink-deep, #021f4d) !important;
    border: none !important;
    font-family: 'Cormorant Garamond', serif !important;
    font-style: italic !important;
    font-size: 0.95rem !important;
    text-transform: none !important;
    text-decoration: underline;
    text-underline-offset: 3px;
  }
</style>
"""


_CLOSE_JS = (
    "var b=document.querySelector('.ios-install-banner');"
    "if(b){b.classList.remove('shown');"
    "setTimeout(function(){b.classList.remove('visible');},350);}"
)


def show_ios_install_banner() -> None:
    if app.storage.user.get('ios_banner_dismissed'):
        return

    ui.add_head_html(IOS_BANNER_CSS)

    share_svg = (
        '<span class="ios-banner-icon">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 16V4"/><path d="M7 9l5-5 5 5"/>'
        '<path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5"/>'
        '</svg></span>'
    )
    plus_svg = (
        '<span class="ios-banner-icon">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="3" width="18" height="18" rx="3"/>'
        '<path d="M12 8v8"/><path d="M8 12h8"/>'
        '</svg></span>'
    )

    with ui.element('div').classes('ios-install-banner'):
        with ui.element('div').classes('ios-banner-shell'):
            ui.html('<div class="ios-banner-title">Instala nuestro catálogo</div>')
            ui.html('<div class="ios-banner-sub">Añade esta app a tu pantalla de inicio para acceder más rápido</div>')
            ui.html(
                f'<div class="ios-banner-step">'
                f'<span class="ios-banner-step-num">1.</span>'
                f'<span class="ios-banner-step-text">Pulsa el botón compartir</span>{share_svg}'
                f'</div>'
            )
            ui.html(
                f'<div class="ios-banner-step">'
                f'<span class="ios-banner-step-num">2.</span>'
                f'<span class="ios-banner-step-text">Selecciona &laquo;Añadir a pantalla de inicio&raquo;</span>{plus_svg}'
                f'</div>'
            )

            def _dismiss_permanent():
                app.storage.user['ios_banner_dismissed'] = True
                ui.run_javascript(_CLOSE_JS)

            def _dismiss_session():
                ui.run_javascript(
                    "sessionStorage.setItem('ios_banner_session_dismissed','1');" + _CLOSE_JS
                )

            with ui.row().classes('ios-banner-actions w-full'):
                ui.button('Ahora no', on_click=_dismiss_session) \
                    .props('flat no-caps').classes('ios-banner-skip')
                ui.button('Entendido', on_click=_dismiss_permanent) \
                    .props('flat no-caps').classes('ios-banner-ok')

    ui.run_javascript("""
        setTimeout(function() {
            try {
                var ua = navigator.userAgent || '';
                var isIOS = /iphone|ipad|ipod/i.test(ua) ||
                            (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
                var isStandalone = window.navigator.standalone === true ||
                                   (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches);
                var isSafari = /^((?!chrome|crios|fxios|android|edgios).)*safari/i.test(ua);
                var dismissed = sessionStorage.getItem('ios_banner_session_dismissed') === '1';
                if (isIOS && !isStandalone && isSafari && !dismissed) {
                    var b = document.querySelector('.ios-install-banner');
                    if (b) {
                        b.classList.add('visible');
                        requestAnimationFrame(function(){
                            requestAnimationFrame(function(){ b.classList.add('shown'); });
                        });
                    }
                }
            } catch(e) {}
        }, 100);
    """)
