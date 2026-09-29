from app import create_app
from app.store.models import create_new_user

app = create_app()

with app.app_context():
    user = create_new_user('Admin', 'User', 'admin@gmail.com', 'admin123')
    print('User created:', user.email_usuario if user else 'Failed')