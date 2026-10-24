# Dominio, DNS y entornos (musicalbox.com.co)

Cómo quedó conectado el dominio `musicalbox.com.co` con la app en PythonAnywhere,
y cómo montar un **entorno de pruebas** gratis con Cloudflare Tunnel.

Para las variables de entorno de producción ver [`DEPLOY_PYTHONANYWHERE.md`](DEPLOY_PYTHONANYWHERE.md).

---

## Resumen de la arquitectura

```
Usuario
   │
   ▼
Cloudflare            ← DNS + HTTPS + WAF + CDN + redirect del apex   (gratis)
   │
   ▼
PythonAnywhere        ← Flask, venv, SQLite, Pillow, consola bash     (la app)
   webapp-3226733.pythonanywhere.com
```

- **Dominio:** registrado en **Conexcol** (sigue siendo el titular; ahí se renueva).
- **DNS:** **Cloudflare** (nameservers propios). Conexcol ya no resuelve el DNS.
- **App:** **PythonAnywhere** (`www.musicalbox.com.co`).

## Estado final (para copiar/pegar)

| Dato | Valor |
|---|---|
| Dominio | `musicalbox.com.co` (registrado en Conexcol hasta 2027) |
| Nameservers (en Conexcol) | `cullen.ns.cloudflare.com` · `rihana.ns.cloudflare.com` |
| DNSSEC | **off** |
| Registros Cloudflare | `www` CNAME → `webapp-3226733.pythonanywhere.com` (**DNS only**) |
| | `@` CNAME → `webapp-3226733.pythonanywhere.com` (**Proxied**) |
| Regla Cloudflare | Hostname `musicalbox.com.co` → **301** → `https://www.musicalbox.com.co` |
| PythonAnywhere | web app renombrada a `www.musicalbox.com.co` |
| HTTPS | Let's Encrypt (auto-renovado) + Force HTTPS |

Resultado:

| URL | Qué hace |
|---|---|
| `https://www.musicalbox.com.co` | ✅ la app (200, HTTPS) |
| `http://www.musicalbox.com.co` | → redirige a HTTPS |
| `https://musicalbox.com.co` | → `301` a `https://www.musicalbox.com.co/` |

---

## Causa raíz del problema original (para no repetirlo)

El dominio estaba delegado al par DNS **heredado de Conexcol** (`condor.conexcol.net` /
`jaguar.conexcol.net`, el producto "AdminDNS" gratuito). Evidencia medida con `dig`:

- `condor.conexcol.net` → **no respondía** (timeout).
- `jaguar.conexcol.net` → **`REFUSED`** (no tenía la zona).
- `dns1/dns2.conexcol.net` (plataforma viva del hosting, que sí sirve `conexcol.net.co`)
  → **`REFUSED`** para la zona (no tenían la zona de musicalbox).
- Delegación parental (registro `.co`): correcta pero apuntando al par muerto.

⇒ La zona **no estaba publicada en ningún nameserver vivo**. No era propagación ni caché.
La salida fue mover el DNS a Cloudflare.

> Lección: `REFUSED` en el autoritativo = "no alojo esa zona" (no se arregla esperando).
> Para leer la delegación actual sin caché: `dig +trace +nodnssec <dominio> NS`.

---

## Cloudflare — configuración

1. **Cuenta + sitio:** dash.cloudflare.com → *Add a site* → `musicalbox.com.co` → plan **Free**.
2. **Nameservers:** copiarlos y ponerlos en Conexcol (Dominios → `musicalbox.com.co` →
   **Servidores de Nombre de Dominio** → Personalizado), quitando los viejos.
3. **DNSSEC:** apagado (el registro `.co` no debe tener registro `DS`). Comprobar:
   `dig +short DS musicalbox.com.co` → vacío.
4. **DNS → Records:**
   - `CNAME` `www` → `webapp-3226733.pythonanywhere.com` · **DNS only** (nube gris)
   - `CNAME` `@` → `webapp-3226733.pythonanywhere.com` · **Proxied** (nube naranja)
     (Cloudflare aplana el CNAME en el apex.)
5. **Redirect del apex:** Rules → Redirect Rules → Create rule:
   - When: **Hostname** `equals` `musicalbox.com.co`
   - Then: **Static redirect** → `https://www.musicalbox.com.co` · status **301**

## PythonAnywhere — configuración

