import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import requests
import seaborn as sns
from sklearn.linear_model import LinearRegression
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
import pandas as pd

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors as rl_colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE  = os.path.join(BASE_DIR, "salon.db")
CSV_FILE = os.path.join(BASE_DIR, "Updated_Car_Sales_Data.csv")
SALON_NAME = "AutoSalon Premium"

STATUSES = ["Dostępny", "Zarezerwowany", "Sprzedany", "W serwisie"]
STATUS_COLORS = {
    "Dostępny":     "#c8f7c5",
    "Zarezerwowany":"#ffeaa7",
    "Sprzedany":    "#fab1a0",
    "W serwisie":   "#a8d8ea",
}

# ── BAZA DANYCH ───────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS cars (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            car_make       TEXT, car_model TEXT, year INTEGER,
            mileage        REAL, purchase_price REAL DEFAULT 0, price REAL,
            fuel_type      TEXT, transmission TEXT, color TEXT,
            accident       TEXT, condition_val TEXT, options TEXT,
            status         TEXT DEFAULT 'Dostępny'
        );
        CREATE TABLE IF NOT EXISTS customers (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL, phone TEXT, email TEXT,
            address TEXT, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS employees (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT NOT NULL, role TEXT, phone TEXT, email TEXT
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id         INTEGER, customer_id INTEGER, employee_id INTEGER,
            sale_price     REAL, purchase_price REAL, date TEXT, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS reminders (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id   INTEGER, type TEXT, due_date TEXT,
            notes    TEXT, done INTEGER DEFAULT 0
        );
    ''')
    conn.commit()
    conn.close()


def db():
    return sqlite3.connect(DB_FILE)


def import_csv():
    conn = db()
    if conn.execute("SELECT COUNT(*) FROM cars").fetchone()[0] > 0:
        conn.close()
        return
    conn.close()
    if not os.path.exists(CSV_FILE):
        return
    try:
        df = pd.read_csv(CSV_FILE).dropna()
        df["Price"] = df["Price"].round(2)
        conn = db()
        for _, row in df.iterrows():
            pp = round(float(row.get("Price", 0)) * 0.8, 2)
            conn.execute('''INSERT INTO cars
                (car_make,car_model,year,mileage,purchase_price,price,
                 fuel_type,transmission,color,accident,condition_val,options,status)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                row.get("Car Make",""),   row.get("Car Model",""),
                int(row.get("Year",0)),   float(row.get("Mileage",0)),
                pp,                       float(row.get("Price",0)),
                row.get("Fuel Type",""),  row.get("Transmission",""),
                row.get("Color",""),      row.get("Accident",""),
                row.get("Condition",""),  row.get("Options/Features",""),
                "Dostępny"))
        conn.commit()
        conn.close()
    except Exception as e:
        messagebox.showerror("Import CSV", str(e))

# ── HELPERS ───────────────────────────────────────────────────────────────────

def make_tree(parent, columns, col_widths):
    frame = ttk.Frame(parent)
    tree  = ttk.Treeview(frame, columns=columns, show="headings")
    sy = ttk.Scrollbar(frame, orient="vertical",   command=tree.yview)
    sx = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    sy.pack(side="right",  fill="y")
    sx.pack(side="bottom", fill="x")
    tree.pack(fill="both", expand=True)
    for col, w in zip(columns, col_widths):
        tree.heading(col, text=col)
        tree.column(col, width=w, minwidth=40)
    return frame, tree


def get_sel(tree):
    s = tree.focus()
    return int(s) if s else None


def simple_editor(title, fields, on_save):
    win = tk.Toplevel(root)
    win.title(title)
    entries = {}
    for i, (label, val, widget_type) in enumerate(fields):
        ttk.Label(win, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=3)
        if widget_type == "entry":
            e = ttk.Entry(win, width=35)
            e.insert(0, str(val))
            e.grid(row=i, column=1, padx=8, pady=3)
        elif isinstance(widget_type, list):
            e = tk.StringVar(value=str(val))
            ttk.Combobox(win, textvariable=e, values=widget_type,
                         state="readonly", width=33).grid(row=i, column=1, padx=8, pady=3)
        entries[label] = e
    ttk.Button(win, text="Zapisz",
               command=lambda: on_save(entries, win)).grid(
        row=len(fields), column=0, columnspan=2, pady=10)

# ── TAB: POJAZDY ──────────────────────────────────────────────────────────────

