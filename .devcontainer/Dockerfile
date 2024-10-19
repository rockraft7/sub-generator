# Use the linuxserver/ffmpeg base image
FROM linuxserver/ffmpeg:version-7.1-cli

# Install Python3 and virtual environment support
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv

# Create a virtual environment
RUN python3 -m venv /opt/venv

# Activate the virtual environment and install Python dependencies
#COPY ./requirements.txt /tmp/requirements.txt
#RUN /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

# Set the PATH to use the virtual environment by default
ENV PATH="/opt/venv/bin:$PATH"

# Clean up
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the default working directory
WORKDIR /workspace

# Set the default shell to bash
CMD [ "bash" ]
