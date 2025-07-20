# RSS Bot

This project was created for my personal use to extract messages from [x.com](https://x.com). It may require adjustments to work with other sites.

```bash
[2025-07-20 16:36:34 CST] [INFO   ] ℹ️	RSS feed XXXX is disabled, skipping...
[2025-07-20 16:36:34 CST] [INFO   ] ℹ️	RSS feed Quantum Physics is disabled, skipping...
[2025-07-20 16:36:34 CST] [INFO   ] 🕒	Waiting 119.46s... Next check at 2025-07-20 16:38:32 CST
[2025-07-20 16:38:33 CST] [INFO   ] 📡	Start handling RSS - abcd (since 2025-07-20 15:46:09 CST)
[2025-07-20 16:38:33 CST] [INFO   ] 📎	Found 0 new item(s) for abcd
[2025-07-20 16:38:33 CST] [INFO   ] 📡	Start handling RSS - trumpstruth (since 2025-07-20 10:07:06 CST)
[2025-07-20 16:38:33 CST] [INFO   ] 📎	Found 0 new item(s) for trumpstruth
[2025-07-20 16:38:33 CST] [INFO   ] ℹ️	RSS feed XXXX is disabled, skipping...
[2025-07-20 16:38:33 CST] [INFO   ] ℹ️	RSS feed Quantum Physics is disabled, skipping...
[2025-07-20 16:38:33 CST] [INFO   ] 🕒	Waiting 119.53s... Next check at 2025-07-20 16:40:33 CST
```

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