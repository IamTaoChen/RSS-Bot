# RSS Bot

This project was created for my personal use to extract messages from [x.com](https://x.com). It may require adjustments to work with other sites.

## How It Works

1. Parse the RSS feed and identify the newest entries that haven’t yet been processed by the AI.  
2. If there are new items, send them to the AI for summarization.  
3. Collect the AI-generated summaries and dispatch them as a notification.

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