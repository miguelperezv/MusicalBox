# Configuración de MercadoPago para MusicalBox

## Credenciales requeridas

Para habilitar los pagos con MercadoPago, debes obtener tus credenciales de la cuenta de MercadoPago:

1. Accede al [panel de desarrolladores de MercadoPago](https://www.mercadopago.com.co/developers/panel)
2. Ve a "Tus credenciales"
3. Obtén las siguientes credenciales:
   - **ACCESS_TOKEN** (para el backend)
   - **PUBLIC_KEY** (para el frontend)

## Variables de entorno

Agrega estas variables al entorno donde corres:

```bash
# En desarrollo (.env o variables del sistema)
MERCADOPAGO_PUBLIC_KEY=TU_PUBLIC_KEY_AQUÍ
MERCADOPAGO_ACCESS_TOKEN=TU_ACCESS_TOKEN_AQUÍ

# En producción (variables del sistema o config de hosting)
MERCADOPAGO_PUBLIC_KEY=PROD_PUBLIC_KEY_AQUÍ
MERCADOPAGO_ACCESS_TOKEN=PROD_ACCESS_TOKEN_AQUÍ
```

## Pruebas

Para pruebas, puedes usar las credenciales de prueba que MercadoPago proporciona en el panel de desarrolladores.

### Tarjetas de prueba

- **Número**: 5031 7557 3453 0004
- **Fecha de vencimiento**: 11/25
- **CVV**: 123
- **Email**: test_user_XXXX@testuser.com (generado en el panel)

## Webhooks (opcional)

Para recibir notificaciones automáticas de cambios de estado:

1. En el panel de MercadoPago, configura la URL de notificaciones:
   ```
   https://tudominio.com/mercadopago/webhook
   ```
2. Selecciona los eventos que quieres recibir (recomendado: payments)

## Personalización

Puedes personalizar el checkout modificando el template `mercadopago_button.html`:
- Colores del tema
- Textos y descripciones
- Elementos visibles del checkout