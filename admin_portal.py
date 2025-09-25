import streamlit as st
import requests
import pandas as pd
from database import (
    init_database, get_all_files, get_file_stats, 
    get_files_by_order, get_file_by_order_line
)
import os

# Configure Streamlit page
st.set_page_config(
    page_title="SVG to PDF Converter Admin",
    page_icon="📄",
    layout="wide"
)

    # API base URL (Flask app running on same container)
API_BASE_URL = "http://127.0.0.1:5000"

def format_file_size(size_bytes):
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f}{size_names[i]}"

def main():
    st.title("📄 SVG to PDF Converter Admin Portal")
    
    # Initialize database
    init_database()
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Choose a page", [
        "Dashboard",
        "Upload File",
        "Search Files",
        "File Management"
    ])
    
    if page == "Dashboard":
        show_dashboard()
    elif page == "Upload File":
        show_upload_page()
    elif page == "Search Files":
        show_search_page()
    elif page == "File Management":
        show_file_management()

def show_dashboard():
    st.header("📊 Dashboard")
    
    # Get statistics
    stats = get_file_stats()
    if stats:
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Files", stats['total_files'] or 0)
        with col2:
            st.metric("Converted", stats['converted_files'] or 0)
        with col3:
            st.metric("Pending", stats['pending_files'] or 0)
        with col4:
            st.metric("Errors", stats['error_files'] or 0)
        with col5:
            st.metric("Total Size", format_file_size(stats['total_size'] or 0))
    
    st.divider()
    
    # Recent files
    st.subheader("Recent Files")
    recent_files = get_all_files(limit=10, offset=0)
    
    if recent_files:
        df_data = []
        for file_record in recent_files:
            df_data.append({
                "Order #": file_record['order_number'],
                "Line #": file_record['line_number'],
                "Filename": file_record['original_filename'],
                "Status": file_record['status'],
                "Size": format_file_size(file_record['file_size'] or 0),
                "Created": file_record['created_at'],
                "Converted": file_record['converted_at'] or "N/A"
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No files uploaded yet.")

def show_upload_page():
    st.header("📤 Upload SVG File")
    
    with st.form("upload_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            order_number = st.number_input(
                "Order Number (6 digits)", 
                min_value=100000, 
                max_value=999999,
                step=1,
                help="Enter a 6-digit order number"
            )
        
        with col2:
            line_number = st.number_input(
                "Line Number (1-999)", 
                min_value=1, 
                max_value=999,
                step=1,
                help="Enter line number between 1 and 999"
            )
        
        uploaded_file = st.file_uploader(
            "Choose an SVG file",
            type=['svg'],
            help="Select an SVG file to upload and convert to PDF"
        )
        
        submitted = st.form_submit_button("Upload and Convert", type="primary")
        
        if submitted:
            if uploaded_file is not None and order_number and line_number:
                # Check if file already exists
                existing_file = get_file_by_order_line(order_number, line_number)
                if existing_file:
                    st.error(f"A file already exists for Order #{order_number}, Line #{line_number}")
                else:
                    # Prepare the upload
                    files = {'file': uploaded_file}
                    data = {
                        'order_number': order_number,
                        'line_number': line_number
                    }
                    
                    try:
                        with st.spinner("Uploading and converting..."):
                            response = requests.post(
                                f"{API_BASE_URL}/upload",
                                files=files,
                                data=data
                            )
                        
                        if response.status_code == 201:
                            result = response.json()
                            st.success(f"✅ File uploaded and converted successfully!")
                            st.json(result)
                        else:
                            error_data = response.json()
                            st.error(f"❌ Upload failed: {error_data.get('error', 'Unknown error')}")
                    
                    except requests.exceptions.ConnectionError:
                        st.error("❌ Cannot connect to the API server. Please ensure the service is running.")
                    except Exception as e:
                        st.error(f"❌ An error occurred: {str(e)}")
            else:
                st.warning("Please fill in all fields and select a file.")

def show_search_page():
    st.header("🔍 Search Files")
    
    search_type = st.radio(
        "Search by:",
        ["Order and Line Number", "Order Number Only"]
    )
    
    if search_type == "Order and Line Number":
        col1, col2 = st.columns(2)
        with col1:
            search_order = st.number_input("Order Number", min_value=100000, max_value=999999, step=1, key="search_order_line")
        with col2:
            search_line = st.number_input("Line Number", min_value=1, max_value=999, step=1, key="search_line")
        
        if st.button("Search", key="search_order_line_btn"):
            if search_order and search_line:
                file_record = get_file_by_order_line(search_order, search_line)
                if file_record:
                    display_file_details(file_record)
                    
                    # Download buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Download SVG"):
                            download_file(search_order, search_line, 'svg')
                    with col2:
                        if file_record['pdf_path'] and st.button("Download PDF"):
                            download_file(search_order, search_line, 'pdf')
                else:
                    st.warning("No file found with these criteria.")
    
    else:  # Order Number Only
        search_order_only = st.number_input("Order Number", min_value=100000, max_value=999999, step=1, key="search_order_only")
        
        if st.button("Search", key="search_order_only_btn"):
            if search_order_only:
                files = get_files_by_order(search_order_only)
                if files:
                    st.success(f"Found {len(files)} file(s) for Order #{search_order_only}")
                    
                    df_data = []
                    for file_record in files:
                        df_data.append({
                            "Line #": file_record['line_number'],
                            "Filename": file_record['original_filename'],
                            "Status": file_record['status'],
                            "Size": format_file_size(file_record['file_size'] or 0),
                            "Created": file_record['created_at'],
                            "PDF Available": "✅" if file_record['pdf_path'] else "❌"
                        })
                    
                    df = pd.DataFrame(df_data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.warning("No files found for this order number.")

def show_file_management():
    st.header("📁 File Management")
    
    # Pagination controls
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        page = st.number_input("Page", min_value=1, value=1, step=1)
    with col2:
        per_page = st.selectbox("Files per page", [10, 25, 50, 100], index=1)
    
    # Get files
    offset = (page - 1) * per_page
    files = get_all_files(limit=per_page, offset=offset)
    
    if files:
        st.info(f"Showing files {offset + 1}-{offset + len(files)}")
        
        for file_record in files:
            with st.expander(f"Order #{file_record['order_number']}, Line #{file_record['line_number']} - {file_record['original_filename']}"):
                display_file_details(file_record)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button(f"Download SVG", key=f"svg_{file_record['id']}"):
                        download_file(file_record['order_number'], file_record['line_number'], 'svg')
                with col2:
                    if file_record['pdf_path'] and st.button(f"Download PDF", key=f"pdf_{file_record['id']}"):
                        download_file(file_record['order_number'], file_record['line_number'], 'pdf')
    else:
        st.info("No files found.")

def display_file_details(file_record):
    """Display file details in a formatted way."""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**Order Number:**", file_record['order_number'])
        st.write("**Line Number:**", file_record['line_number'])
        st.write("**Original Filename:**", file_record['original_filename'])
    
    with col2:
        st.write("**Status:**", file_record['status'])
        st.write("**File Size:**", format_file_size(file_record['file_size'] or 0))
        st.write("**PDF Available:**", "✅ Yes" if file_record['pdf_path'] else "❌ No")
    
    with col3:
        st.write("**Created:**", file_record['created_at'])
        st.write("**Converted:**", file_record['converted_at'] or "Not converted")

def download_file(order_number, line_number, file_type):
    """Download file through API."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/download/{order_number}/{line_number}/{file_type}"
        )
        
        if response.status_code == 200:
            # Create download button with file content
            filename = f"{order_number}_{line_number}.{file_type}"
            st.download_button(
                label=f"💾 Download {file_type.upper()}",
                data=response.content,
                file_name=filename,
                mime="application/octet-stream"
            )
        else:
            error_data = response.json()
            st.error(f"Download failed: {error_data.get('error', 'Unknown error')}")
    
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to the API server.")
    except Exception as e:
        st.error(f"Download error: {str(e)}")

if __name__ == "__main__":
    main()
