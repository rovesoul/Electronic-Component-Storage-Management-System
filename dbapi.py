import sqlite3,os
# -------- 数据库 --------
def init_db():
    conn = sqlite3.connect('components.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            model TEXT,
              package TEXT,
            quantity INTEGER,
            total_price REAL,
            unit_price REAL,
            note TEXT,
            img_path TEXT,
            doc_path TEXT,
            cloud_link TEXT
            
        )
    ''')
    conn.commit()
    conn.close()

def get_component_by_name_model(name, model,package):
    conn = sqlite3.connect('components.db')
    c = conn.cursor()
    c.execute('SELECT * FROM components WHERE name=? AND model=? AND package=?', (name, model, package))
    row = c.fetchone()
    conn.close()
    return row

def add_or_update_component(name, model, package, quantity, total_price, note, img_path, doc_path, cloud_link):
    conn = sqlite3.connect('components.db')
    c = conn.cursor()
    c.execute('SELECT id, quantity, total_price FROM components WHERE name=? AND model=? AND package=?', (name, model, package))
    res = c.fetchone()
    if res:
        cid, old_qty, old_total = res
        new_qty = old_qty + quantity
        new_total = (old_total if old_total else 0) + total_price
        unit_price = new_total / new_qty if new_qty else 0
        c.execute('''
            UPDATE components SET 
                quantity=?, 
                total_price=?, 
                unit_price=?, 
                note=?, 
                img_path=?, 
                doc_path=?,
                cloud_link=?,
                package=?
             WHERE id=?
        ''', (new_qty, new_total, unit_price, note, img_path, doc_path, cloud_link, package, cid))
    else:
        unit_price = total_price / quantity if quantity else 0
        c.execute('''
            INSERT INTO components 
                (name, model, quantity, total_price, unit_price, note, img_path, doc_path, cloud_link, package)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, model, quantity, total_price, unit_price, note, img_path, doc_path, cloud_link, package))
    conn.commit()
    conn.close()

def update_quantity_by_id(cid, delta):
    conn = sqlite3.connect('components.db')
    c = conn.cursor()
    c.execute('SELECT quantity, total_price FROM components WHERE id=?', (cid,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    old_qty, old_total = row
    if old_qty <= 0 or old_qty < abs(delta):
        conn.close()
        return
    new_qty = old_qty + delta
    if new_qty > 0:
        new_total = old_total * new_qty / old_qty
        unit_price = new_total / new_qty
    else:
        new_total = 0
        unit_price = 0
    c.execute('UPDATE components SET quantity=?, total_price=?, unit_price=? WHERE id=?', 
                (new_qty, new_total, unit_price, cid))
    conn.commit()
    conn.close()

def get_all_components():
    conn = sqlite3.connect('components.db')
    c = conn.cursor()
    c.execute('SELECT * FROM components')
    rows = c.fetchall()
    conn.close()
    return rows

def search_components(keyword):
    conn = sqlite3.connect('components.db')
    c = conn.cursor()
    c.execute('SELECT * FROM components WHERE name LIKE ? OR model LIKE ? OR package LIKE ?', ('%'+keyword+'%', '%'+keyword+'%', '%'+keyword+'%'))
    rows = c.fetchall()
    conn.close()
    return rows

def update_img_doc_by_id(cid, new_img, new_doc):
    conn = sqlite3.connect('components.db')
    c = conn.cursor()
    if new_img:
        c.execute('UPDATE components SET img_path=? WHERE id=?', (new_img, cid))
    if new_doc:
        c.execute('UPDATE components SET doc_path=? WHERE id=?', (new_doc, cid))
    conn.commit()
    conn.close()

def update_cloud_link_by_id(cid, cloud_link):
    conn = sqlite3.connect('components.db')
    c = conn.cursor()
    c.execute('UPDATE components SET cloud_link=? WHERE id=?', (cloud_link, cid))
    conn.commit()
    conn.close()

def delete_by_id(cid):
    row = None
    conn = sqlite3.connect('components.db')
    c = conn.cursor()
    c.execute('SELECT img_path, doc_path FROM components WHERE id=?', (cid,))
    row = c.fetchone()
    if row:
        img_path, doc_path = row
        try:
            if img_path and os.path.isfile(img_path):
                os.remove(img_path)
        except Exception:
            pass
        try:
            if doc_path and os.path.isfile(doc_path):
                os.remove(doc_path)
        except Exception:
            pass
    c.execute('DELETE FROM components WHERE id=?', (cid,))
    conn.commit()
    conn.close()
