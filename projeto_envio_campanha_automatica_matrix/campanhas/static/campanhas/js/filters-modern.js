/**
 * FILTROS MODERNOS - JavaScript
 * Interações, validações e microanimações
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeFilters();
});

function initializeFilters() {
    // Toggle Advanced Filters
    const toggleBtn = document.getElementById('toggleAdvancedFilters');
    const advancedFilters = document.getElementById('advancedFilters');
    
    if (toggleBtn && advancedFilters) {
        toggleBtn.addEventListener('click', function() {
            const isVisible = advancedFilters.style.display !== 'none';
            
            if (isVisible) {
                advancedFilters.style.display = 'none';
                toggleBtn.classList.remove('active');
            } else {
                advancedFilters.style.display = 'block';
                toggleBtn.classList.add('active');
                
                // Auto-focus no primeiro campo de data
                setTimeout(() => {
                    const firstDateInput = advancedFilters.querySelector('input[type="datetime-local"]');
                    if (firstDateInput) firstDateInput.focus();
                }, 100);
            }
        });
    }
    
    // Search Input - Clear Button
    const searchInput = document.getElementById('buscaExecutando');
    const clearSearchBtn = document.getElementById('clearSearch');
    
    if (searchInput && clearSearchBtn) {
        searchInput.addEventListener('input', function() {
            clearSearchBtn.style.display = this.value ? 'flex' : 'none';
        });
        
        clearSearchBtn.addEventListener('click', function() {
            searchInput.value = '';
            searchInput.focus();
            clearSearchBtn.style.display = 'none';
            filtrarExecutandocoesLocal();
        });
    }
    
    // Date Presets
    const datePresetBtns = document.querySelectorAll('.date-preset-btn');
    datePresetBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const preset = this.dataset.preset;
            applyDatePreset(preset);
            
            // Visual feedback
            datePresetBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });
    
    // Active Filters Manager
    updateActiveFilters();
    
    // Auto-expand advanced filters se houver filtros de data ativos
    checkAndExpandAdvancedFilters();
    
    // DateTime Input - Validação
    const dateInputs = document.querySelectorAll('input[type="datetime-local"]');
    dateInputs.forEach(input => {
        input.addEventListener('change', validateDateRange);
    });
}

/**
 * Aplica presets de data (atalhos rápidos)
 */
function applyDatePreset(preset) {
    const dataInicioDe = document.getElementById('dataInicioDe');
    const dataInicioAte = document.getElementById('dataInicioAte');
    
    if (!dataInicioDe || !dataInicioAte) return;
    
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    
    let startDate, endDate;
    
    switch(preset) {
        case 'hoje':
            startDate = new Date(today);
            startDate.setHours(0, 0, 0);
            endDate = new Date(today);
            endDate.setHours(23, 59, 59);
            break;
            
        case 'ontem':
            startDate = new Date(today);
            startDate.setDate(startDate.getDate() - 1);
            startDate.setHours(0, 0, 0);
            endDate = new Date(today);
            endDate.setDate(endDate.getDate() - 1);
            endDate.setHours(23, 59, 59);
            break;
            
        case 'ultimos7dias':
            startDate = new Date(today);
            startDate.setDate(startDate.getDate() - 7);
            startDate.setHours(0, 0, 0);
            endDate = new Date(now);
            break;
            
        case 'ultimos30dias':
            startDate = new Date(today);
            startDate.setDate(startDate.getDate() - 30);
            startDate.setHours(0, 0, 0);
            endDate = new Date(now);
            break;
            
        case 'este_mes':
            startDate = new Date(now.getFullYear(), now.getMonth(), 1);
            startDate.setHours(0, 0, 0);
            endDate = new Date(now);
            break;
            
        default:
            return;
    }
    
    // Formatar para datetime-local (YYYY-MM-DDTHH:MM)
    dataInicioDe.value = formatDateTimeLocal(startDate);
    dataInicioAte.value = formatDateTimeLocal(endDate);
    
    // Trigger change event
    dataInicioDe.dispatchEvent(new Event('change'));
    dataInicioAte.dispatchEvent(new Event('change'));
}

/**
 * Formata data para datetime-local input
 */
function formatDateTimeLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

/**
 * Valida range de datas
 */
function validateDateRange() {
    const dataInicioDe = document.getElementById('dataInicioDe');
    const dataInicioAte = document.getElementById('dataInicioAte');
    
    if (!dataInicioDe || !dataInicioAte) return;
    
    const startDate = new Date(dataInicioDe.value);
    const endDate = new Date(dataInicioAte.value);
    
    if (dataInicioDe.value && dataInicioAte.value && startDate > endDate) {
        // Mostrar feedback visual
        dataInicioAte.style.borderColor = '#ef4444';
        
        // Criar tooltip de erro
        showErrorTooltip(dataInicioAte, 'Data final deve ser maior que a data inicial');
        
        setTimeout(() => {
            dataInicioAte.style.borderColor = '';
        }, 2000);
    }
}

/**
 * Mostra tooltip de erro
 */
