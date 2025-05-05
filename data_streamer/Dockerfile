FROM python:3.12-slim

WORKDIR /app

# Install setuptools first
RUN pip install --no-cache-dir setuptools wheel

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Run the application
CMD ["python", "streamer.py"]