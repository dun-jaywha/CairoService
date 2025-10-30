#!/usr/bin/env python3
"""
Database Migration Script
Migrates existing database to support sequence numbers for duplicate files
"""

import sqlite3
import os
import sys
from datetime import datetime

DATABASE_PATH = os.getenv('DATABASE_PATH', 'C:\\SVGData\\files.db')

def backup_database():
    """Create a backup of the database before migration."""
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ Database not found at {DATABASE_PATH}")
        return False
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{DATABASE_PATH}.backup_{timestamp}"
    
    try:
        # Copy database file
        import shutil
        shutil.copy2(DATABASE_PATH, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False

def check_if_migration_needed():
    """Check if the database needs migration."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Check if sequence_number column exists
        cursor.execute("PRAGMA table_info(files)")
        columns = [col[1] for col in cursor.fetchall()]
        
        conn.close()
        
        if 'sequence_number' in columns:
            print("ℹ️  Database already has sequence_number column")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return False

def migrate_database():
    """Perform the database migration."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        print("\n🔄 Starting migration...")
        
        # Step 1: Add sequence_number column
        print("  1. Adding sequence_number column...")
        try:
            cursor.execute("ALTER TABLE files ADD COLUMN sequence_number INTEGER DEFAULT 1")
            print("     ✅ Column added")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("     ℹ️  Column already exists")
            else:
                raise
        
        # Step 2: Set all existing records to sequence 1
        print("  2. Setting existing records to sequence 1...")
        cursor.execute("UPDATE files SET sequence_number = 1 WHERE sequence_number IS NULL")
        updated_rows = cursor.rowcount
        print(f"     ✅ Updated {updated_rows} records")
        
        # Step 3: Drop old unique constraint if it exists
        print("  3. Removing old constraints...")
        try:
            # SQLite doesn't support DROP CONSTRAINT directly, need to recreate table
            # First, check if the old constraint exists
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='files'")
            old_schema = cursor.fetchone()[0]
            
            if "UNIQUE(order_number, line_number)" in old_schema and "sequence_number" not in old_schema:
                print("     ℹ️  Old constraint found, recreating table...")
                
                # Create temporary table with new schema
                cursor.execute('''
                    CREATE TABLE files_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_number INTEGER NOT NULL,
                        line_number INTEGER NOT NULL,
                        sequence_number INTEGER DEFAULT 1,
                        original_filename TEXT NOT NULL,
                        svg_path TEXT NOT NULL,
                        pdf_path TEXT,
                        status TEXT DEFAULT 'uploaded',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        converted_at TIMESTAMP,
                        file_size INTEGER,
                        UNIQUE(order_number, line_number, sequence_number)
                    )
                ''')
                
                # Copy data
                cursor.execute('''
                    INSERT INTO files_new 
                    SELECT id, order_number, line_number, sequence_number, 
                           original_filename, svg_path, pdf_path, status, 
                           created_at, converted_at, file_size
                    FROM files
                ''')
                
                # Drop old table
                cursor.execute("DROP TABLE files")
                
                # Rename new table
                cursor.execute("ALTER TABLE files_new RENAME TO files")
                
                print("     ✅ Table recreated with new constraint")
            else:
                print("     ℹ️  Table already has correct schema")
        except Exception as e:
            print(f"     ⚠️  Warning: {e}")
        
        # Step 4: Create new indexes
        print("  4. Creating indexes...")
        try:
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_order_line 
                ON files (order_number, line_number)
            ''')
            print("     ✅ Created idx_order_line")
        except Exception as e:
            print(f"     ℹ️  {e}")
        
        try:
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_order_line_seq
                ON files (order_number, line_number, sequence_number)
            ''')
            print("     ✅ Created idx_order_line_seq")
        except Exception as e:
            print(f"     ℹ️  {e}")
        
        # Commit changes
        conn.commit()
        
        # Step 5: Verify migration
        print("  5. Verifying migration...")
        cursor.execute("SELECT COUNT(*) FROM files WHERE sequence_number IS NULL")
        null_count = cursor.fetchone()[0]
        
        if null_count > 0:
            print(f"     ⚠️  Warning: {null_count} records still have NULL sequence_number")
        else:
            print("     ✅ All records have sequence numbers")
        
        cursor.execute("SELECT COUNT(*) FROM files")
        total_count = cursor.fetchone()[0]
        print(f"     ℹ️  Total records: {total_count}")
        
        conn.close()
        
        print("\n✅ Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        conn.close()
        return False

def show_migration_summary():
    """Show summary of migrated data."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("\n📊 Migration Summary:")
        print("-" * 50)
        
        # Total files
        cursor.execute("SELECT COUNT(*) as count FROM files")
        total = cursor.fetchone()['count']
        print(f"Total files: {total}")
        
        # Files by sequence
        cursor.execute('''
            SELECT sequence_number, COUNT(*) as count 
            FROM files 
            GROUP BY sequence_number 
            ORDER BY sequence_number
        ''')
        print("\nFiles by sequence number:")
        for row in cursor.fetchall():
            print(f"  Sequence {row['sequence_number']}: {row['count']} file(s)")
        
        # Orders with multiple sequences
        cursor.execute('''
            SELECT order_number, line_number, COUNT(*) as versions
            FROM files
            GROUP BY order_number, line_number
            HAVING COUNT(*) > 1
            ORDER BY order_number, line_number
        ''')
        
        duplicates = cursor.fetchall()
        if duplicates:
            print(f"\n⚠️  Found {len(duplicates)} order/line combinations with multiple versions:")
            for dup in duplicates[:10]:  # Show first 10
                print(f"  Order {dup['order_number']}, Line {dup['line_number']}: {dup['versions']} versions")
            if len(duplicates) > 10:
                print(f"  ... and {len(duplicates) - 10} more")
        else:
            print("\nℹ️  No duplicate order/line combinations found")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error generating summary: {e}")

def main():
    """Main migration function."""
    print("=" * 50)
    print("SVG to PDF Converter - Database Migration")
    print("Adding sequence number support for duplicates")
    print("=" * 50)
    print()
    
    # Check if database exists
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ Database not found at: {DATABASE_PATH}")
        print("   Nothing to migrate.")
        return
    
    print(f"📁 Database location: {DATABASE_PATH}")
    
    # Check if migration is needed
    if not check_if_migration_needed():
        print("\n✅ Database is already up to date!")
        show_migration_summary()
        return
    
    print("\n⚠️  This will modify your database structure.")
    print("   A backup will be created automatically.")
    
    # Ask for confirmation
    response = input("\nProceed with migration? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("\n❌ Migration cancelled by user.")
        return
    
    # Create backup
    print()
    if not backup_database():
        print("\n❌ Cannot proceed without backup. Migration cancelled.")
        return
    
    # Perform migration
    print()
    if migrate_database():
        show_migration_summary()
        print("\n🎉 Migration successful!")
        print("\nYou can now:")
        print("  1. Upload duplicate files for the same order/line")
        print("  2. Access different versions using sequence numbers")
        print("  3. Use the new API endpoints for version management")
    else:
        print("\n❌ Migration failed. Please check the errors above.")
        print("   Your original database is backed up.")
        sys.exit(1)

if __name__ == "__main__":
    main()