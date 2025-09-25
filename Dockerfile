FROM almalinux:9

# Install system dependencies
RUN dnf update -y && \
    dnf groupinstall -y "Development Tools" && \
    dnf install -y python3 python3-pip python3-devel \
                   cairo cairo-devel pango pango-devel \
                   gdk-pixbuf2-devel libffi-devel \
                   nginx epel-release && \
    dnf install -y supervisor && \
    dnf clean all

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/uploads /app/converted /app/static /app/templates \
             /var/log/supervisor /etc/supervisor/conf.d \
             /var/log/nginx /var/cache/nginx /var/run

# Copy application files
COPY app.py .
COPY admin_portal.py .
COPY database.py .
COPY static/ ./static/
COPY templates/ ./templates/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY nginx.conf /etc/nginx/nginx.conf

# Create non-root user and set permissions
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /var/log/supervisor /var/log/nginx /var/cache/nginx /var/run && \
    chmod 755 /var/run

# Expose ports
EXPOSE 80

# Switch to non-root user
USER appuser

# Start supervisor to manage multiple services
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
