from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = 'Cria ou exibe token de API para um usuário'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Nome do usuário')
        parser.add_argument(
            '--recreate',
            action='store_true',
            help='Recria o token se já existir',
        )

    def handle(self, *args, **options):
        username = options['username']
        recreate = options['recreate']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Usuário "{username}" não encontrado')
            )
            return

        if recreate:
            # Remove token existente
            Token.objects.filter(user=user).delete()

        token, created = Token.objects.get_or_create(user=user)

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Token criado para {username}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Token já existia para {username}')
            )

        self.stdout.write(f'Token: {token.key}')
        self.stdout.write('')
        self.stdout.write('Como usar:')
        self.stdout.write(f'curl -H "Authorization: Token {token.key}" http://localhost:8099/api/execucoes/')
