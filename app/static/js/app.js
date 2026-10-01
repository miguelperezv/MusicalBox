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
        body.querySelectorAll('script[src]').forEach(function (s) {
            var n = document.createElement('script'); n.src = s.src; n.async = true; document.body.appendChild(n);
        });
    });
});
