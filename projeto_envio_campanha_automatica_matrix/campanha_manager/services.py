"""
Serviços para gerenciamento de notificações
"""
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Notificacao, TipoNotificacao, ConfiguracaoNotificacao


class ServicoNotificacao:
    """
    Serviço centralizado para criação e gerenciamento de notificações
    """
    
    # Códigos de tipos de notificação
    # WhatsApp
    WHATSAPP_CONSULTA_INICIADA = 'whatsapp_consulta_iniciada'
    WHATSAPP_CONSULTA_CONCLUIDA = 'whatsapp_consulta_concluida'
    WHATSAPP_CONSULTA_ERRO = 'whatsapp_consulta_erro'
    WHATSAPP_ENVIO_INICIADO = 'whatsapp_envio_iniciado'
    WHATSAPP_ENVIO_CONCLUIDO = 'whatsapp_envio_concluido'
    WHATSAPP_ENVIO_ERRO = 'whatsapp_envio_erro'
    
    # Email
    EMAIL_CAMPANHA_INICIADA = 'email_campanha_iniciada'
    EMAIL_CAMPANHA_CONCLUIDA = 'email_campanha_concluida'
    EMAIL_CAMPANHA_ERRO = 'email_campanha_erro'
    EMAIL_IMPORTACAO_LEADS = 'email_importacao_leads'
    
    # Native (Ligações)
    NATIVE_EXECUCAO_INICIADA = 'native_execucao_iniciada'
    NATIVE_EXECUCAO_CONCLUIDA = 'native_execucao_concluida'
    NATIVE_EXECUCAO_ERRO = 'native_execucao_erro'
    
    # Sistema
    SISTEMA_ERRO_CRITICO = 'sistema_erro_critico'
    SISTEMA_AVISO = 'sistema_aviso'
    
    @staticmethod
    def criar_notificacao(
        usuario,
        tipo_codigo,
        titulo,
        mensagem,
        url='',
        dados_extras=None,
        content_type='',
        object_id=None
    ):
        """
        Cria uma nova notificação para um usuário
        
        Args:
            usuario: Instância de User ou ID do usuário
            tipo_codigo: Código do tipo de notificação
            titulo: Título da notificação
            mensagem: Mensagem da notificação
            url: URL de destino (opcional)
            dados_extras: Dados adicionais em formato dict (opcional)
            content_type: Tipo de objeto relacionado (opcional)
            object_id: ID do objeto relacionado (opcional)
        
        Returns:
            Notificacao: Instância da notificação criada ou None se desabilitada
        """
        # Obter usuário se for ID
        if isinstance(usuario, int):
            try:
                usuario = User.objects.get(id=usuario)
            except User.DoesNotExist:
                return None
        
        # Obter tipo de notificação
        try:
            tipo_notificacao = TipoNotificacao.objects.get(codigo=tipo_codigo, ativo=True)
        except TipoNotificacao.DoesNotExist:
            # Se o tipo não existe, criar notificação genérica
            tipo_notificacao = None
        
        # Verificar se o usuário tem essa notificação habilitada
        if tipo_notificacao:
            config = ConfiguracaoNotificacao.objects.filter(
                usuario=usuario,
                tipo_notificacao=tipo_notificacao
            ).first()
            
            if config and not config.ativo:
                return None  # Notificação desabilitada para este usuário
        
        # Obter ícone e cor do tipo
        icone = tipo_notificacao.icone if tipo_notificacao else 'bell'
        cor = tipo_notificacao.cor if tipo_notificacao else 'primary'
        
        # Criar notificação
        notificacao = Notificacao.objects.create(
            usuario=usuario,
            tipo_notificacao=tipo_notificacao,
            titulo=titulo,
            mensagem=mensagem,
            url=url,
            icone=icone,
            cor=cor,
            dados_extras=dados_extras,
            content_type=content_type,
            object_id=object_id
        )
        
        return notificacao
    
    @staticmethod
    def criar_notificacao_para_todos(tipo_codigo, titulo, mensagem, url='', dados_extras=None):
        """
        Cria uma notificação para todos os usuários ativos
        """
        usuarios = User.objects.filter(is_active=True)
        notificacoes_criadas = []
        
        for usuario in usuarios:
            notif = ServicoNotificacao.criar_notificacao(
                usuario=usuario,
                tipo_codigo=tipo_codigo,
                titulo=titulo,
                mensagem=mensagem,
                url=url,
                dados_extras=dados_extras
            )
            if notif:
                notificacoes_criadas.append(notif)
        
        return notificacoes_criadas
    
    @staticmethod
    def obter_notificacoes_usuario(usuario, apenas_nao_lidas=False, limite=None):
        """
        Obtém notificações de um usuário
        """
        queryset = Notificacao.objects.filter(usuario=usuario)
        
        if apenas_nao_lidas:
            queryset = queryset.filter(lida=False)
        
        queryset = queryset.select_related('tipo_notificacao').order_by('-data_criacao')
        
        if limite:
            queryset = queryset[:limite]
        
        return queryset
    
    @staticmethod
    def marcar_como_lida(notificacao_id):
        """Marca uma notificação como lida"""
        try:
            notificacao = Notificacao.objects.get(id=notificacao_id)
            notificacao.marcar_como_lida()
            return True
        except Notificacao.DoesNotExist:
            return False
    
    @staticmethod
    def marcar_todas_como_lidas(usuario):
        """Marca todas as notificações de um usuário como lidas"""
        Notificacao.objects.filter(usuario=usuario, lida=False).update(
            lida=True,
            data_leitura=timezone.now()
        )
    
    @staticmethod
    def limpar_notificacoes_antigas(dias=30):
        """
        Remove notificações lidas mais antigas que X dias
        """
        data_limite = timezone.now() - timezone.timedelta(days=dias)
        count = Notificacao.objects.filter(
            lida=True,
            data_leitura__lt=data_limite
        ).delete()[0]
        return count
    
    @staticmethod
    def inicializar_tipos_notificacao():
        """
        Inicializa os tipos de notificação padrão do sistema
        """
        tipos = [
            # WhatsApp
            {
                'codigo': ServicoNotificacao.WHATSAPP_CONSULTA_INICIADA,
                'nome': 'Consulta WhatsApp Iniciada',
                'descricao': 'Notifica quando uma consulta de clientes é iniciada',
                'categoria': 'whatsapp',
                'icone': 'play-circle',
                'cor': 'info'
            },
            {
                'codigo': ServicoNotificacao.WHATSAPP_CONSULTA_CONCLUIDA,
                'nome': 'Consulta WhatsApp Concluída',
                'descricao': 'Notifica quando uma consulta de clientes é concluída com sucesso',
                'categoria': 'whatsapp',
                'icone': 'check-circle',
                'cor': 'success'
            },
            {
                'codigo': ServicoNotificacao.WHATSAPP_CONSULTA_ERRO,
                'nome': 'Erro na Consulta WhatsApp',
                'descricao': 'Notifica quando ocorre um erro na consulta de clientes',
                'categoria': 'whatsapp',
                'icone': 'alert-circle',
                'cor': 'danger'
            },
            {
                'codigo': ServicoNotificacao.WHATSAPP_ENVIO_INICIADO,
                'nome': 'Envio HSM Iniciado',
                'descricao': 'Notifica quando um envio de HSM é iniciado',
                'categoria': 'whatsapp',
                'icone': 'send',
                'cor': 'info'
            },
            {
                'codigo': ServicoNotificacao.WHATSAPP_ENVIO_CONCLUIDO,
                'nome': 'Envio HSM Concluído',
                'descricao': 'Notifica quando um envio de HSM é concluído',
                'categoria': 'whatsapp',
                'icone': 'check-square',
                'cor': 'success'
            },
            {
                'codigo': ServicoNotificacao.WHATSAPP_ENVIO_ERRO,
                'nome': 'Erro no Envio HSM',
                'descricao': 'Notifica quando ocorre um erro no envio de HSM',
                'categoria': 'whatsapp',
                'icone': 'x-circle',
                'cor': 'danger'
            },
            
            # Email
            {
                'codigo': ServicoNotificacao.EMAIL_CAMPANHA_INICIADA,
                'nome': 'Campanha de Email Iniciada',
                'descricao': 'Notifica quando uma campanha de email é iniciada',
                'categoria': 'email',
                'icone': 'mail',
                'cor': 'info'
            },
            {
                'codigo': ServicoNotificacao.EMAIL_CAMPANHA_CONCLUIDA,
                'nome': 'Campanha de Email Concluída',
                'descricao': 'Notifica quando uma campanha de email é concluída',
                'categoria': 'email',
                'icone': 'mail-check',
                'cor': 'success'
            },
            {
                'codigo': ServicoNotificacao.EMAIL_CAMPANHA_ERRO,
                'nome': 'Erro na Campanha de Email',
                'descricao': 'Notifica quando ocorre um erro na campanha de email',
                'categoria': 'email',
                'icone': 'mail-x',
                'cor': 'danger'
            },
            {
                'codigo': ServicoNotificacao.EMAIL_IMPORTACAO_LEADS,
                'nome': 'Importação de Leads Concluída',
                'descricao': 'Notifica quando uma importação de leads é concluída',
                'categoria': 'email',
                'icone': 'upload',
                'cor': 'success'
            },
            
            # Native
            {
                'codigo': ServicoNotificacao.NATIVE_EXECUCAO_INICIADA,
                'nome': 'Execução de Ligação Iniciada',
                'descricao': 'Notifica quando uma execução de campanha de ligação é iniciada',
                'categoria': 'native',
                'icone': 'phone',
                'cor': 'info'
            },
            {
                'codigo': ServicoNotificacao.NATIVE_EXECUCAO_CONCLUIDA,
                'nome': 'Execução de Ligação Concluída',
                'descricao': 'Notifica quando uma execução de campanha de ligação é concluída',
                'categoria': 'native',
                'icone': 'phone-call',
                'cor': 'success'
            },
            {
                'codigo': ServicoNotificacao.NATIVE_EXECUCAO_ERRO,
                'nome': 'Erro na Execução de Ligação',
                'descricao': 'Notifica quando ocorre um erro na execução de ligação',
                'categoria': 'native',
                'icone': 'phone-off',
                'cor': 'danger'
            },
            
            # Sistema
            {
                'codigo': ServicoNotificacao.SISTEMA_ERRO_CRITICO,
                'nome': 'Erro Crítico do Sistema',
                'descricao': 'Notifica sobre erros críticos que requerem atenção imediata',
                'categoria': 'sistema',
                'icone': 'alert-triangle',
                'cor': 'danger'
            },
            {
                'codigo': ServicoNotificacao.SISTEMA_AVISO,
                'nome': 'Aviso do Sistema',
                'descricao': 'Notificações gerais do sistema',
                'categoria': 'sistema',
                'icone': 'info',
                'cor': 'warning'
            },
        ]
        
        criados = 0
        for tipo_data in tipos:
            tipo, created = TipoNotificacao.objects.get_or_create(
                codigo=tipo_data['codigo'],
                defaults=tipo_data
            )
            if created:
                criados += 1
        
        return criados
