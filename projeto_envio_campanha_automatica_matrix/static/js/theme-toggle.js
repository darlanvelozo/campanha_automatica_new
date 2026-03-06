/**
 * Theme Toggle JS - Alternar entre tema claro e escuro
 */

(function() {
    'use strict';

    const THEME_KEY = 'theme_preference';
    const themeToggle = document.getElementById('themeToggle');
    const html = document.documentElement;

    /**
     * Obter tema salvo ou preferência do sistema
     */
    function getThemePreference() {
        const savedTheme = localStorage.getItem(THEME_KEY);
        if (savedTheme) {
            return savedTheme;
        }
        
        // Verificar preferência do sistema
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        
        return 'light';
    }

    /**
     * Aplicar tema
     */
    function applyTheme(theme) {
        html.setAttribute('data-theme', theme);
        localStorage.setItem(THEME_KEY, theme);
    }

    /**
     * Toggle tema
     */
    function toggleTheme() {
        const currentTheme = html.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        applyTheme(newTheme);
        
        // Animação suave
        document.body.style.transition = 'background-color 0.3s ease, color 0.3s ease';
        setTimeout(function() {
            document.body.style.transition = '';
        }, 300);
    }

    // Inicializar tema
    applyTheme(getThemePreference());

    // Event listener
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    // Observar mudanças na preferência do sistema
    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
            // Só aplicar se usuário não tiver preferência salva
            if (!localStorage.getItem(THEME_KEY)) {
                applyTheme(e.matches ? 'dark' : 'light');
            }
        });
    }

})();
