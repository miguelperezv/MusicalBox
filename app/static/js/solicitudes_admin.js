// Filtro de chips para solicitudes
document.addEventListener('DOMContentLoaded', function() {
    var grupo = document.querySelector('[data-grupo-solicitudes]');
    if (!grupo) return;
    
    function aplicarFiltro(filtro) {
        document.querySelectorAll('[data-grupo-solicitudes] .chip-filtro').forEach(function (b) {
            var activo = b.dataset.filtro === filtro;
            b.classList.toggle('active', activo);
            b.classList.toggle('btn-primary', activo && filtro === 'por_cotizar');
            b.classList.toggle('btn-outline-secondary', !activo || filtro !== 'por_cotizar');
        });
        
        Object.keys({por_cotizar:1, otras:1}).forEach(function (key) {
            var sec = document.getElementById('seccion-' + (key === 'por_cotizar' ? 'por-cotizar' : key));
            if (!sec) return;
            var mostrar = (filtro === 'todas') || (filtro === key);
            if (mostrar) sec.style.display = ''; else sec.style.display = 'none';
        });
    }
    
    document.querySelectorAll('[data-grupo-solicitudes] .chip-filtro').forEach(function (chip) {
        chip.addEventListener('click', function () {
            grupo.querySelectorAll('.chip-filtro').forEach(function (b) {
                b.classList.remove('active', 'btn-primary');
                b.classList.add('btn-outline-secondary');
            });
            this.classList.add('active');
            if (this.dataset.filtro === 'por_cotizar') this.classList.add('btn-primary');
            this.classList.remove('btn-outline-secondary');
            aplicarFiltro(this.dataset.filtro);
        });
    });
    
    var buscador = document.getElementById('filtro-solicitudes');
    if (buscador) {
        buscador.addEventListener('input', function () {
            var q = this.value.trim().toLowerCase();
            document.querySelectorAll('#tbody-por-cotizar tr, #tbody-otras tr').forEach(function (tr) {
                if (tr.querySelector('td[colspan]')) return;
                var ok = tr.textContent.toLowerCase().indexOf(q) !== -1;
                tr.classList.toggle('d-none', !ok);
            });
        });
    }
    
    // Eliminar solicitud
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-eliminar-sol]');
        if (!btn) return;
        if (!confirm('¿Eliminar esta solicitud? No se puede deshacer.')) return;
        fetch(btn.dataset.url, { method: 'POST' })
            .then(function (r) { 
                if (r.ok) btn.closest('tr').remove(); 
                else return r.json().then(function (e) { throw new Error(e.error || 'Error'); }); 
            })
            .catch(function (e) { alert(e.message); });
    });
});
