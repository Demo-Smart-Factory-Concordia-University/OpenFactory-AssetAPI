# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Arguments for non-root user creation
ARG UNAME=state_api
ARG UID=1200
ARG GID=1200

# Install git and create a non-root user and group
RUN apt-get update && apt-get install -y git \
    && groupadd --gid $GID $UNAME \
    && useradd --create-home --uid $UID --gid $GID $UNAME \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . state_api

# Change ownership to the non-root user
RUN chown -R $UNAME:$UNAME /app

# Switch to non-root user
USER $UNAME

# Expose the port your app runs on
EXPOSE 5555

# Command to run the app with uvicorn (adjust module path if needed)
CMD ["python", "-m", "state_api.main"]
