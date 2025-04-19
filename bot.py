import os
import aiohttp
import discord
from discord import Embed
from discord.ext import commands, tasks
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import datetime
import pytz
from flask import Flask
from threading import Thread

# Umgebungsvariablen laden
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# V-Bucks Preise
fixedPrices = {
    "500 V-Bucks": "3 €",
    "800 V-Bucks": "6 €",
    "1000 V-Bucks": "7 €",
    "1200 V-Bucks": "8 €",
    "1500 V-Bucks": "10 €",
    "1800 V-Bucks": "13 €",
    "1900 V-Bucks": "13 €",
    "2000 V-Bucks": "14 €",
    "2100 V-Bucks": "15 €",
    "2200 V-Bucks": "15 €",
    "2500 V-Bucks": "17 €",
    "2800 V-Bucks": "19 €",
    "3000 V-Bucks": "21 €",
    "3200 V-Bucks": "22 €",
    "3400 V-Bucks": "24 €",
    "3600 V-Bucks": "25 €",
}

# Shopdaten abrufen
async def fetch_shop_data():
    url = 'https://fnitemshop.com/'
    headers = {'User-Agent': 'Mozilla/5.0'}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                print(f"Fehler beim Laden der Seite: {response.status}")
                return []

            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            items = []

            for img in soup.find_all('img', {'src': lambda x: x and x.startswith('https://fnitemshop.com/wp-content/uploads')}):
                imageUrl = img['src']
                parent = img.find_parent('div', class_='product')
                name = parent.find('div', class_='product-title').text.strip() if parent else 'Unbekannt'
                price = parent.find('div', class_='product-price').text.strip() if parent else 'Unbekannt'
                items.append({'imageUrl': imageUrl, 'name': name, 'price': price})

            print(f"{len(items)} Items geladen")
            return items

# Preisliste erstellen
def create_price_text_file():
    text = "V-Bucks Preise für diese Items:\n\n"
    text += '\n'.join([f"{k}: {v}" for k, v in fixedPrices.items()])
    path = "./shop-preise.txt"
    with open(path, 'w', encoding='utf-8') as file:
        file.write(text)
    return path

# Bildcollage erstellen
async def create_image_collage(items):
    canvas_size = 2048
    grid_size = 8
    image_size = canvas_size // grid_size
    canvas = Image.new('RGB', (canvas_size, canvas_size), (30, 30, 30))
    image_count = 0

    async with aiohttp.ClientSession() as session:
        for item in items:
            if not item['imageUrl'].lower().endswith(('jpg', 'jpeg', 'png', 'webp')):
                continue

            try:
                async with session.get(item['imageUrl']) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.read()
                    img = Image.open(BytesIO(data)).convert("RGB")
                    img = img.resize((image_size, image_size))
                    x = (image_count % grid_size) * image_size
                    y = (image_count // grid_size) * image_size
                    canvas.paste(img, (x, y))
                    image_count += 1
            except Exception as e:
                print(f"Bildfehler: {item['imageUrl']} – {e}")

    buffer = BytesIO()
    canvas.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

# Shopnachricht senden
async def send_shop_items(channel, items):
    num_per_batch = 64
    total = len(items)
    start = 0
    price_file = create_price_text_file()

    while start < total:
        end = min(start + num_per_batch, total)
        collage = await create_image_collage(items[start:end])
        files = [discord.File(collage, filename="shop-collage.png")]

        if end >= total:
            files.append(discord.File(price_file, filename="shop-preise.txt"))

        await channel.send(
            content="🛒 Hier ist die aktuelle Shop-Auswahl:",
            files=files
        )

        if end >= total:
            embed = Embed(
                title="Jixx's Market",
                description="Zahlung nur per Paypal oder Krypto-Währung möglich.",
                color=0x0099ff
            )
            embed.add_field(name="Zahlungsmethoden", value="💳 Paypal, 💰 Krypto")
            embed.add_field(name="Mindestbestellwert", value="25 €")
            embed.set_footer(text="Vielen Dank für deinen Einkauf!")
            await channel.send(embed=embed)

        start = end

# Täglicher Task
@tasks.loop(hours=24)
async def scheduled_shop_post():
    # Zeitzonenanpassung auf Berlin (CEST / CET)
    tz = pytz.timezone('Europe/Berlin')
    now = datetime.datetime.now(tz)
    # Sicherstellen, dass der Task genau um 2:10 Uhr läuft
    if now.hour == 2 and now.minute == 10:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            items = await fetch_shop_data()
            if items:
                await send_shop_items(channel, items)

# Shop-Befehl
@bot.command()
async def shop(ctx):
    channel = bot.get_channel(CHANNEL_ID)
    items = await fetch_shop_data()
    if items:
        await send_shop_items(channel, items)

# Bot-Start
@bot.event
async def on_ready():
    print(f"Bot gestartet als {bot.user}")

# Flask Setup für Uptime Robot Ping
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot läuft!"  # Gibt eine einfache Antwort zurück

# Flask-Server in einem separaten Thread starten
def run():
    app.run(host="0.0.0.0", port=8080)

# Bot ausführen
if __name__ == "__main__":
    # Starte den Flask-Server im Hintergrund
    t1 = Thread(target=run)  # Flask-Server
    t1.start()

    # Starte den Discord-Bot
    bot.run(TOKEN)
