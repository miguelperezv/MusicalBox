# Subir Musical Box a PythonAnywhere

Guía paso a paso para publicar la tienda en `https://TU_USUARIO.pythonanywhere.com`.
Reemplaza `TU_USUARIO` por tu usuario de PythonAnywhere en todos los comandos.

---

## 0. Cómo sabe la app que está en producción

La configuración se elige con la variable de entorno `APP_CONFIG` (se pone en el archivo WSGI, paso 5):

| `APP_CONFIG` | Debug | Botones "simular pago" | Cookies solo por HTTPS |
|---|---|---|---|
| `production` | No | No | Sí |
| sin definir (desarrollo) | Sí | Sí | No |

En producción la app **no arranca** si falta `SECRET_KEY` (así no queda una clave de ejemplo).

> Base de datos: usar **SQLite** por ahora. La migración que reconstruye `item` solo está escrita
> para SQLite; pasar a MySQL requiere adaptarla primero.

---

## 1. Cuenta

1. Crea la cuenta en <https://www.pythonanywhere.com>.
2. La cuenta **gratuita** sirve para probar, pero su acceso a internet está limitado a una
   **lista blanca** de dominios. Verifica que estén:
   - `secure.epayco.co` (validación de pagos)
   - el servidor SMTP de tu proveedor de correo (cuando lo configures)

   Si no están, necesitas el plan **Hacker** (≈ 5 USD/mes).

---

## 2. Código

En PythonAnywhere: **Consoles → Bash**

```bash
git clone https://github.com/miguelperezv/MusicalBox.git
cd MusicalBox
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Si el repositorio es privado, GitHub pedirá un **token personal** en lugar de la contraseña
(GitHub → Settings → Developer settings → Personal access tokens).

---

## 3. Base de datos

Elige una opción:

### Opción A: empezar limpia

```bash
cd ~/MusicalBox
source .venv/bin/activate
mkdir -p instance
flask --app run db upgrade
```

Crea tu usuario administrador (te pide la contraseña sin mostrarla):

```bash
flask --app run crear-admin tu-correo@ejemplo.com --nombre TuNombre
```

Si el correo ya tiene cuenta, el mismo comando la convierte en administradora y le cambia la contraseña.

### Opción B: llevar los datos que tienes en tu PC

1. En la pestaña **Files**, sube tu archivo local `instance/musicalbox.sqlite3` a
   `/home/TU_USUARIO/MusicalBox/instance/`.
2. En la consola Bash:

```bash
cd ~/MusicalBox
source .venv/bin/activate
flask --app run db upgrade
```

---

## 4. Aplicación web

Pestaña **Web → Add a new web app**:

| Opción | Valor |
|---|---|
| Framework | **Manual configuration** (no elegir "Flask") |
| Python | **3.12** |
| Virtualenv | `/home/TU_USUARIO/MusicalBox/.venv` |
| Static files: URL | `/static/` |
| Static files: Directory | `/home/TU_USUARIO/MusicalBox/app/static` |
| Force HTTPS | **Activado** (lo necesita ePayco) |

---

## 5. Archivo WSGI

En la pestaña **Web**, abre el archivo WSGI, borra su contenido y deja esto:

```python
import os, sys

sys.path.insert(0, '/home/TU_USUARIO/MusicalBox')
os.chdir('/home/TU_USUARIO/MusicalBox')

os.environ['APP_CONFIG'] = 'production'          # ver paso 0
os.environ['SECRET_KEY'] = 'una-clave-larga-y-aleatoria'
os.environ['EPAYCO_PUBLIC_KEY'] = '...'
os.environ['EPAYCO_PRIVATE_KEY'] = '...'
os.environ['EPAYCO_TEST'] = 'true'               # 'false' cuando cobres de verdad
os.environ['MAIL_BACKEND'] = 'consola'           # 'smtp' cuando tengas proveedor de correo
# os.environ['MAIL_SERVER'] = 'smtp.gmail.com'
# os.environ['MAIL_PORT'] = '587'
# os.environ['MAIL_USERNAME'] = 'tu-correo@gmail.com'
# os.environ['MAIL_PASSWORD'] = 'contraseña-de-aplicacion'
# os.environ['MAIL_FROM'] = 'Musical Box <tu-correo@gmail.com>'

from run import app as application
```

Para generar la `SECRET_KEY` (en la consola Bash):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 6. Recargar y probar

1. Pulsa **Reload** en la pestaña **Web**.
2. Abre `https://TU_USUARIO.pythonanywhere.com`.
3. Si algo falla, revisa el **Error log** (enlace en la pestaña Web).

---

## 7. Checklist antes de anunciar la tienda

- [ ] Compra de prueba con ePayco en modo pruebas. En el servidor sí funciona la confirmación
      servidor a servidor, que en local no podía llegar.
- [ ] En la página del pedido **no** aparecen los botones de "simular pago".
- [ ] El panel `/dashboard` pide login de administrador.
- [ ] Pendientes de seguridad antes de recibir clientes reales:
  - [ ] Contraseñas cifradas (hoy se guardan en texto plano).
  - [ ] Protección CSRF en todos los formularios del panel.
  - [ ] La contraseña no debe quedar guardada en la cookie de sesión.
- [ ] Correo real configurado (`MAIL_BACKEND=smtp` y variables `MAIL_*`).
- [ ] `EPAYCO_TEST=false` y llaves de producción de ePayco cuando se cobre de verdad.

---

## Actualizar la tienda después de cambios

```bash
cd ~/MusicalBox
git pull
source .venv/bin/activate
pip install -r requirements.txt
flask --app run db upgrade
```

Luego **Reload** en la pestaña **Web**.

> Antes de migrar en producción, respalda la base:
> `cp instance/musicalbox.sqlite3 instance/respaldo-$(date +%F).sqlite3`
