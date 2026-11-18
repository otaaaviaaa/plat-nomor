
import cv2
import numpy as np
import easyocr
import re
import csv
import io

from flask import (
     Flask, render_template, request,
    redirect, url_for, flash, jsonify, Response
)

from db import get_db_connection
from datetime import datetime
from zoneinfo import ZoneInfo


app = Flask(__name__)
app.secret_key = "truckscan_secret_key"

reader = None


def waktu_sekarang():
    return datetime.now(ZoneInfo("Asia/Jakarta"))


def format_plat(teks):
    teks = re.sub(r"[^A-Z0-9]", "", teks.upper())

    pola = re.fullmatch(
        r"([A-Z]{1,2})([0-9]{1,4})([A-Z]{0,3})",
        teks
    )

    if not pola:
        return None

    depan, angka, belakang = pola.groups()

    if belakang:
        return f"{depan} {angka} {belakang}"

    return f"{depan} {angka}"


def cari_plat(gambar):
    global reader

    if reader is None:
        print("Memuat model EasyOCR...")
        reader = easyocr.Reader(["en"], gpu=False)
        print("EasyOCR siap digunakan.")

    abu = cv2.cvtColor(gambar, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(
        clipLimit=2.5,
        tileGridSize=(8, 8)
    )

    gambar_kontras = clahe.apply(abu)

    gambar_tajam = cv2.addWeighted(
        gambar_kontras,
        1.5,
        cv2.GaussianBlur(gambar_kontras, (0, 0), 3),
        -0.5,
        0
    )

    gambar_biner = cv2.adaptiveThreshold(
        gambar_kontras,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )

    variasi_gambar = [
        gambar,
        gambar_kontras,
        gambar_tajam,
        gambar_biner
    ]

    pola = re.compile(
        r"[A-Z]{1,2}[0-9]{1,4}[A-Z]{0,3}"
    )

    for gambar_uji in variasi_gambar:

        hasil = reader.readtext(
            gambar_uji,
            detail=1,
            paragraph=False,
            allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            text_threshold=0.55,
            low_text=0.30,
            link_threshold=0.30,
            mag_ratio=1.5
        )

        for item in hasil:
            teks = item[1].upper().strip()
            teks = re.sub(r"[^A-Z0-9]", "", teks)

            if item[2] < 0.15:
                continue

            cocok = pola.search(teks)

            if cocok:
                plat = format_plat(cocok.group(0))

                if plat:
                    return plat

        teks_gabungan = "".join(
            re.sub(r"[^A-Z0-9]", "", item[1].upper())
            for item in hasil
            if item[2] >= 0.15
        )

        cocok = pola.search(teks_gabungan)

        if cocok:
            plat = format_plat(cocok.group(0))

            if plat:
                return plat

    return None


def cek_kendaraan(plat):
    connection = get_db_connection()

    if connection is None:
        raise Exception("Database tidak terhubung.")

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id_kendaraan, plat_nomor
            FROM kendaraan
            WHERE REPLACE(UPPER(plat_nomor), ' ', '') = %s
        """, (plat.replace(" ", ""),))

        return cursor.fetchone()

    finally:
        connection.close()


# DASHBOARD
@app.route("/")
def dashboard():
    connection = get_db_connection()

    if connection is None:
        return "Database tidak terhubung."

    try:
        cursor = connection.cursor(dictionary=True)
        sekarang = waktu_sekarang()

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM riwayat_masuk
            WHERE tanggal_masuk = %s
        """, (sekarang.date(),))

        jumlah_masuk_hari_ini = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM kendaraan
        """)

        total_kendaraan = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT
                k.plat_nomor,
                r.tanggal_masuk,
                r.jam_masuk
            FROM riwayat_masuk r
            JOIN kendaraan k
                ON r.id_kendaraan = k.id_kendaraan
            ORDER BY r.id_riwayat DESC
            LIMIT 5
        """)

        riwayat_terbaru = cursor.fetchall()

        return render_template(
            "dashboard.html",
            jumlah_masuk_hari_ini=jumlah_masuk_hari_ini,
            total_kendaraan=total_kendaraan,
            riwayat_terbaru=riwayat_terbaru
        )

    except Exception as error:
        return f"Gagal membuka dashboard: {error}"

    finally:
        connection.close()


