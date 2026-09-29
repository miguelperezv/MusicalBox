"""Toma capturas de las páginas principales en escritorio y celular (necesita la app corriendo).

    python scripts/auditor_web.py [carpeta_salida] [--base http://127.0.0.1:5000]

Entra como admin (el primero de la BD) para capturar también el panel.
Audita también aspectos de accesibilidad, performance básica y SEO.
"""
import argparse
import os
import sqlite3
import json

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PUBLICAS = ["/", "/releases/", "/releases/1", "/products/", "/purchase/", "/solicitud/", "/login", "/signup"]
PRIVADAS = ["/account", "/dashboard"]
VIEWPORTS = {"desktop": {"width": 1366, "height": 900}, "mobile": {"width": 390, "height": 844}}


def nombre(path):
    return path.strip("/").replace("/", "_") or "home"


def auditar_accesibilidad(page):
    """Audita aspectos básicos de accesibilidad"""
    # Verificar contraste de color para elementos importantes
    contraste_bajo = page.evaluate("""
        () => {
            const elementos = document.querySelectorAll('button, a, h1, h2, h3, input, select');
            const problemas = [];
            for (let el of elementos) {
                const estilo = window.getComputedStyle(el);
                const color = estilo.color;
                const fondo = estilo.backgroundColor;
                // Simplificación: solo reportar si hay elementos con color similar a fondo
                if (color === fondo && color !== 'rgba(0, 0, 0, 0)') {
                    problemas.push(el.tagName + (el.className ? '.' + el.className : ''));
                }
            }
            return problemas;
        }
    """)
    return contraste_bajo


def auditar_performance(page):
    """Audita aspectos básicos de performance"""
    # Obtener métricas de performance
    metrics = page.evaluate("""() => {
        const navStart = performance.timing.navigationStart;
        const loadEnd = performance.timing.loadEventEnd;
        const domContentLoaded = performance.timing.domContentLoadedEventEnd;
        
        return {
            load_time: (loadEnd - navStart) / 1000,
            dom_content_loaded: (domContentLoaded - navStart) / 1000
        };
    }""")
    return metrics


def auditar_responsividad(page):
    """Audita aspectos de responsividad"""
    # Verificar si hay scroll horizontal innecesario
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    
    # Verificar si los elementos importantes son visibles
    elementos_fuera_vista = page.evaluate("""
        () => {
            const importantes = document.querySelectorAll('header, main, footer, nav');
            const problemas = [];
            for (let el of importantes) {
                const rect = el.getBoundingClientRect();
                if (rect.right < 0 || rect.left > window.innerWidth) {
                    problemas.push(el.tagName);
                }
            }
            return problemas;
        }
    """)
    
    return {
        "scroll_horizontal": overflow,
        "elementos_fuera_vista": elementos_fuera_vista
    }


def auditar_seo(page):
    """Audita aspectos básicos de SEO"""
    # Verificar título y meta descripción
    titulo = page.title()
    meta_desc = page.evaluate("""() => {
        const meta = document.querySelector('meta[name="description"]');
        return meta ? meta.content : '';
    }""")
    
    # Verificar encabezados
    encabezados = page.evaluate("""() => {
        const h1 = document.querySelectorAll('h1').length;
        const h2 = document.querySelectorAll('h2').length;
        return {h1, h2};
    }""")
    
    # Verificar imágenes sin alt
    imgs_sin_alt = page.evaluate("""() => {
        const imgs = document.querySelectorAll('img');
        let count = 0;
        for (let img of imgs) {
            if (!img.alt || img.alt.trim() === '') {
                count++;
            }
        }
        return count;
    }""")
    
    return {
        "titulo": titulo,
        "longitud_titulo": len(titulo),
        "meta_descripcion": meta_desc,
        "longitud_meta_desc": len(meta_desc),
        "encabezados": encabezados,
        "imagenes_sin_alt": imgs_sin_alt
    }


