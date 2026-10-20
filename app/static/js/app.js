/* Musical Box — utilidades de la interfaz */

// CSRF global para AJAX (jQuery): el token viaja en el header X-CSRFToken
(function () {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && window.jQuery) {
        jQuery.ajaxSetup({ headers: { 'X-CSRFToken': meta.getAttribute('content') } });
    }
})();

// Función para mostrar alertas con SweetAlert
function showAlert(message, type, timer = 4000) {
    let icon = 'info';
    if (type === 'danger' || type === 'error' || type === 'alert-danger') {
        icon = 'error';
    } else if (type === 'warning' || type === 'alert-warning') {
        icon = 'warning';
    } else if (type === 'success' || type === 'alert-success') {
        icon = 'success';
    }
    
    Swal.fire({
        text: message,
        icon: icon,
        timer: timer,
        timerProgressBar: true,
        showConfirmButton: false,
        toast: true,
        position: 'bottom-end',
        width: '350px',
        customClass: {
            container: 'mb-swal-container',
            popup: 'mb-swal-popup',
            title: 'mb-swal-title',
            content: 'mb-swal-content'
        }
    });
}

// <input data-autocomplete="/url"> o <input list="...">: búsqueda en vivo sobre las opciones existentes
// (desde 2 letras, busca en todo el texto de cada opción: artista, disco, categoría); al elegir, llena el campo.
// data-remote: además busca en una fuente en línea (?q=) y, al elegir uno de sus resultados,
// lo guarda por POST (JSON) y emite 'mbac-select' con {portada} en el input
function mbAutocomplete(root) {
    (root || document).querySelectorAll('input[data-autocomplete], input[list]').forEach(function (input) {
        if (input.dataset.autocompleteReady) return;
        input.dataset.autocompleteReady = '1';
        input.setAttribute('autocomplete', 'off');
        var listId = input.getAttribute('list');
        if (listId) input.removeAttribute('list');

        //contenedor relativo para anclar el desplegable justo bajo el input
        var wrap = document.createElement('div');
        wrap.className = 'mb-ac-wrap';
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);
        var lista = document.createElement('div');
        lista.className = 'mb-ac-list';
        wrap.appendChild(lista);

        var cache = null, timer = null, activo = -1, silencio = false, seq = 0, filaOps = [];
        var remoteUrl = input.getAttribute('data-remote') || '';
        var csrfMeta = document.querySelector('meta[name="csrf-token"]');
        var csrf = csrfMeta ? csrfMeta.getAttribute('content') : '';

        function escapar(s) {
            return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
        }

        //cb(ops, listo): listo=false significa que la fuente aún se está cargando (no mostrar "sin coincidencias")
        function obtener(cb) {
            if (cache) { cb(cache, true); return; }
            if (input.dataset.autocomplete) {
                fetch(input.dataset.autocomplete)
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        cache = (data || []).map(function (t) {
                            t = String(t);
                            return { valor: t, texto: t.replace(/^\d+\.\s*/, '') };
                        });
                        cb(cache, true);
                    });
            } else {
                var dl = document.getElementById(listId);
                if (!dl || !dl.options.length) { cb([], false); return; } //aún se está llenando: se reintenta en la siguiente pulsación
                cache = Array.prototype.map.call(dl.options, function (o) {
                    var t = String(o.value);
                    return { valor: t, texto: t.replace(/^\d+\.\s*/, '') };
                });
                cb(cache, true);
            }
        }

        function cerrar() {
            seq++;
            filaOps = [];
            lista.style.display = 'none';
            lista.innerHTML = '';
            activo = -1;
        }

        function anima() {
            //el evento input (que alimenta infoProducto u otros) no debe reabrir el desplegable
            silencio = true;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            setTimeout(function () { silencio = false; }, 0);
        }

        function elegirLocal(op) {
            clearTimeout(timer);
            input.value = op.valor;
            cerrar();
            anima();
        }

        //elige un disco en línea: guarda (o recupera) el lanzamiento y llena el campo
        function elegirRemoto(a) {
            clearTimeout(timer);
            seq++;
            lista.innerHTML = '<div class="mb-ac-vacio">Guardando…</div>';
            fetch(remoteUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({ external_id: a.id, nombre: a.nombre, artista: a.artista, fecha: a.fecha, portada: a.portada, url: a.url })
            })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
            .then(function (x) {
                if (!x.ok) throw new Error((x.d && x.d.error) || 'No se pudo guardar el disco');
                var d = x.d;
                input.value = d.id + '. ' + (a.artista ? a.artista + ' - ' : '') + (d.nombre || a.nombre);
                cache = (cache || []).concat([{ valor: input.value, texto: (a.artista ? a.artista + ' - ' : '') + (d.nombre || a.nombre) }]);
                cerrar();
                anima();
                input.dispatchEvent(new CustomEvent('mbac-select', { bubbles: true, detail: { portada: d.portada || a.portada } }));
            })
            .catch(function (err) {
                lista.innerHTML = '<div class="mb-ac-vacio">' + escapar(err.message || 'No se pudo guardar el disco') + '</div>';
                lista.style.display = 'block';
            });
        }

        function filaRemota(a) {
            var el = document.createElement('div');
            el.className = 'mb-ac-opt mb-ac-remoto';
            el.innerHTML = (a.portada ? '<img src="' + escapar(a.portada) + '" alt="" loading="lazy">' : '') +
                '<div class="min-w-0"><div class="n">' + escapar(a.nombre) + '</div><div class="a">' +
                escapar(a.artista || '') + (a.fecha ? ' · ' + escapar(a.fecha) : '') + '</div></div>';
            el.addEventListener('mousedown', function (e) { e.preventDefault(); elegirRemoto(a); });
            lista.appendChild(el);
            filaOps.push({ remoto: a });
        }

        function buscar() {
            var q = input.value.trim().toLowerCase();
            if (q.length < 2) { cerrar(); return; }
            var token = ++seq;
            obtener(function (ops, listo) {
                if (token !== seq) return;
                var locales = ops.filter(function (o) { return o.valor.toLowerCase().indexOf(q) !== -1; }).slice(0, 12);
                lista.innerHTML = '';
                filaOps = [];
                if (locales.length) {
                    locales.forEach(function (o) {
                        var el = document.createElement('div');
                        el.className = 'mb-ac-opt';
                        var idx = o.texto.toLowerCase().indexOf(q);
                        if (idx === -1) {
                            el.textContent = o.texto;
                        } else {
                            el.innerHTML = escapar(o.texto.slice(0, idx)) +
                                '<span class="mb-ac-hit">' + escapar(o.texto.slice(idx, idx + q.length)) + '</span>' +
                                escapar(o.texto.slice(idx + q.length));
                        }
                        el.addEventListener('mousedown', function (e) { e.preventDefault(); elegirLocal(o); });
                        lista.appendChild(el);
                        filaOps.push({ op: o });
                    });
                } else if (!listo && !remoteUrl) {
                    cerrar();
                    return;
                } else if (!listo) {
                    lista.innerHTML = '<div class="mb-ac-vacio">Buscando…</div>';
                } else {
                    lista.innerHTML = '<div class="mb-ac-vacio">' + (remoteUrl ? 'Buscando…' : 'Sin coincidencias') + '</div>';
                }
                lista.style.display = 'block';
                activo = -1;
                if (remoteUrl) {
                    fetch(remoteUrl + '?q=' + encodeURIComponent(q))
                        .then(function (r) { return r.json(); })
                        .then(function (d) {
                            if (token !== seq || lista.style.display === 'none') return;
                            var espera = lista.querySelector('.mb-ac-vacio');
                            if (d.error) {
                                if (espera) espera.textContent = d.error;
                                return;
                            }
                            var items = (d.items || []).slice(0, 6);
                            if (!items.length) {
                                if (espera && !filaOps.length) espera.textContent = 'Sin coincidencias';
                                return;
                            }
                            if (espera) espera.remove();
                            var sep = document.createElement('div');
                            sep.className = 'mb-ac-sep';
                            sep.textContent = 'Discos en línea';
                            lista.appendChild(sep);
                            items.forEach(filaRemota);
                        })
                        .catch(function () { /*la búsqueda en línea falla en silencio*/ });
                }
            });
        }

        input.addEventListener('input', function () {
            if (silencio) return;
            clearTimeout(timer);
            timer = setTimeout(buscar, 150);
        });
        input.addEventListener('keydown', function (e) {
            if (lista.style.display !== 'block') return;
            var opciones = lista.querySelectorAll('.mb-ac-opt');
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault();
                activo += (e.key === 'ArrowDown' ? 1 : -1);
                if (activo < 0) activo = opciones.length - 1;
                if (activo >= opciones.length) activo = 0;
                opciones.forEach(function (o, i) { o.classList.toggle('mb-ac-active', i === activo); });
            } else if (e.key === 'Enter') {
                var f = filaOps[activo >= 0 ? activo : 0];
                if (f) {
                    e.preventDefault();
                    if (f.op) elegirLocal(f.op);
                    else elegirRemoto(f.remoto);
                }
            } else if (e.key === 'Escape') {
                cerrar();
            }
        });
        input.addEventListener('blur', function () { setTimeout(cerrar, 150); });
    });
}

