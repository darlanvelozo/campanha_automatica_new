# Documentação da API - Sistema de Envio de Campanhas Automáticas

## Visão Geral

Este sistema oferece APIs REST para gerenciar execuções de consultas SQL, processamento de clientes via API Hubsoft e envio de mensagens HSM via API Matrix. O sistema é dividido em dois módulos principais:

1. **Campanhas** - Execução de consultas SQL e processamento de clientes
2. **Emails** - Campanhas de email (módulo separado)

## Base URL
```
http://localhost:8099/api/
```

## Autenticação

Atualmente configurado com `AllowAny` (sem autenticação obrigatória). Para produção, recomenda-se implementar autenticação via token.

## APIs Disponíveis

### 1. Execuções de Consulta (ConsultaExecucaoViewSet)

#### 1.1 Listar Execuções
```http
GET /api/execucoes/
```

**Resposta:**
```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "titulo": "Consulta Vencimentos",
      "status": "concluido",
      "total_registros_sql": 100,
      "total_consultados_api": 95,
      "total_erros": 5,
      "data_inicio": "2024-01-15T10:00:00Z",
      "data_fim": "2024-01-15T10:05:00Z",
      "template_sql_titulo": "Template Vencimentos",
      "credencial_banco_titulo": "Banco Principal",
      "clientes_processados": 100,
      "clientes_com_sucesso": 95,
      "clientes_com_erro": 5
    }
  ]
}
```

#### 1.2 Criar Nova Execução
```http
POST /api/execucoes/
```

**Payload:**
```json
{
  "titulo": "Nova Execução de Teste",
  "template_sql_id": 1,
  "credencial_banco_id": 1,
  "credencial_hubsoft_id": 1,
  "valores_variaveis": {
    "data_vencimento": "2024-01-31",
    "valor_minimo": "100.00"
  },
  "pular_consulta_api": false,
  "iniciar_processamento": true
}
```

**Resposta:**
```json
{
  "id": 2,
  "titulo": "Nova Execução de Teste",
  "status": "pendente",
  "data_inicio": "2024-01-15T10:00:00Z",
  "redirect_url": "/execucao/2/"
}
```

#### 1.3 Detalhes de Execução
```http
GET /api/execucoes/{id}/
```

**Resposta:**
```json
{
  "id": 1,
  "titulo": "Consulta Vencimentos",
  "status": "concluido",
  "total_registros_sql": 100,
  "total_consultados_api": 95,
  "total_erros": 5,
  "log_execucao": "Processamento iniciado...",
  "data_inicio": "2024-01-15T10:00:00Z",
  "data_fim": "2024-01-15T10:05:00Z",
  "pular_consulta_api": false,
  "valores_variaveis": {
    "data_vencimento": "2024-01-31"
  },
  "template_sql": {
    "id": 1,
    "titulo": "Template Vencimentos",
    "descricao": "Template para consultar vencimentos",
    "consulta_sql": "SELECT * FROM faturas WHERE...",
    "ativo": true
  },
  "credencial_banco": {
    "id": 1,
    "titulo": "Banco Principal",
    "tipo_banco": "postgresql",
    "host": "localhost",
    "porta": 5432,
    "banco": "db_campanhas",
    "ativo": true
  },
  "credencial_hubsoft": {
    "id": 1,
    "titulo": "Hubsoft Principal",
    "url_base": "https://api.hubsoft.com.br",
    "username": "usuario",
    "ativo": true
  },
  "consultas_clientes": [
    {
      "id": 1,
      "cliente": {
        "id": 1,
        "codigo_cliente": "12345",
        "nome_razaosocial": "Cliente Exemplo",
        "telefone_corrigido": "11999999999",
        "vencimento_fatura": "2024-01-31",
        "valor_fatura": "150.00"
      },
      "sucesso_api": true,
      "data_consulta": "2024-01-15T10:01:00Z"
    }
  ],
  "clientes_processados": 100,
  "clientes_com_sucesso": 95,
  "clientes_com_erro": 5
}
```

