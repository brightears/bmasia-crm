"""Reset admin password"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Reset admin password to bmasia123'
    
    def handle(self, *args, **options):
        User = get_user_model()
        
        try:
            admin_user = User.objects.get(username='admin')
            admin_user.set_password('bmasia123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Successfully reset admin password to bmasia123'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('Admin user not found'))