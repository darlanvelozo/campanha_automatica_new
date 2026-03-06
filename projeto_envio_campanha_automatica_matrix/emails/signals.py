"""
Signals para enviar notificações automáticas de emails
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from campanha_manager.services import ServicoNotificacao
from .models import CampanhaEmail, BaseLeads


@receiver(post_save, sender=CampanhaEmail)
def notificar_campanha_email(sender, instance, created, **kwargs):
    """
    Notifica quando uma campanha de email é criada, concluída ou tem erro
    """
    # Se foi criada (iniciada)
    if created:
        usuarios = User.objects.filter(is_active=True)
        for usuario in usuarios:
            ServicoNotificacao.criar_notificacao(
                usuario=usuario,
                tipo_codigo=ServicoNotificacao.EMAIL_CAMPANHA_INICIADA,
                titulo='Campanha de Email Iniciada',
                mensagem=f'A campanha "{instance.nome}" foi iniciada.',
                url=f'/emails/campanhas/{instance.id}/',
                content_type='CampanhaEmail',
                object_id=instance.id
            )
    else:
        # Verificar mudanças de status
        try:
            old_instance = CampanhaEmail.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Status mudou
                if instance.status == 'concluida':
                    # Notificar conclusão
                    usuarios = User.objects.filter(is_active=True)
                    for usuario in usuarios:
                        ServicoNotificacao.criar_notificacao(
                            usuario=usuario,
                            tipo_codigo=ServicoNotificacao.EMAIL_CAMPANHA_CONCLUIDA,
                            titulo='Campanha de Email Concluída',
                            mensagem=f'A campanha "{instance.nome}" foi concluída. {instance.total_enviados} emails enviados.',
                            url=f'/emails/campanhas/{instance.id}/',
                            content_type='CampanhaEmail',
                            object_id=instance.id
                        )
                elif instance.status == 'erro':
                    # Notificar erro
                    usuarios = User.objects.filter(is_active=True)
                    for usuario in usuarios:
                        ServicoNotificacao.criar_notificacao(
                            usuario=usuario,
                            tipo_codigo=ServicoNotificacao.EMAIL_CAMPANHA_ERRO,
                            titulo='Erro na Campanha de Email',
                            mensagem=f'Erro na campanha "{instance.nome}".',
                            url=f'/emails/campanhas/{instance.id}/',
                            content_type='CampanhaEmail',
                            object_id=instance.id
                        )
        except CampanhaEmail.DoesNotExist:
            pass


@receiver(post_save, sender=BaseLeads)
def notificar_importacao_leads(sender, instance, created, **kwargs):
    """
    Notifica quando uma importação de leads é concluída
    """
    if created:
        # Notificar importação concluída
        usuarios = User.objects.filter(is_active=True)
        for usuario in usuarios:
            ServicoNotificacao.criar_notificacao(
                usuario=usuario,
                tipo_codigo=ServicoNotificacao.EMAIL_IMPORTACAO_LEADS,
                titulo='Importação de Leads Concluída',
                mensagem=f'Base "{instance.nome}" importada com {instance.total_leads} leads ({instance.total_validos} válidos).',
                url=f'/emails/leads/',
                content_type='BaseLeads',
                object_id=instance.id
            )