function showErrorTooltip(element, message) {
    // Remove tooltip anterior se existir
    const existingTooltip = document.querySelector('.error-tooltip');
    if (existingTooltip) existingTooltip.remove();
    
    // Criar novo tooltip
    const tooltip = document.createElement('div');
    tooltip.className = 'error-tooltip';
    tooltip.textContent = message;
    tooltip.style.cssText = `
        position: absolute;
        bottom: -30px;
        left: 0;
        padding: 6px 12px;
        background: #ef4444;
        color: white;
        font-size: 12px;
        border-radius: 6px;
        white-space: nowrap;
        z-index: 1000;
        animation: fadeIn 0.2s ease;
    `;
    
    element.parentElement.style.position = 'relative';
    element.parentElement.appendChild(tooltip);
    
    setTimeout(() => tooltip.remove(), 2000);
}

/**
 * Atualiza visualização de filtros ativos
 */
function updateActiveFilters() {
    const activeFiltersContainer = document.getElementById('activeFilters');
    const activeFiltersPills = document.getElementById('activeFiltersPills');
    
    if (!activeFiltersContainer || !activeFiltersPills) return;
    
    const filtroStatus = document.getElementById('filtroStatus');
    const dataInicioDe = document.getElementById('dataInicioDe');
    const dataInicioAte = document.getElementById('dataInicioAte');
    const buscaExecutando = document.getElementById('buscaExecutando');
    
    const filters = [];
    
    // Status
    if (filtroStatus && filtroStatus.value) {
        const statusText = filtroStatus.options[filtroStatus.selectedIndex].text;
        filters.push({
            label: 'Status',
            value: statusText,
            field: 'status'
        });
    }
    
    // Data Inicial
    if (dataInicioDe && dataInicioDe.value) {
        filters.push({
            label: 'De',
            value: formatDateTimeBR(dataInicioDe.value),
            field: 'data_inicio_de'
        });
    }
    
    // Data Final
    if (dataInicioAte && dataInicioAte.value) {
        filters.push({
            label: 'Até',
            value: formatDateTimeBR(dataInicioAte.value),
            field: 'data_inicio_ate'
        });
    }
    
    // Busca
    if (buscaExecutando && buscaExecutando.value) {
        filters.push({
            label: 'Busca',
            value: buscaExecutando.value,
            field: 'busca'
        });
    }
    
    // Renderizar pills
    if (filters.length > 0) {
        activeFiltersPills.innerHTML = filters.map(filter => `
            <div class="filter-pill">
                <strong>${filter.label}:</strong> ${filter.value}
                <button type="button" class="filter-pill-remove" onclick="removeFilter('${filter.field}')">
                    <i data-feather="x" style="width: 12px; height: 12px;"></i>
                </button>
            </div>
        `).join('');
        
        activeFiltersContainer.style.display = 'flex';
        feather.replace();
    } else {
        activeFiltersContainer.style.display = 'none';
    }
}

/**
 * Formata datetime para exibição em português
 */
function formatDateTimeBR(datetimeLocal) {
    if (!datetimeLocal) return '';
    
    const date = new Date(datetimeLocal);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    return `${day}/${month}/${year} ${hours}:${minutes}`;
}

/**
 * Remove filtro individual
 */
function removeFilter(field) {
    switch(field) {
        case 'status':
            document.getElementById('filtroStatus').value = '';
            break;
        case 'data_inicio_de':
            document.getElementById('dataInicioDe').value = '';
            break;
        case 'data_inicio_ate':
            document.getElementById('dataInicioAte').value = '';
            break;
        case 'busca':
            document.getElementById('buscaExecutando').value = '';
            document.getElementById('clearSearch').style.display = 'none';
            break;
    }
    
    // Submit do form para atualizar
    document.getElementById('formFiltros').submit();
}

/**
 * Limpa todos os filtros
 */
function limparFiltros() {
    window.location.href = window.location.pathname;
}

/**
 * Verifica se deve expandir filtros avançados automaticamente
 */
function checkAndExpandAdvancedFilters() {
    const dataInicioDe = document.getElementById('dataInicioDe');
    const dataInicioAte = document.getElementById('dataInicioAte');
    const toggleBtn = document.getElementById('toggleAdvancedFilters');
    const advancedFilters = document.getElementById('advancedFilters');
    
    if ((dataInicioDe && dataInicioDe.value) || (dataInicioAte && dataInicioAte.value)) {
        if (advancedFilters && toggleBtn) {
            advancedFilters.style.display = 'block';
            toggleBtn.classList.add('active');
        }
    }
}

/**
 * Filtro local de busca (sem reload)
 */
function filtrarExecutandocoesLocal() {
    const busca = document.getElementById('buscaExecutando').value.toLowerCase();
    const cards = document.querySelectorAll('.execucao-card');

    cards.forEach(card => {
        const cardTitulo = card.dataset.titulo;
        const buscaMatch = !busca || cardTitulo.includes(busca);

        if (buscaMatch) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });
    
    // Atualizar active filters
    updateActiveFilters();
}