#### 1.4 Status da Execução
```http
GET /api/execucoes/{id}/status/
```

**Resposta:**
```json
{
  "id": 1,
  "titulo": "Consulta Vencimentos",
  "status": "processando",
  "status_display": "Processando",
  "total_registros_sql": 100,
  "total_consultados_api": 45,
  "total_erros": 2,
  "clientes_processados": 47,
  "clientes_com_sucesso": 45,
  "clientes_com_erro": 2,
  "data_inicio": "2024-01-15T10:00:00Z",
  "data_fim": null,
  "progresso_percentual": 47.0
}
```

#### 1.5 Clientes da Execução
```http
GET /api/execucoes/{id}/clientes/
```

#### 1.6 Clientes com Sucesso
```http
GET /api/execucoes/{id}/clientes_sucesso/
```

#### 1.7 Clientes com Erro
```http
GET /api/execucoes/{id}/clientes_erro/
```

#### 1.8 Recursos Disponíveis
```http
GET /api/execucoes/recursos/
```

**📝 Atualização:** Este endpoint agora inclui as **variáveis de cada template SQL** com suas configurações completas.

**Resposta:**
```json
{
  "templates_sql": [
    {
      "id": 1,
      "titulo": "Template Vencimentos",
      "descricao": "Template para consultar vencimentos",
      "variaveis": [
        {
          "nome": "data_vencimento",
          "label": "Data de Vencimento",
          "tipo": "date",
          "obrigatorio": true,
          "valor_padrao": "",
          "opcoes": []
        },
        {
          "nome": "valor_minimo",
          "label": "Valor Mínimo",
          "tipo": "decimal",
          "obrigatorio": false,
          "valor_padrao": "0.00",
          "opcoes": []
        }
      ]
    }
  ],
  "credenciais_banco": [
    {
      "id": 1,
      "titulo": "Banco Principal",
      "tipo_banco": "postgresql",
      "host": "localhost",
      "porta": 5432
    }
  ],
  "credenciais_hubsoft": [
    {
      "id": 1,
      "titulo": "Hubsoft Principal",
      "url_base": "https://api.hubsoft.com.br",
      "username": "usuario"
    }
  ]
}
```

#### 1.9 Variáveis do Template
```http
GET /api/execucoes/template_variaveis/?template_id=1
```

**Resposta:**
```json
{
  "template_id": 1,
  "template_titulo": "Template Vencimentos",
  "variaveis": {
    "data_vencimento": {
      "label": "Data de Vencimento",
      "tipo": "date",
      "obrigatorio": true,
      "valor_padrao": null
    },
    "valor_minimo": {
      "label": "Valor Mínimo",
      "tipo": "decimal",
      "obrigatorio": false,
      "valor_padrao": "0.00"
    }
  }
}
```

### 2. Clientes Consultados (ConsultaClienteViewSet)

#### 2.1 Listar Clientes
```http
GET /api/clientes/
```

**Parâmetros de Query:**
- `execucao`: Filtrar por ID da execução
- `sucesso`: Filtrar por sucesso (true/false)

**Exemplo:**
```http
GET /api/clientes/?execucao=1&sucesso=true
```

**Resposta:**
```json
{
  "count": 95,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "cliente": {
        "id": 1,
        "codigo_cliente": "12345",
        "nome_razaosocial": "Cliente Exemplo",
        "telefone_corrigido": "11999999999",
        "vencimento_fatura": "2024-01-31",
        "valor_fatura": "150.00",
        "pix": "pix@exemplo.com",
        "codigo_barras": "123456789",
        "link_boleto": "https://boleto.exemplo.com/123",
        "id_fatura": "FAT-001"
      },
      "sucesso_api": true,
      "data_consulta": "2024-01-15T10:01:00Z",
      "dados_originais_sql": {
        "codigo_cliente": "12345",
        "nome": "Cliente Exemplo"
      },
      "dados_api_response": {
        "telefone": "11999999999",
        "email": "cliente@exemplo.com"
      },
      "erro_api": null
    }
  ]
}
```

