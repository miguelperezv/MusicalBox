# MusicalBox
# Luis Miguel Perez Valderrama

[![Top Langs](https://github-readme-stats.vercel.app/api/top-langs/?username=miguellperezzv&langs_count=8)](https://github.com/anuraghazra/github-readme-stats)

Tienda de CD's, vinilos y cassettes (lanzamientos, productos, carrito, pagos ePayco) con el gestor de
**solicitudes de pedido** y **rótulos de envío** que antes vivía en `musicalbox_manager`.

## Correr local

```bash
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\migrate_legacy.py   # crea instance/musicalbox.sqlite3 con los datos de ambas apps
.venv\Scripts\python run.py                      # http://127.0.0.1:5000
```

Si pip falla con `CERTIFICATE_VERIFY_FAILED` (antivirus/proxy), instala primero `truststore` y usa
`pip install --use-feature=truststore -r requirements.txt`.

## Rutas principales

| Ruta | Qué es |
|---|---|
| `/releases/`, `/products/`, `/purchase/` | Tienda: catálogo y carrito |
| `/solicitud/` | Formulario público "Pide tu disco" (catálogo o pedido especial) |
| `/account` | Perfil, compras y solicitudes del usuario |
| `/dashboard` | Panel admin: lanzamientos, productos, órdenes de compra, solicitudes |
| `/solicitud/<id>/rotulo` | Rótulo de envío imprimible (admin) |

Quien hace una solicitud sin cuenta queda con rol `CLIENTE`; si luego se registra con el mismo email, reclama esa cuenta.
