FROM python:3.12-slim

LABEL author="jan.coufal@gmail.com"

# Create a non-root user
RUN useradd -m appuser

# Workdir
WORKDIR /app

# Install deps first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY app.py .
COPY appcode/ ./appcode/
COPY static/ ./static/
COPY templates/ ./templates/

# Expose the app port
EXPOSE 8000

# Drop privileges
USER appuser

# Use gunicorn in production-like mode
# Bind to 0.0.0.0 so container port mapping works
# Use just one worker (because of scheduled tasks)
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8000", "app:app"]
