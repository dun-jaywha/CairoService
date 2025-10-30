#!/usr/bin/env python3
"""
Development setup script for SVG to PDF Converter
Run this to initialize directories and database for local development
"""

import os
from database import init_database

def setup_directories():
    """Create necessary directories for local development."""
    directories = ['uploads', 'converted', 'data']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ Created directory: {directory}")
        else:
            print(f"📁 Directory already exists: {directory}")

def setup_database():
    """Initialize the SQLite database."""
    try:
        init_database()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

def main():
    print("🚀 Setting up SVG to PDF Converter for local development...")
    print()
    
    # Create directories
    setup_directories()
    print()
    
    # Initialize database
    setup_database()
    print()
    
    print("✅ Setup complete!")
    print()
    print("To run the services:")
    print("1. Flask API:      python app.py")
    print("2. Streamlit:      streamlit run admin_portal.py")
    print()
    print("Access points:")
    print("- Flask API:       http://localhost:5000")
    print("- Health Check:    http://localhost:5000/health")
    print("- Streamlit Admin: http://localhost:8501")

if __name__ == "__main__":
    main()