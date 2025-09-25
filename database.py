import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DATABASE_PATH = '/app/svg_pdf_converter.db'

def init_database():
    """Initialize the SQLite database with required tables."""
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        
        # Create files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number INTEGER NOT NULL,
                line_number INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                svg_path TEXT NOT NULL,
                pdf_path TEXT,
                status TEXT DEFAULT 'uploaded',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                converted_at TIMESTAMP,
                file_size INTEGER,
                UNIQUE(order_number, line_number)
            )
        ''')
        
        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_order_line 
            ON files (order_number, line_number)
        ''')
        
        conn.commit()

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
    finally:
        conn.close()

def insert_file_record(order_number, line_number, original_filename, svg_path, file_size):
    """Insert a new file record into the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO files (order_number, line_number, original_filename, svg_path, file_size)
            VALUES (?, ?, ?, ?, ?)
        ''', (order_number, line_number, original_filename, svg_path, file_size))
        conn.commit()
        return cursor.lastrowid

def update_file_conversion(file_id, pdf_path, status='converted'):
    """Update file record after successful conversion."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE files 
            SET pdf_path = ?, status = ?, converted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (pdf_path, status, file_id))
        conn.commit()

def get_file_by_order_line(order_number, line_number):
    """Retrieve file information by order number and line number."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM files 
            WHERE order_number = ? AND line_number = ?
        ''', (order_number, line_number))
        return cursor.fetchone()

def get_files_by_order(order_number):
    """Retrieve all files for a specific order number."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM files 
            WHERE order_number = ?
            ORDER BY line_number
        ''', (order_number,))
        return cursor.fetchall()

def get_all_files(limit=100, offset=0):
    """Retrieve all files with pagination."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM files 
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        return cursor.fetchall()

def get_file_stats():
    """Get basic statistics about the files."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(*) as total_files,
                COUNT(CASE WHEN status = 'converted' THEN 1 END) as converted_files,
                COUNT(CASE WHEN status = 'uploaded' THEN 1 END) as pending_files,
                COUNT(CASE WHEN status = 'error' THEN 1 END) as error_files,
                SUM(file_size) as total_size
            FROM files
        ''')
        return cursor.fetchone()

def delete_file_record(file_id):
    """Delete a file record from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM files WHERE id = ?', (file_id,))
        conn.commit()
        return cursor.rowcount > 0
