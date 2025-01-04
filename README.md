# News Scraper Telegram Bot

This is a Telegram bot that scrapes news headlines from multiple news sites, checks for new headlines, and sends them to a specified Telegram group. The bot also handles commands to clear the saved headlines or send a recap of similar headlines.

## Prerequisites

Before running the script, make sure you have the following:

Dependencies: The following Python libraries need to be installed. You can install them using `pip`:
   
   pip install aiohttp beautifulsoup4 telethon
   
Telegram API Credentials:
   - API_ID and API_HASH: You can get these by creating a new application on https://my.telegram.org/auth.
   - BOT_TOKEN: You can get this by creating a new bot via https://core.telegram.org/bots#botfather


## Setup

Configure Telegram Credentials:
   - Replace the following placeholders in the script with your own credentials:
     - `API_ID`: Your Telegram API ID.
     - `API_HASH`: Your Telegram API Hash.
     - `BOT_TOKEN`: Your Telegram Bot Token.
     - `GROUP_ID`: The ID or username of the Telegram group you want to send headlines to.

Run the Script:
   - Once everything is set up, run the script:

     python news_bot.py

   - The bot will start scraping headlines, detecting new headlines, and sending them to the Telegram group.


## Commands

- /recap: This command fetches and sends a recap of the most popular headlines in the group.
- /clear: This command clears all previously saved headlines.


## Logs

- Logs are saved in the `news_bot.log` file. You can view the log to track the bot's activities.
- If the message to be sent is too long, it will be saved in a text file and sent as a file instead.

## Troubleshooting

- If you encounter issues with missing or incorrect files (like `news_sites.json` or `previous_headlines.json`), make sure to create them as outlined in the setup section.
- If the bot isn't working properly, check the `news_bot.log` file for error messages and review the configuration settings (API credentials and group ID).

