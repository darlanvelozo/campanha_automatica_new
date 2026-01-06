/**
 * JavaScript para melhorar a interface do admin ConsultaExecucao
 * Torna o campo credencial_hubsoft opcional quando "Pular API" está marcado
 */

(function($) {
    'use strict';
    
    function toggleCredencialHubsoft(checkbox) {
        var credencialField = $('.field-credencial_hubsoft');
        var credencialSelect = $('#id_credencial_hubsoft');
        var helpText = $('.field-credencial_hubsoft .help');
        
        if (checkbox.checked) {
            // API será pulada - torna credencial opcional
            credencialField.removeClass('required');
            credencialSelect.prop('required', false);
            
            // Atualiza help text
            if (helpText.length) {
                helpText.text('Não é necessária quando "Pular Consulta na API" está marcado');
            }
            
            // Adiciona estilo visual para indicar que é opcional
            credencialField.css('opacity', '0.6');
            
        } else {
            // API será consultada - torna credencial obrigatória
            credencialField.addClass('required');
            credencialSelect.prop('required', true);
            
            // Atualiza help text
            if (helpText.length) {
                helpText.text('Obrigatória para consultas na API');
            }
            
            // Remove estilo de opcional
            credencialField.css('opacity', '1');
        }
    }
    
    // Função global para ser chamada pelo onchange
    window.toggleCredencialHubsoft = function(checkbox) {
        toggleCredencialHubsoft(checkbox);
    };
    
    $(document).ready(function() {
        // Aplica o estado inicial quando a página carrega
        var pularApiCheckbox = $('#id_pular_consulta_api');
        if (pularApiCheckbox.length) {
            toggleCredencialHubsoft(pularApiCheckbox[0]);
            
            // Adiciona listener para mudanças
            pularApiCheckbox.on('change', function() {
                toggleCredencialHubsoft(this);
            });
        }
        
        // Adiciona ícones visuais
        var pularApiField = $('.field-pular_consulta_api');
        if (pularApiField.length) {
            pularApiField.find('label').prepend('🔄 ');
        }
        
        var credencialField = $('.field-credencial_hubsoft');
        if (credencialField.length) {
            credencialField.find('label').prepend('🔑 ');
        }
    });
    
})(django.jQuery);
