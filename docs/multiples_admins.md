## Cómo agregar otro usuario como administrador del bot

Para permitir que otro usuario controle el bot (reciba solicitudes y pueda cotizar), sigue estos pasos:

### 1. El nuevo usuario debe iniciar una conversación con el bot
- El usuario debe buscar el bot en Telegram y enviarle cualquier mensaje (por ejemplo, "hola")
- Esto crea el chat y permite obtener su chat_id

### 2. Obtener el chat_id del nuevo usuario
Hay dos formas de hacerlo:

**Opción A: Usar el bot @get_id_bot**
- El usuario envía `/start` al bot @get_id_bot
- El bot responderá con el chat_id

**Opción B: Ver los logs del bot**
- Cuando el usuario envíe un mensaje al bot, aparecerá en los logs de PythonAnywhere
- Busca líneas como: `Nuevo mensaje de: 1234567890`

### 3. Agregar el chat_id al archivo de configuración
Edita el archivo `.env` en la raíz del proyecto y modifica la línea:

```
TG_ADMIN_CHAT_ID=7279406967,1234567890,987654321
```

Puedes agregar tantos chat_id como necesites, separados por comas.

### 4. Reiniciar el bot
En PythonAnywhere:
1. Ve a la pestaña "Consoles"
2. Haz clic en "Reload" para reiniciar la aplicación

### 5. Probar el acceso
El nuevo usuario debe:
- Abrir una conversación con el bot
- Enviar el comando `/start` o cualquier mensaje
- Debería recibir la notificación de nueva solicitud cuando alguien cree una

### Notas importantes:
- Todos los administradores tienen acceso completo al bot
- Las notificaciones se envían a todos los administradores
- Si un administrador no quiere recibir notificaciones, puede desactivar el sonido en Telegram