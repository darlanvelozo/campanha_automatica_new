"""
Middleware para exigir autenticação apenas na interface web da aplicação.
APIs (internas e externas) ficam liberadas por enquanto.
"""
from django.conf import settings
from django.shortcuts import redirect


class LoginRequiredMiddleware:
    """
    Middleware que exige autenticação apenas para a interface web da aplicação.
    Todas as APIs (internas e externas) ficam liberadas.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Rotas que não precisam de autenticação
        self.exempt_paths = [
            '/admin/login/',
            '/admin/logout/',
            '/admin/password_reset/',
            '/admin/password_reset/done/',
            '/admin/reset/',
            '/admin/reset/done/',
            '/api-auth/',  # Rotas de autenticação da API REST Framework
        ]
        
    def __call__(self, request):
        # Verificar se o usuário está autenticado
        if not request.user.is_authenticated:
            path = request.path
            
            # Permitir acesso às rotas de autenticação do admin
            if any(path.startswith(exempt) for exempt in self.exempt_paths):
                return self.get_response(request)
            
            # PERMITIR TODAS AS APIs (internas e externas) - sem autenticação
            # Isso inclui /api/, /emails/api/, /campanhas/api/, etc.
            if '/api/' in path or path.startswith('/api/'):
                return self.get_response(request)
            
            # Permitir acesso a arquivos estáticos e media
            if path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL):
                return self.get_response(request)
            
            # Se tentar acessar admin sem estar autenticado, redirecionar para login
            if path.startswith('/admin/'):
                return redirect('/admin/login/?next=' + path)
            
            # Para todas as outras rotas da interface web (HTML), redirecionar para login
            # Isso protege a aplicação web, mas deixa as APIs livres
            login_url = settings.LOGIN_URL
            return redirect(f'{login_url}?next={path}')
        
        # Se o usuário estiver autenticado, continuar normalmente
        response = self.get_response(request)
        return response