# SCAN
@app.route("/scan", methods=["GET", "POST"])
def scan():

    if request.method == "GET":
        return render_template("scan.html")

    plat_nomor = request.form.get(
        "plat_nomor", ""
    ).strip().upper()

    plat_nomor = format_plat(plat_nomor)

    if not plat_nomor:
        flash("Format plat nomor tidak sesuai.", "danger")
        return redirect(url_for("scan"))

    connection = get_db_connection()

    if connection is None:
        return "Database tidak terhubung."

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id_kendaraan, plat_nomor
            FROM kendaraan
            WHERE REPLACE(UPPER(plat_nomor), ' ', '') = %s
        """, (plat_nomor.replace(" ", ""),))

        kendaraan = cursor.fetchone()

        if kendaraan is None:
            return redirect(
                url_for("tambah_kendaraan", plat=plat_nomor)
            )

        sekarang = waktu_sekarang()

        cursor.execute("""
            INSERT INTO riwayat_masuk
            (id_kendaraan, tanggal_masuk, jam_masuk)
            VALUES (%s, %s, %s)
        """, (
            kendaraan["id_kendaraan"],
            sekarang.date(),
            sekarang.time().replace(microsecond=0)
        ))

        connection.commit()

        flash(
            f"Kendaraan {kendaraan['plat_nomor']} berhasil dicatat masuk.",
            "success"
        )

        return redirect(url_for("scan"))

    except Exception as error:
        connection.rollback()
        return f"Gagal mencatat kendaraan masuk: {error}"

    finally:
        if connection.is_connected():
            connection.close()


# TAMBAH KENDARAAN
@app.route("/tambah-kendaraan", methods=["GET", "POST"])
def tambah_kendaraan():

    if request.method == "GET":
        plat = request.args.get("plat", "").strip().upper()

        return render_template(
            "tambah_kendaraan.html",
            plat=plat
        )

    plat_nomor = request.form.get(
        "plat_nomor", ""
    ).strip().upper()

    plat_nomor = format_plat(plat_nomor)

    if not plat_nomor:
        flash("Masukkan plat nomor dengan format yang benar.", "danger")
        return redirect(url_for("tambah_kendaraan"))

    connection = get_db_connection()

    if connection is None:
        return "Database tidak terhubung."

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id_kendaraan, plat_nomor
            FROM kendaraan
            WHERE REPLACE(UPPER(plat_nomor), ' ', '') = %s
        """, (plat_nomor.replace(" ", ""),))

        kendaraan = cursor.fetchone()

        if kendaraan:
            id_kendaraan = kendaraan["id_kendaraan"]
            plat_nomor = kendaraan["plat_nomor"]

        else:
            cursor.execute("""
                INSERT INTO kendaraan (plat_nomor)
                VALUES (%s)
            """, (plat_nomor,))

            id_kendaraan = cursor.lastrowid

        sekarang = waktu_sekarang()

        cursor.execute("""
            INSERT INTO riwayat_masuk
            (id_kendaraan, tanggal_masuk, jam_masuk)
            VALUES (%s, %s, %s)
        """, (
            id_kendaraan,
            sekarang.date(),
            sekarang.time().replace(microsecond=0)
        ))

        connection.commit()

        flash(
            f"Kendaraan {plat_nomor} berhasil didaftarkan dan dicatat masuk.",
            "success"
        )

        return redirect(url_for("scan"))

    except Exception as error:
        connection.rollback()
        return f"Gagal menyimpan kendaraan: {error}"

    finally:
        if connection.is_connected():
            connection.close()


# PROSES SCAN GAMBAR
@app.route("/proses-scan", methods=["POST"])
def proses_scan():

    if "image" not in request.files:
        return jsonify({
            "error": "Gambar kamera tidak ditemukan."
        }), 400

    try:
        file = request.files["image"]
        image_bytes = file.read()

        if not image_bytes:
            return jsonify({
                "error": "Gambar kosong."
            }), 400

        image_array = np.frombuffer(
            image_bytes,
            np.uint8
        )

        gambar = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

        if gambar is None:
            return jsonify({
                "error": "Gambar tidak dapat dibaca."
            }), 400

        plat = cari_plat(gambar)

        if not plat:
            return jsonify({
                "terdeteksi": False,
                "pesan": "Plat nomor tidak ditemukan."
            })

        kendaraan = cek_kendaraan(plat)

        if kendaraan:
            return jsonify({
                "terdeteksi": True,
                "terdaftar": True,
                "plat_nomor": kendaraan["plat_nomor"],
                "pesan": "Plat kendaraan ditemukan."
            })

        return jsonify({
            "terdeteksi": True,
            "terdaftar": False,
            "plat_nomor": plat,
            "pesan": "Plat kendaraan belum terdaftar."
        })

    except Exception as error:
        print("Kesalahan proses scan:", error)

        return jsonify({
            "error": str(error)
        }), 500