#### 2.2 Detalhes do Cliente
```http
GET /api/clientes/{id}/
```

## Endpoints Web (Não-REST)

### Execuções
- `POST /iniciar-processamento/` - Iniciar processamento de consulta
- `GET /execucao/{id}/status/` - Status via AJAX
- `GET /execucao/{id}/exportar/` - Exportar resultados CSV
- `GET /execucao/{id}/exportar-erros/` - Exportar erros CSV
- `POST /execucao/{id}/cancelar/` - Cancelar processamento
- `POST /execucao/{id}/reiniciar/` - Reiniciar processamento

### HSM (Envio de Mensagens)
- `GET /execucao/{id}/configurar-hsm/` - Configurar envio HSM
- `POST /execucao/{id}/enviar-hsm-atual/` - Enviar HSM com configuração atual
- `POST /iniciar-envio-hsm/` - Iniciar novo envio HSM
- `GET /hsm-template/{id}/variaveis/` - Obter variáveis do template HSM
- `GET /envios-hsm/` - Listar envios HSM
- `GET /envio-hsm/{id}/` - Detalhes do envio HSM
- `GET /envio-hsm/{id}/status/` - Status do envio HSM
- `POST /envio-hsm/{id}/cancelar/` - Cancelar envio HSM

### Utilitários
- `GET /template/{id}/variaveis/` - Variáveis do template SQL
- `GET /cliente/{id}/detalhes/` - Detalhes completos do cliente
- `GET /cliente/{id}/variaveis/` - Variáveis disponíveis do cliente (API)

### 3. Envios HSM (EnvioHSMMatrixViewSet) ✅ **IMPLEMENTADO**

#### 3.1 Listar Envios HSM
```http
GET /api/envios-hsm/
```

**Parâmetros de Query:**
- `status`: Filtrar por status (pendente, enviando, concluido, cancelado, erro, pausado)
- `execucao`: Filtrar por ID da execução

**Exemplo:**
```http
GET /api/envios-hsm/?status=concluido&execucao=1
```

