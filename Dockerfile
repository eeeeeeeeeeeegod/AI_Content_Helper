FROM python:3.12-slim

# ============================================
# Python Environment
# ============================================

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


# ============================================
# Working Directory
# ============================================

WORKDIR /app


# ============================================
# Install Python Packages
# ============================================

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ============================================
# Copy Project
# ============================================

COPY . .


# ============================================
# Container Port
# ============================================

EXPOSE 8000


# ============================================
# Start Flask with Gunicorn
# ============================================

CMD ["sh", "-c", "flask --app app db upgrade && gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 180 app:app"]