# API de Campanhas de Email

## Endpoint: Criar Campanha de Execução Única

### URL
```
POST /emails/api/criar-campanha-execucao-unica/
```

### Descrição
Cria uma campanha de email de execução única usando uma execução já existente. A campanha é criada e executada imediatamente em background.

### Parâmetros Obrigatórios

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `id_execucao` | integer | ID da execução existente (deve estar concluída) |
| `template_email` | integer | ID do template de email (deve estar ativo) |
| `servidor_email` | integer | ID da configuração do servidor SMTP (deve estar ativo) |
| `titulo` | string | Título da campanha |

### Exemplo de Requisição

```bash
curl -X POST http://localhost:8000/emails/api/criar-campanha-execucao-unica/ \
  -H "Content-Type: application/json" \
  -d '{
    "id_execucao": 781,
    "template_email": 6,
    "servidor_email": 1,
    "titulo": "Campanha de Teste - Execução Única"
  }'
```

### Exemplo de Resposta de Sucesso

```json
{
  "success": true,
  "campanha_id": 92,
  "message": "Campanha criada e executada com sucesso. Total: 1 enviados, 1 sucessos, 0 erros",
  "dados": {
    "id": 92,
    "nome": "Teste API - Execução Imediata ID 782 - V2",
    "status": "Concluída",
    "total_destinatarios": 1,
    "total_enviados": 1,
    "total_sucessos": 1,
    "total_erros": 0,
    "template_email": "Megalink Antes Vencimento",
    "servidor_email": "Megalink",
    "execucao_origem": "TESTEmail",
    "data_inicio_execucao": "2025-10-22T14:00:37.846103+00:00",
    "data_fim_execucao": "2025-10-22T14:00:38.718125+00:00"
  }
}
```

### Exemplo de Resposta de Erro

```json
{
  "success": false,
  "error": "Execução com ID 999 não encontrada"
}
```

### Códigos de Status HTTP

| Código | Descrição |
|--------|-----------|
| 200 | Sucesso |
| 400 | Parâmetros inválidos ou execução não concluída |
| 404 | Execução, template ou servidor não encontrado |
| 500 | Erro interno do servidor |

### Validações

1. **Execução**: Deve existir e estar com status "concluida"
2. **Template de Email**: Deve existir e estar ativo
3. **Servidor SMTP**: Deve existir e estar ativo
4. **Parâmetros**: Todos os parâmetros obrigatórios devem ser fornecidos

### Comportamento

1. A campanha é criada com tipo "unico" (execução única)
2. **A execução de envio de emails é iniciada IMEDIATAMENTE**
3. Os emails são enviados em tempo real durante a requisição
4. O total de destinatários é calculado baseado na execução original
5. A configuração de "pular consulta API" é herdada da execução original
6. A resposta só é retornada após a conclusão do envio

### Monitoramento

Após a criação, você pode monitorar a campanha através de:

1. **Dashboard**: `http://localhost:8000/emails/dashboard/`
2. **Detalhes da Campanha**: `http://localhost:8000/emails/campanhas/{campanha_id}/`
3. **API de Status**: `http://localhost:8000/emails/campanhas/{campanha_id}/status/`

### Exemplo de Uso com Python

```python
import requests
import json

# Configurações
url = "http://localhost:8000/emails/api/criar-campanha-execucao-unica/"
dados = {
    "id_execucao": 781,
    "template_email": 6,
    "servidor_email": 1,
    "titulo": "Minha Campanha de Teste"
}

# Fazer requisição
response = requests.post(url, json=dados)

if response.status_code == 200:
    resultado = response.json()
    if resultado['success']:
        print(f"✅ Campanha criada com ID: {resultado['campanha_id']}")
        print(f"Total de destinatários: {resultado['dados']['total_destinatarios']}")
    else:
        print(f"❌ Erro: {resultado['error']}")
else:
    print(f"❌ Erro HTTP: {response.status_code}")
```

### Notas Importantes

1. **Execução Imediata**: Os emails são enviados IMEDIATAMENTE durante a requisição
2. **Síncrono**: A resposta só é retornada após a conclusão de todos os envios
3. **Dados Atualizados**: A campanha usa os dados da execução original (já processados)
4. **Sem Recorrência**: Esta API cria apenas campanhas de execução única
5. **Logs**: Todos os logs são registrados no sistema para monitoramento
6. **Timeout**: Para grandes volumes, considere o timeout da requisição HTTP