def generar_resumen_mejoras(reporte):
    """Genera un resumen de posibles mejoras basado en el reporte"""
    mejoras = []
    
    for pagina, datos in reporte["paginas"].items():
        # Performance
        if datos["performance"]["load_time"] > 2:
            mejoras.append(f"{pagina}: Tiempo de carga alto ({datos['performance']['load_time']:.2f}s)")
        
        # Accesibilidad
        if datos["accesibilidad"]["problemas_contraste"] > 0:
            mejoras.append(f"{pagina}: Problemas de contraste de color")
        
        # Responsividad
        if datos["responsividad"]["scroll_horizontal"] > 0:
            mejoras.append(f"{pagina}: Scroll horizontal detectado")
        
        # SEO
        if "seo" in datos:
            if datos["seo"]["longitud_titulo"] > 60 or datos["seo"]["longitud_titulo"] == 0:
                mejoras.append(f"{pagina}: Título muy largo o faltante")
            if datos["seo"]["longitud_meta_desc"] > 160:
                mejoras.append(f"{pagina}: Meta descripción muy larga")
            if datos["seo"]["imagenes_sin_alt"] > 0:
                mejoras.append(f"{pagina}: Imágenes sin atributo alt")
    
    return mejoras


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("salida", nargs="?", default=os.path.join(ROOT, ".capturas", "actual"))
    parser.add_argument("--base", default="http://127.0.0.1:5000")
    args = parser.parse_args()
    os.makedirs(args.salida, exist_ok=True)

    db = sqlite3.connect(os.path.join(ROOT, "instance", "musicalbox.sqlite3"))
    email, pwd = db.execute("SELECT email_usuario, pwd_usuario FROM usuario WHERE k_rol='ADMIN' ORDER BY id").fetchone()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vp_name, vp in VIEWPORTS.items():
            ctx = browser.new_context(viewport=vp, is_mobile=vp_name == "mobile", has_touch=vp_name == "mobile")
            page = ctx.new_page()
            errores = []
            page.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errores.append(str(e)))
            
            # Crear archivo de reporte para este viewport
            reporte_path = os.path.join(args.salida, f"{vp_name}_reporte.json")
            reporte = {
                "viewport": vp_name,
                "dimensiones": vp,
                "paginas": {}
            }
            
            for path in PUBLICAS + ["LOGIN"] + PRIVADAS:
                if path == "LOGIN":
                    page.goto(args.base + "/login")
                    page.fill("input[name=email_usuario]", email)
                    page.fill("input[name=pwd_usuario]", pwd)
                    page.click("form [type=submit]")
                    page.wait_for_load_state("networkidle")
                    continue
                errores.clear()
                page.goto(args.base + path, wait_until="networkidle")
                page.wait_for_timeout(500)
                
                # Tomar captura
                archivo = os.path.join(args.salida, f"{vp_name}_{nombre(path)}.png")
                page.screenshot(path=archivo, full_page=True)
                
                # Realizar auditorías
                accesibilidad = auditar_accesibilidad(page)
                performance = auditar_performance(page)
                responsividad = auditar_responsividad(page)
                seo = auditar_seo(page)
                
                # Registrar resultados
                reporte["paginas"][path] = {
                    "errores_js": len(errores),
                    "errores_detalles": errores[:2],
                    "accesibilidad": {
                        "problemas_contraste": len(accesibilidad),
                        "elementos_problematicos": accesibilidad
                    },
                    "performance": performance,
                    "responsividad": responsividad,
                    "seo": seo
                }
                
                print(f"{vp_name:8} {path:16} errores_js={len(errores)} perf={performance['load_time']:.2f}s")
            
            # Generar resumen de mejoras
            mejoras = generar_resumen_mejoras(reporte)
            reporte["mejoras_sugeridas"] = mejoras
            
            # Guardar reporte
            with open(reporte_path, 'w', encoding='utf-8') as f:
                json.dump(reporte, f, indent=2, ensure_ascii=False)
                
            # Mostrar resumen en consola
            print(f"\n--- Resumen de mejoras para {vp_name} ---")
            for mejora in mejoras[:5]:  # Mostrar solo las primeras 5
                # Limpiar caracteres especiales para evitar problemas de codificación
                mejora_limpia = mejora.encode('ascii', 'ignore').decode('ascii')
                print(f"  ! {mejora_limpia}")
            if len(mejoras) > 5:
                print(f"  ... y {len(mejoras) - 5} mas")
                
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main()