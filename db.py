
import mysql.connector

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="truckscan",
            port=3306
        )

        return connection

    except mysql.connector.Error as error:
        print("Koneksi database gagal:", error)
        return None

