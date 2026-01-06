# APIs de Consulta - Sistema de Emails

## Visão Geral

Este documento descreve as APIs de consulta para campanhas de email, servidores SMTP e templates de email. Todas as APIs retornam dados em formato JSON e suportam filtros e paginação.

## 🔗 URLs Base

- **Campanhas**: `/emails/api/campanhas/`
- **Servidores**: `/emails/api/servidores/`
- **Templates**: `/emails/api/templates/`

---

## 📧 APIs de Campanhas

### 1. Listar Campanhas

**GET** `/emails/api/campanhas/`

Lista todas as campanhas de email com filtros e paginação.

#### Parâmetros de Filtro

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `status` | string | Filtrar por status (rascunho, agendada, executando, pausada, concluida, cancelada, erro) |
| `search` | string | Buscar por nome, descrição ou template |
| `page` | integer | Número da página (padrão: 1) |
| `limit` | integer | Itens por página (padrão: 20, máximo: 100) |

#### Exemplo de Requisição

```bash
curl "http://localhost:8000/emails/api/campanhas/?status=concluida&search=teste&page=1&limit=10"
```

#### Exemplo de Resposta

```json
{
  "success": true,
  "data": [
    {
      "id": 92,
      "nome": "Teste API - Execução Imediata ID 782 - V2",
      "descricao": "Campanha criada via API para execução 782",
      "status": "concluida",
      "status_display": "Concluída",
      "tipo_agendamento": "unico",
      "tipo_agendamento_display": "Envio Único",
      "ativo": true,
      "total_destinatarios": 1,
      "total_enviados": 1,
      "total_sucessos": 1,
      "total_erros": 0,
      "taxa_sucesso": 100.0,
      "data_criacao": "2025-10-22T14:00:37.842731+00:00",
      "data_agendamento": "2025-10-22T14:00:37.846103+00:00",
      "data_inicio_execucao": "2025-10-22T14:00:37.846103+00:00",
      "data_fim_execucao": "2025-10-22T14:00:38.718125+00:00",
      "proxima_execucao": null,
      "template_email": {
        "id": 6,
        "nome": "Megalink Antes Vencimento",
        "tipo": "fatura"
      },
      "configuracao_servidor": {
        "id": 1,
        "nome": "Megalink",
        "servidor": "smtp.gmail.com"
      },
      "consulta_execucao": {
        "id": 782,
        "titulo": "TESTEmail",
        "status": "concluida"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "pages": 1,
    "total": 1,
    "has_next": false,
    "has_previous": false,
    "next_page": null,
    "previous_page": null
  },
  "filters": {
    "status": "concluida",
    "search": "teste"
  }
}
```

### 2. Detalhes de Campanha

**GET** `/emails/api/campanhas/{campanha_id}/`

Obtém detalhes completos de uma campanha específica.

#### Exemplo de Requisição

```bash
curl "http://localhost:8000/emails/api/campanhas/92/"
```

#### Exemplo de Resposta

```json
{
  "success": true,
  "data": {
    "id": 92,
    "nome": "Teste API - Execução Imediata ID 782 - V2",
    "descricao": "Campanha criada via API para execução 782",
    "status": "concluida",
    "status_display": "Concluída",
    "tipo_agendamento": "unico",
    "tipo_agendamento_display": "Envio Único",
    "ativo": true,
    "pular_consulta_api": true,
    "total_destinatarios": 1,
    "total_enviados": 1,
    "total_sucessos": 1,
    "total_erros": 0,
    "total_pendentes": 0,
    "taxa_sucesso": 100.0,
    "progresso_percentual": 100.0,
    "data_criacao": "2025-10-22T14:00:37.842731+00:00",
    "data_agendamento": "2025-10-22T14:00:37.846103+00:00",
    "data_inicio_execucao": "2025-10-22T14:00:37.846103+00:00",
    "data_fim_execucao": "2025-10-22T14:00:38.718125+00:00",
    "proxima_execucao": null,
    "log_execucao": "[22/10/2025 14:00:37] INFO: Reutilizando execução...",
    "template_email": {
      "id": 6,
      "nome": "Megalink Antes Vencimento",
      "tipo": "fatura",
      "assunto": "Lembrete de Vencimento - {{nome_razaosocial}}"
    },
    "configuracao_servidor": {
      "id": 1,
      "nome": "Megalink",
      "servidor_smtp": "smtp.gmail.com",
      "porta": 587,
      "usar_tls": true
    },
    "consulta_execucao": {
      "id": 782,
      "titulo": "TESTEmail",
      "status": "concluida",
      "status_display": "Concluída",
      "data_inicio": "2025-10-22T13:58:43.460018+00:00",
      "data_fim": "2025-10-22T13:58:44.582872+00:00"
    },
    "estatisticas": {
      "total_destinatarios": 1,
      "total_enviados": 1,
      "total_sucessos": 1,
      "total_erros": 0,
      "taxa_sucesso": 100.0
    },
    "envios_recentes": [
      {
        "id": 1,
        "cliente_codigo": "31826",
        "email_destinatario": "darlanvelozo123@gmail.com",
        "nome_destinatario": "CARLOS AUGUSTO DE VASCONCELOS",
        "status": "enviado",
        "status_display": "Enviado",
        "data_envio": "2025-10-22T14:00:38.709613+00:00",
        "tentativas": 0,
        "message_id": "abc123@example.com",
        "erro_detalhado": null
      }
    ],
    "logs_recentes": [
      {
        "id": 1,
        "nivel": "INFO",
        "acao": "execucao_iniciada",
        "mensagem": "Execução iniciada via API",
        "data_criacao": "2025-10-22T14:00:37.846103+00:00",
        "dados_extras": {}
      }
    ],
    "acoes_disponiveis": {
      "pode_executar": false,
      "pode_pausar": false,
      "pode_cancelar": false,
      "pode_retomar": false
    }
  }
}
```

