# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Arguments for non-root user creation
ARG UNAME=stream_api
ARG UID=1200
ARG GID=1200
ARG VERSION=latest
ARG APPLICATION_MANUFACTURER=OpenFactory-AssetAPI
ARG OPENFACTORY_VERSION=latest

# Create a non-root user and group
RUN groupadd --gid $GID $UNAME \
    && useradd --create-home --uid $UID --gid $GID $UNAME

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . stream_api/non_replicated

# Change ownership to the non-root user
RUN chown -R $UNAME:$UNAME /app

# Set environment variable from build argument
ENV APPLICATION_VERSION=${VERSION}
ENV APPLICATION_MANUFACTURER=${APPLICATION_MANUFACTURER}
ENV OPENFACTORY_VERSION=${OPENFACTORY_VERSION}

# Switch to non-root user
USER $UNAME

# Expose the port your app runs on
EXPOSE 5555

# Command to run the app with uvicorn (adjust module path if needed)
CMD ["python", "-m", "stream_api.non_replicated.main"]
