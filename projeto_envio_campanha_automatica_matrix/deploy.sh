#!/bin/bash

###############################################################################
# Script de Deploy - Campanha Manager
# 
# Este script automatiza o processo de deploy da aplicação Django
# Execute com: bash deploy.sh
###############################################################################

set -e  # Para em caso de erro

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Diretórios
PROJECT_DIR="/home/darlan/projetos_django/novo_envio_campanha_automatica/campanha_automatica_new/projeto_envio_campanha_automatica_matrix"
VENV_DIR="/home/darlan/projetos_django/novo_envio_campanha_automatica/campanha_automatica_new/projeto_envio_campanha_automatica_matrix/myenv"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Script de Deploy - Campanha Manager${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Verifica se está no diretório correto
cd "$PROJECT_DIR" || { echo -e "${RED}Erro: Diretório do projeto não encontrado!${NC}"; exit 1; }

# Ativa o ambiente virtual
echo -e "${YELLOW}1. Ativando ambiente virtual...${NC}"
source "$VENV_DIR/bin/activate" || { echo -e "${RED}Erro ao ativar ambiente virtual!${NC}"; exit 1; }
echo -e "${GREEN}✓ Ambiente virtual ativado${NC}"
echo ""

# Instala/atualiza dependências
echo -e "${YELLOW}2. Instalando/atualizando dependências...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Dependências instaladas${NC}"
echo ""

# Executa migrações
echo -e "${YELLOW}3. Executando migrações do banco de dados...${NC}"
python manage.py migrate --noinput
echo -e "${GREEN}✓ Migrações executadas${NC}"
echo ""

# Coleta arquivos estáticos
echo -e "${YELLOW}4. Coletando arquivos estáticos...${NC}"
python manage.py collectstatic --noinput --clear
echo -e "${GREEN}✓ Arquivos estáticos coletados${NC}"
echo ""

# Cria diretórios necessários
echo -e "${YELLOW}5. Criando diretórios necessários...${NC}"
mkdir -p logs
mkdir -p media
mkdir -p staticfiles
sudo mkdir -p /var/log/gunicorn
sudo chown -R darlan:darlan /var/log/gunicorn
echo -e "${GREEN}✓ Diretórios criados${NC}"
echo ""

# Verifica se o serviço systemd existe
if [ -f "/etc/systemd/system/campanha-web.service" ]; then
    echo -e "${YELLOW}6. Reiniciando serviço campanha-web...${NC}"
    sudo systemctl daemon-reload
    sudo systemctl restart campanha-web
    echo -e "${GREEN}✓ Serviço reiniciado${NC}"
else
    echo -e "${YELLOW}6. Instalando serviço systemd...${NC}"
    sudo cp campanha-web.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable campanha-web
    sudo systemctl start campanha-web
    echo -e "${GREEN}✓ Serviço instalado e iniciado${NC}"
fi
echo ""

# Aguarda alguns segundos
sleep 3

# Verifica status do serviço
echo -e "${YELLOW}7. Verificando status do serviço...${NC}"
if sudo systemctl is-active --quiet campanha-web; then
    echo -e "${GREEN}✓ Serviço campanha-web está rodando!${NC}"
    sudo systemctl status campanha-web --no-pager -l
else
    echo -e "${RED}✗ Serviço campanha-web não está rodando!${NC}"
    echo -e "${YELLOW}Verifique os logs com: sudo journalctl -u campanha-web -f${NC}"
    exit 1
fi
echo ""

# Testa a aplicação
echo -e "${YELLOW}8. Testando aplicação...${NC}"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ | grep -q "200\|301\|302"; then
    echo -e "${GREEN}✓ Aplicação respondendo corretamente!${NC}"
else
    echo -e "${YELLOW}⚠ Aplicação pode não estar respondendo corretamente${NC}"
    echo -e "${YELLOW}Verifique manualmente: curl http://localhost:8000/${NC}"
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploy concluído com sucesso!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Comandos úteis:${NC}"
echo "  • Ver logs: sudo journalctl -u campanha-web -f"
echo "  • Status: sudo systemctl status campanha-web"
echo "  • Reiniciar: sudo systemctl restart campanha-web"
echo "  • Parar: sudo systemctl stop campanha-web"
echo "  • Iniciar: sudo systemctl start campanha-web"
echo ""
