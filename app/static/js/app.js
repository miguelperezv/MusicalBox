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

// <input data-autocomplete="/url"> : llena un <datalist> con el JSON (lista de textos) de esa URL
function mbAutocomplete(root) {
    (root || document).querySelectorAll('input[data-autocomplete]').forEach(function (input) {
        if (input.dataset.autocompleteReady) return;
        input.dataset.autocompleteReady = '1';
        var list = document.createElement('datalist');
        list.id = (input.id || input.name) + '-opciones';
        input.setAttribute('list', list.id);
        input.setAttribute('autocomplete', 'off');
        input.after(list);
        fetch(input.dataset.autocomplete)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                (data || []).forEach(function (texto) {
                    var o = document.createElement('option');
                    o.value = texto;
                    list.appendChild(o);
                });
            });
    });
}

// panel admin: enlaces con data-load cargan su contenido en #admin-content sin recargar la página
function mbAdminLoader() {
    var content = document.getElementById('admin-content');
    if (!content) return;
    document.querySelectorAll('[data-load]').forEach(function (link) {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelectorAll('.mb-sidebar .nav-link').forEach(function (l) { l.classList.remove('active'); });
            link.classList.add('active');
            content.innerHTML = '<div class="mb-loading"><div class="spinner-border" role="status"></div></div>';
            $(content).load(link.dataset.load, function () { mbAutocomplete(content); });
            var sidebar = bootstrap.Offcanvas.getInstance(document.getElementById('adminSidebar'));
            if (sidebar) sidebar.hide();
        });
    });
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
    fetch(link.dataset.quickview).then(function (r) { return r.text(); }).then(function (html) {
        body.innerHTML = html;
        //los embeds de redes necesitan volver a procesarse al insertarse
        if (window.instgrm) window.instgrm.Embeds.process();
        if (window.mbAutocomplete) mbAutocomplete(body);
        body.querySelectorAll('script[src]').forEach(function (s) {
            var n = document.createElement('script'); n.src = s.src; n.async = true; document.body.appendChild(n);
        });
    });
});

//nuevo lanzamiento: búsqueda de Spotify (el formulario llega por data-load o por modal)
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
        document.getElementById('spresultados').innerHTML = '<div class="form-text">Usando <b>' + escapar(album.nombre) + '</b> de Spotify. Revisa los datos antes de crear.</div>';
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
                if (!d.items.length) { resultado.innerHTML = '<div class="text-body-secondary small">Sin resultados en Spotify.</div>'; return; }
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
            .catch(function () { resultado.innerHTML = '<div class="text-danger small">Error de red al consultar Spotify.</div>'; });
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

//órdenes: chips para filtrar la lista por estado (delegado: también en secciones data-load)
(function () {
    function aplicar(filtro, chip) {
        document.querySelectorAll('.chip-filtro').forEach(function (b) {
            b.classList.toggle('active', b === chip);
            b.classList.toggle('btn-primary', b === chip);
            b.classList.toggle('btn-outline-secondary', b !== chip);
        });
        var panel = chip.closest('#admin-content') || document;
        var tabla = panel.querySelector('table');
        var filas = tabla.querySelectorAll('tr[data-estado]');
        var visibles = 0;
        filas.forEach(function (tr) {
            var ok = filtro === 'todas'
                || (filtro === 'pendientes' && tr.dataset.estado === 'PENDIENTE')
                || (filtro !== 'todas' && filtro !== 'pendientes' && tr.dataset.estado === 'PAGADO' && tr.dataset.envio === filtro);
            tr.classList.toggle('d-none', !ok);
            if (ok) visibles++;
        });
        var vacio = tabla.querySelector('.fila-sin-resultado');
        if (vacio) vacio.classList.toggle('d-none', visibles > 0);
    }
    document.addEventListener('click', function (e) {
        var chip = e.target.closest && e.target.closest('.chip-filtro');
        if (chip) aplicar(chip.dataset.filtro, chip);
    });
    window.aplicarFiltroOrdenes = function (row) {
        //al cambiar el estado de envío, la fila pasa al grupo que le toca
        var panel = row.closest('#admin-content') || document;
        var chip = panel.querySelector('.chip-filtro.active');
        if (chip && chip.dataset.filtro !== 'todas') {
            var env = row.dataset.envio, esta = row.dataset.estado;
            var sigue = chip.dataset.filtro === 'pendientes' ? esta === 'PENDIENTE' : (esta === 'PAGADO' && env === chip.dataset.filtro);
            if (!sigue) aplicar('todas', panel.querySelector('.chip-filtro[data-filtro="todas"]'));
        }
    };
})();

//lanzamientos: portada, post y Spotify por un campo en modal (delegado: sección y modal)
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