---

## 🔧 APIs de Servidores de Email

### 1. Listar Servidores

**GET** `/emails/api/servidores/`

Lista todas as configurações de servidores SMTP.

#### Parâmetros de Filtro

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `ativo` | boolean | Filtrar por status ativo (true/false) |
| `search` | string | Buscar por nome, servidor SMTP ou descrição |

#### Exemplo de Requisição

```bash
curl "http://localhost:8000/emails/api/servidores/?ativo=true&search=gmail"
```

#### Exemplo de Resposta

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "nome": "Megalink",
      "descricao": "Servidor SMTP da Megalink",
      "servidor_smtp": "smtp.gmail.com",
      "porta": 587,
      "usar_tls": true,
      "usar_ssl": false,
      "usuario": "contato@megalink.com.br",
      "senha": "***",
      "email_remetente": "contato@megalink.com.br",
      "nome_remetente": "Megalink",
      "ativo": true,
      "data_criacao": "2025-10-22T10:00:00.000000+00:00",
      "ultimo_teste": "2025-10-22T14:00:00.000000+00:00",
      "teste_sucesso": true
    }
  ],
  "total": 1,
  "filters": {
    "ativo": "true",
    "search": "gmail"
  }
}
```

### 2. Detalhes de Servidor

**GET** `/emails/api/servidores/{servidor_id}/`

Obtém detalhes completos de uma configuração de servidor.

#### Exemplo de Resposta

```json
{
  "success": true,
  "data": {
    "id": 1,
    "nome": "Megalink",
    "descricao": "Servidor SMTP da Megalink",
    "servidor_smtp": "smtp.gmail.com",
    "porta": 587,
    "usar_tls": true,
    "usar_ssl": false,
    "usuario": "contato@megalink.com.br",
    "senha": "***",
    "email_remetente": "contato@megalink.com.br",
    "nome_remetente": "Megalink",
    "ativo": true,
    "data_criacao": "2025-10-22T10:00:00.000000+00:00",
    "ultimo_teste": "2025-10-22T14:00:00.000000+00:00",
    "teste_sucesso": true,
    "log_teste": "Teste realizado com sucesso",
    "campanhas_ativas": 2,
    "total_campanhas": 5
  }
}
```

---

## 📝 APIs de Templates de Email

### 1. Listar Templates

**GET** `/emails/api/templates/`

Lista todos os templates de email.

#### Parâmetros de Filtro

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `ativo` | boolean | Filtrar por status ativo (true/false) |
| `tipo` | string | Filtrar por tipo de template |
| `search` | string | Buscar por nome, assunto ou descrição |

#### Exemplo de Requisição

```bash
curl "http://localhost:8000/emails/api/templates/?ativo=true&tipo=fatura&search=vencimento"
```

#### Exemplo de Resposta

```json
{
  "success": true,
  "data": [
    {
      "id": 6,
      "nome": "Megalink Antes Vencimento",
      "descricao": "Template para lembretes de vencimento",
      "tipo": "fatura",
      "tipo_display": "Fatura",
      "assunto": "Lembrete de Vencimento - {{nome_razaosocial}}",
      "corpo_html": "<html>...</html>",
      "corpo_texto": "Texto do email...",
      "ativo": true,
      "total_enviados": 150,
      "data_criacao": "2025-10-22T10:00:00.000000+00:00",
      "data_atualizacao": "2025-10-22T14:00:00.000000+00:00",
      "variaveis_detectadas": ["nome_razaosocial", "valor_fatura", "vencimento_fatura"],
      "campanhas_ativas": 1,
      "total_campanhas": 3
    }
  ],
  "total": 1,
  "filters": {
    "ativo": "true",
    "tipo": "fatura",
    "search": "vencimento"
  }
}
```

### 2. Detalhes de Template

**GET** `/emails/api/templates/{template_id}/`

Obtém detalhes completos de um template de email, incluindo preview renderizado.

#### Exemplo de Resposta

```json
{
  "success": true,
  "data": {
    "id": 6,
    "nome": "Megalink Antes Vencimento",
    "descricao": "Template para lembretes de vencimento",
    "tipo": "fatura",
    "tipo_display": "Fatura",
    "assunto": "Lembrete de Vencimento - {{nome_razaosocial}}",
    "corpo_html": "<html><body><h1>Lembrete de Vencimento</h1>...</body></html>",
    "corpo_texto": "Lembrete de Vencimento\n\nOlá {{nome_razaosocial}}...",
    "ativo": true,
    "total_enviados": 150,
    "data_criacao": "2025-10-22T10:00:00.000000+00:00",
    "data_atualizacao": "2025-10-22T14:00:00.000000+00:00",
    "variaveis_detectadas": ["nome_razaosocial", "valor_fatura", "vencimento_fatura"],
    "template_renderizado": {
      "assunto": "Lembrete de Vencimento - João Silva",
      "corpo_html": "<html><body><h1>Lembrete de Vencimento</h1><p>Olá João Silva...</p></body></html>",
      "corpo_texto": "Lembrete de Vencimento\n\nOlá João Silva..."
    },
    "dados_exemplo": {
      "codigo_cliente": "12345",
      "nome_razaosocial": "João Silva",
      "telefone_corrigido": "(11) 99999-9999",
      "id_fatura": "FAT-2024-001",
      "vencimento_fatura": "15/01/2024",
      "valor_fatura": "150,00"
    },
    "campanhas_ativas": 1,
    "total_campanhas": 3
  }
}
```

---

## 🔍 Códigos de Status HTTP

| Código | Descrição |
|--------|-----------|
| 200 | Sucesso |
| 400 | Parâmetros inválidos |
| 404 | Recurso não encontrado |
| 500 | Erro interno do servidor |

## 📊 Estrutura de Resposta Padrão

### Sucesso

```json
{
  "success": true,
  "data": [...],
  "pagination": {  // Apenas para listagens
    "page": 1,
    "pages": 5,
    "total": 100,
    "has_next": true,
    "has_previous": false,
    "next_page": 2,
    "previous_page": null
  },
  "filters": {  // Apenas para listagens
    "status": "concluida",
    "search": "teste"
  }
}
```

### Erro

```json
{
  "success": false,
  "error": "Mensagem de erro detalhada"
}
```

## 🚀 Exemplos de Uso

### Python

```python
import requests