// panel admin: los enlaces con data-load traen su sección a #admin-content sin recargar la página
// (por delegación: también sirven los enlaces que llegan después por AJAX, p. ej. "Orden #N").
// Cada sección tiene su URL: se empuja al historial, atrás/adelante funcionan y el enlace del menú
// queda marcado. Lo que se trae por AJAX es el fragmento (sin armazón), ver render_seccion.
function mbAdminLoader() {
    var content = document.getElementById('admin-content');
    if (!content) return;

    //innerHTML no ejecuta los <script> de la sección: se vuelven a crear para que corran
    function ejecutarScripts(cont) {
        cont.querySelectorAll('script').forEach(function (viejo) {
            var nuevo = document.createElement('script');
            if (viejo.src) {
                nuevo.src = viejo.src;
                nuevo.async = false; //los scripts con src corren en orden (chart.js antes de las gráficas)
            } else {
                nuevo.textContent = viejo.textContent;
            }
            viejo.parentNode.replaceChild(nuevo, viejo);
        });
    }

    function marcarActivo(link) {
        var enlaces = document.querySelectorAll('.mb-sidebar .nav-link');
        enlaces.forEach(function (l) { l.classList.remove('active'); });
        var activo = link;
        if (!activo) {
            enlaces.forEach(function (l) {
                if (!activo && l.getAttribute('href') && l.pathname === location.pathname) activo = l;
            });
        }
        if (!activo) return;
        activo.classList.add('active');
        var titulo = (activo.textContent || '').trim();
        if (titulo) document.title = titulo + ' · Musical Box';
    }

    function cargar(url, link) {
        content.innerHTML = '<div class="mb-loading"><div class="spinner-border" role="status"></div></div>';
        $.ajax({ url: url, headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .done(function (html) {
                content.innerHTML = html;
                ejecutarScripts(content);
                mbAutocomplete(content);
                marcarActivo(link);
                //la sección se trae con lo que traiga escrito su buscador (p. ej. #filtro-solicitudes)
                var bus = content.querySelector('#filtro-solicitudes');
                if (bus && bus.value && window.mbFiltrarSolicitudes) window.mbFiltrarSolicitudes(content);
            })
            .fail(function (xhr) {
                //sin sesión: antes se metía la página de login dentro del panel
                var login = (xhr.responseJSON && xhr.responseJSON.login) || '/';
                if (xhr.status === 401) {
                    content.innerHTML = '<div class="alert alert-warning mb-0"><i class="bi bi-clock-history me-1"></i>' +
                        'Tu sesión caducó. <a href="' + login + '">Vuelve a entrar</a> para seguir.</div>';
                    Swal.fire({ title: 'Tu sesión caducó', text: 'Vuelve a entrar para seguir en el panel.',
                                icon: 'warning', confirmButtonText: 'Entrar' })
                        .then(function () { window.location = login; });
                    return;
                }
                content.innerHTML = '<div class="alert alert-danger mb-0">No se pudo cargar la sección. ' +
                    '<a href="' + url + '">Ábrela en una página nueva</a> o recarga el panel.</div>';
            });
    }

    document.addEventListener('click', function (e) {
        var link = e.target.closest('[data-load]');
        if (!link) return;
        e.preventDefault();
        var url = link.dataset.load || link.getAttribute('href');
        var href = link.getAttribute('href') || '';
        if (history.pushState && /^\//.test(href)) history.pushState({}, '', href);
        cargar(url, link.classList.contains('nav-link') ? link : null);
        var sidebar = bootstrap.Offcanvas.getInstance(document.getElementById('adminSidebar'));
        if (sidebar) sidebar.hide();
    });

    //atrás/adelante del navegador: se vuelve a pedir la sección de esa URL
    window.addEventListener('popstate', function () {
        cargar(location.pathname + location.search, null);
    });

    //otras partes del panel pueden pedir que se recargue la sección (p. ej. al rechazar un pedido)
    window.mbRecargarSeccion = function () {
        cargar(location.pathname + location.search, null);
    };
}

document.addEventListener('DOMContentLoaded', function () {
    mbAutocomplete();
    mbAdminLoader();
    // las alertas se cierran solas
    document.querySelectorAll('.mb-toasts .alert').forEach(function (a) {
        // Convertir alertas normales a SweetAlert
        var alertType = '';
        var message = a.textContent.trim();
        
        // Determinar el tipo de alerta
        if (a.classList.contains('alert-danger')) {
            alertType = 'danger';
        } else if (a.classList.contains('alert-warning')) {
            alertType = 'warning';
        } else if (a.classList.contains('alert-info')) {
            alertType = 'info';
        } else if (a.classList.contains('alert-success')) {
            alertType = 'success';
        } else {
            // Verificar si hay categorías personalizadas
            for (var i = 0; i < a.classList.length; i++) {
                var cls = a.classList[i];
                if (cls.startsWith('alert-')) {
                    alertType = cls.replace('alert-', '');
                    break;
                }
            }
            // Tipo por defecto
            if (!alertType) {
                alertType = 'info';
            }
        }
        
        showAlert(message, alertType, 6000);
        
        // Remover la alerta original
        a.remove();
    });
});

// vista rápida: enlaces con data-quickview abren su contenido en el modal (Ctrl/Cmd+clic abre la página)
document.addEventListener('click', function (e) {
    var link = e.target.closest('[data-quickview]');
    if (!link || e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault();
    var modalEl = document.getElementById('mbModal');
    var body = modalEl.querySelector('.modal-body');
    body.innerHTML = '<div class="mb-loading"><div class="spinner-border" role="status"></div></div>';
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
    fetch(link.dataset.quickview, { headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.text(); }).then(function (html) {
        body.innerHTML = html;
        //los embeds de redes necesitan volver a procesarse al insertarse
        if (window.instgrm) window.instgrm.Embeds.process();
        if (window.mbAutocomplete) mbAutocomplete(body);
        body.querySelectorAll('script[src]').forEach(function (s) {
            var n = document.createElement('script'); n.src = s.src; n.async = true; document.body.appendChild(n);
        });
    });
});

//nuevo lanzamiento: búsqueda de discos (el formulario llega por data-load o por modal)
(function () {
    var urlSpotify = '/dashboard/newrelease_spotify';
    function escapar(t) { return String(t || '').replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
    function asegurarArtista(nombre) {
        var sel = document.getElementById('artista');
        nombre = (nombre || '').trim();
        if (!sel || !nombre) return;
        for (var i = 0; i < sel.options.length; i++) {
            if (sel.options[i].value.toUpperCase() === nombre.toUpperCase()) { sel.value = sel.options[i].value; return; }
        }
        var opt = document.createElement('option');
        opt.value = nombre.toUpperCase();
        opt.textContent = nombre;
        sel.add(opt);
        sel.value = opt.value;
    }
    function usar(album) {
        document.getElementById('lanzamiento').value = album.nombre || '';
        document.getElementById('i_lanzamiento').value = album.portada || '';
        var f = album.fecha || '';
        if (f.length === 4) f = f + '-01-01';
        else if (f.length === 7) f = f + '-01';
        document.getElementById('f_lanzamiento').value = f;
        asegurarArtista(album.artista);
        document.getElementById('external_id').value = album.id || '';
        document.getElementById('external_url').value = album.url || '';
        document.getElementById('spresultados').innerHTML = '<div class="form-text">Usando <b>' + escapar(album.nombre) + '</b> del buscador. Revisa los datos antes de crear.</div>';
    }
    function buscar() {
        var q = document.getElementById('spq');
        var consulta = q.value.trim();
        if (!consulta) return;
        var resultado = document.getElementById('spresultados');
        resultado.innerHTML = '<div class="text-body-secondary small">Buscando…</div>';
        fetch(urlSpotify + '?q=' + encodeURIComponent(consulta))
            .then(function (r) { return r.json(); })
            .then(function (d) {
                if (d.error) { resultado.innerHTML = '<div class="text-danger small">' + escapar(d.error) + '</div>'; return; }
                if (!d.items.length) { resultado.innerHTML = '<div class="text-body-secondary small">Sin resultados.</div>'; return; }
                var html = d.items.map(function (a, i) {
                    return '<div class="d-flex align-items-center gap-2 mb-2" style="max-width:540px">' +
                        (a.portada ? '<img src="' + escapar(a.portada) + '" width="44" height="44" class="rounded object-fit-cover" alt="">' : '<div style="width:44px;height:44px" class="rounded bg-body-tertiary"></div>') +
                        '<div class="min-w-0 flex-fill"><div class="fw-semibold text-truncate">' + escapar(a.nombre) + '</div>' +
                        '<div class="small text-body-secondary text-truncate">' + escapar(a.artista) + (a.fecha ? ' · ' + escapar(a.fecha) : '') + '</div></div>' +
                        '<button type="button" class="btn btn-sm btn-outline-primary text-nowrap" data-i="' + i + '">Usar</button></div>';
                }).join('');
                resultado.innerHTML = html;
                var items = d.items;
                resultado.querySelectorAll('button[data-i]').forEach(function (b) {
                    b.addEventListener('click', function () { usar(items[parseInt(b.dataset.i, 10)]); });
                });
            })
            .catch(function () { resultado.innerHTML = '<div class="text-danger small">Error de red al buscar el disco.</div>'; });
    }
    document.addEventListener('click', function (e) {
        if (e.target.closest && e.target.closest('#spbuscar')) buscar();
    });
    document.addEventListener('keydown', function (e) {
        if (e.target.closest && e.target.closest('#spq') && e.key === 'Enter') { e.preventDefault(); buscar(); }
    });
})();

//nuevo producto: tipo BUNDLE oculta el stock propio (el formulario llega por data-load o por modal)
document.addEventListener('change', function (e) {
    var t = e.target.closest && e.target.closest('#tipo');
    if (!t) return;
    var s = document.querySelector('.campo-stock');
    if (s) s.style.display = t.value === 'BUNDLE' ? 'none' : '';
});

//edición rápida en los listados: clic en la celda de stock/precio (productos) o fecha (lanzamientos)
(function () {
    function precioCOP(n) { return '$' + Number(n).toLocaleString('es-CO'); }
    function fechaBonita(iso) {
        var p = String(iso || '').slice(0, 10).split('-');
        return p.length === 3 ? p[2] + '/' + p[1] + '/' + p[0] : String(iso || '');
    }
    function pintarStock(celda, v) {
        celda.dataset.valor = v;
        celda.innerHTML = v <= 0 ? '<span class="mb-estado mb-estado-RECHAZADO">Agotado</span>'
            : (v <= 3 ? '<span class="mb-estado mb-estado-PENDIENTE">' + v + ' · bajo</span>' : String(v));
    }
    window.mbPintarStock = pintarStock;
    document.addEventListener('click', function (e) {
        var celda = e.target.closest('td.stock-editable, td.precio-celda, td.fecha-celda');
        if (!celda || celda.querySelector('form.mb-celda')) return;
        var campo = celda.classList.contains('precio-celda') ? 'precio' : (celda.classList.contains('fecha-celda') ? 'f_lanzamiento' : 'stock');
        var url = campo === 'f_lanzamiento'
            ? '/dashboard/lanzamiento/' + celda.dataset.id + '/f_lanzamiento'
            : '/dashboard/producto/' + celda.dataset.id + '/' + campo;
        var form = document.createElement('form');
        form.className = 'mb-celda d-inline-flex align-items-center gap-1';
        form.dataset.campo = campo;
        form.dataset.url = url;
        form.dataset.html = celda.innerHTML;
        form.dataset.valor = celda.dataset.valor || '';
        var input = document.createElement('input');
        input.type = campo === 'f_lanzamiento' ? 'date' : 'number';
        input.min = '0';
        input.className = 'form-control form-control-sm py-0';
        input.style.width = campo === 'f_lanzamiento' ? '140px' : '64px';
        input.value = celda.dataset.valor || '';
        var ok = document.createElement('button');
        ok.type = 'submit'; ok.className = 'btn btn-sm btn-primary py-0'; ok.title = 'Guardar'; ok.innerHTML = '<i class="bi bi-check-lg"></i>';
        var no = document.createElement('button');
        no.type = 'button'; no.className = 'btn btn-sm btn-outline-secondary py-0'; no.title = 'Cancelar'; no.innerHTML = '<i class="bi bi-x-lg"></i>';
        form.appendChild(input); form.appendChild(ok); form.appendChild(no);
        celda.innerHTML = '';
        celda.appendChild(form);
        input.focus();
        if (input.select) input.select();
        input.addEventListener('keydown', function (ev) {
            if (ev.key === 'Enter') { ev.preventDefault(); ok.click(); }
            if (ev.key === 'Escape') no.click();
        });
        no.addEventListener('click', function () { celda.innerHTML = form.dataset.html; celda.dataset.valor = form.dataset.valor; });
    });
    document.addEventListener('submit', function (e) {
        var form = e.target.closest && e.target.closest('form.mb-celda');
        if (!form) return;
        e.preventDefault();
        if (form.dataset.enviado) return;
        var input = form.querySelector('input');
        var campo = form.dataset.campo, valor = input.value.trim();
        if (campo === 'stock') { var s = parseInt(valor, 10); if (isNaN(s) || s < 0) { input.classList.add('is-invalid'); return; } }
        if (campo === 'precio') { var p = parseInt(valor, 10); if (isNaN(p) || p <= 0) { input.classList.add('is-invalid'); return; } }
        if (campo === 'f_lanzamiento' && valor && !/^\d{4}-\d{2}-\d{2}$/.test(valor)) { input.classList.add('is-invalid'); return; }
        form.dataset.enviado = '1';
        var datos = {};
        datos[campo === 'f_lanzamiento' ? 'valor' : campo] = valor;
        $.post(form.dataset.url, datos)
            .done(function (r) {
                var celda = form.closest('td');
                if (campo === 'stock') pintarStock(celda, r.stock);
                else if (campo === 'precio') { celda.innerHTML = precioCOP(r.precio); celda.dataset.valor = r.precio; }
                else { celda.innerHTML = r.f_lanzamiento ? fechaBonita(r.f_lanzamiento) : ''; celda.dataset.valor = r.f_lanzamiento; }
            })
            .fail(function () { form.dataset.enviado = ''; input.classList.add('is-invalid'); });
    });
})();

//solicitudes: chips para filtrar la lista por estado, combinables con el buscador (delegado).
//(las órdenes de compra filtran con su propio script en invoices.html: secciones por grupo + buscador)
(function () {
    function marcar(chip) {
        document.querySelectorAll('.chip-filtro[data-filtra="solicitudes"]').forEach(function (b) {
            var es = b === chip;
            b.classList.toggle('active', es);
            b.classList.toggle('btn-primary', es);
            b.classList.toggle('btn-outline-secondary', !es);
        });
    }
    //solicitudes: chip de estado + texto del buscador, combinados
    window.mbFiltrarSolicitudes = function (panel) {
        panel = panel || document;
        var chip = panel.querySelector('.chip-filtro[data-filtra="solicitudes"].active');
        var filtro = chip ? chip.dataset.filtro : 'todas';
        var input = panel.querySelector('#filtro-solicitudes');
        var q = input ? input.value.trim().toLowerCase() : '';
        var visibles = 0;
        panel.querySelectorAll('#tabla-solicitudes tr[data-est]').forEach(function (tr) {
            var ok = (filtro === 'todas' || tr.dataset.est === filtro) && (!q || tr.textContent.toLowerCase().indexOf(q) !== -1);
            tr.classList.toggle('d-none', !ok);
            if (ok) visibles++;
        });
        var vacio = panel.querySelector('.fila-sin-resultado-sol');
        if (vacio) vacio.classList.toggle('d-none', visibles > 0);
    };
    document.addEventListener('click', function (e) {
        var chip = e.target.closest && e.target.closest('.chip-filtro[data-filtra="solicitudes"]');
        if (!chip) return;
        marcar(chip);
        window.mbFiltrarSolicitudes(chip.closest('#admin-content') || document);
    });
    document.addEventListener('input', function (e) {
        if (e.target && e.target.id === 'filtro-solicitudes') {
            window.mbFiltrarSolicitudes(e.target.closest('#admin-content') || document);
        }
    });
})();

//lanzamientos: portada, post y disco por un campo en modal (delegado: sección y modal)
(function () {
    var titulos = { i_lanzamiento: 'Portada (URL)', url_social: 'Post de Instagram/TikTok (URL)' };
    function esc(t) { return String(t || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;'); }
    document.addEventListener('click', function (e) {
        var b = e.target.closest && e.target.closest('[data-cambio]');
        if (!b) return;
        e.preventDefault();
        var campo = b.dataset.cambio, id = b.dataset.id;
        var m = document.getElementById('mbModal');
        var body = m.querySelector('.modal-body');
        body.innerHTML = '<div style="max-width:560px;margin:0 auto">' +
            '<h6 class="h6">' + titulos[campo] + '</h6>' +
            '<input id="mb-cambio-url" class="form-control" value="' + esc(b.dataset.valor) + '" placeholder="https://...">' +
            '<div class="form-text">Deja vacío para quitar el campo.</div>' +
            '<div id="mb-cambio-err" class="text-danger small mt-2"></div>' +
            '<div class="d-flex gap-2 mt-2"><button type="button" class="btn btn-primary btn-sm" id="mb-cambio-ok">Guardar</button>' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Cancelar</button></div></div>';
        bootstrap.Modal.getOrCreateInstance(m).show();
        var input = document.getElementById('mb-cambio-url');
        input.focus();
        input.select();
        function guardar() {
            var btn = document.getElementById('mb-cambio-ok');
            var err = document.getElementById('mb-cambio-err');
            btn.disabled = true;
            input.classList.remove('is-invalid');
            err.textContent = '';
            $.post('/dashboard/lanzamiento/' + id + '/' + campo, { valor: input.value.trim() })
                .done(function (r) {
                    var tr = b.closest('tr');
                    var v = r[campo] || '';
                    b.dataset.valor = v;
                    if (campo === 'i_lanzamiento') {
                        var img = tr.querySelector('td img');
                        if (v) {
                            if (img) img.src = v;
                            else tr.querySelector('td .d-flex').insertAdjacentHTML('afterbegin',
                                '<img src="' + esc(v) + '" alt="" width="48" height="48" class="rounded object-fit-cover flex-shrink-0">');
                        } else if (img) img.remove();
                    }
                    if (campo === 'url_social' && tr) {
                        var hint = tr.querySelector('[data-post-hint]');
                        if (hint) hint.classList.toggle('d-none', !v);
                    }
                    var inst = bootstrap.Modal.getInstance(m);
                    if (inst) inst.hide();
                })
                .fail(function (xhr) {
                    btn.disabled = false;
                    input.classList.add('is-invalid');
                    err.textContent = (xhr.responseJSON && xhr.responseJSON.error) || 'Error al guardar';
                });
        }
        document.getElementById('mb-cambio-ok').addEventListener('click', guardar);
        input.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); guardar(); } });
    });
})();

//preorden: un clic en el ícono de fuego lo marca/desmarca (producto o paraguas del lanzamiento)
(function () {
    document.addEventListener('click', function (e) {
        var b = e.target.closest && e.target.closest('[data-preorden-toggle]');
        if (!b || b.disabled || b.dataset.enviado) return;
        e.preventDefault();
        b.dataset.enviado = '1';
        $.post(b.dataset.url, {})
            .done(function (r) {
                var activo = !!r.preorden;
                b.dataset.activo = activo ? '1' : '0';
                b.classList.toggle('btn-outline-danger', activo);
                b.classList.toggle('text-danger', activo);
                b.classList.toggle('btn-outline-secondary', !activo);
                b.title = activo ? 'Quitar preorden' : 'Marcar como preorden';
                var chip = b.closest('tr').querySelector('[data-preorden-chip]');
                if (chip) chip.classList.toggle('d-none', typeof r.es_preorden === 'boolean' ? !r.es_preorden : !activo);
            })
            .fail(function (xhr) {
                b.dataset.enviado = '';
                showAlert((xhr.responseJSON && xhr.responseJSON.error) || 'No se pudo actualizar el preorden', 'danger');
            });
    });
})();

//productos: clic en "N tallas" expande la fila con el stock de cada talla (edición inline)
(function () {
    document.addEventListener('click', function (e) {
        var b = e.target.closest && e.target.closest('[data-tallas]');
        if (!b) return;
        e.preventDefault();
        var fila = b.closest('tr').nextElementSibling;
        if (fila && fila.classList.contains('fila-tallas')) fila.classList.toggle('d-none');
    });
    document.addEventListener('submit', function (e) {
        var form = e.target.closest && e.target.closest('form.mb-talla');
        if (!form) return;
        e.preventDefault();
        if (form.dataset.enviado) return;
        var input = form.querySelector('input');
        var s = parseInt(input.value, 10);
        if (isNaN(s) || s < 0 || s > 9999) { input.classList.add('is-invalid'); return; }
        form.dataset.enviado = '1';
        $.post(form.dataset.url, { stock: input.value })
            .done(function (r) {
                input.value = r.stock;
                input.classList.remove('is-invalid');
                var celda = form.closest('tr.fila-tallas').previousElementSibling.querySelector('td.stock-celda');
                if (celda && window.mbPintarStock) window.mbPintarStock(celda, r.total);
            })
            .fail(function () { form.dataset.enviado = ''; input.classList.add('is-invalid'); });
    });
})();

//órdenes: nota interna por modal (corrección de dirección, detalles del cliente, etc.)
(function () {
    function esc(t) { return String(t || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;'); }
    document.addEventListener('click', function (e) {
        var b = e.target.closest && e.target.closest('[data-nota]');
        if (!b) return;
        e.preventDefault();
        var m = document.getElementById('mbModal');
        var body = m.querySelector('.modal-body');
        body.innerHTML = '<div style="max-width:560px;margin:0 auto">' +
            '<h6 class="h6">Nota interna del pedido #' + b.dataset.id + '</h6>' +
            '<textarea id="mb-nota-input" class="form-control" rows="4" placeholder="Ej.: cambió a la dirección de la oficina, avisa por WhatsApp…">' + esc(b.dataset.nota) + '</textarea>' +
            '<div class="form-text">Solo la ve el equipo; no sale en el correo ni en el rótulo.</div>' +
            '<div class="d-flex gap-2 mt-2"><button type="button" class="btn btn-primary btn-sm" id="mb-nota-ok">Guardar</button>' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Cancelar</button></div></div>';
        bootstrap.Modal.getOrCreateInstance(m).show();
        var input = document.getElementById('mb-nota-input');
        input.focus();
        function guardar() {
            $.post(b.dataset.url, { nota: input.value })
                .done(function (r) {
                    b.dataset.nota = r.nota || '';
                    b.classList.toggle('btn-outline-warning', !!r.nota);
                    b.classList.toggle('text-warning', !!r.nota);
                    b.classList.toggle('btn-outline-secondary', !r.nota);
                    b.title = r.nota || 'Agregar nota interna';
                    bootstrap.Modal.getInstance(m).hide();
                })
                .fail(function () { showAlert('No se pudo guardar la nota', 'danger'); });
        }
        document.getElementById('mb-nota-ok').addEventListener('click', guardar);
    });
})();

//órdenes: rechazar un pedido pendiente (libera la reserva de stock)
(function () {
    document.addEventListener('click', function (e) {
        var b = e.target.closest && e.target.closest('[data-rechazar]');
        if (!b) return;
        e.preventDefault();
        Swal.fire({
            title: 'Rechazar el pedido #' + b.dataset.id + '?',
            text: 'Se marcará RECHAZADO y se liberará el stock reservado.',
            icon: 'warning', showCancelButton: true, confirmButtonText: 'Rechazar', cancelButtonText: 'Cancelar'
        }).then(function (r) {
            if (!r.isConfirmed) return;
            $.post(b.dataset.url, {})
                .done(function (res) {
                    var tr = b.closest('tr');
                    tr.dataset.estado = res.estado;
                    var chip = tr.querySelector('.mb-estado');
                    if (chip) chip.outerHTML = '<span class="mb-estado mb-estado-' + res.estado + '">' + res.estado + '</span>';
                    b.remove();
                    //el pedido ya no está pendiente: se recarga la sección para que caiga en su grupo y se muevan los contadores
                    if (window.mbRecargarSeccion) window.mbRecargarSeccion();
                })
                .fail(function (xhr) { showAlert((xhr.responseJSON && xhr.responseJSON.error) || 'No se pudo rechazar el pedido', 'danger'); });
        });
    });
})();

//órdenes: estado de envío, guía/transportadora y costo de envío (delegado: también sirve lo que
//llega por AJAX al panel). Antes estos controles no tenían JS: no hacían nada al usarlos.
(function () {
    function pesos(n) { return '$' + Number(n || 0).toLocaleString('es-CO'); }
    function rotuloDe(tr) { return tr.querySelector('a.rotulo'); }

    //cambiar el estado de envío: POR PREPARAR -> EN PREPARACION -> ENVIADO -> ENTREGADO
    document.addEventListener('change', function (e) {
        var sel = e.target.closest && e.target.closest('select.estado-envio');
        if (!sel || sel.disabled) return;
        var tr = sel.closest('tr');
        sel.disabled = true;
        $.post(sel.dataset.url, { estado_envio: sel.value })
            .done(function (r) {
                tr.dataset.envio = r.estado_envio;
                var rot = rotuloDe(tr);
                if (rot) rot.classList.toggle('d-none', !r.rotulo);
                //al quedar ENTREGADO deja de ser "requiere envío" y pasa al historial
                if (r.estado_envio === 'ENTREGADO') {
                    var destino = document.querySelector('#tabla-entregados tbody');
                    if (destino) destino.appendChild(tr);
                }
                if (r.estado_envio === 'ENVIADO') {
                    showAlert(r.aviso_enviado
                        ? 'Pedido marcado ENVIADO. Le avisamos al comprador por correo.'
                        : 'Pedido marcado ENVIADO, pero no se pudo enviar el correo de aviso: revisa el correo del comprador.',
                        r.aviso_enviado ? 'success' : 'warning');
                }
            })
            .fail(function (xhr) {
                sel.value = tr.dataset.envio || sel.value;
                showAlert((xhr.responseJSON && xhr.responseJSON.error) || 'No se pudo cambiar el estado de envío', 'danger');
            })
            .always(function () { sel.disabled = false; });
    });

    //guía y transportadora del despacho (viajan al correo del comprador)
    document.addEventListener('submit', function (e) {
        var form = e.target.closest && e.target.closest('form.envio-guia');
        if (!form) return;
        e.preventDefault();
        if (form.dataset.enviado) return;
        var tr = form.closest('tr');
        var boton = form.querySelector('button');
        function guardar(avisar) {
            form.dataset.enviado = '1';
            boton.disabled = true;
            var datos = $(form).serialize();
            if (avisar) datos += '&avisar=1';
            $.post(form.dataset.url, datos)
                .done(function (r) {
                    showAlert(avisar && r.aviso_enviado
                        ? 'Guía guardada y enviada al comprador por correo.'
                        : 'Guía y transportadora guardadas.', 'success');
                })
                .fail(function (xhr) {
                    form.dataset.enviado = '';
                    showAlert((xhr.responseJSON && xhr.responseJSON.error) || 'No se pudo guardar la guía', 'danger');
                })
                .always(function () { boton.disabled = false; });
        }
        //si el pedido ya está ENVIADO, la guía se puede mandar al comprador en ese momento
        if (tr && tr.dataset.envio === 'ENVIADO') {
            Swal.fire({
                title: 'Guardar la guía',
                text: 'El pedido ya está marcado ENVIADO. ¿Le avisamos al comprador por correo con esta guía?',
                icon: 'question', showCancelButton: true,
                confirmButtonText: 'Sí, avisar', cancelButtonText: 'Solo guardar'
            }).then(function (r) { guardar(!!r.isConfirmed); });
        } else {
            guardar(false);
        }
    });

    //costo de envío de la orden (se corrige hasta que el pedido quede ENVIADO)
    document.addEventListener('submit', function (e) {
        var form = e.target.closest && e.target.closest('form.envio-override');
        if (!form) return;
        e.preventDefault();
        if (form.dataset.enviado) return;
        var input = form.querySelector('input[name="p_envio"]');
        var valor = parseInt(input.value, 10);
        if (isNaN(valor) || valor < 0) { input.classList.add('is-invalid'); return; }
        input.classList.remove('is-invalid');
        form.dataset.enviado = '1';
        $.post(form.dataset.url, { p_envio: valor })
            .done(function (r) {
                var tr = form.closest('tr');
                var total = tr.querySelector('.total-pago');
                if (total) total.textContent = pesos(r.total_pago);
                var detalle = tr.querySelector('.detalle-envio');
                if (detalle) detalle.innerHTML = '<i class="bi bi-pencil" title="Ajustado manualmente"></i> envío +' + pesos(r.p_envio);
                showAlert('Costo de envío actualizado: ' + pesos(r.p_envio), 'success');
            })
            .fail(function (xhr) {
                form.dataset.enviado = '';
                showAlert((xhr.responseJSON && xhr.responseJSON.error) || 'No se pudo actualizar el costo de envío', 'danger');
            });
    });
})();

/* ---------- compra rápida en móvil (ficha de producto) ----------
   La barra aparece cuando el formulario de compra no está a la vista y lleva
   al formulario (o enfoca la talla) sin obligar a buscar el botón. */
(function () {
    var barra = document.querySelector('.mb-pdp-sticky');
    if (!barra) return;
    var form = document.querySelector('.mb-detalle form[action*="/addtocart"]');
    var boton = barra.querySelector('[data-mb-pdp-cta]');
    if (boton && form) {
        boton.addEventListener('click', function () {
            if (form.scrollIntoView) form.scrollIntoView({ behavior: 'smooth', block: 'center' });
            var select = form.querySelector('select[name="variante_id"]');
            var input = form.querySelector('input[name="quantity"]');
            window.setTimeout(function () {
                if (select) select.focus();
                else if (input) input.focus();
            }, 350);
        });
    }
    if (form && 'IntersectionObserver' in window) {
        var obs = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                barra.classList.toggle('mb-pdp-sticky-visible', !entry.isIntersecting);
            });
        }, { threshold: 0.2 });
        obs.observe(form);
    } else {
        barra.classList.add('mb-pdp-sticky-visible');
    }
})();

/* ---------- buscador móvil ----------
   Al abrir el panel, el foco va directo al campo para escribir sin otro toque. */
(function () {
    var panel = document.getElementById('mbSearchMobile');
    if (!panel) return;
    panel.addEventListener('shown.bs.collapse', function () {
        var input = panel.querySelector('input[type="search"]');
        if (input) input.focus();
    });
})();

/* ---------- sugerencias del buscador ----------
   Mientras se escribe, muestra lanzamientos, productos y artistas. El endpoint
   devuelve los grupos ya armados; aquí solo se pintan y se navega con teclado. */
(function () {
    if (!window.fetch) return;
    var formularios = document.querySelectorAll('form[data-mb-suggest-url]');
    if (!formularios.length) return;

    function escapar(texto) {
        var div = document.createElement('div');
        div.textContent = texto == null ? '' : String(texto);
        return div.innerHTML;
    }

    function iniciar(form) {
        var input = form.querySelector('input[type="search"]');
        var panel = form.querySelector('.mb-suggest');
        if (!input || !panel) return;
        var url = form.getAttribute('data-mb-suggest-url');
        var timer = null, controlador = null, items = [], activo = -1, ultima = '', token = 0;

        function cerrar() {
            token++;
            clearTimeout(timer);
            panel.hidden = true;
            panel.innerHTML = '';
            input.setAttribute('aria-expanded', 'false');
            input.removeAttribute('aria-activedescendant');
            items = [];
            activo = -1;
            ultima = '';
        }

        function abrir() {
            panel.hidden = false;
            input.setAttribute('aria-expanded', 'true');
        }

        function mover(delta) {
            if (!items.length) return;
            if (activo < 0) {
                activo = delta > 0 ? 0 : items.length - 1;
            } else {
                activo = (activo + delta + items.length) % items.length;
            }
            items.forEach(function (item, i) {
                item.classList.toggle('mb-suggest-active', i === activo);
                item.setAttribute('aria-selected', i === activo ? 'true' : 'false');
            });
            input.setAttribute('aria-activedescendant', items[activo].id);
            items[activo].scrollIntoView({ block: 'nearest' });
        }

        function itemHtml(item, indice) {
            var foto = item.imagen
                ? '<img src="' + escapar(item.imagen) + '" alt="" loading="lazy">'
                : '<span class="mb-suggest-icon"><i class="bi ' + escapar(item.icono || 'bi-search') + '"></i></span>';
            return '<a class="mb-suggest-item" id="' + panel.id + '-item-' + indice + '" role="option" aria-selected="false" href="' + escapar(item.url) + '">' +
                foto +
                '<span><strong>' + escapar(item.titulo) + '</strong>' +
                (item.subtitulo ? '<small>' + escapar(item.subtitulo) + '</small>' : '') +
                '</span></a>';
        }

        function pintar(data) {
            var grupos = [
                ['Lanzamientos', data.lanzamientos],
                ['Productos', data.productos],
                ['Artistas', data.artistas]
            ];
            var html = '', indice = 0;
            grupos.forEach(function (grupo) {
                if (!grupo[1] || !grupo[1].length) return;
                html += '<div class="mb-suggest-group" role="group" aria-label="' + escapar(grupo[0]) + '">' +
                    '<div class="mb-suggest-title">' + escapar(grupo[0]) + '</div>';
                grupo[1].forEach(function (item) {
                    html += itemHtml(item, indice++);
                });
                html += '</div>';
            });
            if (!html) {
                html = '<div class="mb-suggest-empty">Sin resultados. Presiona Enter para buscar en todo el catálogo.</div>';
            } else if (data.ver_todos) {
                html += '<a class="mb-suggest-all" href="' + escapar(data.ver_todos) + '">Ver todos los resultados</a>';
            }
            panel.innerHTML = html;
            items = Array.prototype.slice.call(panel.querySelectorAll('.mb-suggest-item'));
            activo = -1;
            abrir();
        }

        function buscar() {
            var q = input.value.trim();
            if (!q) { cerrar(); return; }
            if (q === ultima) return;
            ultima = q;
            var actual = ++token;
            if (controlador) controlador.abort();
            controlador = ('AbortController' in window) ? new AbortController() : null;
            fetch(url + '?q=' + encodeURIComponent(q), {
                headers: { 'Accept': 'application/json' },
                credentials: 'same-origin',
                signal: controlador ? controlador.signal : undefined
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (actual !== token) return;
                    if (input.value.trim() !== data.q) return;
                    pintar(data);
                })
                .catch(function (e) {
                    if (actual !== token) return;
                    if (!e || e.name !== 'AbortError') cerrar();
                });
        }

        input.addEventListener('input', function () {
            clearTimeout(timer);
            if (!input.value.trim()) { cerrar(); return; }
            timer = setTimeout(buscar, 180);
        });
        input.addEventListener('focus', function () {
            if (input.value.trim() && panel.hidden) {
                ultima = '';
                buscar();
            }
        });
        input.addEventListener('keydown', function (e) {
            if (panel.hidden) return;
            if (e.key === 'ArrowDown') { e.preventDefault(); mover(1); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); mover(-1); }
            else if (e.key === 'Escape') { cerrar(); }
            else if (e.key === 'Enter' && activo >= 0 && items[activo]) {
                e.preventDefault();
                window.location.href = items[activo].href;
            }
        });
        document.addEventListener('click', function (e) {
            if (!form.contains(e.target)) cerrar();
        });
    }

    Array.prototype.forEach.call(formularios, iniciar);
})();

