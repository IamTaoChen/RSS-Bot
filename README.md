# RSS Bot

This project was created for my personal use to extract messages from [x.com](https://x.com). It may require adjustments to work with other sites.

> **Note:** It currently only supports sending notifications via Matrix.

## How to Use

### Docker

1. Copy the example configuration:

   ```bash
   cp config_example.yaml config.yaml
   ```

2. Start the service:

   ```bash
   docker compose up -d
   ```

### Local

1. Create a Python virtual environment:

   ```bash
   python3 -m venv venv
   source ./venv/bin/activate
   ```

2. Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy the example configuration:

   ```bash
   cp config_example.yaml config.yaml
   ```

4. Run the application:

   ```bash
   python3 main.py
   ```