FROM python:3.11-slim

WORKDIR /app

# Prevent python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY run.py .
COPY src/ src/
COPY validate_submission.py .

# Default command runs prediction pipeline and validates output
CMD ["sh", "-c", "python run.py --data /app/data --out /app/predictions.csv && python validate_submission.py /app/predictions.csv"]