# Listar campanhas
response = requests.get('http://localhost:8000/emails/api/campanhas/')
data = response.json()

# Filtrar campanhas concluídas
response = requests.get('http://localhost:8000/emails/api/campanhas/?status=concluida')
data = response.json()

# Obter detalhes de uma campanha
response = requests.get('http://localhost:8000/emails/api/campanhas/92/')
data = response.json()
```

### JavaScript

```javascript
// Listar servidores ativos
fetch('http://localhost:8000/emails/api/servidores/?ativo=true')
  .then(response => response.json())
  .then(data => console.log(data));

// Buscar templates por tipo
fetch('http://localhost:8000/emails/api/templates/?tipo=fatura')
  .then(response => response.json())
  .then(data => console.log(data));
```

### cURL

```bash
# Listar todas as campanhas
curl "http://localhost:8000/emails/api/campanhas/"

# Filtrar campanhas por status
curl "http://localhost:8000/emails/api/campanhas/?status=executando"

# Buscar templates
curl "http://localhost:8000/emails/api/templates/?search=vencimento"

# Obter detalhes de um servidor
curl "http://localhost:8000/emails/api/servidores/1/"
```

## 📝 Notas Importantes

1. **Paginação**: Use `page` e `limit` para controlar a paginação
2. **Filtros**: Todos os filtros são opcionais e podem ser combinados
3. **Busca**: A busca é case-insensitive e funciona em múltiplos campos
4. **Segurança**: Senhas de servidores são mascaradas (`***`)
5. **Performance**: Use filtros para reduzir o volume de dados retornados
6. **Rate Limiting**: Considere implementar rate limiting para APIs públicas

## 🔧 Testando as APIs

Use o script de teste incluído:

```bash
python testar_apis_consulta.py
```

Este script testa todas as APIs e demonstra os diferentes filtros e funcionalidades disponíveis.
