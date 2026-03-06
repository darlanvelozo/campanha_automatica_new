"""
Signals para enviar notificações automáticas quando eventos importantes acontecem
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from campanha_manager.services import ServicoNotificacao
from .models import ConsultaExecucao, EnvioHSMMatrix


@receiver(post_save, sender=ConsultaExecucao)
def notificar_consulta_whatsapp(sender, instance, created, **kwargs):
    """
    Notifica quando uma consulta WhatsApp é criada, concluída ou tem erro
    """
    # Se foi criada (iniciada)
    if created:
        # Notificar todos os usuários ativos
        usuarios = User.objects.filter(is_active=True)
        for usuario in usuarios:
            ServicoNotificacao.criar_notificacao(
                usuario=usuario,
                tipo_codigo=ServicoNotificacao.WHATSAPP_CONSULTA_INICIADA,
                titulo='Consulta WhatsApp Iniciada',
                mensagem=f'A consulta "{instance.titulo}" foi iniciada.',
                url=f'/whatsapp/execucao/{instance.id}/',
                content_type='ConsultaExecucao',
                object_id=instance.id
            )
    else:
        # Verificar mudanças de status
        try:
            old_instance = ConsultaExecucao.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Status mudou
                if instance.status == 'concluido':
                    # Notificar conclusão
                    usuarios = User.objects.filter(is_active=True)
                    for usuario in usuarios:
                        ServicoNotificacao.criar_notificacao(
                            usuario=usuario,
                            tipo_codigo=ServicoNotificacao.WHATSAPP_CONSULTA_CONCLUIDA,
                            titulo='Consulta WhatsApp Concluída',
                            mensagem=f'A consulta "{instance.titulo}" foi concluída. {instance.total_registros_sql} registros processados.',
                            url=f'/whatsapp/execucao/{instance.id}/',
                            content_type='ConsultaExecucao',
                            object_id=instance.id
                        )
                elif instance.status == 'erro':
                    # Notificar erro
                    usuarios = User.objects.filter(is_active=True)
                    for usuario in usuarios:
                        ServicoNotificacao.criar_notificacao(
                            usuario=usuario,
                            tipo_codigo=ServicoNotificacao.WHATSAPP_CONSULTA_ERRO,
                            titulo='Erro na Consulta WhatsApp',
                            mensagem=f'Erro na consulta "{instance.titulo}": {instance.erro_detalhado[:100] if instance.erro_detalhado else "Erro desconhecido"}',
                            url=f'/whatsapp/execucao/{instance.id}/',
                            content_type='ConsultaExecucao',
                            object_id=instance.id
                        )
        except ConsultaExecucao.DoesNotExist:
            pass


@receiver(post_save, sender=EnvioHSMMatrix)
def notificar_envio_hsm(sender, instance, created, **kwargs):
    """
    Notifica quando um envio HSM é criado, concluído ou tem erro
    """
    # Se foi criado (iniciado)
    if created:
        usuarios = User.objects.filter(is_active=True)
        for usuario in usuarios:
            ServicoNotificacao.criar_notificacao(
                usuario=usuario,
                tipo_codigo=ServicoNotificacao.WHATSAPP_ENVIO_INICIADO,
                titulo='Envio HSM Iniciado',
                mensagem=f'O envio "{instance.titulo}" foi iniciado.',
                url=f'/whatsapp/envio-hsm/{instance.id}/',
                content_type='EnvioHSMMatrix',
                object_id=instance.id
            )
    else:
        # Verificar mudanças de status
        try:
            old_instance = EnvioHSMMatrix.objects.get(pk=instance.pk)
            if old_instance.status_envio != instance.status_envio:
                # Status mudou
                if instance.status_envio == 'concluido':
                    # Notificar conclusão
                    usuarios = User.objects.filter(is_active=True)
                    for usuario in usuarios:
                        ServicoNotificacao.criar_notificacao(
                            usuario=usuario,
                            tipo_codigo=ServicoNotificacao.WHATSAPP_ENVIO_CONCLUIDO,
                            titulo='Envio HSM Concluído',
                            mensagem=f'O envio "{instance.titulo}" foi concluído. {instance.total_enviados} mensagens enviadas.',
                            url=f'/whatsapp/envio-hsm/{instance.id}/',
                            content_type='EnvioHSMMatrix',
                            object_id=instance.id
                        )
                elif instance.status_envio == 'erro':
                    # Notificar erro
                    usuarios = User.objects.filter(is_active=True)
                    for usuario in usuarios:
                        ServicoNotificacao.criar_notificacao(
                            usuario=usuario,
                            tipo_codigo=ServicoNotificacao.WHATSAPP_ENVIO_ERRO,
                            titulo='Erro no Envio HSM',
                            mensagem=f'Erro no envio "{instance.titulo}": {instance.log_envio[:100] if instance.log_envio else "Erro desconhecido"}',
                            url=f'/whatsapp/envio-hsm/{instance.id}/',
                            content_type='EnvioHSMMatrix',
                            object_id=instance.id
                        )
        except EnvioHSMMatrix.DoesNotExist:
            pass
