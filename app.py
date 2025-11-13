from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import cairosvg
import os
from werkzeug.utils import secure_filename
from database import (
    init_database, insert_file_record, update_file_conversion,
    get_file_by_order_line, get_file_by_order_line_seq,
    get_files_by_order, get_all_files, get_next_sequence_number,
    get_all_files_by_order_line, insert_merged_file_record, get_merged_file_by_order,
    get_all_merged_files_by_order, get_all_merged_files
)

app = Flask(__name__)
CORS(app, origins="http://172.21.10.139:10000", methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"])
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', os.path.abspath('uploads'))
app.config['CONVERTED_FOLDER'] = os.getenv('CONVERTED_FOLDER', os.path.abspath('converted'))

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CONVERTED_FOLDER'], exist_ok=True)

#@app.before_request
#def log_request_info():
#    print("---- Incoming Request ----")
#    print("Path:", request.path)
#    print("Method:", request.method)
#    print("Headers:", request.headers)
#    print("Body:", request.get_data(as_text=True))
#    print("--------------------------")*/

def allowed_file(filename):
    """Check if file has allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'svg'

def convert_svg_to_pdf(svg_path, pdf_path):
    """Convert SVG file to PDF using cairosvg."""
    try:
        # Read and sanitize the SVG content
        with open(svg_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        
        import re
        
        # Remove problematic onload attributes
        svg_content = re.sub(r'onload="[^"]*"', '', svg_content)
        
        # Remove percentage values from opacity in CSS
        svg_content = re.sub(r'opacity:\s*(\d+)%', lambda m: f'opacity: {int(m.group(1))/100}', svg_content)
        
        # Convert px units to plain numbers in width/height attributes
        svg_content = re.sub(r'width="([\d.]+)px"', r'width="\1"', svg_content)
        svg_content = re.sub(r'height="([\d.]+)px"', r'height="\1"', svg_content)
        
        # Try conversion with sanitized content
        try:
            cairosvg.svg2pdf(bytestring=svg_content.encode('utf-8'), write_to=pdf_path)
            print("Conversion successful after sanitization")
            return True
        except Exception as e:
            print(f"Conversion failed after sanitization: {e}")
            return False
                
    except Exception as e:
        print(f"Conversion error: {e}")
        return False

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "SVG to PDF Converter"}), 200
pass

@app.route('/images/<imgName>', methods=['GET'])
def get_image(imgName):
    """Serve static image files."""
    try:
        image_path = os.path.join('images', secure_filename(imgName))
        return send_file(image_path, mimetype='image/png'), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500   
pass

@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload SVG file and convert to PDF. Accepts either multipart form data or JSON."""
    try:
        # Determine if request is JSON or form data
        is_json = request.is_json
        # print(f"Upload method: {'JSON' if is_json else 'Multipart Form Data'}")

        if is_json:
            # Handle JSON payload with raw SVG string
            data = request.get_json()
            
            # data.get(key, default)
            svg_content = data.get('svg_content')
            order_number = data.get('order_number')
            line_number = data.get('line_number')
            drawing_type = data.get('drawing_type', 'LG')
            original_filename = data.get('filename', 'uploaded.svg')
            
            if not svg_content:
                return jsonify({"error": "svg_content is required in JSON payload"}), 400  
        else:
            # Handle multipart form data (existing logic)
            if 'file' not in request.files:
                return jsonify({"error": "No file provided"}), 400
            
            file = request.files['file']
            order_number = request.form.get('order_number')
            line_number = request.form.get('line_number')
            
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            if not allowed_file(file.filename):
                return jsonify({"error": "Only SVG files are allowed"}), 400
            
            original_filename = file.filename
            svg_content = None  # Will read from file later
        
        # Validate order_number and line_number
        if not order_number or not line_number:
            return jsonify({"error": "order_number and line_number are required"}), 400
        
        try:
            order_number = int(order_number)
            line_number = int(line_number)
        except ValueError:
            return jsonify({"error": "order_number and line_number must be integers"}), 400
        
        # Validate order_number (6 digits) and line_number (1-999)
        if not (100000 <= order_number <= 999999):
            return jsonify({"error": "order_number must be a 6-digit number"}), 400
        
        if not (1 <= line_number <= 999):
            return jsonify({"error": "line_number must be between 1 and 999"}), 400
        
        # Get next sequence number (1 for LG, 2 for U1 - will replace existing)
        sequence_number = drawing_type == 'LG' and 1 or 2
        
        # Check if file exists (for informational purposes only)
        existing_file = get_file_by_order_line_seq(order_number, line_number, sequence_number)
        is_replacement = existing_file is not None
        
        # Save SVG file
        filename = secure_filename(original_filename)
        svg_filename = f"{filename}"
        svg_path = os.path.join(app.config['UPLOAD_FOLDER'], svg_filename)
        
        if is_json:
            # Write SVG content from JSON string
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(svg_content)
        else:
            # Save uploaded file
            file.save(svg_path)
        
        # Get file size
        file_size = os.path.getsize(svg_path)
        
        # Insert record into database
        file_id = insert_file_record(order_number, line_number, filename, svg_path, file_size, sequence_number)
        
        # Convert to PDF
        pdf_filename = f"{filename.rsplit('.', 1)[0]}.pdf"
        pdf_path = os.path.join(app.config['CONVERTED_FOLDER'], pdf_filename)
        
        if convert_svg_to_pdf(svg_path, pdf_path):
            update_file_conversion(file_id, pdf_path, 'converted')
            return jsonify({
                "message": "File uploaded and converted successfully" + (" (replaced existing)" if is_replacement else ""),
                "file_id": file_id,
                "order_number": order_number,
                "line_number": line_number,
                "sequence_number": sequence_number,
                "is_replacement": is_replacement,
                "pdf_available": True,
                "upload_method": "json" if is_json else "multipart"
            }), 201
        else:
            update_file_conversion(file_id, None, 'error')
            return jsonify({
                "message": "File uploaded but conversion failed" + (" (replaced existing)" if is_replacement else ""),
                "file_id": file_id,
                "order_number": order_number,
                "line_number": line_number,
                "sequence_number": sequence_number,
                "is_replacement": is_replacement,
                "pdf_available": False,
                "upload_method": "json" if is_json else "multipart"
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/routes', methods=['GET'])
def list_routes():
    """List all available API routes."""
    routes = []
    for rule in app.url_map.iter_rules():
        if rule.methods is not None:
            methods = ','.join(rule.methods)
            routes.append({
                "endpoint": rule.endpoint,
                "methods": methods,
                "route": str(rule)
            })
        pass
    pass

    return jsonify({"routes": routes}), 200
pass

@app.route('/file/<int:order_number>/<int:line_number>', methods=['GET'])
@app.route('/file/<int:order_number>/<int:line_number>/<int:sequence_number>', methods=['GET'])
def get_file(order_number, line_number, sequence_number=None):
    """Get file information by order number, line number, and optional sequence number."""
    try:
        if sequence_number is not None:
            file_record = get_file_by_order_line_seq(order_number, line_number, sequence_number)
        else:
            file_record = get_file_by_order_line(order_number, line_number)
        
        if not file_record:
            return jsonify({"error": "File not found"}), 404
        
        return jsonify({
            "id": file_record['id'],
            "order_number": file_record['order_number'],
            "line_number": file_record['line_number'],
            "sequence_number": file_record['sequence_number'],
            "original_filename": file_record['original_filename'],
            "status": file_record['status'],
            "created_at": file_record['created_at'],
            "converted_at": file_record['converted_at'],
            "file_size": file_record['file_size'],
            "pdf_available": file_record['pdf_path'] is not None
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/files/<int:order_number>/<int:line_number>/all', methods=['GET'])
def get_all_file_versions(order_number, line_number):
    """Get all versions of files for a specific order and line number."""
    try:
        files = get_all_files_by_order_line(order_number, line_number)
        
        result = []
        for file_record in files:
            result.append({
                "id": file_record['id'],
                "order_number": file_record['order_number'],
                "line_number": file_record['line_number'],
                "sequence_number": file_record['sequence_number'],
                "original_filename": file_record['original_filename'],
                "status": file_record['status'],
                "created_at": file_record['created_at'],
                "converted_at": file_record['converted_at'],
                "file_size": file_record['file_size'],
                "pdf_available": file_record['pdf_path'] is not None
            })
        
        return jsonify({"files": result, "count": len(result)}), 200
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/download/<int:order_number>/<int:line_number>/<file_type>', methods=['GET'])
@app.route('/download/<int:order_number>/<int:line_number>/<int:sequence_number>/<file_type>', methods=['GET'])
def download_file(order_number, line_number, file_type, sequence_number=None):
    """Download SVG or PDF file."""
    try:
        if sequence_number is not None:
            file_record = get_file_by_order_line_seq(order_number, line_number, sequence_number)
        else:
            file_record = get_file_by_order_line(order_number, line_number)
        
        if not file_record:
            return jsonify({"error": "File not found"}), 404
        
        if file_type.lower() == 'svg':
            if os.path.exists(file_record['svg_path']):
                return send_file(file_record['svg_path'], as_attachment=True)
        elif file_type.lower() == 'pdf':
            if file_record['pdf_path'] and os.path.exists(file_record['pdf_path']):
                return send_file(file_record['pdf_path'], as_attachment=True)
            else:
                return jsonify({"error": "PDF not available"}), 404
        else:
            return jsonify({"error": "Invalid file type. Use 'svg' or 'pdf'"}), 400
        
        return jsonify({"error": "File not found on disk"}), 404
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/files/order/<int:order_number>', methods=['GET'])
def get_files_by_order_number(order_number):
    """Get all files for a specific order number."""
    try:
        files = get_files_by_order(order_number)
        
        result = []
        for file_record in files:
            result.append({
                "id": file_record['id'],
                "order_number": file_record['order_number'],
                "line_number": file_record['line_number'],
                "original_filename": file_record['original_filename'],
                "status": file_record['status'],
                "created_at": file_record['created_at'],
                "converted_at": file_record['converted_at'],
                "file_size": file_record['file_size'],
                "pdf_available": file_record['pdf_path'] is not None
            })
        
        return jsonify({"files": result, "count": len(result)}), 200
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/files', methods=['GET'])
def list_files():
    """List all files with pagination."""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        offset = (page - 1) * per_page
        files = get_all_files(per_page, offset)
        
        result = []
        for file_record in files:
            result.append({
                "id": file_record['id'],
                "order_number": file_record['order_number'],
                "line_number": file_record['line_number'],
                "original_filename": file_record['original_filename'],
                "status": file_record['status'],
                "created_at": file_record['created_at'],
                "converted_at": file_record['converted_at'],
                "file_size": file_record['file_size'],
                "pdf_available": file_record['pdf_path'] is not None
            })
        
        return jsonify({
            "files": result, 
            "page": page, 
            "per_page": per_page,
            "count": len(result)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/merge/<int:order_number>', methods=['POST'])
def merge_order_pdfs(order_number):
    """Merge all available PDFs for a given order number."""
    try:
        from pdf_merger import merge_pdfs_by_order
        import json
        
        # Check if request wants specific line numbers
        request_data = request.get_json() if request.is_json else {}
        specific_lines = request_data.get('line_numbers', None)
        
        # Perform the merge
        if specific_lines:
            from pdf_merger import merge_specific_pdfs
            success, output_path, error_msg = merge_specific_pdfs(order_number, specific_lines)
        else:
            success, output_path, error_msg = merge_pdfs_by_order(order_number)
        
        if not success:
            return jsonify({"error": error_msg}), 400
        
        # Get file size
        file_size = os.path.getsize(output_path)
        
        # Get the line numbers that were merged
        from pdf_merger import get_order_summary
        summary = get_order_summary(order_number)
        
        if specific_lines:
            merged_lines = specific_lines
        else:
            merged_lines = [pdf['line_number'] for pdf in summary['available_pdfs']]
        
        file_count = len(merged_lines)
        
        # Store in database
        merged_id = insert_merged_file_record(
            order_number=order_number,
            merged_pdf_path=output_path,
            file_size=file_size,
            line_numbers=merged_lines,
            file_count=file_count
        )
        
        return jsonify({
            "message": "PDFs merged successfully",
            "merged_id": merged_id,
            "order_number": order_number,
            "file_count": file_count,
            "line_numbers": merged_lines,
            "file_size": file_size,
            "download_url": f"/merged/{order_number}"
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/merged/<int:order_number>', methods=['GET'])
@app.route('/merged/<int:order_number>/<int:sequence_number>', methods=['GET'])
def get_merged_pdf_info(order_number, sequence_number=None):
    """Get information about merged PDF(s) for an order."""
    try:
        import json
        
        if sequence_number is not None:
            # Get specific version
            merged_file = get_merged_file_by_order(order_number, sequence_number)
            if not merged_file:
                return jsonify({"error": "Merged file not found"}), 404
            
            return jsonify({
                "id": merged_file['id'],
                "order_number": merged_file['order_number'],
                "sequence_number": merged_file['sequence_number'],
                "file_size": merged_file['file_size'],
                "line_numbers": json.loads(merged_file['line_numbers']),
                "file_count": merged_file['file_count'],
                "status": merged_file['status'],
                "created_at": merged_file['created_at'],
                "download_url": f"/merged/{order_number}/{sequence_number}/download"
            }), 200
        else:
            # Get all versions for this order
            merged_files = get_all_merged_files_by_order(order_number)
            if not merged_files:
                return jsonify({"error": "No merged files found for this order"}), 404
            
            result = []
            for merged_file in merged_files:
                result.append({
                    "id": merged_file['id'],
                    "order_number": merged_file['order_number'],
                    "sequence_number": merged_file['sequence_number'],
                    "file_size": merged_file['file_size'],
                    "line_numbers": json.loads(merged_file['line_numbers']),
                    "file_count": merged_file['file_count'],
                    "status": merged_file['status'],
                    "created_at": merged_file['created_at'],
                    "download_url": f"/merged/{order_number}/{merged_file['sequence_number']}/download"
                })
            
            return jsonify({
                "order_number": order_number,
                "versions": result,
                "count": len(result)
            }), 200
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/merged/<int:order_number>/download', methods=['GET'])
@app.route('/merged/<int:order_number>/<int:sequence_number>/download', methods=['GET'])
def download_merged_pdf(order_number, sequence_number=None):
    """Download merged PDF file."""
    try:
        merged_file = get_merged_file_by_order(order_number, sequence_number)
        
        if not merged_file:
            return jsonify({"error": "Merged file not found"}), 404
        
        if not os.path.exists(merged_file['merged_pdf_path']):
            return jsonify({"error": "Merged PDF file not found on disk"}), 404
        
        return send_file(
            merged_file['merged_pdf_path'],
            as_attachment=True,
            download_name=f"merged_{order_number}_v{merged_file['sequence_number']}.pdf"
        )
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/merged', methods=['GET'])
def list_merged_files():
    """List all merged files with pagination."""
    try:
        import json
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        offset = (page - 1) * per_page
        merged_files = get_all_merged_files(per_page, offset)
        
        result = []
        for merged_file in merged_files:
            result.append({
                "id": merged_file['id'],
                "order_number": merged_file['order_number'],
                "sequence_number": merged_file['sequence_number'],
                "file_size": merged_file['file_size'],
                "line_numbers": json.loads(merged_file['line_numbers']),
                "file_count": merged_file['file_count'],
                "status": merged_file['status'],
                "created_at": merged_file['created_at'],
                "download_url": f"/merged/{merged_file['order_number']}/{merged_file['sequence_number']}/download"
            })
        
        return jsonify({
            "merged_files": result,
            "page": page,
            "per_page": per_page,
            "count": len(result)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=False)