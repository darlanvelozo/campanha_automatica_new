# API Iniciar Processamento

## Descrição
API para iniciar o processamento de uma nova consulta SQL, criando uma `ConsultaExecucao` e iniciando o processamento em background.

## URL
```
POST /campanhas/iniciar-processamento/
```

## Parâmetros Obrigatórios

### 1. Parâmetros Básicos
- **`titulo`** (string): Título da execução
- **`template_sql`** (integer): ID do Template SQL a ser utilizado
- **`credencial_banco`** (integer): ID da credencial de banco de dados

### 2. Parâmetros Condicionais
- **`credencial_hubsoft`** (integer): ID da credencial Hubsoft (obrigatório apenas se `pular_consulta_api` for `false`)
- **`pular_consulta_api`** (string): Se deve pular a consulta na API Hubsoft
  - `"on"` - Pular consulta da API
  - `""` ou ausente - Não pular consulta da API

### 3. Variáveis do Template SQL
As variáveis são dinâmicas e dependem do template SQL selecionado. Cada variável deve ser enviada no formato:
- **`var_{nome_da_variavel}`** (string): Valor da variável

## Exemplo de Uso

### Exemplo 1: Com consulta da API Hubsoft
```python
import requests

url = "http://localhost:8000/campanhas/iniciar-processamento/"
data = {
    'titulo': 'Consulta de Clientes - Janeiro 2024',
    'template_sql': '1',  # ID do template SQL
    'credencial_hubsoft': '1',  # ID da credencial Hubsoft
    'credencial_banco': '1',  # ID da credencial de banco
    'pular_consulta_api': '',  # Não pular consulta da API
    'var_data_inicio': '2024-01-01',  # Variável do template
    'var_data_fim': '2024-01-31',  # Variável do template
    'var_status': 'ativo'  # Variável do template
}

response = requests.post(url, data=data)
print(response.json())
```

### Exemplo 2: Pulando consulta da API Hubsoft
```python
import requests

url = "http://localhost:8000/campanhas/iniciar-processamento/"
data = {
    'titulo': 'Teste de Envio - Sem API',
    'template_sql': '2',  # ID do template SQL
    'credencial_banco': '1',  # ID da credencial de banco
    'pular_consulta_api': 'on',  # Pular consulta da API
    'var_data_inicio': '2024-01-01',  # Variável do template
    'var_data_fim': '2024-01-31'  # Variável do template
}

response = requests.post(url, data=data)
print(response.json())
```

## Resposta de Sucesso
```json
{
    "status": "success",
    "message": "Processamento \"Consulta de Clientes - Janeiro 2024\" iniciado com sucesso!",
    "redirect_url": "/campanhas/execucao/123/"
}
```

## Resposta de Erro
```json
{
    "status": "error",
    "message": "Título, Template SQL e Credencial de Banco são obrigatórios."
}
```

## Validações

### 1. Validações Básicas
- `titulo`, `template_sql` e `credencial_banco` são obrigatórios
- Se `pular_consulta_api` não for `"on"`, então `credencial_hubsoft` é obrigatório

### 2. Validações de Variáveis
- Cada variável configurada no template SQL é validada
- Variáveis marcadas como obrigatórias no template devem ter valor
- Variáveis opcionais podem usar valores padrão se não fornecidas

## Como Descobrir as Variáveis do Template

### 1. Listar Templates SQL Disponíveis
```python
# Via Django shell
from campanhas.models import TemplateSQL

templates = TemplateSQL.objects.filter(ativo=True)
for template in templates:
    print(f"ID: {template.id} - {template.titulo}")
    print(f"Variáveis: {template.get_variaveis_configuradas()}")
    print("---")
```

### 2. Verificar Configuração de Variáveis
```python
# Via Django shell
template = TemplateSQL.objects.get(id=1)
variaveis = template.get_variaveis_configuradas()
print(variaveis)
```

Exemplo de saída:
```json
{
    "data_inicio": {
        "tipo": "date",
        "label": "Data de Início",
        "obrigatorio": true,
        "valor_padrao": "",
        "opcoes": []
    },
    "data_fim": {
        "tipo": "date", 
        "label": "Data de Fim",
        "obrigatorio": true,
        "valor_padrao": "",
        "opcoes": []
    },
    "status": {
        "tipo": "select",
        "label": "Status",
        "obrigatorio": false,
        "valor_padrao": "ativo",
        "opcoes": ["ativo", "inativo", "todos"]
    }
}
```

## Fluxo de Processamento

1. **Validação**: Verifica se todos os parâmetros obrigatórios foram fornecidos
2. **Criação**: Cria uma nova `ConsultaExecucao` com status 'pendente'
3. **Thread**: Inicia o processamento em uma thread separada
4. **Resposta**: Retorna JSON com status e URL de redirecionamento

## Status da Execução

- **`pendente`**: Execução criada, aguardando processamento
- **`processando`**: Execução em andamento
- **`concluida`**: Execução finalizada com sucesso
- **`erro`**: Execução finalizada com erro

## Monitoramento

Após iniciar o processamento, você pode:
1. Acessar a URL retornada em `redirect_url` para acompanhar o progresso
2. Verificar o status da execução
3. Visualizar os clientes consultados
4. Acompanhar os logs de processamento
