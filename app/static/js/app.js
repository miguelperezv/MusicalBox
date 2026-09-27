/* Musical Box — utilidades de la interfaz */

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
        setTimeout(function () { bootstrap.Alert.getOrCreateInstance(a).close(); }, 6000);
    });
});
