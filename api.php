<?php
header("Content-Type: application/json");
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST");
header("Access-Control-Allow-Headers: Content-Type");

$host = "localhost";
$user = "root";
$pass = "";
$dbname = "tambang_pasir";

$conn = new mysqli($host, $user, $pass, $dbname);
if ($conn->connect_error) {
    echo json_encode(["status" => "error", "message" => "Koneksi database gagal"]);
    exit;
}

$action = $_GET['action'] ?? '';

// API 1: Scan / Cek Plat Nomor Truk Masuk
if ($action === 'scan_plat') {
    $plat = strtoupper(trim($_GET['plat'] ?? ''));
    if (empty($plat)) {
        echo json_encode(["status" => "error", "message" => "Plat nomor kosong"]);
        exit;
    }

    $stmt = $conn->prepare("SELECT * FROM kendaraan WHERE plat_nomor = ?");
    $stmt->bind_param("s", $plat);
    $stmt->execute();
    $result = $stmt->get_result();

    if ($row = $result->fetch_assoc()) {
        // Jika plat ditemukan, otomatis catat masuk ke riwayat
        $stmt_log = $conn->prepare("INSERT INTO riwayat_masuk (plat_nomor, jenis_kendaraan, tipe_scan) VALUES (?, ?, 'IoT / Camera')");
        $stmt_log->bind_param("ss", $row['plat_nomor'], $row['jenis_kendaraan']);
        $stmt_log->execute();

        echo json_encode([
            "status" => "found",
            "data" => [
                "plat_nomor" => $row['plat_nomor'],
                "jenis_kendaraan" => $row['jenis_kendaraan'],
                "waktu_masuk" => date("Y-m-d H:i:s")
            ]
        ]);
    } else {
        // Jika plat belum terdaftar
        echo json_encode(["status" => "not_found", "plat_nomor" => $plat]);
    }
}

// API 2: Tambah Kendaraan Baru (jika belum ada) + Otomatis Catat Masuk
if ($action === 'tambah_kendaraan') {
    $data = json_decode(file_get_contents("php://input"), true);
    $plat = strtoupper(trim($data['plat_nomor'] ?? ''));
    $jenis = trim($data['jenis_kendaraan'] ?? '');

    if (!$plat || !$jenis) {
        echo json_encode(["status" => "error", "message" => "Data tidak lengkap"]);
        exit;
    }

    $stmt = $conn->prepare("INSERT INTO kendaraan (plat_nomor, jenis_kendaraan) VALUES (?, ?)");
    $stmt->bind_param("ss", $plat, $jenis);
    
    if ($stmt->execute()) {
        $stmt_log = $conn->prepare("INSERT INTO riwayat_masuk (plat_nomor, jenis_kendaraan, tipe_scan) VALUES (?, ?, 'Manual')");
        $stmt_log->bind_param("ss", $plat, $jenis);
        $stmt_log->execute();

        echo json_encode(["status" => "success", "message" => "Data berhasil disimpan & dicatat masuk"]);
    } else {
        echo json_encode(["status" => "error", "message" => "Gagal menyimpan data"]);
    }
}

// API 3: Ambil Data Riwayat Masuk
if ($action === 'get_riwayat') {
    $res = $conn->query("SELECT * FROM riwayat_masuk ORDER BY waktu_masuk DESC LIMIT 100");
    $data = [];
    while ($row = $res->fetch_assoc()) {
        $data[] = $row;
    }
    echo json_encode(["status" => "success", "data" => $data]);
}
?>