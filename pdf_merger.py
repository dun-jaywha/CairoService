"""
PDF Merger Module
Handles merging multiple PDF files from the same order
"""

import os
from PyPDF2 import PdfMerger, PdfReader
from database import get_files_by_order, get_file_by_order_line
from typing import List, Dict, Tuple


def get_order_summary(order_number: int) -> Dict:
    """
    Get a summary of all files for an order number.
    
    Args:
        order_number: The 6-digit order number
        
    Returns:
        Dictionary containing order summary with available and missing line items
    """
    files = get_files_by_order(order_number)
    
    if not files:
        return {
            "order_number": order_number,
            "total_files": 0,
            "available_pdfs": [],
            "missing_pdfs": [],
            "all_line_numbers": []
        }
    
    available_pdfs = []
    missing_pdfs = []
    
    for file_record in files:
        line_info = {
            "line_number": file_record['line_number'],
            "filename": file_record['original_filename'],
            "status": file_record['status'],
            "pdf_path": file_record['pdf_path']
        }
        
        if file_record['pdf_path'] and os.path.exists(file_record['pdf_path']):
            available_pdfs.append(line_info)
        else:
            missing_pdfs.append(line_info)
    
    # Sort by line number
    available_pdfs.sort(key=lambda x: x['line_number'])
    missing_pdfs.sort(key=lambda x: x['line_number'])
    
    all_line_numbers = sorted([f['line_number'] for f in files])
    
    return {
        "order_number": order_number,
        "total_files": len(files),
        "available_pdfs": available_pdfs,
        "missing_pdfs": missing_pdfs,
        "all_line_numbers": all_line_numbers,
        "available_count": len(available_pdfs),
        "missing_count": len(missing_pdfs)
    }


def validate_pdf_files(pdf_paths: List[str]) -> Tuple[List[str], List[str]]:
    """
    Validate that PDF files exist and are readable.
    
    Args:
        pdf_paths: List of PDF file paths
        
    Returns:
        Tuple of (valid_paths, invalid_paths)
    """
    valid_paths = []
    invalid_paths = []
    
    for pdf_path in pdf_paths:
        if not os.path.exists(pdf_path):
            invalid_paths.append(pdf_path)
            continue
            
        try:
            # Try to open and read the PDF to verify it's valid
            reader = PdfReader(pdf_path)
            if len(reader.pages) > 0:
                valid_paths.append(pdf_path)
            else:
                invalid_paths.append(pdf_path)
        except Exception as e:
            print(f"Invalid PDF {pdf_path}: {e}")
            invalid_paths.append(pdf_path)
    
    return valid_paths, invalid_paths


def merge_pdfs_by_order(order_number: int, line_numbers: List[int] = None, 
                        output_path: str = None) -> Tuple[bool, str, str]:
    """
    Merge all PDFs for a given order number.
    
    Args:
        order_number: The 6-digit order number
        line_numbers: Optional list of specific line numbers to merge (in order)
        output_path: Optional custom output path
        
    Returns:
        Tuple of (success: bool, output_path: str, error_message: str)
    """
    try:
        # Get order summary
        summary = get_order_summary(order_number)
        
        if summary['total_files'] == 0:
            return False, "", f"No files found for order number {order_number}"
        
        if summary['available_count'] == 0:
            return False, "", "No PDF files available to merge"
        
        # Determine which PDFs to merge
        if line_numbers:
            # User specified specific line numbers in a specific order
            pdfs_to_merge = []
            for line_num in line_numbers:
                found = False
                for pdf_info in summary['available_pdfs']:
                    if pdf_info['line_number'] == line_num:
                        pdfs_to_merge.append(pdf_info)
                        found = True
                        break
                if not found:
                    return False, "", f"Line number {line_num} not found or PDF not available"
        else:
            # Merge all available PDFs in line number order
            pdfs_to_merge = summary['available_pdfs']
        
        # Extract PDF paths
        pdf_paths = [pdf['pdf_path'] for pdf in pdfs_to_merge]
        
        # Validate PDFs
        valid_paths, invalid_paths = validate_pdf_files(pdf_paths)
        
        if invalid_paths:
            invalid_lines = [pdf['line_number'] for pdf in pdfs_to_merge 
                           if pdf['pdf_path'] in invalid_paths]
            return False, "", f"Invalid or corrupted PDFs for line numbers: {invalid_lines}"
        
        if not valid_paths:
            return False, "", "No valid PDFs found to merge"
        
        # Set output path
        if not output_path:
            output_dir = os.getenv('CONVERTED_FOLDER', './converted')
            output_filename = f"merged_{order_number}.pdf"
            output_path = os.path.join(output_dir, output_filename)
        
        # Perform the merge
        merger = PdfMerger()
        
        for pdf_path in valid_paths:
            merger.append(pdf_path)
        
        # Write the merged PDF
        merger.write(output_path)
        merger.close()
        
        return True, output_path, ""
        
    except Exception as e:
        return False, "", f"Error merging PDFs: {str(e)}"


def merge_specific_pdfs(order_number: int, line_numbers: List[int], 
                       output_path: str = None) -> Tuple[bool, str, str]:
    """
    Merge specific PDFs by order number and line numbers in the specified order.
    
    Args:
        order_number: The 6-digit order number
        line_numbers: List of line numbers to merge in the specified order
        output_path: Optional custom output path
        
    Returns:
        Tuple of (success: bool, output_path: str, error_message: str)
    """
    return merge_pdfs_by_order(order_number, line_numbers, output_path)


def get_pdf_page_count(pdf_path: str) -> int:
    """
    Get the number of pages in a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Number of pages, or 0 if error
    """
    try:
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return 0


def get_merge_preview(order_number: int, line_numbers: List[int] = []) -> Dict:
    """
    Get a preview of what will be merged without actually merging.
    
    Args:
        order_number: The 6-digit order number
        line_numbers: Optional list of specific line numbers
        
    Returns:
        Dictionary with merge preview information
    """
    summary = get_order_summary(order_number)
    
    if line_numbers is not [] and len(line_numbers) > 0:
        pdfs_to_merge = [pdf for pdf in summary['available_pdfs'] 
                        if pdf['line_number'] in line_numbers]
        # Sort by the order specified in line_numbers
        pdfs_to_merge.sort(key=lambda x: line_numbers.index(x['line_number']))
    else:
        pdfs_to_merge = summary['available_pdfs']
    
    total_pages = 0
    merge_details = []
    
    for pdf in pdfs_to_merge:
        pages = get_pdf_page_count(pdf['pdf_path'])
        total_pages += pages
        merge_details.append({
            "line_number": pdf['line_number'],
            "filename": pdf['filename'],
            "pages": pages
        })
    
    return {
        "order_number": order_number,
        "files_to_merge": len(merge_details),
        "total_pages": total_pages,
        "merge_details": merge_details,
        "missing_pdfs": summary['missing_pdfs']
    }