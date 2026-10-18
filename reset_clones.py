import sqlite3
conn = sqlite3.connect('/app/data/data.db')
conn.execute('UPDATE users SET voice_id = NULL')
conn.commit()
print('Клоны сброшены у всех')