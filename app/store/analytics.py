"""Analytics tracking para eventos de negocio."""
import hashlib
from functools import wraps
from flask import request, session, current_app, g
from .models import WebEvent, db


def track_event(event_name, payload=None, user_id=None):
    """Guarda evento de negocio en BD propia."""
    try:
        # Generar session_id si no existe
        if 'session_id' not in session:
            import uuid
            session['session_id'] = str(uuid.uuid4())
        
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else None
        
        evt = WebEvent(
            event_name=event_name,
            session_id=session.get('session_id'),
            user_id=user_id or getattr(g, 'user_id', None),
            page_url=request.referrer or request.url,
            referrer=request.headers.get('Referer'),
            user_agent=request.headers.get('User-Agent'),
            ip_hash=hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else None,
            payload=payload or {}
        )
        db.session.add(evt)
        db.session.commit()
    except Exception as e:
        current_app.logger.warning(f"Analytics track failed: {e}")
        db.session.rollback()


def track(event_name, payload_fn=None):
    """Decorador para trackear eventos en rutas."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            result = f(*args, **kwargs)
            try:
                payload = payload_fn(*args, **kwargs) if payload_fn else {}
                track_event(event_name, payload)
            except Exception:
                pass  # Silenciar errores de analytics
            return result
        return wrapper
    return decorator


# Eventos predefinidos para consistencia
class Events:
    # E-commerce
    ADD_TO_CART = 'add_to_cart'
    CHECKOUT_START = 'checkout_start'
    PURCHASE = 'purchase'
    PSE_REDIRECT = 'pse_redirect'
    PAYMENT_FAILED = 'payment_failed'
    
    # Solicitudes a la medida
    COTIZACION_SOLICITADA = 'cotizacion_solicitada'
    COTIZACION_APROBADA = 'cotizacion_aprobada'
    
    # Engagement
    PRODUCT_VIEW = 'product_view'
    LANZAMIENTO_VIEW = 'lanzamiento_view'
    SEARCH = 'search'
    
    # Auth
    SIGNUP = 'signup'
    LOGIN = 'login'