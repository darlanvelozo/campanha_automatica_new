/**
 * Script para melhorar a UX do formulário de Envio HSM com Mídia
 * Mostra/oculta campos dinamicamente e adiciona validações
 */

(function($) {
    'use strict';
    
    $(document).ready(function() {
        console.log('✅ Script de mídia HSM carregado');
        
        // Seletores dos campos
        const $enviarComMidia = $('#id_enviar_com_midia');
        const $arquivoMidia = $('#id_arquivo_midia');
        const $urlMidia = $('#id_url_midia');
        const $midiaSectionRows = $('.form-row.field-arquivo_midia, .form-row.field-url_midia, .form-row.field-get_midia_preview');
        
        // Função para mostrar/ocultar campos de mídia
        function toggleCamposMidia() {
            if ($enviarComMidia.is(':checked')) {
                $midiaSectionRows.show();
                console.log('📎 Campos de mídia exibidos');
            } else {
                $midiaSectionRows.hide();
                console.log('📎 Campos de mídia ocultados');
            }
        }
        
        // Executa ao carregar a página
        toggleCamposMidia();
        
        // Executa quando o checkbox muda
        $enviarComMidia.on('change', function() {
            toggleCamposMidia();
            
            // Adiciona animação suave
            if ($(this).is(':checked')) {
                $midiaSectionRows.slideDown(300);
                
                // Adiciona destaque visual temporário
                $midiaSectionRows.addClass('destaque-midia');
                setTimeout(function() {
                    $midiaSectionRows.removeClass('destaque-midia');
                }, 1500);
            } else {
                $midiaSectionRows.slideUp(300);
            }
        });
        
        // Validação: avisa se marcou "enviar com mídia" mas não preencheu nenhum campo
        $('form').on('submit', function(e) {
            if ($enviarComMidia.is(':checked')) {
                const temArquivo = $arquivoMidia.val();
                const temUrl = $urlMidia.val();
                
                if (!temArquivo && !temUrl) {
                    e.preventDefault();
                    alert('⚠️ Atenção!\n\nVocê marcou "Enviar com Mídia" mas não selecionou nenhum arquivo nem informou uma URL.\n\nPor favor:\n✅ Faça upload de um arquivo OU\n✅ Cole uma URL externa OU\n✅ Desmarque a opção "Enviar com Mídia"');
                    
                    // Destaca os campos vazios
                    $arquivoMidia.closest('.form-row').addClass('destaque-erro');
                    $urlMidia.closest('.form-row').addClass('destaque-erro');
                    
                    setTimeout(function() {
                        $('.destaque-erro').removeClass('destaque-erro');
                    }, 3000);
                    
                    return false;
                }
            }
        });
        
        // Feedback visual quando o usuário seleciona um arquivo
        $arquivoMidia.on('change', function() {
            if (this.files && this.files[0]) {
                const fileName = this.files[0].name;
                const fileSize = (this.files[0].size / 1024 / 1024).toFixed(2); // MB
                
                console.log(`📎 Arquivo selecionado: ${fileName} (${fileSize} MB)`);
                
                // Adiciona feedback visual
                $(this).closest('.form-row').addClass('arquivo-selecionado');
                
                // Se há arquivo, limpa a URL
                if ($urlMidia.val()) {
                    if (confirm('Você selecionou um arquivo para upload.\n\nDeseja limpar a URL externa?\n\n(O arquivo terá prioridade sobre a URL)')) {
                        $urlMidia.val('');
                    }
                }
            }
        });
        
        // Feedback visual quando o usuário cola uma URL
        $urlMidia.on('input', function() {
            const url = $(this).val();
            if (url) {
                console.log(`🔗 URL informada: ${url}`);
                
                // Adiciona feedback visual
                $(this).closest('.form-row').addClass('url-informada');
                
                // Valida se é uma URL válida
                try {
                    new URL(url);
                    $(this).closest('.form-row').removeClass('url-invalida');
                } catch (_) {
                    $(this).closest('.form-row').addClass('url-invalida');
                }
            } else {
                $(this).closest('.form-row').removeClass('url-informada url-invalida');
            }
        });
        
        // Adiciona dica visual sobre prioridade
        if ($arquivoMidia.length && $urlMidia.length) {
            const $helpText = $('<div class="help midia-priority-info">' +
                '<strong>💡 Dica:</strong> Se você preencher ambos os campos, ' +
                'o <strong>arquivo enviado terá prioridade</strong> sobre a URL externa.' +
                '</div>');
            
            $urlMidia.closest('.form-row').after($helpText);
        }
    });
    
})(django.jQuery);
