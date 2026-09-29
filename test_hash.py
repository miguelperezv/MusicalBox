from app.store.seguridad import check_password
import sqlite3

conn = sqlite3.connect('instance/musicalbox.sqlite3')
cursor = conn.execute('SELECT pwd_usuario FROM usuario WHERE email_usuario = "admin@gmail.com"')
hash_val = cursor.fetchone()[0]
print('Hash from DB:', repr(hash_val))
print('Check result:', check_password('admin123', hash_val))
conn.close()