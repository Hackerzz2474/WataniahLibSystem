import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
import sqlite3
from datetime import datetime

# === DATABASE FUNCTIONS ===
def run_query(query, params=()):
    conn = sqlite3.connect("library.db")
    cursor = conn.cursor()
    cursor.execute(query, params)
    data = cursor.fetchall()
    conn.commit()
    conn.close()
    return data

def create_db():
    run_query("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT,
            genre TEXT DEFAULT 'Unknown',
            status TEXT DEFAULT 'Available',
            borrower TEXT,
            class TEXT,
            borrow_date TEXT,
            due_date TEXT,
            returned_date TEXT
        )
    """)

create_db()

# === MAIN FUNCTIONS ===
def add_book():
    title = entries["title"].get()
    author = entries["author"].get()
    isbn = entries["isbn"].get()
    genre = entries["genre"].get()

    if not title or not author:
        messagebox.showwarning("Missing Info", "Title and Author are required.")
        return

    run_query("INSERT INTO books (title, author, isbn, genre) VALUES (?, ?, ?, ?)",
              (title, author, isbn, genre))
    refresh_tabs()

def delete_book():
    for tree in treeviews.values():
        selected = tree.selection()
        if selected:
            book_id = tree.item(selected[0])["values"][0]
            run_query("DELETE FROM books WHERE id=?", (book_id,))
            break

    if run_query("SELECT COUNT(*) FROM books")[0][0] == 0:
        run_query("DELETE FROM sqlite_sequence WHERE name='books'")
    refresh_tabs()

def open_borrow_tab():
    for tab in notebook.tabs():
        if notebook.tab(tab, "text") == "Borrowing":
            notebook.select(tab)
            return

    borrow_tab = ttk.Frame(notebook)
    notebook.add(borrow_tab, text="Borrowing")
    notebook.select(borrow_tab)

    tk.Label(borrow_tab, text="Borrower").grid(row=0, column=0, padx=5, pady=5)
    borrower_entry = tk.Entry(borrow_tab)
    borrower_entry.grid(row=0, column=1)

    tk.Label(borrow_tab, text="Class").grid(row=0, column=2, padx=5, pady=5)
    class_entry = tk.Entry(borrow_tab)
    class_entry.grid(row=0, column=3)

    tk.Label(borrow_tab, text="Due Date").grid(row=0, column=4, padx=5, pady=5)
    borrow_due_date = DateEntry(borrow_tab, width=15, date_pattern="yyyy-mm-dd")
    borrow_due_date.grid(row=0, column=5)

    # Define which columns to show in the Borrowing tab
    borrow_columns = (
        "ID", "Title", "Author", "ISBN", "Genre", "Status"
    )

    borrow_tree = ttk.Treeview(borrow_tab, columns=borrow_columns, show="headings", height=10)

    global temp_borrow_tree
    temp_borrow_tree = borrow_tree

    # Column styling
    column_widths = {
        "ID": 50,
        "Title": 180,
        "Author": 150,
        "ISBN": 120,
        "Genre": 100,
        "Status": 120
    }

    for col in borrow_columns:
        borrow_tree.heading(col, text=col)
        borrow_tree.column(col, width=column_widths.get(col, 100), anchor="center")

    borrow_tree.grid(row=1, column=0, columnspan=6, padx=10, pady=10)

    available_books = run_query("""
        SELECT * FROM books 
        WHERE status='Available' OR (status='Returned' AND id NOT IN 
            (SELECT id FROM books WHERE status='Borrowed'))
    """)

    for row in available_books:
        row = list(row)  # convert to mutable list
        row[5] = "Available"  # Ensure status is explicitly shown
        borrow_tree.insert("", "end", values=row)

    def confirm_borrow():
        borrower = borrower_entry.get()
        class_ = class_entry.get()
        if not borrower or not class_:
            messagebox.showwarning("Missing Info", "Borrower name and class required.")
            return

        selected = borrow_tree.selection()
        if len(selected) > 3:
            messagebox.showwarning("Limit", "Only 3 books can be borrowed.")
            return

        current_count = run_query("SELECT COUNT(*) FROM books WHERE borrower=? AND status='Borrowed'", (borrower,))[0][0]
        if current_count + len(selected) > 3:
            messagebox.showwarning("Limit", f"{borrower} already has {current_count} book(s) borrowed.")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        due = borrow_due_date.get_date().strftime("%Y-%m-%d")
        for sel in selected:
            book_id = borrow_tree.item(sel)["values"][0]
            run_query("""UPDATE books SET status='Borrowed', borrower=?, class=?, 
                         borrow_date=?, due_date=?, returned_date=NULL WHERE id=?""",
                      (borrower, class_, today, due, book_id))

        notebook.forget(borrow_tab)
        refresh_tabs()

    # Confirm Borrow Button
    tk.Button(borrow_tab, text="Confirm Borrow", command=confirm_borrow).grid(row=2, column=0, columnspan=3, pady=10)

    # ❗ Add this: Close Tab Button
    def close_tab():
        notebook.forget(borrow_tab)

    tk.Button(borrow_tab, text="Close", command=close_tab).grid(row=2, column=3, columnspan=3, pady=10)


def return_book():
    selected_borrowers = set()

    for tab_name in ["Borrowed", "Overdue"]:
        for sel in treeviews[tab_name].selection():
            values = treeviews[tab_name].item(sel)["values"]
            borrower = values[6]  # Borrower name
            if borrower:
                selected_borrowers.add(borrower)

    if not selected_borrowers:
        messagebox.showinfo("No Selection", "Please select a borrower or book to return.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    for borrower in selected_borrowers:
        run_query("""
            UPDATE books 
            SET status='Returned', returned_date=? 
            WHERE borrower=? AND status='Borrowed'
        """, (today, borrower))

    refresh_tabs()

def on_group_expand(event):
    tree = event.widget
    item = tree.focus()
    tree.item(item, open=True)  # Ensures group opens

def on_group_collapse(event):
    tree = event.widget
    item = tree.focus()
    tree.item(item, open=False)  # Ensures group collapses


def refresh_tabs(filtered=False):
    for tv in treeviews.values():
        for i in tv.get_children():
            tv.delete(i)

    query = "SELECT * FROM books"
    params = ()
    if filtered and search_value.get().strip():
        field = search_field.get().lower()
        value = search_value.get().strip()
        query += f" WHERE {field} LIKE ?"
        params = ('%' + value + '%',)

    data = run_query(query, params)
    today = datetime.now().date()

    borrowed_groups, overdue_groups, returned_groups = {}, {}, {}
    available_rows = []

    for row in data:
        book = {
            "id": row[0], "title": row[1], "author": row[2], "isbn": row[3], "genre": row[4],
            "status": row[5], "borrower": row[6], "class": row[7],
            "borrow_date": row[8], "due_date": row[9], "returned_date": row[10]
        }

        fine = ""
        if book["due_date"]:
            try:
                due = datetime.strptime(book["due_date"], "%Y-%m-%d").date()
                if book["status"] == "Borrowed" and today > due:
                    fine = f"RM {round(0.20 * (today - due).days, 2)}"
                if book["returned_date"]:
                    returned = datetime.strptime(book["returned_date"], "%Y-%m-%d").date()
                    if returned > due:
                        fine = f"RM {round(0.20 * (returned - due).days, 2)}"
            except ValueError:
                fine = ""

        row_values = list(book.values()) + [fine]

        if book["status"] == "Available":
            row_values[5] = "Available"  # Ensure Status shows explicitly
            row_values[6:11] = [""] * 5  # Hide borrower info
            row_values[11] = ""  # Clear fine
            available_rows.append(row_values)



        elif book["status"] == "Borrowed":
            if fine:
                overdue_groups.setdefault((book["borrower"], book["class"]), []).append(row_values)
            else:
                borrowed_groups.setdefault((book["borrower"], book["class"]), []).append(row_values)


        elif book["status"] == "Returned":
            returned_groups.setdefault((book["borrower"], book["class"]), []).append(row_values)

            # Also add to available tab (override status to "Available")
            returned_available_row = row_values.copy()
            returned_available_row[5] = "Available"  # override status
            returned_available_row[6:11] = [""] * 5  # clear borrower info
            returned_available_row[11] = ""  # clear fine
            available_rows.append(returned_available_row)

    for row in available_rows:
        treeviews["Available"].insert("", "end", values=row)

    def insert_grouped(tree, groups, tag_name, group_label):
        for (borrower, class_), books in groups.items():
            if len(books) == 1:
                tree.insert("", "end", values=books[0])
            else:
                group_id = tree.insert("", "end", text="", open=True,
                                       values=("", f"{borrower} ({class_})", "", "", "", group_label), tags=(tag_name,))

                for book_row in books:
                    tree.insert(group_id, "end", values=book_row)

    insert_grouped(treeviews["Borrowed"], borrowed_groups, "group", "Borrowed Group")
    insert_grouped(treeviews["Overdue"], overdue_groups, "group", "Overdue Group")
    insert_grouped(treeviews["Returned"], returned_groups, "group", "Returned Group")

    # === UPDATE TEMPORARY BORROWING TAB IF OPEN ===
    try:
        if temp_borrow_tree.winfo_exists():
            for i in temp_borrow_tree.get_children():
                temp_borrow_tree.delete(i)

            borrow_query = """
                SELECT * FROM books 
                WHERE status='Available' OR (status='Returned' AND id NOT IN 
                    (SELECT id FROM books WHERE status='Borrowed'))
            """

            borrow_params = ()
            if filtered and search_value.get().strip():
                field = search_field.get().lower()
                value = search_value.get().strip()
                borrow_query += f" AND {field} LIKE ?"
                borrow_params = ('%' + value + '%',)

            available_books = run_query(borrow_query, borrow_params)

            for row in available_books:
                row = list(row)
                row[5] = "Available"
                temp_borrow_tree.insert("", "end", values=row)
    except NameError:
        pass  # Borrow tab not open, ignore    # === UPDATE TEMPORARY BORROWING TAB IF OPEN ===
    try:
        if temp_borrow_tree and temp_borrow_tree.winfo_exists():
            for i in temp_borrow_tree.get_children():
                temp_borrow_tree.delete(i)

            borrow_query = """
                SELECT * FROM books 
                WHERE (status='Available' OR (status='Returned' AND id NOT IN 
                    (SELECT id FROM books WHERE status='Borrowed')))
            """

            borrow_params = ()
            if filtered and search_value.get().strip():
                field = search_field.get().lower()
                value = search_value.get().strip()
                borrow_query += f" AND {field} LIKE ?"
                borrow_params = ('%' + value + '%',)

            available_books = run_query(borrow_query, borrow_params)

            for row in available_books:
                row = list(row)
                row[5] = "Available"  # Explicitly mark status
                temp_borrow_tree.insert("", "end", values=row)
    except:
        pass  # Borrow tab might be closed, ignore


# === COLORS AND STYLES ===
primary_color = "#2c3e50"     # Dark Blue
secondary_color = "#ecf0f1"   # Light Grey
accent_color = "#3498db"      # Blue
text_color = "#ffffff"        # White
button_color = "#2980b9"      # Button Blue
hover_color = "#1abc9c"       # Turquoise

default_font = ("Segoe UI", 10)
title_font = ("Segoe UI", 14, "bold")

# === GUI SETUP ===
root = tk.Tk()

root.option_add("*Font", default_font)
root.configure(bg=primary_color)
root.title("Library Management System")
root.geometry("1200x700")

btn_frame = tk.Frame(root, bg=primary_color)
btn_frame.pack(pady=10)

tk.Button(btn_frame, text="Add", command=add_book, bg=button_color, fg="white", width=10).pack(side=tk.LEFT, padx=5)
tk.Button(btn_frame, text="Delete", command=delete_book, bg=button_color, fg="white", width=10).pack(side=tk.LEFT, padx=5)
tk.Button(btn_frame, text="Borrow", command=open_borrow_tab, bg=button_color, fg="white", width=10).pack(side=tk.LEFT, padx=5)
tk.Button(btn_frame, text="Return", command=return_book, bg=button_color, fg="white", width=10).pack(side=tk.LEFT, padx=5)

form = tk.Frame(root)
form.pack(pady=10)

entries = {}
entry_bg = "#f0f8ff"  # Light blue-ish background
entry_fg = "#2c3e50"  # Dark text

for i, label in enumerate(["Title", "Author", "ISBN", "Genre"]):
    tk.Label(form, text=label, bg=primary_color, fg=text_color).grid(
        row=i // 2, column=(i % 2) * 2, padx=5, pady=5
    )
    entry = tk.Entry(
        form,
        bg=entry_bg,
        fg=entry_fg,
        relief="groove",
        borderwidth=2,
        insertbackground=entry_fg
    )
    entry.grid(row=i // 2, column=(i % 2) * 2 + 1, padx=5, pady=5, ipadx=5, ipady=3)
    entries[label.lower()] = entry


search_frame = tk.Frame(root)
search_frame.pack(pady=5)

search_field = tk.StringVar(value="Title")
search_value = tk.StringVar()

tk.Label(search_frame, text="Search by:").pack(side=tk.LEFT)
search_combo = ttk.Combobox(search_frame, textvariable=search_field, state="readonly",
                            values=["ID", "Title", "Author", "ISBN", "Genre", "Status", "Borrower", "Class"], width=15)
search_combo.pack(side=tk.LEFT, padx=5)

tk.Entry(search_frame, textvariable=search_value, width=30).pack(side=tk.LEFT, padx=5)

tk.Button(search_frame, text="Search", command=lambda: refresh_tabs(filtered=True),
          bg=button_color, fg="white", width=10).pack(side=tk.LEFT, padx=5)

tk.Button(search_frame, text="Clear", command=lambda: [search_value.set(""), refresh_tabs()],
          bg=button_color, fg="white", width=10).pack(side=tk.LEFT, padx=5)

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

tabs = ["Available", "Borrowed", "Overdue", "Returned"]
tab_frames = {}
treeviews = {}

columns = (
    "ID", "Title", "Author", "ISBN", "Genre", "Status",
    "Borrower", "Class", "Borrow Date", "Due Date", "Returned Date", "Fine"
)

for tab in tabs:
    frame = ttk.Frame(notebook)
    notebook.add(frame, text=tab)
    tab_frames[tab] = frame

    tree = ttk.Treeview(frame, columns=columns, show="headings", height=15)
    column_widths = {
        "ID": 50,
        "Title": 180,
        "Author": 150,
        "ISBN": 120,
        "Genre": 100,
        "Status": 130,  # Increased to fit "Borrowed Group"
        "Borrower": 130,
        "Class": 100,
        "Borrow Date": 110,
        "Due Date": 110,
        "Returned Date": 120,
        "Fine": 80
    }

    for col in columns:
        tree.heading(col, text=col, anchor="center")
        tree.column(col, width=column_widths.get(col, 100), anchor="center")

    tree.pack(fill="both", expand=True)
    treeviews[tab] = tree

    tree.bind("<<TreeviewOpen>>", on_group_expand)
    tree.bind("<<TreeviewClose>>", on_group_collapse)

# Treeview styling
style = ttk.Style()
style.theme_use("default")

style.configure("Treeview",
    background="white",
    foreground="black",
    rowheight=25,
    fieldbackground="white")

style.configure("Treeview.Heading",
    background=accent_color,
    foreground="white",
    font=("Segoe UI", 10, "bold"))

for tree in treeviews.values():
    tree.tag_configure("group", font=("Arial", 10, "bold"))


refresh_tabs()
root.mainloop()
