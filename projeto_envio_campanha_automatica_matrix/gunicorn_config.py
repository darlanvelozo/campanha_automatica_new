"""
Configuração do Gunicorn para o projeto campanha_manager

Este arquivo contém as configurações otimizadas para execução do Django
com Gunicorn em ambiente de produção.
"""

import multiprocessing
import os

# Diretório base do projeto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =======================
# Configurações de Servidor
# =======================

# Endereço e porta onde o Gunicorn vai escutar
# Use '0.0.0.0:8001' para aceitar conexões externas (mesma porta do projeto anterior)
# Ou use um socket Unix: 'unix:/run/gunicorn.sock' se usar Nginx
bind = '0.0.0.0:8001'

# Número de workers (processos)
# Recomendação: (2 x núcleos de CPU) + 1
# Ajuste conforme os recursos do servidor
workers = 4

# Classe de worker
# 'sync' é a padrão e funciona bem para a maioria dos casos
# Use 'gevent' ou 'eventlet' para aplicações com muitas requisições I/O
worker_class = 'sync'

# Número de threads por worker (se usar workers síncronos)
threads = 2

# Timeout para requisições (em segundos)
# Aumentado para 120s devido às operações de campanha que podem ser longas
timeout = 120

# Timeout para workers silenciosos (sem atividade)
graceful_timeout = 30

# Timeout para keep-alive
keepalive = 5

# =======================
# Configurações de Workers
# =======================

# Número máximo de requisições que um worker processa antes de ser reiniciado
# Isso ajuda a evitar memory leaks
max_requests = 1000

# Adiciona jitter ao max_requests para evitar que todos os workers reiniciem ao mesmo tempo
max_requests_jitter = 100

# =======================
# Configurações de Logs
# =======================

# Diretório de logs
log_dir = '/var/log/gunicorn'

# Cria o diretório se não existir (requer permissões)
if not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir)
    except PermissionError:
        # Se não tiver permissão, usa o diretório do projeto
        log_dir = os.path.join(BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)

# Arquivo de log de acesso
accesslog = os.path.join(log_dir, 'access.log')

# Arquivo de log de erros
errorlog = os.path.join(log_dir, 'error.log')

# Nível de log
# Opções: 'debug', 'info', 'warning', 'error', 'critical'
loglevel = 'info'

# Formato do log de acesso
# h: remote address
# l: '-'
# u: user name
# t: date of the request
# r: status line (e.g. GET / HTTP/1.1)
# s: status code
# b: response length
# f: referer
# a: user agent
# T: request time in seconds
# D: request time in microseconds
# L: request time in decimal seconds
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'

# =======================
# Configurações de Processo
# =======================

# Nome do processo no sistema
proc_name = 'campanha_manager'

# Diretório de trabalho (onde o manage.py está)
chdir = BASE_DIR

# Arquivo PID
pidfile = os.path.join(log_dir, 'gunicorn.pid')

# Usuário e grupo para executar o Gunicorn
# Deixe comentado se já estiver rodando com o usuário correto
# user = 'darlan'
# group = 'darlan'

# Modo daemon (False para usar com systemd)
daemon = False

# =======================
# Configurações de Segurança
# =======================

# Limita o tamanho do cabeçalho da requisição
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# =======================
# Hooks do Gunicorn
# =======================

def on_starting(server):
    """
    Executado quando o Gunicorn está iniciando
    """
    print(f"Iniciando Gunicorn no diretório: {BASE_DIR}")
    print(f"Workers: {workers}")
    print(f"Bind: {bind}")
    print(f"Timeout: {timeout}s")


def on_reload(server):
    """
    Executado quando o Gunicorn recarrega a configuração
    """
    print("Recarregando configuração do Gunicorn")


def when_ready(server):
    """
    Executado quando o Gunicorn está pronto para aceitar requisições
    """
    print(f"Gunicorn pronto! PID: {os.getpid()}")
    print(f"Logs em: {log_dir}")


def worker_int(worker):
    """
    Executado quando um worker recebe SIGINT ou SIGQUIT
    """
    print(f"Worker {worker.pid} interrompido pelo usuário")


def pre_fork(server, worker):
    """
    Executado antes de criar um novo worker
    """
    pass


def post_fork(server, worker):
    """
    Executado após criar um novo worker
    """
    print(f"Worker spawned (pid: {worker.pid})")


def pre_exec(server):
    """
    Executado antes de executar o servidor
    """
    print("Preparando para executar o servidor")


def worker_exit(server, worker):
    """
    Executado quando um worker é encerrado
    """
    print(f"Worker {worker.pid} encerrado")


# =======================
# Configurações SSL (Opcional)
# =======================

# Descomente e configure se for servir HTTPS diretamente pelo Gunicorn
# (Recomendado: use Nginx como proxy reverso para SSL)
# keyfile = '/path/to/ssl/key.pem'
# certfile = '/path/to/ssl/cert.pem'
# ssl_version = 'TLS'
# cert_reqs = 0
# ca_certs = '/path/to/ca_certs.pem'

# =======================
# Configurações Avançadas
# =======================

# Envia estatísticas para o StatsD (se configurado)
# statsd_host = 'localhost:8125'
# statsd_prefix = 'campanha_manager'

# Worker temporário
# worker_tmp_dir = '/dev/shm'  # Usa RAM para melhor performance

# Desabilita paste deploy
paste = None

# Configurações do servidor
# forwarded_allow_ips = '*'  # Configure adequadamente para proxies
# proxy_protocol = False
# proxy_allow_ips = '*'

print(f"""
==============================================
Configuração do Gunicorn carregada
==============================================
Workers: {workers}
Bind: {bind}
Timeout: {timeout}s
Max Requests: {max_requests}
Log Dir: {log_dir}
==============================================
""")
