#!/bin/bash

###############################################################################
# Script de Migração - Projeto Campanha (Antigo → Novo)
# 
# Este script automatiza a migração do projeto antigo para o novo
# Executar com: bash migrar_projeto.sh
###############################################################################

set -e  # Para em caso de erro

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Diretórios
NOVO_PROJETO_DIR="/home/darlan/projetos_django/novo_envio_campanha_automatica/campanha_automatica_new/projeto_envio_campanha_automatica_matrix"
VENV_DIR="/home/darlan/projetos_django/novo_envio_campanha_automatica/campanha_automatica_new/projeto_envio_campanha_automatica_matrix/myenv"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}MIGRAÇÃO DO PROJETO CAMPANHA${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}⚠️  ATENÇÃO: Este script irá:${NC}"
echo "   1. Identificar e parar o serviço antigo na porta 8001"
echo "   2. Fazer backup da configuração atual do Nginx"
echo "   3. Instalar a nova configuração do Nginx"
echo "   4. Instalar e iniciar o novo serviço campanha-web"
echo ""
read -p "Deseja continuar? (s/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo -e "${RED}Migração cancelada.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FASE 1: PREPARAÇÃO${NC}"
echo -e "${GREEN}========================================${NC}"

# Verificar se está no diretório correto
cd "$NOVO_PROJETO_DIR" || { echo -e "${RED}Erro: Diretório do novo projeto não encontrado!${NC}"; exit 1; }

# 1.1. Identificar processo na porta 8001
echo -e "${YELLOW}1.1. Identificando processo na porta 8001...${NC}"
PORT_PROCESS=$(sudo lsof -ti :8001 2>/dev/null || echo "")

if [ -n "$PORT_PROCESS" ]; then
    echo -e "${YELLOW}Processo encontrado na porta 8001: PID $PORT_PROCESS${NC}"
    
    # Tentar identificar o serviço systemd
    SERVICE_NAME=$(sudo systemctl status $PORT_PROCESS 2>/dev/null | grep "Loaded:" | awk '{print $2}' | sed 's/.*\///' | sed 's/\.service//' || echo "")
    
    if [ -n "$SERVICE_NAME" ]; then
        echo -e "${YELLOW}Serviço identificado: $SERVICE_NAME${NC}"
        read -p "Deseja parar o serviço $SERVICE_NAME? (s/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            echo -e "${YELLOW}Parando serviço $SERVICE_NAME...${NC}"
            sudo systemctl stop $SERVICE_NAME
            echo -e "${GREEN}✓ Serviço parado${NC}"
        fi
    else
        echo -e "${YELLOW}Processo manual/gunicorn detectado${NC}"
        read -p "Deseja matar o processo PID $PORT_PROCESS? (s/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            echo -e "${YELLOW}Matando processo $PORT_PROCESS...${NC}"
            sudo kill -9 $PORT_PROCESS
            echo -e "${GREEN}✓ Processo encerrado${NC}"
        fi
    fi
else
    echo -e "${GREEN}✓ Porta 8001 livre${NC}"
fi
echo ""

# 1.2. Backup da configuração do Nginx
echo -e "${YELLOW}1.2. Fazendo backup da configuração do Nginx...${NC}"
if [ -f "/etc/nginx/sites-available/campanha.megalinkpiaui.com.br" ]; then
    sudo cp /etc/nginx/sites-available/campanha.megalinkpiaui.com.br /etc/nginx/sites-available/campanha.megalinkpiaui.com.br.backup_$(date +%Y%m%d_%H%M%S)
    echo -e "${GREEN}✓ Backup criado${NC}"
else
    echo -e "${YELLOW}⚠ Arquivo de configuração não encontrado (primeira instalação?)${NC}"
fi
echo ""

