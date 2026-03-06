/**
 * Keyboard Shortcuts JS - Atalhos de Teclado
 */

(function() {
    'use strict';

    // Mapeamento de atalhos
    const shortcuts = {
        // Ctrl/Cmd + K - Busca global
        'k': function(e) {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                const searchModal = document.getElementById('searchModal');
                const globalSearch = document.getElementById('globalSearch');
                if (searchModal && globalSearch) {
                    searchModal.classList.add('active');
                    globalSearch.focus();
                }
            }
        },

        // Ctrl/Cmd + D - Dashboard
        'd': function(e) {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                window.location.href = '/';
            }
        },

        // Ctrl/Cmd + 1 - Módulo WhatsApp
        '1': function(e) {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                window.location.href = '/whatsapp/';
            }
        },

        // Ctrl/Cmd + 2 - Módulo Emails
        '2': function(e) {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                window.location.href = '/emails/';
            }
        },

        // Ctrl/Cmd + 3 - Módulo Native
        '3': function(e) {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                window.location.href = '/native/';
            }
        },

        // Ctrl/Cmd + N - Nova campanha (contextual)
        'n': function(e) {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                const currentPath = window.location.pathname;
                
                if (currentPath.includes('/emails/')) {
                    window.location.href = '/emails/campanhas/nova/';
                } else if (currentPath.includes('/whatsapp/')) {
                    window.location.href = '/whatsapp/processar-consulta/';
                } else if (currentPath.includes('/native/')) {
                    // Native não tem criar via interface, redireciona para lista
                    window.location.href = '/native/';
                }
            }
        },

        // ESC - Fechar modais/busca
        'Escape': function(e) {
            // Fechar busca
            const searchModal = document.getElementById('searchModal');
            if (searchModal && searchModal.classList.contains('active')) {
                searchModal.classList.remove('active');
            }

            // Fechar quaisquer modais abertos
            document.querySelectorAll('.modal.active').forEach(function(modal) {
                modal.classList.remove('active');
            });

            // Fechar overlay de sidebar mobile
            const sidebarOverlay = document.getElementById('sidebarOverlay');
            if (sidebarOverlay && sidebarOverlay.classList.contains('active')) {
                sidebarOverlay.click();
            }
        },

        // ? - Mostrar ajuda de atalhos
        '?': function(e) {
            if (!e.ctrlKey && !e.metaKey && !e.shiftKey) {
                e.preventDefault();
                showShortcutsHelp();
            }
        }
    };

    /**
     * Handler principal de teclas
     */
    document.addEventListener('keydown', function(e) {
        // Ignorar se estiver em input/textarea/select
        const tagName = e.target.tagName.toLowerCase();
        if (['input', 'textarea', 'select'].includes(tagName)) {
            // Exceto para ESC e Ctrl+K que funcionam em qualquer lugar
            if (e.key !== 'Escape' && !(e.key === 'k' && (e.ctrlKey || e.metaKey))) {
                return;
            }
        }

        const handler = shortcuts[e.key];
        if (handler) {
            handler(e);
        }
    });

    /**
     * Mostrar modal de ajuda com todos os atalhos
     */
    function showShortcutsHelp() {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        const modKey = isMac ? '⌘' : 'Ctrl';

        const helpHTML = `
            <div class="modal-backdrop active" id="shortcutsHelpBackdrop" onclick="this.remove(); document.getElementById('shortcutsHelpModal').remove();">
                <div class="modal active" id="shortcutsHelpModal" onclick="event.stopPropagation();" style="max-width: 500px;">
                    <div class="modal-header">
                        <h3 class="modal-title">Atalhos de Teclado</h3>
                        <button class="modal-close" onclick="document.getElementById('shortcutsHelpBackdrop').click();">
                            <i data-feather="x"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        <div style="display: grid; gap: 1rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>Busca Global</span>
                                <kbd style="padding: 0.25rem 0.5rem; background: var(--bg-tertiary); border-radius: 0.25rem; font-size: 0.875rem;">${modKey} + K</kbd>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>Ir para Dashboard</span>
                                <kbd style="padding: 0.25rem 0.5rem; background: var(--bg-tertiary); border-radius: 0.25rem; font-size: 0.875rem;">${modKey} + D</kbd>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>Módulo WhatsApp</span>
                                <kbd style="padding: 0.25rem 0.5rem; background: var(--bg-tertiary); border-radius: 0.25rem; font-size: 0.875rem;">${modKey} + 1</kbd>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>Módulo Emails</span>
                                <kbd style="padding: 0.25rem 0.5rem; background: var(--bg-tertiary); border-radius: 0.25rem; font-size: 0.875rem;">${modKey} + 2</kbd>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>Módulo Native</span>
                                <kbd style="padding: 0.25rem 0.5rem; background: var(--bg-tertiary); border-radius: 0.25rem; font-size: 0.875rem;">${modKey} + 3</kbd>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>Nova Campanha</span>
                                <kbd style="padding: 0.25rem 0.5rem; background: var(--bg-tertiary); border-radius: 0.25rem; font-size: 0.875rem;">${modKey} + N</kbd>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>Fechar Modal/Busca</span>
                                <kbd style="padding: 0.25rem 0.5rem; background: var(--bg-tertiary); border-radius: 0.25rem; font-size: 0.875rem;">ESC</kbd>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span>Mostrar esta ajuda</span>
                                <kbd style="padding: 0.25rem 0.5rem; background: var(--bg-tertiary); border-radius: 0.25rem; font-size: 0.875rem;">?</kbd>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Inserir no body
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = helpHTML.trim();
        document.body.appendChild(tempDiv.firstChild);

        // Inicializar ícones
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    }

    // Hint visual do atalho de ajuda (opcional)
    window.addEventListener('load', function() {
        // Aguardar 2 segundos e mostrar hint
        setTimeout(function() {
            const hint = document.createElement('div');
            hint.innerHTML = 'Pressione <kbd style="padding: 0.25rem 0.5rem; background: var(--bg-tertiary); border-radius: 0.25rem; font-size: 0.75rem;">?</kbd> para ver atalhos';
            hint.style.cssText = 'position: fixed; bottom: 1rem; right: 1rem; background: var(--bg-primary); border: 1px solid var(--border-primary); border-radius: 0.5rem; padding: 0.75rem 1rem; font-size: 0.875rem; box-shadow: var(--shadow-lg); z-index: 1000; animation: slideInRight 0.3s ease-out;';
            
            document.body.appendChild(hint);

            // Remover após 5 segundos
            setTimeout(function() {
                hint.style.animation = 'fadeOut 0.3s ease-out';
                setTimeout(function() {
                    hint.remove();
                }, 300);
            }, 5000);
        }, 2000);
    });

})();