**Resposta:**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "titulo": "Campanha Vencimentos Janeiro",
      "status_envio": "concluido",
      "total_clientes": 100,
      "total_enviados": 95,
      "total_erros": 5,
      "total_pendentes": 0,
      "data_criacao": "2024-01-15T10:00:00Z",
      "data_inicio_envio": "2024-01-15T10:05:00Z",
      "data_fim_envio": "2024-01-15T10:15:00Z",
      "hsm_template_nome": "Aviso de Vencimento",
      "matrix_config_nome": "Matrix Principal",
      "execucao_titulo": "Consulta Vencimentos",
      "progresso_percentual": 100.0
    }
  ]
}
```

#### 3.2 Criar Novo Envio HSM
```http
POST /api/envios-hsm/
```

**Payload para HSM Padrão:**
```json
{
  "titulo": "Campanha Vencimentos Fevereiro",
  "execucao_id": 1,
  "hsm_template_id": 2,
  "matrix_config_id": 1,
  "configuracao_variaveis": {
    "1": "nome_cliente",
    "2": "valor_fatura",
    "3": "vencimento_fatura"
  },
  "iniciar_processamento": true
}
```

**Payload para HSM de Pagamento (com configuração predefinida):**
```json
{
  "titulo": "HSM Pagamento - MegaLink 5 dias vencidos",
  "execucao_id": 471,
  "hsm_template_id": 48,
  "matrix_config_id": 1,
  "configuracao_variaveis": {
    "1": "nome_cliente",
    "2": "valor_fatura",
    "3": "vencimento_fatura"
  },
  "configuracao_pagamento_hsm_id": 1,
  "iniciar_processamento": true
}
```

**Payload para HSM de Pagamento (configuração manual):**
```json
{
  "titulo": "HSM Pagamento Manual",
  "execucao_id": 471,
  "hsm_template_id": 48,
  "matrix_config_id": 1,
  "configuracao_variaveis": {
    "1": "nome_cliente",
    "2": "valor_fatura",
    "3": "vencimento_fatura"
  },
  "razao_social_empresa": "MEGA TELEINFORMATICA LTDA",
  "cnpj_empresa": "11408142000109",
  "nome_produto_padrao": "FATURA MENSAL",
  "iniciar_processamento": true
}
```

**Formato Alternativo (também aceito):**
```json
{
  "titulo": "Campanha Vencimentos Fevereiro",
  "execucao_id": 1,
  "hsm_template_id": 2,
  "matrix_config_id": 1,
  "configuracao_variaveis": {
    "1": {
      "campo_cliente": "nome_cliente",
      "obrigatorio": true
    },
    "2": {
      "campo_cliente": "valor_fatura",
      "obrigatorio": true
    },
    "3": {
      "campo_cliente": "vencimento_fatura",
      "obrigatorio": true
    }
  },
  "iniciar_processamento": true
}
```

**Resposta:**
```json
{
  "id": 2,
  "titulo": "Campanha Vencimentos Fevereiro",
  "status_envio": "pendente",
  "data_criacao": "2024-01-15T10:00:00Z",
  "redirect_url": "/envio-hsm/2/"
}
```

#### 3.3 Detalhes do Envio HSM
```http
GET /api/envios-hsm/{id}/
```

**Resposta:**
```json
{
  "id": 1,
  "titulo": "Campanha Vencimentos Janeiro",
  "hsm_template": {
    "id": 2,
    "nome": "Aviso de Vencimento",
    "hsm_id": 12345,
    "cod_flow": 67,
    "tipo_envio": 1,
    "tipo_template": "padrao"
  },
  "matrix_api_config": {
    "id": 1,
    "nome": "Matrix Principal",
    "base_url": "https://megalink.matrixdobrasil.ai",
    "cod_conta": 123
  },
  "consulta_execucao": {
    "id": 1,
    "titulo": "Consulta Vencimentos",
    "status": "concluido"
  },
  "status_envio": "concluido",
  "data_criacao": "2024-01-15T10:00:00Z",
  "data_inicio_envio": "2024-01-15T10:05:00Z",
  "data_fim_envio": "2024-01-15T10:15:00Z",
  "total_clientes": 100,
  "total_enviados": 95,
  "total_erros": 5,
  "total_pendentes": 0,
  "log_execucao": "Processamento iniciado...",
  "configuracao_variaveis": {
    "1": "nome_razaosocial",
    "2": "valor_fatura"
  },
  "envios_individuais": [
    {
      "id": 1,
      "cliente_nome": "João Silva",
      "cliente_telefone": "11999999999",
      "status": "enviado",
      "data_envio": "2024-01-15T10:05:30Z",
      "template_usado": "principal",
      "hsm_enviado": "primeiro"
    }
  ],
  "progresso_percentual": 100.0
}
```

#### 3.4 Status do Envio HSM
```http
GET /api/envios-hsm/{id}/status/
```

**Resposta:**
```json
{
  "id": 1,
  "titulo": "Campanha Vencimentos Janeiro",
  "status_envio": "enviando",
  "total_clientes": 100,
  "total_enviados": 45,
  "total_erros": 2,
  "total_pendentes": 53,
  "progresso_percentual": 47.0,
  "data_criacao": "2024-01-15T10:00:00Z",
  "data_inicio_envio": "2024-01-15T10:05:00Z",
  "data_fim_envio": null
}
```

#### 3.5 Executar Envio HSM
```http
POST /api/envios-hsm/{id}/executar/
```

**Resposta:**
```json
{
  "message": "Envio iniciado com sucesso",
  "envio_id": 1,
  "status": "processando"
}
```

#### 3.6 Cancelar Envio HSM
```http
POST /api/envios-hsm/{id}/cancelar/
```

**Resposta:**
```json
{
  "message": "Envio cancelado com sucesso",
  "envio_id": 1,
  "status": "cancelado"
}
```

### 4. Templates HSM (HSMTemplateViewSet) ✅ **IMPLEMENTADO**

#### 4.1 Listar Templates HSM
```http
GET /api/hsm-templates/
```

**Parâmetros de Query:**
- `ativo`: Filtrar por status ativo (true/false)

**Exemplo:**
```http
GET /api/hsm-templates/?ativo=true
```

**Resposta:**
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "nome": "Aviso de Vencimento",
      "hsm_id": 12345,
      "cod_flow": 67,
      "tipo_envio": 1,
      "tipo_template": "padrao",
      "tipo_envio_display": "Atendimento Automático",
      "tipo_template_display": "Padrão",
      "descricao": "Template para avisar sobre vencimento de fatura",
      "ativo": true,
      "data_criacao": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### 4.2 Detalhes do Template HSM
```http
GET /api/hsm-templates/{id}/
```

#### 4.3 Variáveis do Template HSM
```http
GET /api/hsm-templates/{id}/variaveis/
```

**Resposta:**
```json
{
  "template_id": 1,
  "template_nome": "Aviso de Vencimento",
  "hsm_id": 12345,
  "variaveis": [
    {
      "id": "1",
      "nome": "nome_cliente",
      "obrigatorio": true,
      "descricao": "Nome do cliente"
    },
    {
      "id": "2", 
      "nome": "valor",
      "obrigatorio": true,
      "descricao": "Valor da fatura"
    },
    {
      "id": "3",
      "nome": "vencimento",
      "obrigatorio": false,
      "descricao": "Data de vencimento"
    }
  ]
}
```

### 5. Configurações de Pagamento HSM (ConfiguracaoPagamentoHSMViewSet) ✅ **IMPLEMENTADO**

#### 5.1 Listar Configurações de Pagamento
```http
GET /api/configuracoes-pagamento-hsm/
```

**Parâmetros de Query:**
- `ativo`: Filtrar por status ativo (true/false)

**Exemplo:**
```http
GET /api/configuracoes-pagamento-hsm/?ativo=true
```

**Resposta:**
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "nome": "Megalink",
      "descricao": "",
      "razao_social_empresa": "MEGA TELEINFORMATICA LTDA",
      "cnpj_empresa": "11408142000109",
      "nome_produto_padrao": "FATURA MENSAL",
      "tipo_produto": "digital-goods",
      "val_imposto": "0.00",
      "val_desconto": "0.00",
      "variaveis_flow_padrao": {},
      "configuracao_extra": {},
      "ativo": true,
      "data_criacao": "2025-08-19T15:46:20.603181-03:00",
      "data_atualizacao": "2025-08-19T15:46:20.603193-03:00"
    }
  ]
}
```

