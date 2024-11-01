import os
import discord
import requests
from dotenv import load_dotenv
from collections import Counter

# Load environment variables from .env file
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RIOT_API_KEY = os.getenv('RIOT_API_KEY')

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Define the queue IDs for Summoner’s Rift normal and ranked games
SUMMONERS_RIFT_QUEUE_IDS = {420, 430, 440, 400}  # Ranked Solo, Normal Blind, Ranked Flex, Normal Draft

@client.event
async def on_ready():
    print(f'Logged in as {client.user}!')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!stats'):
        parts = message.content.split(' ')
        if len(parts) < 3:
            await message.channel.send("Please provide a Riot ID in the format: `!stats <gameName> <tagLine>`")
            return
        game_name, tag_line = parts[1], parts[2]

        try:
            # Step 1: Get PUUID from Riot ID
            account_response = requests.get(
                f'https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}',
                headers={'X-Riot-Token': RIOT_API_KEY}
            )
            account_response.raise_for_status()
            account_data = account_response.json()
            puuid = account_data['puuid']

            # Step 2: Get Summoner Details
            summoner_response = requests.get(
                f'https://na1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}',
                headers={'X-Riot-Token': RIOT_API_KEY}
            )
            summoner_response.raise_for_status()
            summoner_data = summoner_response.json()
            summoner_name = summoner_data.get('name', game_name)
            summoner_level = summoner_data.get('summonerLevel', 'Unknown')

            # Step 3: Get Recent Match IDs
            match_response = requests.get(
                f'https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=20',
                headers={'X-Riot-Token': RIOT_API_KEY}
            )
            match_response.raise_for_status()
            match_ids = match_response.json()

            # Step 4: Analyze Matches for Overall Stats
            total_kills = total_deaths = total_assists = wins = losses = 0
            champion_counts = Counter()
            role_counts = Counter()

            for match_id in match_ids:
                match_detail_response = requests.get(
                    f'https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}',
                    headers={'X-Riot-Token': RIOT_API_KEY}
                )
                match_detail_response.raise_for_status()
                match_data = match_detail_response.json()

                # Filter to include only Summoner’s Rift normal and ranked games
                if match_data['info']['queueId'] not in SUMMONERS_RIFT_QUEUE_IDS:
                    continue

                # Find participant data for this summoner
                participant = next((p for p in match_data['info']['participants'] if p['puuid'] == puuid), None)
                if participant:
                    total_kills += participant['kills']
                    total_deaths += participant['deaths']
                    total_assists += participant['assists']
                    champion_counts[participant['championName']] += 1
                    role_counts[participant['role']] += 1

                    if participant['win']:
                        wins += 1
                    else:
                        losses += 1

            # Calculate overall K/D ratio and best champion
            total_games = wins + losses
            overall_kd = (total_kills + total_assists) / total_deaths if total_deaths > 0 else "Perfect KDA"
            best_champ = champion_counts.most_common(1)[0][0] if champion_counts else "Unknown"
            most_played_role = role_counts.most_common(1)[0][0] if role_counts else "Unknown"

            # Prepare stats message
            stats_message = (
                f"**Summoner Name**: {summoner_name}\n"
                f"**Account Level**: {summoner_level}\n\n"
                f"**Overall Stats:**\n"
                f"- **Win/Loss**: {wins}/{losses} ({total_games} games)\n"
                f"- **K/D Ratio**: {overall_kd}\n"
                f"- **Best Champion**: {best_champ}\n"
                f"- **Most Played Champion**: {best_champ}\n"
                f"- **Most Played Role**: {most_played_role}"
            )

            # Send overall stats to Discord
            await message.channel.send(stats_message)

        except requests.exceptions.RequestException as e:
            await message.channel.send('Could not retrieve stats. Please try again.')
            print(f"Error fetching stats: {e}")

client.run(DISCORD_TOKEN)