# RIWAYAT KENDARAAN

# RIWAYAT KENDARAAN

@app.route("/riwayat")
def riwayat():
    connection = get_db_connection()

    if connection is None:
        return "Database tidak terhubung."

    try:
        cursor = connection.cursor(dictionary=True)
        sekarang = waktu_sekarang()

        bulan = request.args.get("bulan", sekarang.month, type=int)
        tahun = request.args.get("tahun", sekarang.year, type=int)

        if bulan < 1 or bulan > 12:
            bulan = sekarang.month

        if tahun < 2000 or tahun > 2100:
            tahun = sekarang.year

        nama_bulan = [
            "Januari", "Februari", "Maret", "April",
            "Mei", "Juni", "Juli", "Agustus",
            "September", "Oktober", "November", "Desember"
        ]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM riwayat_masuk
        """)

        total_riwayat = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM riwayat_masuk
            WHERE tanggal_masuk = %s
        """, (sekarang.date(),))

        jumlah_masuk_hari_ini = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM riwayat_masuk
            WHERE MONTH(tanggal_masuk) = %s
            AND YEAR(tanggal_masuk) = %s
        """, (bulan, tahun))

        jumlah_masuk_bulan = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT
                r.id_riwayat,
                k.plat_nomor,
                r.tanggal_masuk,
                r.jam_masuk
            FROM riwayat_masuk r
            JOIN kendaraan k
                ON r.id_kendaraan = k.id_kendaraan
            WHERE MONTH(r.tanggal_masuk) = %s
            AND YEAR(r.tanggal_masuk) = %s
            ORDER BY r.tanggal_masuk DESC, r.jam_masuk DESC
        """, (bulan, tahun))

        data_riwayat = cursor.fetchall()

        cursor.execute("""
            SELECT DISTINCT YEAR(tanggal_masuk) AS tahun
            FROM riwayat_masuk
            ORDER BY tahun DESC
        """)

        tahun_list = [data["tahun"] for data in cursor.fetchall()]

        if tahun not in tahun_list:
            tahun_list.append(tahun)

        tahun_list.sort(reverse=True)

        bulan_list = [
            {"angka": i, "nama": nama_bulan[i - 1]}
            for i in range(1, 13)
        ]

        return render_template(
            "riwayat.html",
            data_riwayat=data_riwayat,
            total_riwayat=total_riwayat,
            jumlah_masuk_hari_ini=jumlah_masuk_hari_ini,
            jumlah_masuk_bulan=jumlah_masuk_bulan,
            bulan=bulan,
            tahun=tahun,
            nama_bulan=nama_bulan[bulan - 1],
            bulan_list=bulan_list,
            tahun_list=tahun_list
        )

    except Exception as error:
        return f"Gagal menampilkan riwayat: {error}"

    finally:
        connection.close()


# EKSPOR RIWAYAT CSV

@app.route("/export-csv")
def export_csv():
    connection = get_db_connection()

    if connection is None:
        return "Database tidak terhubung."

    try:
        cursor = connection.cursor(dictionary=True)

        semua = request.args.get("semua", "0")
        sekarang = waktu_sekarang()

        bulan = request.args.get("bulan", sekarang.month, type=int)
        tahun = request.args.get("tahun", sekarang.year, type=int)

        nama_bulan = [
            "Januari", "Februari", "Maret", "April",
            "Mei", "Juni", "Juli", "Agustus",
            "September", "Oktober", "November", "Desember"
        ]

        if semua == "1":
            cursor.execute("""
                SELECT
                    k.plat_nomor,
                    r.tanggal_masuk,
                    r.jam_masuk
                FROM riwayat_masuk r
                JOIN kendaraan k
                    ON r.id_kendaraan = k.id_kendaraan
                ORDER BY r.tanggal_masuk ASC, r.jam_masuk ASC
            """)

            nama_file = "Riwayat_Seluruh_Kendaraan.csv"

        else:
            if bulan < 1 or bulan > 12:
                return "Bulan tidak valid."

            if tahun < 2000 or tahun > 2100:
                return "Tahun tidak valid."

            cursor.execute("""
                SELECT
                    k.plat_nomor,
                    r.tanggal_masuk,
                    r.jam_masuk
                FROM riwayat_masuk r
                JOIN kendaraan k
                    ON r.id_kendaraan = k.id_kendaraan
                WHERE MONTH(r.tanggal_masuk) = %s
                AND YEAR(r.tanggal_masuk) = %s
                ORDER BY r.tanggal_masuk ASC, r.jam_masuk ASC
            """, (bulan, tahun))

            nama_file = (
                f"Riwayat_{nama_bulan[bulan - 1]}_{tahun}.csv"
            )

        data = cursor.fetchall()

        output = io.StringIO()
        output.write("\ufeff")

        penulis = csv.writer(output)

        penulis.writerow([
            "Plat Nomor",
            "Tanggal Masuk",
            "Jam Masuk"
        ])

        for baris in data:
            penulis.writerow([
                baris["plat_nomor"],
                baris["tanggal_masuk"],
                baris["jam_masuk"]
            ])

        return Response(
            output.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename={nama_file}"
            }
        )

    except Exception as error:
        return f"Gagal mengekspor CSV: {error}"

    finally:
        connection.close()