#### 5.2 Detalhes da Configuração de Pagamento
```http
GET /api/configuracoes-pagamento-hsm/{id}/
```

#### 5.3 Criar Configuração de Pagamento
```http
POST /api/configuracoes-pagamento-hsm/
```

**Payload:**
```json
{
  "nome": "Nova Empresa",
  "descricao": "Configuração para nova empresa",
  "razao_social_empresa": "NOVA EMPRESA LTDA",
  "cnpj_empresa": "12345678000199",
  "nome_produto_padrao": "MENSALIDADE",
  "tipo_produto": "digital-goods",
  "val_imposto": "0.00",
  "val_desconto": "0.00",
  "variaveis_flow_padrao": {},
  "configuracao_extra": {},
  "ativo": true
}
```

### 6. Configurações Matrix (MatrixAPIConfigViewSet) ✅ **IMPLEMENTADO**

#### 6.1 Listar Configurações Matrix
```http
GET /api/configuracoes-matrix/
```

**Parâmetros de Query:**
- `ativo`: Filtrar por status ativo (true/false)

**Exemplo:**
```http
GET /api/configuracoes-matrix/?ativo=true
```

**Resposta:**
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "nome": "Matrix Principal",
      "base_url": "https://megalink.matrixdobrasil.ai",
      "cod_conta": 123,
      "ativo": true,
      "data_criacao": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### 6.2 Detalhes da Configuração Matrix
