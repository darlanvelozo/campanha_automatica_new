from django.core.management.base import BaseCommand
from campanhas.models import TemplateSQL


class Command(BaseCommand):
    help = 'Configura automaticamente variáveis SQL não configuradas'

    def handle(self, *args, **options):
        self.stdout.write('=== CONFIGURANDO VARIÁVEIS SQL ===')
        
        templates = TemplateSQL.objects.all()
        configurados = 0
        
        for template in templates:
            # Extrair variáveis do SQL
            variaveis = template.extrair_variaveis_do_sql()
            
            if variaveis:
                self.stdout.write(f'\nTemplate: {template.titulo} (ID: {template.id})')
                self.stdout.write(f'Variáveis encontradas: {variaveis}')
                
                # Verificar se precisa configurar
                config_atual = template.variaveis_config or {}
                precisa_configurar = False
                
                for var in variaveis:
                    if var not in config_atual:
                        precisa_configurar = True
                        break
                
                if precisa_configurar:
                    # Configurar variáveis automaticamente
                    nova_config = config_atual.copy()
                    
                    for var in variaveis:
                        if var not in nova_config:
                            # Configuração baseada no nome da variável
                            if 'dia' in var.lower():
                                nova_config[var] = {
                                    'label': f'Dias ({var})',
                                    'tipo': 'number',
                                    'obrigatorio': True,
                                    'valor_padrao': '3' if '1' in var else '7',
                                    'opcoes': ''
                                }
                            elif 'data' in var.lower():
                                nova_config[var] = {
                                    'label': f'Data ({var})',
                                    'tipo': 'date',
                                    'obrigatorio': True,
                                    'valor_padrao': '',
                                    'opcoes': ''
                                }
                            elif 'id' in var.lower() or 'codigo' in var.lower():
                                nova_config[var] = {
                                    'label': f'Código ({var})',
                                    'tipo': 'text',
                                    'obrigatorio': True,
                                    'valor_padrao': '',
                                    'opcoes': ''
                                }
                            else:
                                nova_config[var] = {
                                    'label': var.replace('_', ' ').title(),
                                    'tipo': 'text',
                                    'obrigatorio': True,
                                    'valor_padrao': '',
                                    'opcoes': ''
                                }
                    
                    # Salvar configuração
                    template.variaveis_config = nova_config
                    template.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Configurado: {list(nova_config.keys())}')
                    )
                    configurados += 1
                else:
                    self.stdout.write('✅ Já configurado')
        
        self.stdout.write(
            self.style.SUCCESS(f'\n=== CONCLUÍDO ===\n{configurados} templates configurados')
        )
