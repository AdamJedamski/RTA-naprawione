FROM python:3.10-slim

WORKDIR /app

# Install dependencies with specific compatible versions
COPY requirements.txt .
RUN pip install --no-cache-dir numpy==1.23.5 &&     pip install --no-cache-dir pandas==1.5.3 &&     pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Run the application
CMD ["python", "streamer.py"]