```http
GET /api/configuracoes-matrix/{id}/
```

**Resposta:**
```json
{
  "id": 1,
  "nome": "Matrix Principal",
  "base_url": "https://megalink.matrixdobrasil.ai",
  "api_key": "abc12345...",
  "cod_conta": 123,
  "ativo": true,
  "data_criacao": "2024-01-01T00:00:00Z",
  "data_atualizacao": "2024-01-15T10:00:00Z"
}
```

#### 6.3 Testar Configuração Matrix
```http
POST /api/configuracoes-matrix/{id}/testar/
```

**Resposta de Sucesso:**
```json
{
  "sucesso": true,
  "mensagem": "Conexão com API Matrix estabelecida com sucesso",
  "status_code": 200,
  "configuracao": {
    "id": 1,
    "nome": "Matrix Principal",
    "base_url": "https://megalink.matrixdobrasil.ai"
  }
}
```

**Resposta de Erro:**
```json
{
  "sucesso": false,
  "mensagem": "Erro de conexão: Não foi possível conectar com a API Matrix",
  "configuracao": {
    "id": 1,
    "nome": "Matrix Principal",
    "base_url": "https://megalink.matrixdobrasil.ai"
  }
}
```

## Funcionalidades Faltantes para APIs REST

### ❌ APIs REST Faltantes para Configurações

1. **ViewSet para TemplateSQL**
   - `GET /api/templates-sql/` - Listar templates SQL
   - `POST /api/templates-sql/` - Criar template SQL
   - `GET /api/templates-sql/{id}/` - Detalhes do template
   - `PUT/PATCH /api/templates-sql/{id}/` - Atualizar template
   - `DELETE /api/templates-sql/{id}/` - Deletar template

2. **ViewSet para CredenciaisBancoDados**
   - `GET /api/credenciais-banco/` - Listar credenciais
   - `POST /api/credenciais-banco/` - Criar credencial
   - `GET /api/credenciais-banco/{id}/` - Detalhes da credencial
   - `PUT/PATCH /api/credenciais-banco/{id}/` - Atualizar credencial
   - `DELETE /api/credenciais-banco/{id}/` - Deletar credencial
   - `POST /api/credenciais-banco/{id}/testar/` - Testar conexão

3. **ViewSet para CredenciaisHubsoft**
   - `GET /api/credenciais-hubsoft/` - Listar credenciais
   - `POST /api/credenciais-hubsoft/` - Criar credencial
   - `GET /api/credenciais-hubsoft/{id}/` - Detalhes da credencial
   - `PUT/PATCH /api/credenciais-hubsoft/{id}/` - Atualizar credencial
   - `DELETE /api/credenciais-hubsoft/{id}/` - Deletar credencial
   - `POST /api/credenciais-hubsoft/{id}/testar/` - Testar conexão

## Mapeamento de Variáveis HSM ✅ **IMPORTANTE**

### Campos Virtuais vs Campos do Modelo

O sistema cria **campos virtuais** para facilitar o mapeamento de variáveis HSM. É importante usar os campos corretos:

#### Campos Virtuais (criados automaticamente):
- `nome_cliente` → mapeado para `nome_razaosocial` do modelo
- `telefone` → mapeado para `telefone_corrigido` do modelo  
- `pix_copia_cola` → mapeado para `pix` do modelo
- `empresa` → mapeado para `credencial_banco.titulo`

#### Campos do Modelo ClienteConsultado:
- `codigo_cliente`, `nome_razaosocial`, `telefone_corrigido`
- `vencimento_fatura`, `valor_fatura`, `pix`, `codigo_barras`
- `link_boleto`, `id_fatura`

### ⚠️ **ATENÇÃO: Mapeamento Correto**

