import json
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from collections import defaultdict
from telethon import TelegramClient, events
from telethon.tl.types import InputFile
import logging
import time

# Telegram API credentials
API_ID = ""  # Replace with your API ID
API_HASH = ""  # Replace with your API Hash
BOT_TOKEN = ""  # Replace with your Bot Token
GROUP_ID = ""  # Replace with the target group ID (e.g., username or chat ID)

# Logging setup
logging.basicConfig(
    filename="news_bot.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

SIMILARITY_THRESHOLD = 0.5
CONCURRENT_REQUESTS = 5
UPDATE_INTERVAL = 1800  # Check every 30 minutes
PREVIOUS_HEADLINES_FILE = "previous_headlines.json"

# Load news sites from JSON
def load_news_sites(filename="news_sites.json"):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)

# Load previous headlines
def load_previous_headlines():
    try:
        with open(PREVIOUS_HEADLINES_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Save current headlines
def save_current_headlines(headlines):
    with open(PREVIOUS_HEADLINES_FILE, "w", encoding="utf-8") as file:
        json.dump(headlines, file, indent=4, ensure_ascii=False)

# Clear previous headlines
def clear_previous_headlines():
    try:
        with open(PREVIOUS_HEADLINES_FILE, "w", encoding="utf-8") as file:
            json.dump({}, file)
        logging.info("Cleared previous headlines.")
    except Exception as e:
        logging.error(f"Failed to clear previous headlines: {e}")

# Detect new headlines
def detect_new_headlines(current_headlines, previous_headlines):
    new_headlines = defaultdict(list)
    for site, headlines in current_headlines.items():
        previous_site_headlines = previous_headlines.get(site, [])
        for headline in headlines:
            if headline not in previous_site_headlines:
                new_headlines[site].append(headline)
    return new_headlines

# Async fetch HTML
async def fetch_html(session, url, semaphore):
    async with semaphore:
        try:
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            logging.error(f"Failed to fetch {url}: {e}")
            return None

# Async scrape site
async def scrape_site(session, site, semaphore):
    url = site["url"]
    selector = site["selector"]
    logging.info(f"Scraping headlines from {url}...")

    html = await fetch_html(session, url, semaphore)
    if not html:
        logging.warning(f"Failed to scrape headlines from {url}.")
        return url, []

    soup = BeautifulSoup(html, 'html.parser')
    site_headlines = soup.select(selector)

    filtered_headlines = [
        headline.get_text(strip=True)
        for headline in site_headlines
        if headline.get_text() and len(headline.get_text(strip=True).split()) > 4
    ]
    logging.info(f"Scraped {len(filtered_headlines)} headlines from {url}.")
    return url, filtered_headlines

# Async scrape all sites
async def scrape_headlines_async(news_sites):
    headlines = defaultdict(list)
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    async with aiohttp.ClientSession() as session:
        tasks = [scrape_site(session, site, semaphore) for site in news_sites]
        results = await asyncio.gather(*tasks)
        for url, site_headlines in results:
            if site_headlines:
                headlines[url] = site_headlines
    return headlines

# Find similar headlines
def find_similar_headlines(headlines):
    all_headlines = []
    for site_headlines in headlines.values():
        all_headlines.extend(site_headlines)

    grouped_headlines = defaultdict(list)
    visited = set()

    for i, headline1 in enumerate(all_headlines):
        if i in visited:
            continue
        group = [headline1]
        visited.add(i)
        for j, headline2 in enumerate(all_headlines):
            if j != i and j not in visited:
                similarity = SequenceMatcher(None, headline1, headline2).ratio()
                if similarity >= SIMILARITY_THRESHOLD:
                    group.append(headline2)
                    visited.add(j)
        if len(group) >= 3:
            grouped_headlines[headline1] = group

    return grouped_headlines

# Save recap to text file
def save_recap_to_file(filename, grouped_headlines):
    if grouped_headlines:
        with open(filename, "w", encoding="utf-8") as file:
            file.write("📰 **Popular Headlines Recap**:\n\n")
            for main_headline, group in grouped_headlines.items():
                file.write(f"**{main_headline}**:\n")
                for similar in group:
                    file.write(f" - {similar}\n")
                file.write("\n")
        logging.info(f"Recap saved to {filename}")

# Send new headlines to Telegram
async def send_new_headlines(client, group_id, new_headlines):
    grouped_headlines = find_similar_headlines(new_headlines)
    if not grouped_headlines:
        logging.info("No new popular headlines to send.")
        return

    message = "📰 **New Popular News Updates**:\n\n"
    for main_headline, group in grouped_headlines.items():
        message += f"**{main_headline}**:\n"
        for similar in group:
            message += f" - {similar}\n"
        message += "\n"

    try:
        logging.info(f"Sending to group ID: {group_id}")
        
        # Check if the message is too long
        if len(message) > 4000:
            # If the message is too long, save it to a file
            filename = "news_updates.txt"
            with open(filename, "w", encoding="utf-8") as file:
                file.write(message)
            # Send the file
            input_file = await client.upload_file(filename)
            await client.send_file(group_id, input_file, caption="📰 **New Popular News Updates**")
            logging.info("Message was too long, sent as a file.")
        else:
            # Send the message as a regular message
            await client.send_message(group_id, message)
            logging.info("New popular headlines sent to Telegram.")

    except Exception as e:
        logging.error(f"Failed to send popular headlines to Telegram: {e}")

# Send recap as a text file to Telegram
async def send_recap_as_file(client, group_id, filename):
    try:
        logging.info(f"Sending recap file {filename} to group ID: {group_id}")
        input_file = await client.upload_file(filename)
        await client.send_file(group_id, input_file, caption="📰 **Popular Headlines Recap**")
        logging.info("Recap file sent to Telegram.")
    except Exception as e:
        logging.error(f"Failed to send recap file to Telegram: {e}")

# Handle /recap command
async def handle_recap(event):
    logging.info("Received /recap command.")
    news_sites = load_news_sites()
    headlines = await scrape_headlines_async(news_sites)
    grouped_headlines = find_similar_headlines(headlines)
    
    if grouped_headlines:
        recap_filename = "popular_headlines_recap.txt"
        save_recap_to_file(recap_filename, grouped_headlines)
        await send_recap_as_file(event.client, event.chat_id, recap_filename)

# Handle /clear command
async def handle_clear(event):
    logging.info("Received /clear command.")
    clear_previous_headlines()
    await event.respond("🧹 **All previous headlines have been cleared.**")

# Main bot loop
async def main():
    news_sites = load_news_sites()
    previous_headlines = load_previous_headlines()

    # Initialize Telegram client
    client = TelegramClient("news_bot", API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    logging.info("Telegram bot started.")

    @client.on(events.NewMessage(pattern="/recap"))
    async def recap_command_handler(event):
        await handle_recap(event)

    @client.on(events.NewMessage(pattern="/clear"))
    async def clear_command_handler(event):
        await handle_clear(event)

    while True:
        try:
            logging.info("Starting a new scraping cycle...")
            current_headlines = await scrape_headlines_async(news_sites)
            new_headlines = detect_new_headlines(current_headlines, previous_headlines)

            if new_headlines:
                logging.info(f"Detected {sum(len(h) for h in new_headlines.values())} new headlines.")
                await send_new_headlines(client, GROUP_ID, new_headlines)
            else:
                logging.info("No new headlines detected.")

            save_current_headlines(current_headlines)
            previous_headlines = current_headlines
        except Exception as e:
            logging.error(f"Error in main loop: {e}")

        logging.info(f"Sleeping for {UPDATE_INTERVAL} seconds...")
        await asyncio.sleep(UPDATE_INTERVAL)

# Run the bot
if __name__ == "__main__":
    asyncio.run(main())
