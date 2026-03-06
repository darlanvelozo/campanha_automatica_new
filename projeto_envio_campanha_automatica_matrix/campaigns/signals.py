"""
Signals para enviar notificações automáticas de ligações nativas
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from campanha_manager.services import ServicoNotificacao
from .models import Execution


@receiver(post_save, sender=Execution)
def notificar_execucao_native(sender, instance, created, **kwargs):
    """
    Notifica quando uma execução de campanha Native é criada, concluída ou tem erro
    """
    # Se foi criada (iniciada)
    if created:
        usuarios = User.objects.filter(is_active=True)
        for usuario in usuarios:
            ServicoNotificacao.criar_notificacao(
                usuario=usuario,
                tipo_codigo=ServicoNotificacao.NATIVE_EXECUCAO_INICIADA,
                titulo='Execução de Ligação Iniciada',
                mensagem=f'A execução da campanha "{instance.campaign.name}" foi iniciada.',
                url=f'/native/executions/{instance.id}/',
                content_type='Execution',
                object_id=instance.id
            )
    else:
        # Verificar mudanças de status
        try:
            old_instance = Execution.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Status mudou
                if instance.status == 'completed':
                    # Notificar conclusão
                    usuarios = User.objects.filter(is_active=True)
                    for usuario in usuarios:
                        ServicoNotificacao.criar_notificacao(
                            usuario=usuario,
                            tipo_codigo=ServicoNotificacao.NATIVE_EXECUCAO_CONCLUIDA,
                            titulo='Execução de Ligação Concluída',
                            mensagem=f'A execução da campanha "{instance.campaign.name}" foi concluída. {instance.total_records} registros processados.',
                            url=f'/native/executions/{instance.id}/',
                            content_type='Execution',
                            object_id=instance.id
                        )
                elif instance.status == 'failed':
                    # Notificar erro
                    usuarios = User.objects.filter(is_active=True)
                    for usuario in usuarios:
                        ServicoNotificacao.criar_notificacao(
                            usuario=usuario,
                            tipo_codigo=ServicoNotificacao.NATIVE_EXECUCAO_ERRO,
                            titulo='Erro na Execução de Ligação',
                            mensagem=f'Erro na execução da campanha "{instance.campaign.name}": {instance.error_message[:100] if instance.error_message else "Erro desconhecido"}',
                            url=f'/native/executions/{instance.id}/',
                            content_type='Execution',
                            object_id=instance.id
                        )
        except Execution.DoesNotExist:
            pass