**❌ INCORRETO (não funciona):**
```json
{
  "configuracao_variaveis": {
    "1": "nome_razaosocial",  // Campo direto do modelo
    "2": "valor_fatura",
    "3": "vencimento_fatura"
  }
}
```

**✅ CORRETO (funciona):**
```json
{
  "configuracao_variaveis": {
    "1": "nome_cliente",      // Campo virtual
    "2": "valor_fatura",      // Campo do modelo
    "3": "vencimento_fatura"  // Campo do modelo
  }
}
```

### Como Verificar Variáveis do Template

Sempre consulte as variáveis que o template HSM espera:

```bash
curl -X GET "http://localhost:8099/api/hsm-templates/{template_id}/variaveis/"
```

**Exemplo de resposta:**
```json
{
  "template_id": 48,
  "template_nome": "5 dias vencidos mega",
  "hsm_id": 251,
  "variaveis": [
    {
      "id": "1",
      "nome": "nome_cliente",     // ← Use "nome_cliente" no mapeamento
      "obrigatorio": true,
      "descricao": ""
    },
    {
      "id": "2", 
      "nome": "valor",            // ← Use "valor_fatura" no mapeamento
      "obrigatorio": true,
      "descricao": ""
    },
    {
      "id": "3",
      "nome": "data_vencimento",  // ← Use "vencimento_fatura" no mapeamento
      "obrigatorio": true,
      "descricao": ""
    }
  ]
}
```

## Processo Completo de Execução e Envio HSM

### Fluxo Completo (Via API REST) ✅ **IMPLEMENTADO**
1. **Criar Execução**: `POST /api/execucoes/`
2. **Aguardar Conclusão**: `GET /api/execucoes/{id}/status/`
3. **Ver Variáveis do Template**: `GET /api/hsm-templates/{id}/variaveis/`
4. **Criar Envio HSM**: `POST /api/envios-hsm/`
5. **Executar Envio**: `POST /api/envios-hsm/{id}/executar/`
6. **Acompanhar Progresso**: `GET /api/envios-hsm/{id}/status/`

### Exemplo de Uso Completo via API

```python
import requests
import time

# 1. Criar execução (já funcionava)
exec = requests.post('/api/execucoes/', json={
    "titulo": "Consulta Vencimentos",
    "template_sql_id": 1,
    "credencial_banco_id": 1,
    "credencial_hubsoft_id": 1,
    "valores_variaveis": {"data_vencimento": "2024-02-28"},
    "iniciar_processamento": True
}).json()

# 2. Aguardar conclusão (já funcionava)
while requests.get(f'/api/execucoes/{exec["id"]}/status/').json()['status'] != 'concluido':
    time.sleep(5)

# 3. Ver variáveis do template HSM (NOVO)
vars = requests.get('/api/hsm-templates/2/variaveis/').json()

# 4. Criar envio HSM (NOVO) - ✅ MAPEAMENTO CORRETO
envio = requests.post('/api/envios-hsm/', json={
    "titulo": "Campanha Vencimentos",
    "execucao_id": exec["id"],
    "hsm_template_id": 2,
    "matrix_config_id": 1,
    "configuracao_variaveis": {
        "1": "nome_cliente",      # ✅ Campo virtual (não nome_razaosocial)
        "2": "valor_fatura",      # ✅ Campo do modelo
        "3": "vencimento_fatura"  # ✅ Campo do modelo
    },
    "iniciar_processamento": True
}).json()

# 4b. Para HSM de Pagamento (NOVO)
envio_pagamento = requests.post('/api/envios-hsm/', json={
    "titulo": "HSM Pagamento - 5 dias vencidos",
    "execucao_id": exec["id"],
    "hsm_template_id": 48,  # Template de pagamento
    "matrix_config_id": 1,
    "configuracao_variaveis": {
        "1": "nome_cliente",      # ✅ Campo virtual
        "2": "valor_fatura",      # ✅ Campo do modelo
        "3": "vencimento_fatura"  # ✅ Campo do modelo
    },
    "configuracao_pagamento_hsm_id": 1,  # ✅ Configuração de pagamento
    "iniciar_processamento": True
}).json()

# 5. Executar envio (NOVO)
requests.post(f'/api/envios-hsm/{envio["id"]}/executar/')

# 6. Acompanhar progresso (NOVO)
while True:
    status = requests.get(f'/api/envios-hsm/{envio["id"]}/status/').json()
    print(f"Progresso: {status['progresso_percentual']}%")
    if status['status_envio'] == 'concluido':
        break
    time.sleep(5)

print("Campanha concluída!")
```

