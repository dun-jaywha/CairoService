#!/bin/bash

# SVG to PDF Converter - Build Script
# This script builds and runs the Docker container for AlmaLinux

echo "Building SVG to PDF Converter Docker Image..."

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p data uploads converted static templates

# Create placeholder files for static and templates directories
echo "# Static files directory" > static/placeholder.txt
echo "# Templates directory" > templates/placeholder.txt

# Build the Docker image
echo "Building Docker image..."
docker build -t svg-pdf-converter:latest .

if [ $? -eq 0 ]; then
    echo "Docker image built successfully!"
    
    # Run the container using docker compose
    echo "Starting the container..."
    docker compose up -d
    
    if [ $? -eq 0 ]; then
        echo "Container started successfully!"
        echo ""
        echo "Services are available at:"
        echo "   Admin Interface: http://localhost"
        echo "   REST API: http://localhost/api"
        echo "   Health Check: http://localhost/health"
        echo ""
        echo "API Endpoints:"
        echo "   POST /api/upload - Upload SVG file"
        echo "   GET  /api/file/{order_number}/{line_number} - Get file info"
        echo "   GET  /api/download/{order_number}/{line_number}/{svg|pdf} - Download file"
        echo "   GET  /api/files/order/{order_number} - Get files by order"
        echo "   GET  /api/files - List all files"
        echo ""
        echo "View logs:"
        echo "   docker compose logs -f"
        echo ""
        echo "Stop the container:"
        echo "   docker compose down"
    else
        echo "Failed to start container!"
        exit 1
    fi
else
    echo "Failed to build Docker image!"
    exit 1
fi