# 1.3. Verificar SECRET_KEY
echo -e "${YELLOW}1.3. Verificando SECRET_KEY...${NC}"
if grep -q "django-insecure-z2r1356f" campanha-web.service; then
    echo -e "${RED}⚠️  ATENÇÃO: SECRET_KEY padrão detectada!${NC}"
    echo -e "${YELLOW}Para produção, você DEVE gerar uma nova SECRET_KEY.${NC}"
    echo ""
    echo "Execute: python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
    echo ""
    read -p "Deseja continuar mesmo assim? (NÃO recomendado para produção) (s/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
        echo -e "${RED}Migração cancelada. Gere uma nova SECRET_KEY e edite o arquivo campanha-web.service${NC}"
        exit 1
    fi
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FASE 2: PREPARAR NOVO PROJETO${NC}"
echo -e "${GREEN}========================================${NC}"

# 2.1. Ativar ambiente virtual
echo -e "${YELLOW}2.1. Ativando ambiente virtual...${NC}"
source "$VENV_DIR/bin/activate" || { echo -e "${RED}Erro ao ativar ambiente virtual!${NC}"; exit 1; }
echo -e "${GREEN}✓ Ambiente virtual ativado${NC}"
echo ""

# 2.2. Instalar dependências
echo -e "${YELLOW}2.2. Verificando dependências...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Dependências verificadas${NC}"
echo ""

# 2.3. Executar migrações
echo -e "${YELLOW}2.3. Executando migrações do banco de dados...${NC}"
python manage.py migrate --noinput
echo -e "${GREEN}✓ Migrações executadas${NC}"
echo ""

# 2.4. Coletar arquivos estáticos
echo -e "${YELLOW}2.4. Coletando arquivos estáticos...${NC}"
python manage.py collectstatic --noinput --clear
echo -e "${GREEN}✓ Arquivos estáticos coletados${NC}"
echo ""

# 2.5. Criar diretórios necessários
echo -e "${YELLOW}2.5. Criando diretórios necessários...${NC}"
mkdir -p logs media staticfiles
sudo mkdir -p /var/log/gunicorn
sudo chown -R darlan:darlan /var/log/gunicorn
echo -e "${GREEN}✓ Diretórios criados${NC}"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FASE 3: INSTALAR NGINX E SERVIÇO${NC}"
echo -e "${GREEN}========================================${NC}"

# 3.1. Instalar configuração do Nginx
echo -e "${YELLOW}3.1. Instalando nova configuração do Nginx...${NC}"
if [ -f "campanha.megalinkpiaui.com.br.nginx" ]; then
    sudo cp campanha.megalinkpiaui.com.br.nginx /etc/nginx/sites-available/campanha.megalinkpiaui.com.br
    echo -e "${GREEN}✓ Configuração copiada${NC}"
    
    # Testar configuração
    echo -e "${YELLOW}3.2. Testando configuração do Nginx...${NC}"
    if sudo nginx -t; then
        echo -e "${GREEN}✓ Configuração válida${NC}"
        echo -e "${YELLOW}3.3. Recarregando Nginx...${NC}"
        sudo systemctl reload nginx
        echo -e "${GREEN}✓ Nginx recarregado${NC}"
    else
        echo -e "${RED}✗ Erro na configuração do Nginx!${NC}"
        echo -e "${YELLOW}Restaurando backup...${NC}"
        sudo cp /etc/nginx/sites-available/campanha.megalinkpiaui.com.br.backup_* /etc/nginx/sites-available/campanha.megalinkpiaui.com.br 2>/dev/null || true
        exit 1
    fi
else
    echo -e "${RED}✗ Arquivo campanha.megalinkpiaui.com.br.nginx não encontrado!${NC}"
    exit 1
fi
echo ""