1. **Web** → lápiz ✏️ junto a la web app → cambiar el dominio a **`www.musicalbox.com.co`**.
2. Sección **DNS setup**: el valor CNAME debe ser `webapp-3226733.pythonanywhere.com`
   (debe coincidir con el de Cloudflare).
3. **Security → HTTPS certificate** → lápiz → **Auto-renewed Let's Encrypt certificate** → Save.
4. **Force HTTPS** → activado.

---

## Verificación

```bash
# Delegación y resolución
dig +short NS musicalbox.com.co @1.1.1.1                 # cullen/rihana (Cloudflare)
dig +short www.musicalbox.com.co @1.1.1.1                # webapp-...+IP
dig +short musicalbox.com.co @1.1.1.1                    # IP (Cloudflare, apex proxied)

# Funcionamiento
curl -sI https://www.musicalbox.com.co | head -1          # HTTP/2 200
curl -sI http://www.musicalbox.com.co | grep -i location  # https://www.musicalbox.com.co/
curl -sIL https://musicalbox.com.co | grep -iE "^HTTP|^location"  # 301 -> www, luego 200
```

---

## Entorno de pruebas con Cloudflare Tunnel (gratis)

Con el plan **Developer de PythonAnywhere solo hay 1 web app** (producción). Para probar sin
pagar otra web app, se expone el **servidor local** en un subdominio público del mismo dominio,
usando **Cloudflare Tunnel**.

URL de pruebas resultante: **`https://test.musicalbox.com.co`** → apunta a tu Mac.

### Requisitos

```bash
brew install cloudflared
cloudflared --version
```

### Crear el túnel (una sola vez)

```bash
cloudflared tunnel login                                         # autoriza la zona musicalbox.com.co
cloudflared tunnel create staging                                # guarda el ID y el .json
cloudflared tunnel route dns staging test.musicalbox.com.co      # crea el DNS en Cloudflare
```

### Archivo `~/.cloudflared/config.yml`

```yaml
tunnel: f3e791d8-6ef9-48ee-8ed3-ff97c733f789
credentials-file: /Users/migue/.cloudflared/f3e791d8-6ef9-48ee-8ed3-ff97c733f789.json
ingress:
  - hostname: test.musicalbox.com.co
    service: http://localhost:5001
  - service: http_status:404
```

Validar:

```bash
cloudflared tunnel ingress validate      # debe decir OK
```

### Levantar las dos piezas

```bash
# Terminal 1 — la app local
cd /Users/migue/Documents/MusicalBox
PORT=5001 venv/bin/python run.py

# Terminal 2 — el túnel
cloudflared tunnel run staging
```

Cuando el túnel diga *Registered tunnel connection*, abrir <https://test.musicalbox.com.co>.

> - Corriendo local, `APP_CONFIG` cae en **development**: simulación de pagos y VinylMockup activos.
> - Usa la **base de datos local** (`instance/musicalbox.sqlite3`); producción no se toca.
> - Mientras probás, las **dos terminales** deben quedar abiertas.

### (Opcional) Hacer privado el staging con Cloudflare Access

En Cloudflare → **Zero Trust → Access → Applications** → *Add an application* (Self-hosted):
- Domain: `test.musicalbox.com.co`
- Policy: permitir solo tu correo (One-time PIN)

Así `test.musicalbox.com.co` deja de ser público y solo entra quien autorices. (Plan gratis.)

> El **ID del túnel es solo un identificador**; el secreto es el `credentials-file`
> (`~/.cloudflared/*.json`), que **nunca** debe subirse al repositorio.

---

## Flujo de trabajo recomendado

| Etapa | Dónde |
|---|---|
| Programar + ver UI | Mac (`http://127.0.0.1:5001`) |
| URL pública para probar/mostrar | Cloudflare Tunnel → `test.musicalbox.com.co` |
| Tests automáticos en entorno real | consola/SSH de PythonAnywhere (`pytest`) |
| **Producción** | PythonAnywhere `www.musicalbox.com.co` (`git pull` + Reload) |

Regla de oro: **la web app de producción no se toca para probar**; solo recibe `git pull` de
commits ya probados.

### Para actualizar producción

```bash
cd ~/MusicalBox
git pull
source .venv/bin/activate
pip install -r requirements.txt
flask --app run db upgrade
# luego: Web → Reload
```
