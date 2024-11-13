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

# Define the queue IDs for Normal Draft only
NORMAL_DRAFT_QUEUE_ID = 400  # Normal Draft queue ID
ARAM_QUEUE_ID = 450  # ARAM queue ID

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

            # Step 3: Get Recent Match IDs (count set to 40)
            match_response = requests.get(
                f'https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=40',
                headers={'X-Riot-Token': RIOT_API_KEY}
            )
            match_response.raise_for_status()
            match_ids = match_response.json()

            # Initialize counters for Normal Draft Stats
            normal_kills = normal_deaths = normal_assists = normal_wins = normal_losses = 0
            normal_champion_counts = Counter()
            role_counts = Counter()

            # Initialize counters for ARAM Stats
            aram_kills = aram_deaths = aram_assists = aram_wins = aram_losses = 0
            aram_champion_counts = Counter()

            for match_id in match_ids:
                match_detail_response = requests.get(
                    f'https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}',
                    headers={'X-Riot-Token': RIOT_API_KEY}
                )
                match_detail_response.raise_for_status()
                match_data = match_detail_response.json()

                # Filter for Normal Draft games only
                if match_data['info']['queueId'] == NORMAL_DRAFT_QUEUE_ID:
                    participant = next((p for p in match_data['info']['participants'] if p['puuid'] == puuid), None)
                    if participant:
                        normal_kills += participant['kills']
                        normal_deaths += participant['deaths']
                        normal_assists += participant['assists']
                        normal_champion_counts[participant['championName']] += 1

                        # Capture primary role/lane
                        lane = participant.get('lane', '')
                        if lane == 'TOP':
                            role_counts['Top Lane'] += 1
                        elif lane == 'JUNGLE':
                            role_counts['Jungle'] += 1
                        elif lane == 'BOTTOM':
                            if participant.get('role', '') == 'DUO_CARRY':
                                role_counts['Bot Lane'] += 1
                            elif participant.get('role', '') == 'DUO_SUPPORT':
                                role_counts['Support'] += 1
                        elif lane == 'MIDDLE':
                            role_counts['Mid Lane'] += 1
                        else:
                            role_counts['Unknown Role'] += 1

                        if participant['win']:
                            normal_wins += 1
                        else:
                            normal_losses += 1

                # Filter for ARAM games
                elif match_data['info']['queueId'] == ARAM_QUEUE_ID:
                    participant = next((p for p in match_data['info']['participants'] if p['puuid'] == puuid), None)
                    if participant:
                        aram_kills += participant['kills']
                        aram_deaths += participant['deaths']
                        aram_assists += participant['assists']
                        aram_champion_counts[participant['championName']] += 1

                        if participant['win']:
                            aram_wins += 1
                        else:
                            aram_losses += 1

            # Calculate Normal Game Stats
            normal_games = normal_wins + normal_losses
            normal_kd = (normal_kills + normal_assists) / normal_deaths if normal_deaths > 0 else "Perfect KDA"
            most_played_champ = normal_champion_counts.most_common(1)[0][0] if normal_champion_counts else "Unknown"
            best_champ = most_played_champ
            most_played_role = role_counts.most_common(1)[0][0] if role_counts else "Unknown Role"

            # Calculate ARAM Game Stats
            aram_games = aram_wins + aram_losses
            aram_kd = (aram_kills + aram_assists) / aram_deaths if aram_deaths > 0 else "Perfect KDA"
            aram_most_played_champs = ", ".join([champ for champ, _ in aram_champion_counts.most_common(3)]) or "Unknown"
            aram_best_champs = aram_most_played_champs

            # Prepare message
            stats_message = (
                f"**Summoner Name**: {summoner_name}\n"
                f"**Account Level**: {summoner_level}\n\n"
                f"**Normal Draft Game Stats:**\n"
                f"- **Win/Loss**: {normal_wins}/{normal_losses} ({normal_games} games)\n"
                f"- **K/D Ratio**: {normal_kd}\n"
                f"- **Best Champion**: {best_champ}\n"
                f"- **Most Played Champion**: {most_played_champ}\n"
                f"- **Most Played Role**: {most_played_role}\n\n"
                f"**ARAM Game Stats:**\n"
                f"- **Win/Loss**: {aram_wins}/{aram_losses} ({aram_games} games)\n"
                f"- **K/D Ratio**: {aram_kd}\n"
                f"- **Most Played Champions**: {aram_most_played_champs}\n"
                f"- **Best Champions**: {aram_best_champs}"
            )

            # Send stats to Discord
            await message.channel.send(stats_message)

        except requests.exceptions.RequestException as e:
            await message.channel.send('Could not retrieve stats. Please try again.')
            print(f"Error fetching stats: {e}")

client.run(DISCORD_TOKEN)
