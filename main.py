import asyncio
import os
import random
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from fastapi import FastAPI, Request
import uvicorn

# --- FastAPI & Bot の初期化 ---
app = FastAPI()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# グローバル変数
verify_role_id = None

# ==========================================
# 1. 認証システム (Verify)
# ==========================================
class AuthView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="認証する (Verify)", style=discord.ButtonStyle.green, custom_id="auth_button")
    async def verify_button(self, interaction: discord.Interaction, button: Button):
        global verify_role_id
        target_role_id = verify_role_id or int(os.getenv("MEMBER_ROLE_ID", 0))
        role = interaction.guild.get_role(target_role_id)
        
        if not role:
            await interaction.response.send_message("❌ 認証ロールが設定されていません。", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("✅ すでに認証されています！", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("🎉 認証が完了しました！あつまりさばへようこそ！", ephemeral=True)

@bot.tree.command(name="verifysetup", description="認証時に付与するロールを設定します。")
@app_commands.describe(role="付与するロールを選択してください")
@app_commands.checks.has_permissions(administrator=True)
async def verify_setup(interaction: discord.Interaction, role: discord.Role):
    global verify_role_id
    verify_role_id = role.id
    await interaction.response.send_message(f"✅ 認証ロールを {role.mention} に設定しました！", ephemeral=True)

@bot.tree.command(name="verifypanel", description="認証パネルを設置します。")
@app_commands.checks.has_permissions(administrator=True)
async def verify_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="あつまりさば 認証パネル",
        description="下のボタンを押してサーバーの認証を完了させてください。",
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=AuthView())
    await interaction.response.send_message("📌 認証パネルを設置しました。", ephemeral=True)


# ==========================================
# 2. チケットシステム (Ticket)
# ==========================================
class TicketCloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 チケットを閉じる", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("チケットを閉じます（5秒後削除）...", ephemeral=True)
        await asyncio.sleep(5)
        await interaction.channel.delete()

class TicketCreateView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 チケットを作成", style=discord.ButtonStyle.blurple, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=interaction.channel.category,
            overwrites=overwrites
        )
        embed = discord.Embed(
            title="お問い合わせチケット",
            description="スタッフが対応するまでお待ちください。",
            color=discord.Color.green()
        )
        await channel.send(f"{interaction.user.mention} 様ようこそ！", embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"チケットを作成しました: {channel.mention}", ephemeral=True)

@bot.command(name="setup_ticket")
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx):
    embed = discord.Embed(
        title="サポートチケット",
        description="下のボタンからチケットを作成できます。",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed, view=TicketCreateView())


# ==========================================
# 3. 管理コマンドパック (Moderation & Utility)
# ==========================================
@bot.tree.command(name="kick", description="指定したメンバーをキックします。")
@app_commands.describe(member="対象のメンバー", reason="理由")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_member(interaction: discord.Interaction, member: discord.Member, reason: str = "理由なし"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 {member.mention} をキックしました。（理由: {reason}）", ephemeral=True)

@bot.tree.command(name="ban", description="指定したメンバーをバースト(BAN)します。")
@app_commands.describe(member="対象のメンバー", reason="理由")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_member(interaction: discord.Interaction, member: discord.Member, reason: str = "理由なし"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 {member.mention} をBANしました。（理由: {reason}）", ephemeral=True)

@bot.tree.command(name="purge", description="指定した数のメッセージを削除します。")
@app_commands.describe(limit="削除するメッセージ数（1〜100）")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge_messages(interaction: discord.Interaction, limit: int):
    if limit < 1 or limit > 100:
        await interaction.response.send_message("❌ 1から100の間で指定してください。", ephemeral=True)
        return
    await interaction.channel.purge(limit=limit)
    await interaction.response.send_message(f"🧹 {limit}件のメッセージを削除しました。", ephemeral=True)

@bot.tree.command(name="serverinfo", description="あつまりさばの情報を表示します。")
async def server_info(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📊 {guild.name} のサーバー情報", color=discord.Color.purple())
    embed.add_field(name="オーナー", value=guild.owner, inline=True)
    embed.add_field(name="メンバー数", value=f"{guild.member_count}人", inline=True)
    embed.add_field(name="作成日", value=guild.created_at.strftime('%Y/%m/%d'), inline=True)
    await interaction.response.send_message(embed=embed)


# ==========================================
# 4. ゲームコマンドパック (Games)
# ==========================================
@bot.tree.command(name="omikuji", description="今日の運勢を占います！")
async def omikuji(interaction: discord.Interaction):
    results = ["大吉 🎯", "中吉 ✨", "小吉 🌱", "吉 📘", "末吉 🍀", "凶 ⚠️", "大凶 💀"]
    result = random.choice(results)
    embed = discord.Embed(title="🔮 おみくじ", description=f"あなたの今日の運勢は **{result}** です！", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="dice", description="サイコロを振ります（1〜6）。")
async def dice_roll(interaction: discord.Interaction):
    num = random.randint(1, 6)
    await interaction.response.send_message(f"🎲 サイコロの出目: **{num}**")

@bot.tree.command(name="rps", description="じゃんけん勝負をします！")
@app_commands.choices(hand=[
    app_commands.Choice(name="グー", value="rock"),
    app_commands.Choice(name="チョキ", value="scissors"),
    app_commands.Choice(name="パー", value="paper")
])
async def rock_paper_scissors(interaction: discord.Interaction, hand: str):
    hands = {"rock": "グー ✊", "scissors": "チョキ ✌️", "paper": "パー 🖐️"}
    bot_hand = random.choice(list(hands.keys()))
    
    user_choice = hands[hand]
    bot_choice = hands[bot_hand]
    
    if hand == bot_hand:
        result = "あいこ！ 🤝"
    elif (hand == "rock" and bot_hand == "scissors") or \
         (hand == "scissors" and bot_hand == "paper") or \
         (hand == "paper" and bot_hand == "rock"):
        result = "あなたの勝ち！ 🎉"
    else:
        result = "わたしの勝ち！ 🤖"
        
    embed = discord.Embed(title="✊ じゃんけん勝負", color=discord.Color.teal())
    embed.add_field(name="あなた", value=user_choice, inline=True)
    embed.add_field(name="ボット", value=bot_choice, inline=True)
    embed.add_field(name="結果", value=f"**{result}**", inline=False)
    await interaction.response.send_message(embed=embed)


# ==========================================
# 5. ボット起動イベント & スラッシュコマンド同期
# ==========================================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(e)


# ==========================================
# 6. FastAPI エンドポイント (UptimeRobot & HAD対応)
# ==========================================
@app.get("/health")
async def uptimerobot_health():
    """UptimeRobotによる死活監視（スピンダウン防止用）"""
    return {"status": "active", "message": "Bot is alive!"}

@app.post("/api/had-request")
async def handle_had_request(request: Request):
    data = await request.json()
    print(f"Received HAD Request: {data}")
    return {"status": "success", "received": data}

@app.get("/")
async def health_check():
    return {"status": "online"}


# ==========================================
# 7. アプリケーション起動管理 (Render用)
# ==========================================
@app.on_event("startup")
async def startup_event():
    token = os.getenv("DISCORD_TOKEN")
    if token:
        asyncio.create_task(bot.start(token))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
