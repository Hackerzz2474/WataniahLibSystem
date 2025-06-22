import sqlite3

def create_db():
    conn = sqlite3.connect("library.db")
    cursor = conn.cursor()

    # Create the books table if it doesn't exist
    cursor.execute('''
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
    ''')

    # Ensure all required columns exist
    cursor.execute("PRAGMA table_info(books)")
    existing_columns = [col[1] for col in cursor.fetchall()]

    required_columns = {
        "isbn": "TEXT",
        "genre": "TEXT DEFAULT 'Unknown'",
        "status": "TEXT DEFAULT 'Available'",
        "borrower": "TEXT",
        "class": "TEXT",
        "borrow_date": "TEXT",
        "due_date": "TEXT",
        "returned_date": "TEXT"
    }

    for column, col_type in required_columns.items():
        if column not in existing_columns:
            cursor.execute(f"ALTER TABLE books ADD COLUMN {column} {col_type}")

    conn.commit()
    conn.close()
    print("✅ Database created or updated successfully.")

if __name__ == "__main__":
    create_db()