# IMPORT CSV
@app.route("/import-csv", methods=["POST"])
def import_csv():

    file = request.files.get("file_csv")

    if not file or file.filename == "":
        flash("Pilih file CSV terlebih dahulu.", "danger")
        return redirect(url_for("riwayat"))

    if not file.filename.lower().endswith(".csv"):
        flash("File harus berformat CSV.", "danger")
        return redirect(url_for("riwayat"))

    connection = get_db_connection()

    if connection is None:
        flash("Database tidak terhubung.", "danger")
        return redirect(url_for("riwayat"))

    berhasil = 0
    dilewati = 0
    gagal = 0

    try:
        isi_file = file.stream.read().decode("utf-8-sig")
        pembaca = csv.DictReader(io.StringIO(isi_file))

        if not pembaca.fieldnames:
            flash("File CSV kosong atau tidak memiliki judul kolom.", "danger")
            return redirect(url_for("riwayat"))

        kolom = {
            nama.strip().lower(): nama
            for nama in pembaca.fieldnames
            if nama
        }

        kolom_wajib = [
            "plat nomor",
            "tanggal masuk",
            "jam masuk"
        ]

        if not all(nama in kolom for nama in kolom_wajib):
            flash(
                "Format CSV salah. Kolom wajib: Plat Nomor, Tanggal Masuk, Jam Masuk.",
                "danger"
            )
            return redirect(url_for("riwayat"))

        cursor = connection.cursor(dictionary=True)

        for baris in pembaca:

            try:
                plat_asli = baris.get(kolom["plat nomor"], "")
                tanggal_asli = baris.get(kolom["tanggal masuk"], "")
                jam_asli = baris.get(kolom["jam masuk"], "")

                plat = format_plat(plat_asli.strip())

                if not plat:
                    gagal += 1
                    continue

                tanggal = datetime.strptime(
                    tanggal_asli.strip(), "%Y-%m-%d"
                ).date()

                jam_teks = jam_asli.strip()

                try:
                    jam = datetime.strptime(
                        jam_teks, "%H:%M:%S"
                    ).time()
                except ValueError:
                    jam = datetime.strptime(
                        jam_teks, "%H:%M"
                    ).time()

                cursor.execute("""
                    SELECT id_kendaraan, plat_nomor
                    FROM kendaraan
                    WHERE REPLACE(UPPER(plat_nomor), ' ', '') = %s
                """, (plat.replace(" ", ""),))

                kendaraan = cursor.fetchone()

                if kendaraan:
                    id_kendaraan = kendaraan["id_kendaraan"]

                else:
                    cursor.execute("""
                        INSERT INTO kendaraan (plat_nomor)
                        VALUES (%s)
                    """, (plat,))

                    id_kendaraan = cursor.lastrowid

                cursor.execute("""
                    SELECT id_riwayat
                    FROM riwayat_masuk
                    WHERE id_kendaraan = %s
                    AND tanggal_masuk = %s
                    AND jam_masuk = %s
                    LIMIT 1
                """, (id_kendaraan, tanggal, jam))

                riwayat_sama = cursor.fetchone()

                if riwayat_sama:
                    dilewati += 1
                    continue

                cursor.execute("""
                    INSERT INTO riwayat_masuk
                    (id_kendaraan, tanggal_masuk, jam_masuk)
                    VALUES (%s, %s, %s)
                """, (id_kendaraan, tanggal, jam))

                berhasil += 1

            except (ValueError, TypeError, AttributeError):
                gagal += 1

        connection.commit()

        flash(
            f"Import selesai! Berhasil: {berhasil}, "
            f"Dilewati: {dilewati}, Gagal: {gagal}.",
            "success" if gagal == 0 else "danger"
        )

    except Exception as error:
        connection.rollback()
        flash(f"Import CSV gagal: {error}", "danger")

    finally:
        connection.close()

    return redirect(url_for("riwayat"))



if __name__ == "__main__":
    app.run(debug=True)
