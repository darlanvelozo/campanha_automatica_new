# 📧 MANUAL DE CAMPANHAS DE EMAIL

## 🎯 Visão Geral

Este sistema permite criar e executar campanhas de email automatizadas, integradas com consultas SQL e dados da API Hubsoft. As campanhas podem ser executadas uma única vez ou de forma recorrente (diária, semanal, mensal).

## 📋 Componentes do Sistema

### 1. **Configuração do Servidor SMTP**
- Define as credenciais para envio de emails
- Suporte a TLS/SSL
- Teste de conexão integrado

### 2. **Templates de Email**
- Templates HTML e texto para os emails
- Suporte a variáveis dinâmicas ({{nome_cliente}}, {{valor_fatura}}, etc.)
- CSS personalizado

### 3. **Templates SQL**
- Consultas SQL para buscar dados dos clientes
- Suporte a variáveis SQL
- Integração com banco de dados

### 4. **Campanhas de Email**
- Configuração de agendamento
- Recorrência (diária, semanal, mensal)
- Filtros e limites

## 🚀 Processo Passo a Passo

### **PASSO 1: Configurar Servidor SMTP**

```bash
# Acessar admin Django ou interface web
# Criar nova configuração SMTP:
```

**Campos obrigatórios:**
- **Nome**: Identificação da configuração
- **Servidor SMTP**: Ex: smtp.gmail.com, webmail.seudominio.com.br
- **Porta**: 587 (TLS) ou 465 (SSL)
- **Usuário**: Email para autenticação
- **Senha**: Senha do email
- **Email Remetente**: DEVE ser igual ao usuário
- **Nome Remetente**: Nome que aparece no email
- **TLS/SSL**: Configurar conforme servidor

**⚠️ IMPORTANTE**: O email remetente deve ser igual ao usuário SMTP!

### **PASSO 2: Criar Template de Email**

```bash
# Criar template com variáveis dinâmicas
```

**Exemplo de template:**
```html
<h2>Olá {{nome_cliente}}!</h2>
<p>Sua fatura de <strong>R$ {{valor_fatura}}</strong> está vencida.</p>
<p>Vencimento: {{data_vencimento}}</p>
<p>Para regularizar, acesse: {{link_pagamento}}</p>
```

**Variáveis disponíveis:**
- `{{nome_cliente}}` - Nome do cliente
- `{{email}}` - Email do cliente
- `{{telefone}}` - Telefone do cliente
- `{{valor_fatura}}` - Valor da fatura
- `{{data_vencimento}}` - Data de vencimento
- `{{data_atual}}` - Data atual
- `{{hora_atual}}` - Hora atual

### **PASSO 3: Criar Template SQL**

```sql
-- Exemplo: Clientes com fatura vencida
SELECT 
    c.id as cliente_id,
    c.nome as nome_cliente,
    c.email,
    c.telefone,
    f.valor as valor_fatura,
    f.data_vencimento,
    f.id as fatura_id
FROM clientes c
JOIN faturas f ON c.id = f.cliente_id
WHERE f.status = 'vencida'
  AND f.data_vencimento < CURDATE()
  AND c.email IS NOT NULL
  AND c.email != ''
```

### **PASSO 4: Criar Campanha**

**Configurações básicas:**
- **Nome**: "Cobrança Faturas Vencidas"
- **Template Email**: Selecionar template criado
- **Servidor SMTP**: Selecionar configuração
- **Template SQL**: Selecionar consulta
- **Tipo**: Semanal
- **Dias da Semana**: 1,2,3,4,5 (segunda a sexta)
- **Hora**: 09:00
- **Status**: Agendada

### **PASSO 5: Executar Campanha**

#### **Execução Manual (Teste)**
```bash
# Ativar ambiente virtual
source myenv/bin/activate

# Testar campanha (modo teste)
python manage.py executar_email_simples --id=84 --teste

# Executar campanha real
python manage.py executar_email_simples --id=84
```

#### **Execução Automática (Produção)**
```bash
# Executar campanhas agendadas
python manage.py executar_campanhas_agendadas

# Monitorar campanhas
python manage.py monitor_campanhas
```

## 📅 Configuração de Recorrência

### **Segunda a Sexta (Dias Úteis)**
```
Tipo: Semanal
Dias da Semana: 1,2,3,4,5
Hora: 09:00
Intervalo: 1 (toda semana)
```

### **Todos os Dias**
```
Tipo: Diário
Hora: 09:00
Intervalo: 1 (todo dia)
```

### **Personalizado (Cron)**
```
Tipo: Personalizado
Expressão Cron: 0 9 * * 1-5 (segunda a sexta às 9h)
```

## 🔧 Comandos Úteis

### **Executar Campanha Específica**
```bash
python manage.py executar_email_simples --id=84
```

### **Executar Todas Agendadas**
```bash
python manage.py executar_email_simples --todas
```

### **Modo Teste (Sem Enviar)**
```bash
python manage.py executar_email_simples --id=84 --teste
```

### **Monitorar Status**
```bash
python manage.py monitor_campanhas --verbose
```

## 📊 Monitoramento

### **Verificar Status da Campanha**
```bash
python manage.py shell -c "
from emails.models import CampanhaEmail
campanha = CampanhaEmail.objects.get(id=84)
print(f'Status: {campanha.get_status_display()}')
print(f'Total destinatários: {campanha.total_destinatarios}')
print(f'Total enviados: {campanha.total_enviados}')
print(f'Total sucessos: {campanha.total_sucessos}')
print(f'Total erros: {campanha.total_erros}')
print(f'Próxima execução: {campanha.proxima_execucao}')
"
```

### **Ver Logs de Envio**
```bash
python manage.py shell -c "
from emails.models import LogEnvioEmail
logs = LogEnvioEmail.objects.filter(campanha_id=84).order_by('-data_criacao')[:10]
for log in logs:
    print(f'{log.data_criacao}: {log.acao} - {log.mensagem}')
"
```

## ⚠️ Problemas Comuns

### **1. Erro de Autenticação SMTP**
```
Erro: Account user@domain.com can not send emails from other@domain.com
```
**Solução**: Email remetente deve ser igual ao usuário SMTP

### **2. Nenhum Cliente Encontrado**
```
Erro: Nenhum cliente encontrado com email válido
```
**Solução**: Verificar template SQL e dados dos clientes

### **3. Template SQL com Erro**
```
Erro: Falha ao executar consulta SQL
```
**Solução**: Testar SQL diretamente no banco de dados

### **4. Campanha Não Executa**
```
Status: Agendada (nunca muda)
```
**Solução**: Verificar se o comando de execução está rodando

## 🔄 Automação com Cron

### **Executar a Cada Minuto**
```bash
# Editar crontab
crontab -e

# Adicionar linha:
* * * * * cd /caminho/do/projeto && source myenv/bin/activate && python manage.py executar_campanhas_agendadas
```

### **Executar de Hora em Hora**
```bash
# Adicionar ao crontab:
0 * * * * cd /caminho/do/projeto && source myenv/bin/activate && python manage.py executar_campanhas_agendadas
```

## 📈 Boas Práticas

1. **Sempre testar** com modo `--teste` primeiro
2. **Verificar logs** após execução
3. **Configurar limites** para evitar sobrecarga
4. **Monitorar** taxa de sucesso
5. **Backup** das configurações importantes
6. **Testar SMTP** antes de criar campanhas
7. **Validar templates** com dados reais

## 🆘 Suporte

Em caso de problemas:
1. Verificar logs da campanha
2. Testar configuração SMTP
3. Validar template SQL
4. Verificar dados dos clientes
5. Consultar documentação da API Hubsoft
