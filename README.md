# SVG to PDF Converter

A Docker-based REST API service for converting SVG files to PDF files with an integrated admin portal. Built specifically for AlmaLinux hosts with efficient resource usage.
Created by Anthropic Claude Sonnet 4
Prompted by Jay Whaley

## Original Prompt
> Create a docker image that will run  on an AlmaLinux host for a REST API using Python 3 that will manage converting SVG files to PDF files using CairoSVG.
> The REST API should be simple  POST and GET requests.
> There's a need for lookup capability to find files by an "order number" which is a 6 digit number and a line number which ranges from 1 to 999.
> Ideally, the REST API would run alongside an admin portal front-end in the same docker image; streamlit is fine but alternatives should be considered for performance.
> Store all of this data in a SQLite database unless there's an alternative SQL database which uses little processing power and storage space.

## Features

- **REST API**: Simple POST/GET endpoints for file upload and retrieval
- **SVG to PDF Conversion**: Uses CairoSVG for high-quality conversions
- **File Management**: Organized by 6-digit order numbers and line numbers (1-999)
- **Admin Portal**: Web-based Streamlit interface for file management
- **SQLite Database**: Lightweight, efficient data storage
- **Docker Container**: Single container deployment with nginx reverse proxy

## Architecture

- **Flask REST API** (Port 5000): Handles file uploads and conversions
- **Streamlit Admin Portal** (Port 8501): Web interface for administration
- **Nginx Reverse Proxy** (Port 80): Routes traffic and serves static files
- **SQLite Database**: Stores file metadata and tracking information
- **Supervisor**: Process manager for running multiple services

## Quick Start

### Prerequisites
- Docker and Docker Compose
- AlmaLinux host (recommended)

### Build and Run

1. Make the build script executable:
```bash
chmod +x build.sh
```

2. Run the build script:
```bash
./build.sh
```

3. Access the services:
   - **Admin Interface**: http://localhost
   - **REST API**: http://localhost/api
   - **Health Check**: http://localhost/health

## API Endpoints

### Upload File
```http
POST /api/upload
Content-Type: multipart/form-data

Parameters:
- file: SVG file (required)
- order_number: 6-digit number (100000-999999)
- line_number: Line number (1-999)
```

### Get File Information
```http
GET /api/file/{order_number}/{line_number}
```

### Download File
```http
GET /api/download/{order_number}/{line_number}/{svg|pdf}
```

### List Files by Order
```http
GET /api/files/order/{order_number}
```

### List All Files
```http
GET /api/files?page=1&per_page=50
```

## Usage Examples

### Upload SVG File
```bash
curl -X POST \
  -F "file=@example.svg" \
  -F "order_number=123456" \
  -F "line_number=1" \
  http://localhost/api/upload
```

### Get File Information
```bash
curl http://localhost/api/file/123456/1
```

### Download PDF
```bash
curl -O http://localhost/api/download/123456/1/pdf
```

## Admin Portal Features

### Dashboard
- File statistics overview
- Recent files list
- Status monitoring

### Upload Interface
- Drag-and-drop file upload
- Order and line number input
- Real-time conversion status

### Search & Management
- Search by order number and line number
- Bulk operations
- File details and download options

## Directory Structure

```
/app/
├── app.py                 # Flask REST API
├── admin_portal.py        # Streamlit admin interface
├── database.py           # SQLite database operations
├── uploads/              # Original SVG files
├── converted/            # Generated PDF files
├── static/               # Static web assets
└── svg_pdf_converter.db  # SQLite database
```

## Configuration

### Environment Variables
- `DATABASE_PATH`: SQLite database file path (default: `/app/data/svg_pdf_converter.db`)
- `FLASK_ENV`: Flask environment (default: `production`)

### Volume Mounts
- `./data:/app/data` - Database persistence
- `./uploads:/app/uploads` - Uploaded SVG files
- `./converted:/app/converted` - Generated PDF files

## Resource Usage

- **Memory**: ~200-300MB typical usage
- **Storage**: SQLite database + uploaded files
- **CPU**: Low usage, spikes during conversion

## File Organization

Files are organized using a consistent naming pattern:
- **SVG files**: `{order_number}_{line_number}_{original_filename}.svg`
- **PDF files**: `{order_number}_{line_number}_{original_filename}.pdf`

## Database Schema

```sql
CREATE TABLE files (
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
);
```

## Health Monitoring

The service includes health check endpoints:
- **HTTP**: `GET /health`
- **Docker**: Built-in healthcheck every 30 seconds

## Logging

Logs are managed by Supervisor and can be viewed:
```bash
# All logs
docker-compose logs -f

# Specific service logs
docker-compose logs -f svg-pdf-converter
```

## Troubleshooting

### Common Issues

1. **Port 80 already in use**
   - Change port mapping in `docker-compose.yml`
   - Example: `"8080:80"`

2. **Permission errors**
   - Ensure directories have proper permissions
   - Check Docker daemon permissions

3. **SVG conversion fails**
   - Verify SVG file format
   - Check for complex SVG elements
   - Review conversion logs

### Debug Mode

For development, modify `app.py`:
```python
app.run(host='0.0.0.0', port=5000, debug=True)
```

## Performance Considerations

- **File Size Limits**: 16MB max upload size
- **Concurrent Processing**: 2 Gunicorn workers
- **Database**: SQLite with indexing for fast lookups
- **Caching**: Nginx static file caching enabled

## Security Notes

- Files are stored with secure filenames
- Input validation on all endpoints
- Non-root user execution
- Network isolation via Docker

## Alternative Databases

While SQLite is recommended for its low resource usage, you can easily switch to other databases by modifying `database.py`:

- **PostgreSQL**: For larger scale deployments
- **MySQL/MariaDB**: For existing infrastructure integration
- **In-memory**: For temporary processing workflows

## License

This project is provided as-is for educational and commercial use.
