
document.addEventListener("DOMContentLoaded", function () {

    // =========================
    // TANGGAL OTOMATIS
    // =========================

    const dateElement = document.getElementById("currentDate");

    function updateDate() {

        if (!dateElement) return;

        const now = new Date();

        dateElement.textContent = now.toLocaleDateString("id-ID", {
            day: "numeric",
            month: "long",
            year: "numeric"
        });

    }

    updateDate();


    // =========================
    // SIDEBAR HAMBURGER
    // =========================

    const appContainer = document.getElementById("appContainer");
    const sidebarToggle = document.getElementById("sidebarToggle");

    if (!appContainer || !sidebarToggle) return;


    // Status sidebar sebelumnya
    const savedSidebarState = localStorage.getItem(
        "truckscanSidebarCollapsed"
    );


    // Atur tampilan awal
    if (window.innerWidth > 750 && savedSidebarState === "true") {

        appContainer.classList.add("sidebar-collapsed");

    }


    // Klik hamburger
    sidebarToggle.addEventListener("click", function () {

        appContainer.classList.toggle("sidebar-collapsed");

        const isCollapsed = appContainer.classList.contains(
            "sidebar-collapsed"
        );

        localStorage.setItem(
            "truckscanSidebarCollapsed",
            isCollapsed
        );

        sidebarToggle.setAttribute(
            "aria-label",
            isCollapsed ? "Tutup sidebar" : "Buka sidebar"
        );

    });

});
