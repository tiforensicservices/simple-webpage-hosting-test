# =============================================================
# Dev Container — Shoe Print Image System
# Base: Python 3.13 slim (Debian Bookworm)
# Includes: AWS CLI v2, boto3, image processing, scraping tools
# =============================================================

FROM python:3.13-slim-bookworm

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    git \
    wget \
    ca-certificates \
    gnupg \
    lsb-release \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI v2
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip" \
    && unzip /tmp/awscliv2.zip -d /tmp/ \
    && /tmp/aws/install \
    && rm -rf /tmp/awscliv2.zip /tmp/aws

# Upgrade pip
RUN pip install --upgrade pip

# Set working directory
WORKDIR /workspaces/simple-webpage-hosting-test

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Verify installations
RUN python --version && aws --version && pip --version

CMD ["bash"]