/* ---------- agregar al carrito sin recargar ----------
   Al agregar, mostramos un aviso breve con la portada del producto, la bolsa hace
   un pulso y el contador se actualiza. Sin fetch, el formulario sigue funcionando
   como siempre (POST + aviso). */
(function () {
    function bolsa() { return document.querySelector('.mb-cart'); }

    function urlCarrito() {
        var cart = bolsa();
        return cart ? cart.href : '/purchase/';
    }

    function logoUrl() {
        var img = document.querySelector('.navbar-brand img');
        return img ? img.src : '/static/imgs/musicalbox.png';
    }

    function actualizarContador(n) {
        var cart = bolsa();
        if (!cart) return;
        var badge = cart.querySelector('.badge');
        if (!n) { if (badge) badge.remove(); return; }
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'badge';
            cart.appendChild(badge);
        }
        badge.textContent = n;
        badge.classList.remove('mb-badge-bump');
        void badge.offsetWidth;
        badge.classList.add('mb-badge-bump');
    }

    function pulsoBolsa() {
        var cart = bolsa();
        if (!cart) return;
        cart.classList.remove('mb-cart-bump');
        void cart.offsetWidth;
        cart.classList.add('mb-cart-bump');
        window.setTimeout(function () { cart.classList.remove('mb-cart-bump'); }, 650);
    }

    // La portada y el nombre salen de la tarjeta o de la ficha que contiene el botón.
    function datosProducto(origen) {
        var cont = origen && origen.closest
            ? (origen.closest('article.mb-card') || origen.closest('.mb-detalle') || origen.closest('.modal'))
            : null;
        var img = cont ? cont.querySelector('.cover img, .mb-detalle img, img') : null;
        var nombre = cont ? cont.querySelector('.title, h1, h2') : null;
        return {
            imagen: img ? img.src : logoUrl(),
            nombre: nombre ? nombre.textContent.trim() : ''
        };
    }

    function cerrarAviso(aviso) {
        if (!aviso || aviso.dataset.saliendo) return;
        aviso.dataset.saliendo = '1';
        aviso.classList.remove('mb-cart-toast-in');
        aviso.classList.add('mb-cart-toast-out');
        window.setTimeout(function () { aviso.remove(); }, 260);
    }

    function mostrarAviso(datos) {
        var anterior = document.querySelector('.mb-cart-toast');
        if (anterior) anterior.remove();

        var aviso = document.createElement('div');
        aviso.className = 'mb-cart-toast' + (datos.ok ? '' : ' mb-cart-toast-warn');
        aviso.setAttribute('role', 'status');
        aviso.setAttribute('aria-live', 'polite');

        var foto = document.createElement('img');
        foto.className = 'mb-cart-toast-img';
        foto.src = datos.imagen || logoUrl();
        foto.alt = '';
        foto.addEventListener('error', function () { foto.src = logoUrl(); }, { once: true });

        var cuerpo = document.createElement('div');
        cuerpo.className = 'mb-cart-toast-body';

        var titulo = document.createElement('div');
        titulo.className = 'mb-cart-toast-title';
        titulo.innerHTML = '<i class="bi ' + (datos.ok ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill') + '"></i>';
        titulo.appendChild(document.createTextNode(datos.titulo || ''));
        cuerpo.appendChild(titulo);

        var texto = document.createElement('div');
        texto.className = 'mb-cart-toast-name';
        texto.textContent = datos.mensaje || '';
        cuerpo.appendChild(texto);

        if (datos.ok) {
            var enlace = document.createElement('a');
            enlace.className = 'mb-cart-toast-link';
            enlace.href = urlCarrito();
            enlace.textContent = 'Ver carrito';
            cuerpo.appendChild(enlace);
        }

        var cerrar = document.createElement('button');
        cerrar.type = 'button';
        cerrar.className = 'mb-cart-toast-close';
        cerrar.setAttribute('aria-label', 'Cerrar');
        cerrar.innerHTML = '&times;';
        cerrar.addEventListener('click', function () { cerrarAviso(aviso); });

        var barra = document.createElement('div');
        barra.className = 'mb-cart-toast-bar';
        barra.style.animationDuration = (datos.ok ? 4.2 : 5.2) + 's';

        aviso.appendChild(foto);
        aviso.appendChild(cuerpo);
        aviso.appendChild(cerrar);
        aviso.appendChild(barra);
        document.body.appendChild(aviso);

        // Pequeño reflow para que la entrada se anime.
        void aviso.offsetWidth;
        aviso.classList.add('mb-cart-toast-in');

        var temporizador = window.setTimeout(function () { cerrarAviso(aviso); }, datos.ok ? 4200 : 5200);
        aviso.addEventListener('mouseenter', function () { window.clearTimeout(temporizador); });
        aviso.addEventListener('mouseleave', function () {
            temporizador = window.setTimeout(function () { cerrarAviso(aviso); }, 1800);
        });
    }

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form || !form.matches || !form.matches('form[action*="/addtocart"]')) return;
        if (!window.fetch || !window.FormData) return; // sin fetch, POST normal
        if (typeof form.reportValidity === 'function' && !form.reportValidity()) return;

        e.preventDefault();
        var btn = e.submitter || form.querySelector('button[type="submit"], button:not([type])');
        var origen = btn || form;
        var datos = datosProducto(origen);
        var htmlOriginal = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>Agregando…';
        }

        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' },
            credentials: 'same-origin'
        })
            .then(function (r) {
                return r.json().then(function (body) { return { ok: r.ok, body: body || {} }; });
            })
            .then(function (res) {
                var body = res.body;
                if (body.ok) {
                    pulsoBolsa();
                    actualizarContador(body.cantidad || 0);
                    mostrarAviso({
                        ok: true,
                        titulo: 'Agregado al carrito',
                        mensaje: body.categoria === 'info' ? body.mensaje : (datos.nombre || 'Producto agregado'),
                        imagen: datos.imagen
                    });
                    if (btn) {
                        btn.innerHTML = '<i class="bi bi-check2 me-1"></i>Agregado';
                        window.setTimeout(function () {
                            btn.disabled = false;
                            btn.innerHTML = htmlOriginal;
                        }, 1400);
                    }
                } else {
                    if (btn) { btn.disabled = false; btn.innerHTML = htmlOriginal; }
                    mostrarAviso({
                        ok: false,
                        titulo: 'No se agregó',
                        mensaje: body.mensaje || 'No se pudo agregar al carrito',
                        imagen: datos.imagen
                    });
                }
            })
            .catch(function () {
                if (btn) { btn.disabled = false; btn.innerHTML = htmlOriginal; }
                mostrarAviso({
                    ok: false,
                    titulo: 'No se agregó',
                    mensaje: 'No se pudo agregar al carrito. Inténtalo de nuevo.',
                    imagen: datos.imagen
                });
            });
    });
})();