def make_vehicles_tab(nb):
    tab = ttk.Frame(nb)
    nb.add(tab, text="  Pojazdy  ")

    # Filtr
    ff = ttk.Frame(tab)
    ff.pack(fill="x", padx=6, pady=5)
    ttk.Label(ff, text="Szukaj:").pack(side="left")
    search_var = tk.StringVar()
    ttk.Entry(ff, textvariable=search_var, width=22).pack(side="left", padx=4)
    ttk.Label(ff, text="Status:").pack(side="left")
    status_var = tk.StringVar(value="Wszystkie")
    ttk.Combobox(ff, textvariable=status_var,
                 values=["Wszystkie"] + STATUSES, state="readonly", width=15).pack(side="left", padx=4)
    ttk.Button(ff, text="Szukaj",      command=lambda: refresh()).pack(side="left", padx=4)
    ttk.Button(ff, text="Importuj CSV",command=lambda: [import_csv(), refresh()]).pack(side="right", padx=4)

    cols   = ("ID","Marka","Model","Rok","Przebieg","Cena zakupu $","Cena sprzed. $","Paliwo","Skrzynia","Status")
    widths = (40, 100, 120, 55, 90, 105, 110, 80, 85, 105)
    tv_frame, tree = make_tree(tab, cols, widths)
    tv_frame.pack(fill="both", expand=True, padx=6)
    for s, c in STATUS_COLORS.items():
        tree.tag_configure(s, background=c)

    def refresh():
        tree.delete(*tree.get_children())
        q = ("SELECT id,car_make,car_model,year,mileage,purchase_price,"
             "price,fuel_type,transmission,status FROM cars WHERE 1=1")
        p = []
        s = search_var.get().strip()
        if s:
            q += " AND (car_make LIKE ? OR car_model LIKE ?)"
            p += [f"%{s}%", f"%{s}%"]
        sv = status_var.get()
        if sv != "Wszystkie":
            q += " AND status=?"
            p.append(sv)
        conn = db()
        for row in conn.execute(q, p).fetchall():
            tree.insert("", "end", iid=str(row[0]), values=row, tags=(row[9],))
        conn.close()

    def open_editor(car_id=None):
        conn = db()
        r = conn.execute("SELECT * FROM cars WHERE id=?", (car_id,)).fetchone() if car_id else None
        conn.close()
        win = tk.Toplevel(root)
        win.title("Edytuj pojazd" if car_id else "Dodaj pojazd")
        flds = [
            ("Marka",              r[1]  if r else "", "entry"),
            ("Model",              r[2]  if r else "", "entry"),
            ("Rok",                r[3]  if r else "", "entry"),
            ("Przebieg",           r[4]  if r else "", "entry"),
            ("Cena zakupu ($)",    r[5]  if r else "", "entry"),
            ("Cena sprzedaży ($)", r[6]  if r else "", "entry"),
            ("Paliwo",             r[7]  if r else "", "entry"),
            ("Skrzynia",           r[8]  if r else "", "entry"),
            ("Kolor",              r[9]  if r else "", "entry"),
            ("Wypadek",            r[10] if r else "No",  ["No","Yes"]),
            ("Stan",               r[11] if r else "", "entry"),
            ("Opcje",              r[12] if r else "", "entry"),
            ("Status",             r[13] if r else "Dostępny", STATUSES),
        ]
        entries = {}
        for i, (label, val, wt) in enumerate(flds):
            ttk.Label(win, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=2)
            if wt == "entry":
                e = ttk.Entry(win, width=30); e.insert(0, str(val))
                e.grid(row=i, column=1, padx=8, pady=2)
            else:
                e = tk.StringVar(value=str(val))
                ttk.Combobox(win, textvariable=e, values=wt,
                             state="readonly", width=28).grid(row=i, column=1, padx=8, pady=2)
            entries[label] = e

        def save():
            def v(k): return entries[k].get() if hasattr(entries[k],"get") else entries[k].get()
            try:
                vals = (v("Marka"), v("Model"), int(v("Rok")), float(v("Przebieg")),
                        float(v("Cena zakupu ($)")), float(v("Cena sprzedaży ($)")),
                        v("Paliwo"), v("Skrzynia"), v("Kolor"), v("Wypadek"),
                        v("Stan"), v("Opcje"), v("Status"))
            except ValueError:
                messagebox.showerror("Błąd", "Sprawdź pola liczbowe.")
                return
            conn = db()
            if car_id:
                conn.execute('''UPDATE cars SET car_make=?,car_model=?,year=?,mileage=?,
                    purchase_price=?,price=?,fuel_type=?,transmission=?,color=?,
                    accident=?,condition_val=?,options=?,status=? WHERE id=?''', vals+(car_id,))
            else:
                conn.execute('''INSERT INTO cars(car_make,car_model,year,mileage,purchase_price,price,
                    fuel_type,transmission,color,accident,condition_val,options,status)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', vals)
            conn.commit(); conn.close()
            win.destroy(); refresh()

        ttk.Button(win, text="Zapisz", command=save).grid(
            row=len(flds), column=0, columnspan=2, pady=10)

    def change_status():
        cid = get_sel(tree)
        if not cid:
            messagebox.showwarning("Uwaga","Zaznacz pojazd."); return
        win = tk.Toplevel(root); win.title("Zmień status"); win.geometry("240x110")
        sv = tk.StringVar()
        ttk.Label(win, text="Nowy status:").pack(pady=8)
        ttk.Combobox(win, textvariable=sv, values=STATUSES, state="readonly").pack()
        def save():
            if sv.get():
                conn=db(); conn.execute("UPDATE cars SET status=? WHERE id=?",(sv.get(),cid))
                conn.commit(); conn.close(); win.destroy(); refresh()
        ttk.Button(win, text="Zapisz", command=save).pack(pady=8)

    def delete_car():
        cid = get_sel(tree)
        if not cid:
            messagebox.showwarning("Uwaga","Zaznacz pojazd."); return
        if messagebox.askyesno("Usuń","Usunąć pojazd?"):
            conn=db(); conn.execute("DELETE FROM cars WHERE id=?",(cid,))
            conn.commit(); conn.close(); refresh()

    bf = ttk.Frame(tab); bf.pack(pady=5)
    ttk.Button(bf, text="Dodaj",         command=lambda: open_editor()).pack(side="left",padx=3)
    ttk.Button(bf, text="Edytuj",        command=lambda: open_editor(get_sel(tree))).pack(side="left",padx=3)
    ttk.Button(bf, text="Usuń",          command=delete_car).pack(side="left",padx=3)
    ttk.Button(bf, text="Zmień status",  command=change_status).pack(side="left",padx=3)
    ttk.Button(bf, text="Kalkulator marży", command=margin_calculator).pack(side="left",padx=3)

    refresh()
    return refresh

# ── TAB: KLIENCI ──────────────────────────────────────────────────────────────

def make_customers_tab(nb):
    tab = ttk.Frame(nb)
    nb.add(tab, text="  Klienci  ")

    ff = ttk.Frame(tab); ff.pack(fill="x", padx=6, pady=5)
    ttk.Label(ff, text="Szukaj:").pack(side="left")
    sv = tk.StringVar()
    ttk.Entry(ff, textvariable=sv, width=25).pack(side="left", padx=4)
    ttk.Button(ff, text="Szukaj", command=lambda: refresh()).pack(side="left")

    cols   = ("ID","Imię i nazwisko","Telefon","Email","Adres","Notatki")
    widths = (40, 160, 110, 180, 190, 160)
    tv_frame, tree = make_tree(tab, cols, widths)
    tv_frame.pack(fill="both", expand=True, padx=6)

    def refresh():
        tree.delete(*tree.get_children())
        q = "SELECT id,name,phone,email,address,notes FROM customers"
        p = []
        s = sv.get().strip()
        if s:
            q += " WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?"
            p = [f"%{s}%"]*3
        conn = db()
        for row in conn.execute(q, p).fetchall():
            tree.insert("", "end", iid=str(row[0]), values=row)
        conn.close()

    def open_editor(cid=None):
        conn = db()
        r = conn.execute("SELECT * FROM customers WHERE id=?",(cid,)).fetchone() if cid else None
        conn.close()
        win = tk.Toplevel(root)
        win.title("Edytuj klienta" if cid else "Dodaj klienta")
        flds = [("Imię i nazwisko", r[1] if r else "","entry"),
                ("Telefon",         r[2] if r else "","entry"),
                ("Email",           r[3] if r else "","entry"),
                ("Adres",           r[4] if r else "","entry"),
                ("Notatki",         r[5] if r else "","entry")]
        entries = {}
        for i,(label,val,_) in enumerate(flds):
            ttk.Label(win,text=label).grid(row=i,column=0,sticky="w",padx=8,pady=3)
            e=ttk.Entry(win,width=35); e.insert(0,str(val))
            e.grid(row=i,column=1,padx=8,pady=3); entries[label]=e
        def save():
            name = entries["Imię i nazwisko"].get().strip()
            if not name:
                messagebox.showwarning("Uwaga","Imię jest wymagane."); return
            vals=(name,entries["Telefon"].get(),entries["Email"].get(),
                  entries["Adres"].get(),entries["Notatki"].get())
            conn=db()
            if cid:
                conn.execute("UPDATE customers SET name=?,phone=?,email=?,address=?,notes=? WHERE id=?",vals+(cid,))
            else:
                conn.execute("INSERT INTO customers(name,phone,email,address,notes) VALUES(?,?,?,?,?)",vals)
            conn.commit(); conn.close(); win.destroy(); refresh()
        ttk.Button(win,text="Zapisz",command=save).grid(row=len(flds),column=0,columnspan=2,pady=10)

    def show_history():
        cid = get_sel(tree)
        if not cid:
            messagebox.showwarning("Uwaga","Zaznacz klienta."); return
        conn = db()
        cname = conn.execute("SELECT name FROM customers WHERE id=?",(cid,)).fetchone()
        rows  = conn.execute('''
            SELECT t.date, c.car_make||' '||c.car_model||' ('||c.year||')',
                   t.sale_price, e.name
            FROM transactions t
            LEFT JOIN cars c ON t.car_id=c.id
            LEFT JOIN employees e ON t.employee_id=e.id
            WHERE t.customer_id=? ORDER BY t.date DESC''',(cid,)).fetchall()
        conn.close()
        win = tk.Toplevel(root)
        win.title(f"Historia zakupów – {cname[0] if cname else ''}")
        cols2   = ("Data","Pojazd","Cena ($)","Sprzedawca")
        widths2 = (100,220,90,150)
        tv2,tree2 = make_tree(win,cols2,widths2)
        tv2.pack(fill="both",expand=True,padx=10,pady=10)
        for row in rows:
            tree2.insert("","end",values=row)

    def delete_cust():
        cid = get_sel(tree)
        if not cid:
            messagebox.showwarning("Uwaga","Zaznacz klienta."); return
        if messagebox.askyesno("Usuń","Usunąć klienta?"):
            conn=db(); conn.execute("DELETE FROM customers WHERE id=?",(cid,))
            conn.commit(); conn.close(); refresh()

    bf = ttk.Frame(tab); bf.pack(pady=5)
    ttk.Button(bf,text="Dodaj",          command=lambda: open_editor()).pack(side="left",padx=3)
    ttk.Button(bf,text="Edytuj",         command=lambda: open_editor(get_sel(tree))).pack(side="left",padx=3)
    ttk.Button(bf,text="Usuń",           command=delete_cust).pack(side="left",padx=3)
    ttk.Button(bf,text="Historia zakupów",command=show_history).pack(side="left",padx=3)
    refresh()

# ── TAB: PRACOWNICY ───────────────────────────────────────────────────────────

def make_employees_tab(nb):
    tab = ttk.Frame(nb)
    nb.add(tab, text="  Pracownicy  ")

    cols   = ("ID","Imię i nazwisko","Stanowisko","Telefon","Email")
    widths = (40, 180, 150, 120, 200)
    tv_frame, tree = make_tree(tab, cols, widths)
    tv_frame.pack(fill="both", expand=True, padx=6, pady=6)

    def refresh():
        tree.delete(*tree.get_children())
        conn = db()
        for row in conn.execute("SELECT id,name,role,phone,email FROM employees").fetchall():
            tree.insert("","end",iid=str(row[0]),values=row)
        conn.close()

    def open_editor(eid=None):
        conn = db()
        r = conn.execute("SELECT * FROM employees WHERE id=?",(eid,)).fetchone() if eid else None
        conn.close()
        win = tk.Toplevel(root)
        win.title("Edytuj pracownika" if eid else "Dodaj pracownika")
        flds = [("Imię i nazwisko", r[1] if r else "","entry"),
                ("Stanowisko",      r[2] if r else "","entry"),
                ("Telefon",         r[3] if r else "","entry"),
                ("Email",           r[4] if r else "","entry")]
        entries = {}
        for i,(label,val,_) in enumerate(flds):
            ttk.Label(win,text=label).grid(row=i,column=0,sticky="w",padx=8,pady=3)
            e=ttk.Entry(win,width=35); e.insert(0,str(val))
            e.grid(row=i,column=1,padx=8,pady=3); entries[label]=e
        def save():
            name = entries["Imię i nazwisko"].get().strip()
            if not name:
                messagebox.showwarning("Uwaga","Imię jest wymagane."); return
            vals=(name,entries["Stanowisko"].get(),entries["Telefon"].get(),entries["Email"].get())
            conn=db()
            if eid:
                conn.execute("UPDATE employees SET name=?,role=?,phone=?,email=? WHERE id=?",vals+(eid,))
            else:
                conn.execute("INSERT INTO employees(name,role,phone,email) VALUES(?,?,?,?)",vals)
            conn.commit(); conn.close(); win.destroy(); refresh()
        ttk.Button(win,text="Zapisz",command=save).grid(row=len(flds),column=0,columnspan=2,pady=10)

    def delete_emp():
        eid = get_sel(tree)
        if not eid:
            messagebox.showwarning("Uwaga","Zaznacz pracownika."); return
        if messagebox.askyesno("Usuń","Usunąć pracownika?"):
            conn=db(); conn.execute("DELETE FROM employees WHERE id=?",(eid,))
            conn.commit(); conn.close(); refresh()

    bf = ttk.Frame(tab); bf.pack(pady=5)
    ttk.Button(bf,text="Dodaj",  command=lambda: open_editor()).pack(side="left",padx=3)
    ttk.Button(bf,text="Edytuj", command=lambda: open_editor(get_sel(tree))).pack(side="left",padx=3)
    ttk.Button(bf,text="Usuń",   command=delete_emp).pack(side="left",padx=3)
    refresh()

# ── TAB: SPRZEDAŻE ────────────────────────────────────────────────────────────

def make_sales_tab(nb):
    tab = ttk.Frame(nb)
    nb.add(tab, text="  Sprzedaże  ")

    ff = ttk.Frame(tab); ff.pack(fill="x", padx=6, pady=5)
    ttk.Label(ff,text="Od:").pack(side="left")
    from_var = tk.StringVar(value="2020-01-01")
    ttk.Entry(ff,textvariable=from_var,width=12).pack(side="left",padx=3)
    ttk.Label(ff,text="Do:").pack(side="left")
    to_var = tk.StringVar(value=datetime.today().strftime("%Y-%m-%d"))
    ttk.Entry(ff,textvariable=to_var,width=12).pack(side="left",padx=3)
    ttk.Button(ff,text="Filtruj",command=lambda: refresh()).pack(side="left",padx=5)

    cols   = ("ID","Data","Pojazd","Klient","Pracownik","Cena ($)","Zysk ($)","Marża (%)","Notatki")
    widths = (40, 100, 190, 160, 150, 100, 90, 80, 150)
    tv_frame, tree = make_tree(tab, cols, widths)
    tv_frame.pack(fill="both", expand=True, padx=6)
    tree.tag_configure("profit", background="#f0fff0")
    tree.tag_configure("loss",   background="#fff0f0")

    def refresh():
        tree.delete(*tree.get_children())
        conn = db()
        rows = conn.execute('''
            SELECT t.id, t.date,
                   c.car_make||' '||c.car_model||' ('||c.year||')',
                   cu.name, e.name,
                   t.sale_price,
                   ROUND(t.sale_price - t.purchase_price, 2),
                   t.purchase_price,
                   t.notes
            FROM transactions t
            LEFT JOIN cars     c  ON t.car_id=c.id
            LEFT JOIN customers cu ON t.customer_id=cu.id
            LEFT JOIN employees e  ON t.employee_id=e.id
            WHERE t.date BETWEEN ? AND ?
            ORDER BY t.date DESC''', (from_var.get(), to_var.get())).fetchall()
        conn.close()
        for row in rows:
            zysk = row[6] or 0
            purchase = row[7] or 0
            marza = round((zysk / purchase * 100), 1) if purchase > 0 else 0.0
            display = row[:7] + (f"{marza}%", row[8])
            tag = "profit" if zysk >= 0 else "loss"
            tree.insert("","end",iid=str(row[0]),values=display,tags=(tag,))

    def register_sale():
        conn = db()
        cars_avail = conn.execute(
            "SELECT id,car_make,car_model,year,price,purchase_price FROM cars WHERE status='Dostępny'"
        ).fetchall()
        custs = conn.execute("SELECT id,name FROM customers").fetchall()
        emps  = conn.execute("SELECT id,name FROM employees").fetchall()
        conn.close()

        if not cars_avail:
            messagebox.showinfo("Info","Brak dostępnych pojazdów."); return
        if not custs:
            messagebox.showinfo("Info","Najpierw dodaj klientów."); return
        if not emps:
            messagebox.showinfo("Info","Najpierw dodaj pracowników."); return

        win = tk.Toplevel(root); win.title("Zarejestruj sprzedaż")
        car_map  = {f"{r[1]} {r[2]} ({r[3]}) – {r[4]:,.0f}$": r for r in cars_avail}
        cust_map = {r[1]: r[0] for r in custs}
        emp_map  = {r[1]: r[0] for r in emps}

        ttk.Label(win,text="Pojazd:").grid(row=0,column=0,sticky="w",padx=8,pady=4)
        car_var = tk.StringVar()
        car_cb  = ttk.Combobox(win,textvariable=car_var,values=list(car_map),state="readonly",width=42)
        car_cb.grid(row=0,column=1,padx=8,pady=4)

        ttk.Label(win,text="Klient:").grid(row=1,column=0,sticky="w",padx=8,pady=4)
        cust_var = tk.StringVar()
        ttk.Combobox(win,textvariable=cust_var,values=list(cust_map),state="readonly",width=42).grid(row=1,column=1,padx=8,pady=4)

        ttk.Label(win,text="Pracownik:").grid(row=2,column=0,sticky="w",padx=8,pady=4)
        emp_var = tk.StringVar()
        ttk.Combobox(win,textvariable=emp_var,values=list(emp_map),state="readonly",width=42).grid(row=2,column=1,padx=8,pady=4)

        ttk.Label(win,text="Cena sprzedaży ($):").grid(row=3,column=0,sticky="w",padx=8,pady=4)
        price_var = tk.StringVar()
        ttk.Entry(win,textvariable=price_var,width=20).grid(row=3,column=1,sticky="w",padx=8,pady=4)

        def on_car_sel(e):
            r = car_map.get(car_var.get())
            if r: price_var.set(str(r[4]))
        car_cb.bind("<<ComboboxSelected>>", on_car_sel)

        ttk.Label(win,text="Data (RRRR-MM-DD):").grid(row=4,column=0,sticky="w",padx=8,pady=4)
        date_var = tk.StringVar(value=datetime.today().strftime("%Y-%m-%d"))
        ttk.Entry(win,textvariable=date_var,width=20).grid(row=4,column=1,sticky="w",padx=8,pady=4)

        ttk.Label(win,text="Notatki:").grid(row=5,column=0,sticky="w",padx=8,pady=4)
        notes_e = ttk.Entry(win,width=42); notes_e.grid(row=5,column=1,padx=8,pady=4)

        def save():
            car_row = car_map.get(car_var.get())
            cust_id = cust_map.get(cust_var.get())
            emp_id  = emp_map.get(emp_var.get())
            if not car_row or not cust_id or not emp_id:
                messagebox.showwarning("Uwaga","Wypełnij wszystkie pola."); return
            try:
                sale_price = float(price_var.get())
            except ValueError:
                messagebox.showerror("Błąd","Podaj poprawną cenę."); return
            conn = db()
            conn.execute('''INSERT INTO transactions
                (car_id,customer_id,employee_id,sale_price,purchase_price,date,notes)
                VALUES(?,?,?,?,?,?,?)''',
                (car_row[0],cust_id,emp_id,sale_price,car_row[5],date_var.get(),notes_e.get()))
            conn.execute("UPDATE cars SET status='Sprzedany' WHERE id=?",(car_row[0],))
            conn.commit(); conn.close()
            win.destroy(); refresh(); refresh_vehicles_cb()

        ttk.Button(win,text="Zapisz sprzedaż",command=save).grid(row=6,column=0,columnspan=2,pady=12)

    def delete_sale():
        tid = get_sel(tree)
        if not tid:
            messagebox.showwarning("Uwaga","Zaznacz transakcję."); return
        if messagebox.askyesno("Usuń","Usunąć transakcję?"):
            conn=db(); conn.execute("DELETE FROM transactions WHERE id=?",(tid,))
            conn.commit(); conn.close(); refresh()

    def export_invoice():
        tid = get_sel(tree)
        if not tid:
            messagebox.showwarning("Uwaga","Zaznacz transakcję."); return
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Brak biblioteki","Zainstaluj: pip install reportlab"); return
        generate_invoice_pdf(tid)

    bf = ttk.Frame(tab); bf.pack(pady=5)
    ttk.Button(bf,text="Zarejestruj sprzedaż", command=register_sale).pack(side="left",padx=3)
    ttk.Button(bf,text="Usuń",                 command=delete_sale).pack(side="left",padx=3)
    ttk.Button(bf,text="Eksport faktury PDF",  command=export_invoice).pack(side="left",padx=3)

    refresh()
    return refresh

# ── TAB: PRZYPOMNIENIA ────────────────────────────────────────────────────────

def make_reminders_tab(nb):
    tab = ttk.Frame(nb)
    nb.add(tab, text="  Przypomnienia  ")

    ff = ttk.Frame(tab); ff.pack(fill="x",padx=6,pady=5)
    show_var = tk.StringVar(value="Aktywne")
    ttk.Combobox(ff,textvariable=show_var,values=["Wszystkie","Aktywne","Wykonane"],
                 state="readonly",width=14).pack(side="left",padx=5)
    ttk.Button(ff,text="Filtruj",command=lambda: refresh()).pack(side="left")

    cols   = ("ID","Pojazd","Typ","Termin","Notatki","Status")
    widths = (40, 210, 130, 110, 200, 90)
    tv_frame, tree = make_tree(tab, cols, widths)
    tv_frame.pack(fill="both",expand=True,padx=6)
    tree.tag_configure("overdue", background="#FFCCCC")
    tree.tag_configure("soon",    background="#FFFACD")
    tree.tag_configure("ok",      background="#CCFFCC")
    tree.tag_configure("done",    background="#DDDDDD")

    def refresh():
        tree.delete(*tree.get_children())
        today_str = datetime.today().strftime("%Y-%m-%d")
        q = '''SELECT r.id, c.car_make||' '||c.car_model||' ('||c.year||')',
                      r.type, r.due_date, r.notes, r.done
               FROM reminders r LEFT JOIN cars c ON r.car_id=c.id'''
        sv = show_var.get()
        if sv == "Aktywne":   q += " WHERE r.done=0"
        elif sv == "Wykonane": q += " WHERE r.done=1"
        q += " ORDER BY r.due_date"
        conn = db()
        for row in conn.execute(q).fetchall():
            done = row[5]
            if done:
                tag = "done"; status_txt = "Wykonane"
            else:
                status_txt = "Aktywne"
                try:
                    diff = (datetime.strptime(row[3],"%Y-%m-%d") -
                            datetime.strptime(today_str,"%Y-%m-%d")).days
                    tag = "overdue" if diff < 0 else "soon" if diff <= 30 else "ok"
                except Exception:
                    tag = "ok"
            tree.insert("","end",iid=str(row[0]),values=row[:5]+(status_txt,),tags=(tag,))
        conn.close()

    def add_reminder():
        conn = db()
        cars_list = conn.execute("SELECT id,car_make,car_model,year FROM cars").fetchall()
        conn.close()
        win = tk.Toplevel(root); win.title("Dodaj przypomnienie")
        car_map = {f"{r[1]} {r[2]} ({r[3]})": r[0] for r in cars_list}
        ttk.Label(win,text="Pojazd:").grid(row=0,column=0,sticky="w",padx=8,pady=4)
        car_var = tk.StringVar()
        ttk.Combobox(win,textvariable=car_var,values=list(car_map),state="readonly",width=35).grid(row=0,column=1,padx=8,pady=4)
        ttk.Label(win,text="Typ:").grid(row=1,column=0,sticky="w",padx=8,pady=4)
        type_var = tk.StringVar()
        ttk.Combobox(win,textvariable=type_var,
                     values=["Przegląd techniczny","Ubezpieczenie","Inne"],
                     state="readonly",width=35).grid(row=1,column=1,padx=8,pady=4)
        ttk.Label(win,text="Termin (RRRR-MM-DD):").grid(row=2,column=0,sticky="w",padx=8,pady=4)
        date_var = tk.StringVar()
        ttk.Entry(win,textvariable=date_var,width=20).grid(row=2,column=1,sticky="w",padx=8,pady=4)
        ttk.Label(win,text="Notatki:").grid(row=3,column=0,sticky="w",padx=8,pady=4)
        notes_e = ttk.Entry(win,width=35); notes_e.grid(row=3,column=1,padx=8,pady=4)
        def save():
            cid = car_map.get(car_var.get())
            if not cid or not type_var.get() or not date_var.get():
                messagebox.showwarning("Uwaga","Wypełnij wszystkie pola."); return
            conn=db()
            conn.execute("INSERT INTO reminders(car_id,type,due_date,notes) VALUES(?,?,?,?)",
                         (cid,type_var.get(),date_var.get(),notes_e.get()))
            conn.commit(); conn.close(); win.destroy(); refresh()
        ttk.Button(win,text="Zapisz",command=save).grid(row=4,column=0,columnspan=2,pady=10)

    def mark_done():
        rid = get_sel(tree)
        if not rid:
            messagebox.showwarning("Uwaga","Zaznacz przypomnienie."); return
        conn=db(); conn.execute("UPDATE reminders SET done=1 WHERE id=?",(rid,))
        conn.commit(); conn.close(); refresh()

    def delete_rem():
        rid = get_sel(tree)
        if not rid:
            messagebox.showwarning("Uwaga","Zaznacz przypomnienie."); return
        if messagebox.askyesno("Usuń","Usunąć przypomnienie?"):
            conn=db(); conn.execute("DELETE FROM reminders WHERE id=?",(rid,))
            conn.commit(); conn.close(); refresh()

    bf = ttk.Frame(tab); bf.pack(pady=5)
    ttk.Button(bf,text="Dodaj",                  command=add_reminder).pack(side="left",padx=3)
    ttk.Button(bf,text="Oznacz jako wykonane",   command=mark_done).pack(side="left",padx=3)
    ttk.Button(bf,text="Usuń",                   command=delete_rem).pack(side="left",padx=3)
    refresh()

# ── TAB: RAPORTY ──────────────────────────────────────────────────────────────

def make_reports_tab(nb):
    tab = ttk.Frame(nb)
    nb.add(tab, text="  Raporty  ")

    cf = ttk.Frame(tab); cf.pack(fill="x",padx=6,pady=6)
    ttk.Label(cf,text="Rok:").pack(side="left")
    year_var = tk.StringVar(value=str(datetime.today().year))
    ttk.Entry(cf,textvariable=year_var,width=8).pack(side="left",padx=5)
    ttk.Button(cf,text="Generuj raporty",command=lambda: generate()).pack(side="left",padx=5)
    ttk.Button(cf,text="Eksport raportu PDF",command=lambda: export_report_pdf(year_var.get())).pack(side="left",padx=5)
    ttk.Button(cf,text="Kalkulator marży",command=margin_calculator).pack(side="right",padx=5)

    summary = ttk.Label(tab,text="",font=("Arial",10),justify="left",
                        foreground="#2c3e50")
    summary.pack(padx=10,pady=4,anchor="w")

    chart_frame = ttk.Frame(tab)
    chart_frame.pack(fill="both",expand=True,padx=6)

    def generate():
        year = year_var.get().strip()
        conn = db()
        rows = conn.execute('''
            SELECT t.date, t.sale_price,
                   t.sale_price - t.purchase_price AS profit,
                   c.car_make, c.car_model, e.name
            FROM transactions t
            LEFT JOIN cars      c  ON t.car_id=c.id
            LEFT JOIN employees e  ON t.employee_id=e.id
            WHERE t.date LIKE ?''',(f"{year}%",)).fetchall()

        inv_count = conn.execute("SELECT COUNT(*) FROM cars").fetchone()[0]
        avail_count = conn.execute(
            "SELECT COUNT(*) FROM cars WHERE status='Dostępny'").fetchone()[0]
        conn.close()

        for w in chart_frame.winfo_children():
            w.destroy()

        if not rows:
            summary.config(text=f"Brak sprzedaży w roku {year}.  "
                                 f"Pojazdów w bazie: {inv_count}  |  Dostępnych: {avail_count}")
            return

        df = pd.DataFrame(rows,columns=["date","sale","profit","make","model","emp"])
        df["month"]      = pd.to_datetime(df["date"]).dt.month
        df["model_full"] = df["make"]+" "+df["model"]

        total_rev    = df["sale"].sum()
        total_profit = df["profit"].sum()
        cnt          = len(df)
        best_model   = df["model_full"].value_counts().idxmax()
        best_emp     = df["emp"].value_counts().idxmax() if df["emp"].notna().any() else "-"

        summary.config(text=(
            f"Rok {year}  |  Sprzedaży: {cnt}  |  "
            f"Przychód: {total_rev:,.0f}$  |  Zysk: {total_profit:,.0f}$  |  "
            f"Top model: {best_model}  |  Top sprzedawca: {best_emp}  |  "
            f"Pojazdów w bazie: {inv_count}  |  Dostępnych: {avail_count}"))

        fig, axes = plt.subplots(1, 3, figsize=(14, 4))
        fig.tight_layout(pad=3.0)

        monthly = pd.Series(0, index=range(1,13))
        monthly = monthly.add(df.groupby("month")["sale"].sum(), fill_value=0)
        axes[0].bar(monthly.index, monthly.values, color="steelblue")
        axes[0].set_title(f"Przychód miesięczny {year}")
        axes[0].set_xlabel("Miesiąc"); axes[0].set_ylabel("$")

        top5 = df["model_full"].value_counts().head(5)
        axes[1].barh(top5.index, top5.values, color="teal")
        axes[1].set_title("Top 5 modeli")
        axes[1].set_xlabel("Sprzedaży")

        emp_sales = df.groupby("emp")["sale"].sum().sort_values()
        axes[2].barh(emp_sales.index, emp_sales.values, color="coral")
        axes[2].set_title("Sprzedaż wg pracownika ($)")

        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    generate()

# ── TAB: WYKRESY ──────────────────────────────────────────────────────────────

def make_charts_tab(nb):
    tab = ttk.Frame(nb)
    nb.add(tab, text="  Wykresy  ")

    plot_options = {
        "Średnia cena wg marki":          "avg_price_by_brand",
        "Cena vs przebieg":               "price_vs_mileage",
        "Rodzaj paliwa":                  "fuel_type_dist",
        "Korelacja cech z ceną":          "price_correlation",
        "Macierz korelacji":              "correlation_matrix",
        "Skrzynia biegów – udział":       "transmission_pie",
        "Rozkład roczników":              "year_distribution",
        "Rozkład cen":                    "price_distribution",
        "Rozkład przebiegu":              "mileage_distribution",
        "Top 10 marek – liczba i cena":   "top_brands_analysis",
    }
    cf = ttk.Frame(tab); cf.pack(fill="x",padx=6,pady=6)
    sel = tk.StringVar(value="Wybierz wykres")
    ttk.OptionMenu(cf,sel,"Wybierz wykres",*plot_options).pack(side="left",padx=5)
    ttk.Button(cf,text="Pokaż wykres",
               command=lambda: show_plot(plot_options.get(sel.get(),""))).pack(side="left")


def show_plot(kind):
    if not kind: return
    conn = db()
    df = pd.read_sql_query("SELECT * FROM cars", conn)
    conn.close()
    df.rename(columns={"car_make":"Car Make","car_model":"Car Model","mileage":"Mileage",
                        "price":"Price","year":"Year","fuel_type":"Fuel Type",
                        "transmission":"Transmission"},inplace=True)

    fig, ax = plt.subplots(figsize=(10,6))
    if kind == "avg_price_by_brand":
        df.groupby("Car Make")["Price"].mean().sort_values().plot(kind="barh",ax=ax)
        ax.set_title("Średnia cena wg marki")
    elif kind == "price_vs_mileage":
        df.plot(kind="scatter",x="Mileage",y="Price",alpha=0.5,ax=ax)
        ax.set_title("Cena vs Przebieg")
    elif kind == "fuel_type_dist":
        c=df["Fuel Type"].value_counts()
        ax.pie(c,labels=c.index,autopct="%1.1f%%",startangle=140)
        ax.set_title("Rodzaj paliwa")
    elif kind == "price_correlation":
        df[['Year','Mileage','Price']].corr()['Price'].drop('Price').plot(kind='bar',ax=ax,color='teal')
        ax.set_title("Korelacja cech z ceną")
    elif kind == "correlation_matrix":
        ax.remove(); fig,ax=plt.subplots(figsize=(8,6))
        sns.heatmap(df[['Year','Mileage','Price']].corr(),annot=True,cmap='coolwarm',fmt=".2f",ax=ax)
        ax.set_title("Macierz korelacji")
    elif kind == "transmission_pie":
        c=df['Transmission'].value_counts()
        ax.pie(c,labels=c.index,autopct='%1.1f%%',startangle=140,
               colors=['lightcoral','lightskyblue'])
        ax.set_title("Udział skrzyni biegów")
    elif kind == "year_distribution":
        sns.histplot(df['Year'],bins=range(int(df['Year'].min()),int(df['Year'].max())+2),
                     kde=False,color='steelblue',ax=ax)
        ax.set_title("Rozkład roczników")
    elif kind == "price_distribution":
        sns.histplot(df['Price'],bins=20,kde=True,color='orange',ax=ax)
        ax.set_title("Rozkład cen")
    elif kind == "mileage_distribution":
        sns.histplot(df['Mileage'],bins=20,kde=True,color='green',ax=ax)
        ax.set_title("Rozkład przebiegu")
    elif kind == "top_brands_analysis":
        ax.remove(); fig,ax1=plt.subplots(figsize=(10,6))
        bc=df['Car Make'].value_counts().head(10)
        bp=df.groupby('Car Make')['Price'].mean().loc[bc.index]
        ax1.set_ylabel('Liczba aut',color='tab:blue')
        bc.plot(kind='bar',ax=ax1,color='tab:blue',position=0,width=0.4)
        ax2=ax1.twinx(); ax2.set_ylabel('Średnia cena ($)',color='tab:red')
        bp.plot(kind='bar',ax=ax2,color='tab:red',position=1,width=0.4)
        plt.title('Top 10 marek'); fig.tight_layout()

    win = tk.Toplevel(root); win.title("Wykres")
    canvas = FigureCanvasTkAgg(fig,master=win)
    canvas.draw(); canvas.get_tk_widget().pack(fill="both",expand=True)
    def save():
        fp=filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG","*.png")])
        if fp: fig.savefig(fp); messagebox.showinfo("Zapisano",f"Zapisano:\n{fp}")
    ttk.Button(win,text="Zapisz jako PNG",command=save).pack(pady=5)

# ── TAB: PREDYKCJA ────────────────────────────────────────────────────────────

def make_prediction_tab(nb):
    tab = ttk.Frame(nb)
    nb.add(tab, text="  Predykcja ceny  ")

    ttk.Label(tab,text="Predykcja ceny pojazdu (regresja liniowa na danych z bazy)",
              font=("Arial",10)).pack(pady=10)
    ff = ttk.Frame(tab); ff.pack()

    labels = ["Marka (np. Toyota)","Rok produkcji","Przebieg (km)","Wypadek (yes/no)"]
    entries = {}
    for i,label in enumerate(labels):
        ttk.Label(ff,text=label).grid(row=i,column=0,sticky="w",padx=10,pady=5)
        e=ttk.Entry(ff,width=25); e.grid(row=i,column=1,padx=10,pady=5)
        entries[label]=e

    result_lbl = ttk.Label(tab,text="",font=("Arial",13,"bold"))
    result_lbl.pack(pady=10)

    def predict():
        conn=db()
        df=pd.read_sql_query("SELECT car_make,year,mileage,accident,price FROM cars",conn)
        conn.close()
        if len(df)<10:
            messagebox.showinfo("Info","Za mało danych do trenowania modelu."); return
        df['Accident_Flag']=df['accident'].map({'No':0,'Yes':1}).fillna(0)
        df_enc=pd.get_dummies(df[['car_make']],prefix='Make')
        X=pd.concat([df[['year','mileage','Accident_Flag']],df_enc],axis=1)
        y=df['price']
        mdl=LinearRegression(); mdl.fit(X,y)
        try:
            make=entries["Marka (np. Toyota)"].get().strip().title()
            year=int(entries["Rok produkcji"].get())
            mileage=int(entries["Przebieg (km)"].get())
            acc_str=entries["Wypadek (yes/no)"].get().strip().lower()
            if acc_str not in ['yes','no']:
                messagebox.showerror("Błąd","Wypadek: yes lub no"); return
            acc=1 if acc_str=='yes' else 0
            row={f:0 for f in X.columns}
            row['year']=year; row['mileage']=mileage; row['Accident_Flag']=acc
            mcol=f"Make_{make}"
            if mcol not in row:
                messagebox.showerror("Błąd marki","Marka nie znaleziona w danych."); return
            row[mcol]=1
            pred=mdl.predict(pd.DataFrame([row]))[0]
            if pred<=0:
                result_lbl.config(text="Nie udało się oszacować ceny.",foreground="red")
            else:
                result_lbl.config(text=f"Szacowana cena: {pred:,.0f} $",foreground="green")
        except ValueError:
            messagebox.showerror("Błąd","Podaj poprawne wartości liczbowe.")

    ttk.Button(tab,text="Oblicz cenę",command=predict).pack(pady=5)

# ── RAPORT SPRZEDAŻY PDF ──────────────────────────────────────────────────────

def export_report_pdf(year):
    if not REPORTLAB_AVAILABLE:
        messagebox.showerror("Brak biblioteki","Zainstaluj: pip install reportlab"); return

    conn = db()
    rows = conn.execute('''
        SELECT t.date,
               c.car_make||' '||c.car_model||' ('||c.year||')',
               cu.name, e.name,
               t.sale_price,
               ROUND(t.sale_price - t.purchase_price, 2),
               t.purchase_price
        FROM transactions t
        LEFT JOIN cars      c  ON t.car_id=c.id
        LEFT JOIN customers cu ON t.customer_id=cu.id
        LEFT JOIN employees e  ON t.employee_id=e.id
        WHERE t.date LIKE ?
        ORDER BY t.date''', (f"{year}%",)).fetchall()
    conn.close()

    if not rows:
        messagebox.showinfo("Brak danych", f"Brak transakcji w roku {year}."); return

    fp = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF","*.pdf")],
        initialfile=f"raport_sprzedazy_{year}.pdf"
    )
    if not fp: return

    doc = SimpleDocTemplate(fp, pagesize=A4)
    styles = getSampleStyleSheet()
    el = []

    el.append(Paragraph(f"<b>{SALON_NAME}</b>", styles["Title"]))
    el.append(Paragraph(f"<b>Raport sprzedaży – rok {year}</b>", styles["Heading2"]))
    el.append(Paragraph(f"Wygenerowano: {datetime.today().strftime('%Y-%m-%d')}", styles["Normal"]))
    el.append(Spacer(1, 14))

    total_revenue = sum(r[4] for r in rows)
    total_profit  = sum(r[5] for r in rows)
    avg_margin    = round((total_profit / total_revenue * 100), 1) if total_revenue > 0 else 0

    summary_data = [
        ["Liczba transakcji", "Łączny przychód", "Łączny zysk", "Średnia marża"],
        [str(len(rows)), f"{total_revenue:,.2f} $", f"{total_profit:,.2f} $", f"{avg_margin}%"]
    ]
    st = Table(summary_data, colWidths=[110, 130, 110, 110])
    st.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), rl_colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",  (0,0), (-1,0), rl_colors.white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("BACKGROUND", (0,1), (-1,1), rl_colors.HexColor("#eaf4fb")),
        ("FONTNAME",   (0,1), (-1,1), "Helvetica-Bold"),
        ("GRID",       (0,0), (-1,-1), 0.5, rl_colors.grey),
        ("PADDING",    (0,0), (-1,-1), 6),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
    ]))
    el.append(st)
    el.append(Spacer(1, 16))

    el.append(Paragraph("<b>Szczegółowe zestawienie transakcji:</b>", styles["Heading3"]))
    el.append(Spacer(1, 6))

    header = ["Data", "Pojazd", "Klient", "Pracownik", "Cena ($)", "Zysk ($)", "Marża (%)"]
    table_data = [header]
    for r in rows:
        purchase = r[6] or 0
        marza = round((r[5] / purchase * 100), 1) if purchase > 0 else 0.0
        table_data.append([
            r[0], r[1], r[2] or "-", r[3] or "-",
            f"{r[4]:,.2f}", f"{r[5]:,.2f}", f"{marza}%"
        ])

    t = Table(table_data, colWidths=[60, 130, 90, 90, 65, 65, 60])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0),  rl_colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",    (0,0), (-1,0),  rl_colors.white),
        ("FONTNAME",     (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [rl_colors.white, rl_colors.HexColor("#f5f5f5")]),
        ("GRID",         (0,0), (-1,-1), 0.4, rl_colors.grey),
        ("PADDING",      (0,0), (-1,-1), 4),
    ]))
    el.append(t)

    doc.build(el)
    messagebox.showinfo("PDF", f"Raport zapisany:\n{fp}")


# ── KALKULATOR MARŻY ──────────────────────────────────────────────────────────

def margin_calculator():
    win = tk.Toplevel(root); win.title("Kalkulator marży"); win.geometry("300x210")
    ttk.Label(win,text="Cena zakupu ($):").grid(row=0,column=0,padx=10,pady=8,sticky="w")
    ttk.Label(win,text="Cena sprzedaży ($):").grid(row=1,column=0,padx=10,pady=8,sticky="w")
    buy_var=tk.StringVar(); sell_var=tk.StringVar()
    ttk.Entry(win,textvariable=buy_var,width=16).grid(row=0,column=1,padx=10,pady=8)
    ttk.Entry(win,textvariable=sell_var,width=16).grid(row=1,column=1,padx=10,pady=8)
    res=ttk.Label(win,text="",font=("Arial",12,"bold")); res.grid(row=3,column=0,columnspan=2,pady=10)
    def calc():
        try:
            buy=float(buy_var.get()); sell=float(sell_var.get())
            profit=sell-buy; margin=(profit/buy*100) if buy>0 else 0
            res.config(text=f"Zysk: {profit:,.2f} $\nMarża: {margin:.1f}%",
                       foreground="green" if profit>=0 else "red")
        except ValueError:
            res.config(text="Podaj poprawne wartości.",foreground="red")
    ttk.Button(win,text="Oblicz",command=calc).grid(row=2,column=0,columnspan=2,pady=5)

# ── PDF: FAKTURA ──────────────────────────────────────────────────────────────

def generate_invoice_pdf(tid):
    conn=db()
    row=conn.execute('''
        SELECT t.id, t.date, t.sale_price, t.notes,
               c.car_make||' '||c.car_model||' ('||c.year||')', c.color, c.mileage,
               cu.name, cu.phone, cu.email, cu.address,
               e.name
        FROM transactions t
        LEFT JOIN cars      c  ON t.car_id=c.id
        LEFT JOIN customers cu ON t.customer_id=cu.id
        LEFT JOIN employees e  ON t.employee_id=e.id
        WHERE t.id=?''',(tid,)).fetchone()
    conn.close()
    if not row:
        messagebox.showerror("Błąd","Nie znaleziono transakcji."); return

    fp=filedialog.asksaveasfilename(defaultextension=".pdf",
                                    filetypes=[("PDF","*.pdf")],
                                    initialfile=f"faktura_{tid}.pdf")
    if not fp: return

    doc=SimpleDocTemplate(fp,pagesize=A4)
    styles=getSampleStyleSheet()
    el=[]
    el.append(Paragraph(f"<b>{SALON_NAME}</b>",styles["Title"]))
    el.append(Spacer(1,10))
    el.append(Paragraph(f"<b>FAKTURA NR F/{row[0]}/{str(row[1])[:4]}</b>",styles["Heading2"]))
    el.append(Paragraph(f"Data wystawienia: {row[1]}",styles["Normal"]))
    el.append(Spacer(1,14))

    el.append(Paragraph("<b>Nabywca:</b>",styles["Heading3"]))
    for line in [row[7],row[8],row[9],row[10]]:
        if line: el.append(Paragraph(str(line),styles["Normal"]))
    el.append(Spacer(1,14))

    el.append(Paragraph("<b>Sprzedawca:</b>",styles["Heading3"]))
    el.append(Paragraph(str(row[11]) if row[11] else "-",styles["Normal"]))
    el.append(Spacer(1,14))

    data=[
        ["Pojazd","Kolor","Przebieg","Cena sprzedaży"],
        [row[4], str(row[5]), f"{row[6]:,.0f} km", f"{row[2]:,.2f} $"]
    ]
    t=Table(data,colWidths=[200,80,90,110])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),rl_colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",(0,0),(-1,0),rl_colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[rl_colors.white,rl_colors.HexColor("#f5f5f5")]),
        ("GRID",(0,0),(-1,-1),0.5,rl_colors.grey),
        ("PADDING",(0,0),(-1,-1),6),
    ]))
    el.append(t)
    el.append(Spacer(1,20))
    el.append(Paragraph(f"<b>Łączna kwota: {row[2]:,.2f} $</b>",styles["Heading2"]))
    if row[3]:
        el.append(Spacer(1,10))
        el.append(Paragraph(f"Notatki: {row[3]}",styles["Normal"]))

    doc.build(el)
    messagebox.showinfo("PDF",f"Faktura zapisana:\n{fp}")

# ── MAIN ──────────────────────────────────────────────────────────────────────

init_db()
import_csv()

root = tk.Tk()
root.title(f"{SALON_NAME} – System Zarządzania")
root.geometry("1150x680")
root.minsize(900, 550)

style = ttk.Style()
style.theme_use("clam")

nb = ttk.Notebook(root)
nb.pack(fill="both", expand=True, padx=4, pady=4)

refresh_vehicles_cb = make_vehicles_tab(nb)
make_customers_tab(nb)
make_employees_tab(nb)
make_sales_tab(nb)
make_reminders_tab(nb)
make_reports_tab(nb)
make_charts_tab(nb)
make_prediction_tab(nb)


def check_overdue():
    today = datetime.today().strftime("%Y-%m-%d")
    conn = db()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM reminders WHERE done=0 AND due_date < ?", (today,)
    ).fetchone()[0]
    conn.close()
    if cnt > 0:
        messagebox.showwarning(
            "Przeterminowane przypomnienia",
            f"Masz {cnt} przeterminowane przypomnienie(a)!\n"
            "Sprawdź zakładkę 'Przypomnienia'.")


root.after(600, check_overdue)
root.mainloop()
