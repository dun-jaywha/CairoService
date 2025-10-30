from flask import Flask, request, jsonify, send_file
import cairosvg
import os
from werkzeug.utils import secure_filename
from database import (
    init_database, insert_file_record, update_file_conversion,
    get_file_by_order_line, get_files_by_order, get_all_files,
    get_next_sequence_number, get_all_files_by_order_line
)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', './uploads')
app.config['CONVERTED_FOLDER'] = os.getenv('CONVERTED_FOLDER', './converted')

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CONVERTED_FOLDER'], exist_ok=True)

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

@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload SVG file and convert to PDF."""
    try:
        # Validate request
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        order_number = request.form.get('order_number')
        line_number = request.form.get('line_number')
        allow_duplicate = request.form.get('allow_duplicate', 'true').lower() == 'true'
        
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
        
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": "Only SVG files are allowed"}), 400
        
        # Get next sequence number
        sequence_number = get_next_sequence_number(order_number, line_number)
        
        # Check if this would be a duplicate (sequence > 1)
        if sequence_number > 1 and not allow_duplicate:
            return jsonify({
                "error": f"File already exists for order {order_number}, line {line_number}",
                "existing_sequences": sequence_number - 1,
                "hint": "Set allow_duplicate=true to upload a new version"
            }), 409
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        svg_filename = f"{order_number}_{line_number}_seq{sequence_number}_{filename}"
        svg_path = os.path.join(app.config['UPLOAD_FOLDER'], svg_filename)
        file.save(svg_path)
        
        # Get file size
        file_size = os.path.getsize(svg_path)
        
        # Insert record into database
        file_id = insert_file_record(order_number, line_number, filename, svg_path, file_size, sequence_number)
        
        # Convert to PDF
        pdf_filename = f"{order_number}_{line_number}_seq{sequence_number}_{filename.rsplit('.', 1)[0]}.pdf"
        pdf_path = os.path.join(app.config['CONVERTED_FOLDER'], pdf_filename)
        
        if convert_svg_to_pdf(svg_path, pdf_path):
            update_file_conversion(file_id, pdf_path, 'converted')
            return jsonify({
                "message": "File uploaded and converted successfully",
                "file_id": file_id,
                "order_number": order_number,
                "line_number": line_number,
                "sequence_number": sequence_number,
                "is_duplicate": sequence_number > 1,
                "pdf_available": True
            }), 201
        else:
            update_file_conversion(file_id, None, 'error')
            return jsonify({
                "message": "File uploaded but conversion failed",
                "file_id": file_id,
                "order_number": order_number,
                "line_number": line_number,
                "sequence_number": sequence_number,
                "is_duplicate": sequence_number > 1,
                "pdf_available": False
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/file/<int:order_number>/<int:line_number>', methods=['GET'])
@app.route('/file/<int:order_number>/<int:line_number>/<int:sequence_number>', methods=['GET'])
def get_file(order_number, line_number, sequence_number=None):
    """Get file information by order number, line number, and optional sequence number."""
    try:
        file_record = get_file_by_order_line(order_number, line_number, sequence_number)
        
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
        file_record = get_file_by_order_line(order_number, line_number, sequence_number)
        
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

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=False)