# 3.4. Instalar serviço systemd
echo -e "${YELLOW}3.4. Instalando serviço systemd...${NC}"
if [ -f "campanha-web.service" ]; then
    sudo cp campanha-web.service /etc/systemd/system/
    sudo systemctl daemon-reload
    echo -e "${GREEN}✓ Serviço instalado${NC}"
    
    echo -e "${YELLOW}3.5. Habilitando serviço para iniciar no boot...${NC}"
    sudo systemctl enable campanha-web
    echo -e "${GREEN}✓ Serviço habilitado${NC}"
    
    echo -e "${YELLOW}3.6. Iniciando serviço campanha-web...${NC}"
    sudo systemctl start campanha-web
    echo -e "${GREEN}✓ Serviço iniciado${NC}"
else
    echo -e "${RED}✗ Arquivo campanha-web.service não encontrado!${NC}"
    exit 1
fi
echo ""

# Aguardar serviço inicializar
echo -e "${YELLOW}Aguardando serviço inicializar...${NC}"
sleep 5

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FASE 4: VERIFICAÇÕES${NC}"
echo -e "${GREEN}========================================${NC}"

# 4.1. Verificar status do serviço
echo -e "${YELLOW}4.1. Verificando status do serviço...${NC}"
if sudo systemctl is-active --quiet campanha-web; then
    echo -e "${GREEN}✓ Serviço campanha-web está rodando!${NC}"
else
    echo -e "${RED}✗ Serviço campanha-web NÃO está rodando!${NC}"
    echo -e "${YELLOW}Verificando logs...${NC}"
    sudo journalctl -u campanha-web -n 50 --no-pager
    exit 1
fi
echo ""

# 4.2. Verificar porta 8001
echo -e "${YELLOW}4.2. Verificando porta 8001...${NC}"
if sudo lsof -i :8001 | grep -q gunicorn; then
    echo -e "${GREEN}✓ Gunicorn rodando na porta 8001${NC}"
else
    echo -e "${RED}✗ Nenhum processo na porta 8001!${NC}"
    exit 1
fi
echo ""

# 4.3. Testar aplicação localmente
echo -e "${YELLOW}4.3. Testando aplicação localmente...${NC}"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ | grep -q "200\|301\|302"; then
    echo -e "${GREEN}✓ Aplicação respondendo na porta 8001!${NC}"
else
    echo -e "${YELLOW}⚠ Aplicação pode não estar respondendo corretamente${NC}"
fi
echo ""

# 4.4. Testar via domínio
echo -e "${YELLOW}4.4. Testando via domínio HTTPS...${NC}"
if curl -s -o /dev/null -w "%{http_code}" https://campanha.megalinkpiaui.com.br/ | grep -q "200\|301\|302"; then
    echo -e "${GREEN}✓ Domínio acessível via HTTPS!${NC}"
else
    echo -e "${YELLOW}⚠ Verifique o domínio manualmente: https://campanha.megalinkpiaui.com.br/${NC}"
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}MIGRAÇÃO CONCLUÍDA COM SUCESSO!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📊 Resumo:${NC}"
echo "  • Serviço: campanha-web.service"
echo "  • Status: $(sudo systemctl is-active campanha-web)"
echo "  • Porta: 8001"
echo "  • Domínio: https://campanha.megalinkpiaui.com.br/"
echo ""
echo -e "${YELLOW}📝 Próximos Passos:${NC}"
echo "  1. Acesse: https://campanha.megalinkpiaui.com.br/"
echo "  2. Verifique o novo app 'campaigns'"
echo "  3. Teste as funcionalidades"
echo "  4. Monitore os logs: sudo journalctl -u campanha-web -f"
echo ""
echo -e "${YELLOW}⚠️  Importante:${NC}"
echo "  • Gere uma nova SECRET_KEY para produção!"
echo "  • Monitore os logs por 24-48h"
echo "  • Faça backup do banco de dados regularmente"
echo ""
echo -e "${BLUE}Comandos úteis:${NC}"
echo "  • Ver logs: sudo journalctl -u campanha-web -f"
echo "  • Status: sudo systemctl status campanha-web"
echo "  • Reiniciar: sudo systemctl restart campanha-web"
echo "  • Ver processos: ps aux | grep gunicorn"
echo ""
