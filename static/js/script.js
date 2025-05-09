// script.js (principal)

document.addEventListener('DOMContentLoaded', function () {
    console.log("Sistema de Laticínios - Frontend JS Carregado.");

    // Exemplo: tornar linhas da tabela clicáveis (se necessário no futuro)
    // const tableRows = document.querySelectorAll('table tbody tr');
    // tableRows.forEach(row => {
    //     row.addEventListener('click', () => {
    //         const href = row.dataset.href;
    //         if (href) {
    //             window.location.href = href;
    //         }
    //     });
    // });

    // Fechar alertas automaticamente após alguns segundos (opcional)
    const autoDismissAlerts = document.querySelectorAll('.alert-dismissible.fade.show');
    autoDismissAlerts.forEach(function(alert) {
        // Apenas para alertas de sucesso ou informação
        if (alert.classList.contains('alert-success') || alert.classList.contains('alert-info')) {
            setTimeout(function() {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }, 5000); // Fecha após 5 segundos
        }
    });

    // Scripts específicos de páginas (como o de area_detalhes.html)
    // já estão no bloco `scripts_extra` dos respectivos templates.
});