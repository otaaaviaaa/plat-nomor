
document.addEventListener("DOMContentLoaded", function () {

    const appContainer = document.getElementById("appContainer");
    const sidebarToggle = document.getElementById("sidebarToggle");
    const searchInput = document.getElementById("searchInput");
    const clearSearch = document.getElementById("clearSearch");
    const historyTable = document.getElementById("historyTable");
    const noSearchResult = document.getElementById("noSearchResult");
    const tableCount = document.getElementById("tableCount");
    const currentDate = document.getElementById("currentDate");

    // TANGGAL HARI INI
    if (currentDate) {
        currentDate.textContent = new Date().toLocaleDateString("id-ID", {
            day: "numeric",
            month: "long",
            year: "numeric"
        });
    }

    // SIDEBAR
    if (sidebarToggle && appContainer) {

        const mobileView = () => window.innerWidth <= 700;

        if (!mobileView()) {
            const savedState = localStorage.getItem("truckscanSidebarCollapsed");

            if (savedState === "true") {
                appContainer.classList.add("sidebar-collapsed");
            }
        }

        sidebarToggle.addEventListener("click", function () {

            if (mobileView()) {
                appContainer.classList.toggle("mobile-sidebar-open");
            } else {
                appContainer.classList.toggle("sidebar-collapsed");

                localStorage.setItem(
                    "truckscanSidebarCollapsed",
                    appContainer.classList.contains("sidebar-collapsed")
                );
            }
        });

        window.addEventListener("resize", function () {
            if (!mobileView()) {
                appContainer.classList.remove("mobile-sidebar-open");

                const savedState = localStorage.getItem("truckscanSidebarCollapsed");

                if (savedState === "true") {
                    appContainer.classList.add("sidebar-collapsed");
                } else {
                    appContainer.classList.remove("sidebar-collapsed");
                }
            } else {
                appContainer.classList.remove("sidebar-collapsed");
            }
        });
    }

    // PENCARIAN PLAT NOMOR
    if (searchInput && historyTable) {

        const rows = Array.from(
            historyTable.querySelectorAll("tbody tr")
        ).filter(row => row.id !== "noSearchResult");

        function searchHistory() {

            const keyword = searchInput.value
                .toLowerCase()
                .trim();

            let visibleCount = 0;

            rows.forEach(function (row) {

                const plate = row.querySelector(".plate-number");

                if (!plate) {
                    return;
                }

                const plateText = plate.textContent
                    .toLowerCase()
                    .trim();

                const matched = plateText.includes(keyword);

                row.style.display = matched ? "" : "none";

                if (matched) {
                    visibleCount++;
                }
            });

            if (noSearchResult) {
                noSearchResult.style.display =
                    keyword !== "" && visibleCount === 0 ? "" : "none";
            }

            if (tableCount) {
                tableCount.textContent =
                    keyword === ""
                        ? `Menampilkan ${visibleCount} data kendaraan`
                        : `Menampilkan ${visibleCount} hasil pencarian`;
            }

            if (clearSearch) {
                clearSearch.style.display =
                    keyword !== "" ? "block" : "none";
            }
        }

        searchInput.addEventListener("input", searchHistory);

        if (clearSearch) {
            clearSearch.addEventListener("click", function () {
                searchInput.value = "";
                searchHistory();
                searchInput.focus();
            });
        }
    }

    // NOTIFIKASI
    const notifications = document.querySelectorAll(".notification");

    notifications.forEach(function (notification) {

        setTimeout(function () {
            notification.style.transition = "opacity 0.5s ease, transform 0.5s ease";
            notification.style.opacity = "0";
            notification.style.transform = "translateY(-8px)";

            setTimeout(function () {
                notification.remove();
            }, 500);

        }, 4500);
    });

});
