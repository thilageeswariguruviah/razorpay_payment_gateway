# Use the latest version of Python
FROM python:latest

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies from the requirements file
RUN pip install --no-cache-dir -r requirements.txt

# Create a directory for logs
RUN mkdir -p /app/logs

# Copy the rest of your application code into the container
COPY . .

# Define environment variable to prevent Python from buffering output
ENV PYTHONUNBUFFERED=1
EXPOSE 5000

# Command to run the application
CMD ["python", "src/app.py"]