## Recomendações

1. ✅ **ViewSets REST para HSM implementados** - Processo completo funcional
2. **Adicionar autenticação** via Token ou JWT
3. **Implementar paginação** consistente em todos os endpoints
4. **Adicionar filtros avançados** nos ViewSets
5. **Implementar validações** mais robustas nos serializers
6. **Adicionar documentação automática** com drf-spectacular
7. **Implementar logs de auditoria** para todas as operações
8. **Adicionar rate limiting** para proteger a API

## Status dos Endpoints

| Categoria | Endpoints REST | Endpoints Web | Status |
|-----------|----------------|---------------|---------|
| Execuções | ✅ Completos | ✅ Completos | Funcional |
| Clientes | ✅ Completos | ✅ Completos | Funcional |
| HSM Envios | ✅ **IMPLEMENTADOS** | ✅ Completos | **100% Funcional** |
| HSM Templates | ✅ **IMPLEMENTADOS** | ❌ Faltando | **100% Funcional** |
| Matrix Config | ✅ **IMPLEMENTADOS** | ❌ Faltando | **100% Funcional** |
| Pagamento HSM | ✅ **IMPLEMENTADOS** | ✅ Completos | **100% Funcional** |
| Configurações | ❌ Faltando | ❌ Faltando | Parcial |

## Conclusão

✅ **IMPLEMENTAÇÃO CONCLUÍDA E CORRIGIDA!** 

O sistema agora possui **APIs REST completas para todo o processo de envio de HSM**, incluindo **HSM de Pagamento**. É possível:

- ✅ Criar execuções via API
- ✅ Processar clientes via API  
- ✅ Configurar templates HSM via API
- ✅ Criar envios HSM padrão via API
- ✅ **Criar envios HSM de pagamento via API** 🆕
- ✅ **Gerenciar configurações de pagamento via API** 🆕
- ✅ Executar campanhas HSM via API
- ✅ Acompanhar progresso em tempo real via API
- ✅ Cancelar envios via API
- ✅ Testar configurações Matrix via API

### 🎯 **Correções Implementadas:**

1. **Mapeamento de Variáveis Corrigido**: Agora a API usa os mesmos campos virtuais que a aplicação web
2. **Validação de Campos Virtuais**: Serializer aceita campos como `nome_cliente`, `telefone`, `pix_copia_cola`
3. **Suporte Completo a HSM de Pagamento**: API funciona identicamente à aplicação web
4. **Configurações de Pagamento**: Endpoint completo para gerenciar configurações de pagamento

### 📋 **Exemplo Funcional Testado:**

```bash
curl -X POST "http://localhost:8099/api/envios-hsm/" \
  -H "Content-Type: application/json" \
  -d '{
    "titulo": "HSM Pagamento - MegaLink 5 dias vencidos",
    "execucao_id": 471,
    "hsm_template_id": 48,
    "matrix_config_id": 1,
    "configuracao_variaveis": {
      "1": "nome_cliente",
      "2": "valor_fatura",
      "3": "vencimento_fatura"
    },
    "configuracao_pagamento_hsm_id": 1,
    "iniciar_processamento": true
  }'
```

**Resultado**: ✅ Status `concluido`, 4 de 5 mensagens enviadas com sucesso

**O processo está 100% automatizável via API REST** sem necessidade de interface web para o módulo HSM, incluindo HSM de pagamento.
