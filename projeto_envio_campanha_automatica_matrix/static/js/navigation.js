/**
 * Navigation JS - Controle de Navegação e Sidebar
 */

(function() {
    'use strict';

    // Elementos
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');

    // Estado da sidebar (salvo em localStorage)
    const SIDEBAR_STATE_KEY = 'sidebar_collapsed';

    /**
     * Inicializar estado da sidebar
     */
    function initSidebarState() {
        const isCollapsed = localStorage.getItem(SIDEBAR_STATE_KEY) === 'true';
        if (isCollapsed && window.innerWidth > 1024) {
            sidebar.classList.add('collapsed');
        }
    }

    /**
     * Toggle sidebar (desktop)
     */
    function toggleSidebar() {
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem(SIDEBAR_STATE_KEY, isCollapsed);
    }

    /**
     * Toggle sidebar mobile
     */
    function toggleMobileSidebar() {
        sidebar.classList.toggle('mobile-open');
        sidebarOverlay.classList.toggle('active');
        document.body.style.overflow = sidebar.classList.contains('mobile-open') ? 'hidden' : '';
    }

    /**
     * Fechar sidebar mobile
     */
    function closeMobileSidebar() {
        sidebar.classList.remove('mobile-open');
        sidebarOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    /**
     * Lidar com redimensionamento da janela
     */
    function handleResize() {
        if (window.innerWidth > 768) {
            closeMobileSidebar();
        }
    }

    // Event Listeners
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', toggleSidebar);
    }

    if (mobileMenuToggle) {
        mobileMenuToggle.addEventListener('click', toggleMobileSidebar);
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeMobileSidebar);
    }

    // Fechar sidebar mobile ao clicar em um link
    document.querySelectorAll('.sidebar .nav-item').forEach(function(link) {
        link.addEventListener('click', function() {
            if (window.innerWidth <= 768) {
                closeMobileSidebar();
            }
        });
    });

    window.addEventListener('resize', handleResize);

    // Inicializar
    initSidebarState();

    /**
     * Busca Global
     */
    const searchTrigger = document.getElementById('searchTrigger');
    const searchModal = document.getElementById('searchModal');
    const globalSearch = document.getElementById('globalSearch');
    const searchResults = document.getElementById('searchResults');

    let searchTimeout;

    function openSearchModal() {
        searchModal.classList.add('active');
        globalSearch.focus();
    }

    function closeSearchModal() {
        searchModal.classList.remove('active');
        globalSearch.value = '';
        searchResults.innerHTML = '';
    }

    function performSearch(query) {
        if (!query || query.length < 2) {
            searchResults.innerHTML = '<div style="padding: 1rem; text-align: center; color: var(--text-tertiary);">Digite pelo menos 2 caracteres para buscar</div>';
            return;
        }

        // Mostrar loading
        searchResults.innerHTML = '<div style="padding: 1rem; text-align: center;"><div class="spinner spinner-sm" style="margin: 0 auto;"></div></div>';

        // Fazer requisição de busca
        fetch(`/api/busca-global/?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                displaySearchResults(data);
            })
            .catch(error => {
                console.error('Erro na busca:', error);
                searchResults.innerHTML = '<div style="padding: 1rem; text-align: center; color: var(--color-danger-600);">Erro ao buscar. Tente novamente.</div>';
            });
    }

    function displaySearchResults(data) {
        let html = '';
        let hasResults = false;

        // Campanhas de Email
        if (data.campanhas_email && data.campanhas_email.length > 0) {
            hasResults = true;
            html += '<div style="padding: 0.5rem 1rem; font-size: 0.75rem; font-weight: 600; color: var(--text-tertiary); text-transform: uppercase;">Campanhas de Email</div>';
            data.campanhas_email.forEach(function(item) {
                html += `<a href="/emails/campanhas/${item.id}/" class="dropdown-item">
                    <i data-feather="mail" style="width: 16px; height: 16px; margin-right: 0.5rem;"></i>
                    ${item.nome}
                </a>`;
            });
        }

        // Envios HSM
        if (data.envios_hsm && data.envios_hsm.length > 0) {
            hasResults = true;
            html += '<div style="padding: 0.5rem 1rem; font-size: 0.75rem; font-weight: 600; color: var(--text-tertiary); text-transform: uppercase; margin-top: 0.5rem;">Envios WhatsApp</div>';
            data.envios_hsm.forEach(function(item) {
                html += `<a href="/whatsapp/envio-hsm/${item.id}/" class="dropdown-item">
                    <i data-feather="message-circle" style="width: 16px; height: 16px; margin-right: 0.5rem;"></i>
                    ${item.titulo}
                </a>`;
            });
        }

        // Campanhas Native
        if (data.campanhas_native && data.campanhas_native.length > 0) {
            hasResults = true;
            html += '<div style="padding: 0.5rem 1rem; font-size: 0.75rem; font-weight: 600; color: var(--text-tertiary); text-transform: uppercase; margin-top: 0.5rem;">Campanhas Native</div>';
            data.campanhas_native.forEach(function(item) {
                html += `<a href="/native/${item.id}/" class="dropdown-item">
                    <i data-feather="phone" style="width: 16px; height: 16px; margin-right: 0.5rem;"></i>
                    ${item.name}
                </a>`;
            });
        }

        if (!hasResults) {
            html = '<div style="padding: 2rem; text-align: center; color: var(--text-tertiary);">Nenhum resultado encontrado</div>';
        }

        searchResults.innerHTML = html;
        feather.replace();
    }

    if (searchTrigger) {
        searchTrigger.addEventListener('click', openSearchModal);
    }

    if (globalSearch) {
        globalSearch.addEventListener('input', function(e) {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(function() {
                performSearch(e.target.value);
            }, 300);
        });
    }

    // Fechar modal de busca ao clicar fora
    document.addEventListener('click', function(e) {
        if (searchModal && !searchModal.contains(e.target) && e.target !== searchTrigger && !searchTrigger.contains(e.target)) {
            closeSearchModal();
        }
    });

    // ESC para fechar busca
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && searchModal.classList.contains('active')) {
            closeSearchModal();
        }
    });

    /**
     * Notificações
     */
    const notificationsButton = document.getElementById('notificationsButton');
    const notificationsDropdown = document.getElementById('notificationsDropdown');
    const notificationBadge = document.getElementById('notificationBadge');
    const notificationsBody = document.getElementById('notificationsBody');
    const markAllReadBtn = document.getElementById('markAllReadBtn');

    function loadNotifications(showInDropdown = false) {
        fetch('/api/notificacoes/?apenas_nao_lidas=false&limite=50')
            .then(response => response.json())
            .then(data => {
                const unreadCount = data.filter(n => !n.lida).length;
                
                // Atualizar badge
                if (notificationBadge) {
                    notificationBadge.textContent = unreadCount;
                    notificationBadge.style.display = unreadCount > 0 ? 'flex' : 'none';
                }
                
                // Atualizar dropdown se estiver aberto
                if (showInDropdown && notificationsBody) {
                    renderNotifications(data);
                }
            })
            .catch(error => {
                console.error('Erro ao carregar notificações:', error);
            });
    }

    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
               document.querySelector('meta[name="csrf-token"]')?.content || '';
    }

    function renderNotifications(notifications) {
        if (notifications.length === 0) {
            notificationsBody.innerHTML = `
                <div class="notifications-empty">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>
                        <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>
                    </svg>
                    <p style="margin: 0; font-weight: 600;">Nenhuma notificação</p>
                    <p style="margin: var(--space-xs) 0 0 0; font-size: var(--font-size-xs);">Você está em dia!</p>
                </div>
            `;
            return;
        }

        notificationsBody.innerHTML = notifications.map(notif => `
            <div class="notification-item ${!notif.lida ? 'unread' : ''}" data-id="${notif.id}" data-url="${notif.url || '#'}" style="position: relative;">
                <div class="notification-icon-wrapper notification-icon-${notif.cor}">
                    <i data-feather="${notif.icone}"></i>
                </div>
                <div class="notification-content" style="cursor: pointer;">
                    <p class="notification-title">${notif.titulo}</p>
                    <p class="notification-message">${notif.mensagem}</p>
                    <span class="notification-time">${notif.tempo_relativo} atrás</span>
                </div>
                <div class="notification-item-actions">
                    ${!notif.lida ? `
                        <button class="btn-icon-sm btn-mark-read" title="Marcar como lida" data-id="${notif.id}">
                            <i data-feather="check"></i>
                        </button>
                    ` : ''}
                    <button class="btn-icon-sm btn-delete" title="Excluir" data-id="${notif.id}">
                        <i data-feather="trash-2"></i>
                    </button>
                </div>
            </div>
        `).join('');

        // Re-inicializar ícones Feather
        if (typeof feather !== 'undefined') {
            feather.replace();
        }

        // Adicionar event listeners para o conteúdo (marcar como lida e redirecionar)
        document.querySelectorAll('.notification-content').forEach(content => {
            content.addEventListener('click', function(e) {
                const item = this.closest('.notification-item');
                const notifId = item.dataset.id;
                const url = item.dataset.url;
                const isUnread = item.classList.contains('unread');
                
                // Marcar como lida se não estiver lida
                if (isUnread) {
                    fetch(`/api/notificacoes/${notifId}/marcar-lida/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCsrfToken(),
                        }
                    }).then(() => {
                        // Atualizar contadores
                        loadNotifications(false);
                        
                        // Redirecionar se tiver URL
                        if (url && url !== '#' && url !== 'None') {
                            window.location.href = url;
                        }
                    });
                } else if (url && url !== '#' && url !== 'None') {
                    // Redirecionar diretamente se já estiver lida
                    window.location.href = url;
                }
            });
        });

        // Event listeners para marcar como lida
        document.querySelectorAll('.btn-mark-read').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const notifId = this.dataset.id;
                
                fetch(`/api/notificacoes/${notifId}/marcar-lida/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                    }
                }).then(() => {
                    loadNotifications(true);
                });
            });
        });

        // Event listeners para deletar
        document.querySelectorAll('.btn-delete').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const notifId = this.dataset.id;
                
                if (confirm('Deseja realmente excluir esta notificação?')) {
                    fetch(`/api/notificacoes/${notifId}/deletar/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCsrfToken(),
                        }
                    }).then(() => {
                        loadNotifications(true);
                    });
                }
            });
        });
    }

    // Toggle dropdown
    if (notificationsButton && notificationsDropdown) {
        notificationsButton.addEventListener('click', function(e) {
            e.stopPropagation();
            notificationsDropdown.classList.toggle('active');
            
            if (notificationsDropdown.classList.contains('active')) {
                loadNotifications(true);
            }
        });

        // Fechar ao clicar fora
        document.addEventListener('click', function(e) {
            if (!notificationsButton.contains(e.target) && !notificationsDropdown.contains(e.target)) {
                notificationsDropdown.classList.remove('active');
            }
        });
    }

    // Marcar todas como lidas
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            
            if (confirm('Marcar todas as notificações como lidas?')) {
                fetch('/api/notificacoes/marcar-todas-lidas/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                    }
                }).then(() => {
                    loadNotifications(true);
                });
            }
        });
    }

    // Limpar todas as notificações
    const clearAllBtn = document.getElementById('clearAllBtn');
    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            
            if (confirm('Deseja realmente excluir TODAS as notificações? Esta ação não pode ser desfeita.')) {
                fetch('/api/notificacoes/limpar-todas/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                    }
                }).then(response => response.json()).then(data => {
                    if (data.status === 'success') {
                        loadNotifications(true);
                    }
                });
            }
        });
    }

    // Carregar notificações a cada 30 segundos
    if (notificationsButton) {
        loadNotifications(false);
        setInterval(() => loadNotifications(false), 30000);
    }

    /**
     * Smooth Scroll para âncoras
     */
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });

    /**
     * User Menu Dropdown
     */
    const userMenuButton = document.getElementById('userMenuButton');
    const userDropdown = document.getElementById('userDropdown');

    if (userMenuButton && userDropdown) {
        userMenuButton.addEventListener('click', function(e) {
            e.stopPropagation();
            userDropdown.classList.toggle('active');
        });

        // Fechar dropdown ao clicar fora
        document.addEventListener('click', function(e) {
            if (!userMenuButton.contains(e.target) && !userDropdown.contains(e.target)) {
                userDropdown.classList.remove('active');
            }
        });

        // Fechar dropdown ao pressionar ESC
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && userDropdown.classList.contains('active')) {
                userDropdown.classList.remove('active');
            }
        });
    }

    /**
     * Auto-fechar alerts após 5 segundos
     */
    document.querySelectorAll('.alert').forEach(function(alert) {
        setTimeout(function() {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(function() {
                alert.remove();
            }, 300);
        }, 5000);
    });

})();
