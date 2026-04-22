import discord
from discord.ext import commands
from discord import app_commands
import random
import time
import asyncio
from datetime import timedelta

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

balances = {}
STARTING_MONEY = 10
daily_cooldowns = {}
DAILY_AMOUNT = 5
DAILY_COOLDOWN = 86400
loan_requests = {}
debts = {}
work_cooldowns = {}
WORK_COOLDOWN = 43200
budgets = {}
budget_reset = {}

def get_balance(user_id: str):
    if user_id not in balances:
        balances[user_id] = STARTING_MONEY
    return balances[user_id]

def check_budget(user_id: str, amount: int):
    if user_id not in budgets:
        return False, "❌ You must set a budget first using /budget."

    now = time.time()
    last_reset = budget_reset.get(user_id, 0)

    if now - last_reset >= 86400:
        budgets[user_id]["spent"] = 0
        budget_reset[user_id] = now

    remaining = budgets[user_id]["limit"] - budgets[user_id]["spent"]

    if amount > remaining:
        return False, f"❌ Budget exceeded. Remaining: {remaining} coins."

    return True, ""

advice_list = [
    "Save at least 20% of your income.",
    "Avoid impulse purchases, wait 24 hours before buying.",
    "Build an emergency fund covering 3–6 months of expenses.",
    "Invest consistently, not emotionally.",
    "Don’t put all your money in one place, diversify.",
    "Track your spending. Small leaks sink big ships.",
    "Debt with high interest should be your first enemy.",
    "If it sounds too good to be true, it probably is.",
    "DO NOT GAMBLE!!!"
]

job_roles = {
    "Broke": 1,
    "Unemployed": 5,
    "Janitor": 15,
    "Laborer": 25,
    "Employee": 50,
    "Senior Employee": 70,
    "Junior Manager": 90,
    "Working Manager": 100,
    "Senior Manager": 130,
    "Teacher": 150,
    "Professor": 200,
    "Principal": 250,
    "Banker": 350,
    "Soldier": 500,
    "Sergeant": 600,
    "Lieutenant": 750,
    "Captain": 900,
    "Major": 950,
    "General": 1000,
    "CEO": 1250
}

class DebtModal(discord.ui.Modal, title="Set Debt Details"):
    def __init__(self, sender_id, receiver_id, amount):
        super().__init__()
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.amount = amount

    debt_amount = discord.ui.TextInput(label="Set Debt Amount", placeholder="Enter amount")
    duration = discord.ui.TextInput(label="Set Duration (days)", placeholder="Enter days")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            debt_value = int(self.debt_amount.value)
            days = int(self.duration.value)
        except:
            await interaction.response.send_message("❌ Invalid input.", ephemeral=True)
            return


        min_debt = self.amount
        max_debt = int(self.amount * 1.25)

        if not (min_debt <= debt_value <= max_debt):
            await interaction.response.send_message(
                f"❌ Debt must be between {min_debt} and {max_debt} coins.",
                ephemeral=True
            )
            return


        if days < 3:
            await interaction.response.send_message(
                "❌ Duration must be at least 3 days.",
                ephemeral=True
            )
            return

        now = time.time()


        balances[self.sender_id] = get_balance(self.sender_id) + self.amount
        balances[self.receiver_id] -= self.amount

        debts[self.sender_id] = {
            "to": self.receiver_id,
            "amount": debt_value,
            "created_at": now,
            "due_time": now + (days * 86400),
            "last_penalty": now,
            "warnings_sent": []
        }

        await interaction.response.send_message(
            f"📄 Debt created!\nAmount: {debt_value}\nDuration: {days} days"
        )

class RequestView(discord.ui.View):
    def __init__(self, sender_id, receiver_id, amount):
        super().__init__(timeout=60)
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.amount = amount

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.receiver_id:
            await interaction.response.send_message("❌ This request isn't for you.", ephemeral=True)
            return

        receiver_balance = get_balance(self.receiver_id)

        if receiver_balance < self.amount:
            await interaction.response.send_message("❌ You don't have enough money.", ephemeral=True)
            return

        if self.amount > receiver_balance * 1.3:
            await interaction.response.send_message(
                f"⚠️ This loan is too risky! You're trying to lend more than 130% of your balance.\nTransaction cancelled.",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content="⚙️ Configure the loan:",
            view=DebtChoiceView(self.sender_id, self.receiver_id, self.amount)
    )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.receiver_id:
            await interaction.response.send_message("❌ This request isn't for you.", ephemeral=True)
            return

        await interaction.response.edit_message(
            content="❌ Loan request declined.",
            view=None
        )

class DebtChoiceView(discord.ui.View):
    def __init__(self, sender_id, receiver_id, amount):
        super().__init__(timeout=60)
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.amount = amount

    @discord.ui.button(label="Set Debt", style=discord.ButtonStyle.primary)
    async def set_debt(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.receiver_id:
            await interaction.response.send_message("❌ Not your request.", ephemeral=True)
            return

        await interaction.response.send_modal(
            DebtModal(self.sender_id, self.receiver_id, self.amount)
        )

    @discord.ui.button(label="No Debt", style=discord.ButtonStyle.green)
    async def no_debt(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.receiver_id:
            await interaction.response.send_message("❌ Not your request.", ephemeral=True)
            return

        balances[self.sender_id] = get_balance(self.sender_id) + self.amount
        balances[self.receiver_id] -= self.amount

        await interaction.response.edit_message(
            content=f"✅ {self.amount} coins sent (no debt).",
            view=None
        )

@bot.event
async def on_ready():
    synced = await bot.tree.sync()
    bot.loop.create_task(check_debts())
    print(f"{bot.user} is ready! Synced {len(synced)} commands")

@bot.tree.command(name="advice", description="Get a random financial tip")
async def advice(interaction: discord.Interaction):
    tip = random.choice(advice_list)
    await interaction.response.send_message(f"📈 {tip}")

@bot.tree.command(name="balance", description="Check your current balance")
async def balance(interaction: discord.Interaction):
    user = str(interaction.user.id)
    bal = get_balance(user)
    await interaction.response.send_message(
        f"💰 Stonks31 Wallet\nYour balance: **{bal} coins**"
    )

@bot.tree.command(name="gift", description="Send money to another user")
async def gift(interaction: discord.Interaction, user: discord.User, amount: int):
    sender_id = str(interaction.user.id)
    receiver_id = str(user.id)

    sender_balance = get_balance(sender_id)

    if sender_id == receiver_id:
        await interaction.response.send_message("❌ You can't send money to yourself.")
        return

    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be greater than 0.")
        return

    if amount > sender_balance:
        await interaction.response.send_message(
            f"❌ You don’t have enough money. Your balance is {sender_balance} coins."
        )
        return

    if amount > sender_balance * 0.5:
        await interaction.response.send_message(
            f"⚠️ That’s more than 50% of your balance ({sender_balance} coins).\nTransaction cancelled."
        )
        return

    allowed, msg = check_budget(sender_id, amount)
    if not allowed:
        await interaction.response.send_message(msg)
        return
    balances[sender_id] -= amount
    balances[receiver_id] = get_balance(receiver_id) + amount
    budgets[sender_id]["spent"] += amount

    await interaction.response.send_message(
        f"💸 You sent {amount} coins to {user.mention}!\n"
        f"Your new balance: {balances[sender_id]} coins"
    )

@bot.tree.command(name="daily", description="Claim your daily reward")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = time.time()

    last_claim = daily_cooldowns.get(user_id, 0)

    if now - last_claim < DAILY_COOLDOWN:
        remaining = int(DAILY_COOLDOWN - (now - last_claim))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60

        await interaction.response.send_message(
            f"⏳ You already claimed your daily.\nTry again in {hours}h {minutes}m."
        )
        return

    balances[user_id] = get_balance(user_id) + DAILY_AMOUNT
    daily_cooldowns[user_id] = now

    await interaction.response.send_message(
        f"🎁 You received {DAILY_AMOUNT} coins!\nBalance: {balances[user_id]}"
    )

@bot.tree.command(name="request", description="Request money from a user")
async def request(interaction: discord.Interaction, user: discord.User, amount: int):
    sender = str(interaction.user.id)
    receiver = str(user.id)

    if sender == receiver:
        await interaction.response.send_message("❌ You can't request from yourself.")
        return

    if amount <= 0:
        await interaction.response.send_message("❌ Invalid amount.")
        return

    view = RequestView(sender, receiver, amount)

    await interaction.response.send_message(
        f"📩 {user.mention}, {interaction.user.mention} is requesting {amount} coins.\nDo you accept?",
        view=view
    )

@bot.tree.command(name="shop", description="View available jobs")
async def shop(interaction: discord.Interaction):
    msg = "🛒 **Job Shop**\n\n"

    for role, cost in job_roles.items():
        msg += f"{role} — {cost} coins\n"

    await interaction.response.send_message(msg)

@bot.tree.command(name="buy", description="Buy a job role")
async def buy(interaction: discord.Interaction, role_name: str):
    user_id = str(interaction.user.id)
    balance = get_balance(user_id)

    role_name = role_name.title()

    if role_name not in job_roles:
        await interaction.response.send_message("❌ Role not found.")
        return

    cost = job_roles[role_name]

    if balance < cost:
        await interaction.response.send_message("❌ Not enough money.")
        return

    role = discord.utils.get(interaction.guild.roles, name=role_name)

    if not role:
        await interaction.response.send_message("❌ Role does not exist in server.")
        return

    allowed, msg = check_budget(user_id, cost)
    if not allowed:
        await interaction.response.send_message(msg)
        return

    for r in interaction.user.roles:
        if r.name in job_roles:
            await interaction.user.remove_roles(r)

    await interaction.user.add_roles(role)

    balances[user_id] -= cost
    budgets[user_id]["spent"] += cost

    await interaction.response.send_message(
        f"✅ You are now a **{role_name}**!\nBalance: {balances[user_id]}"
    )

@bot.tree.command(name="work", description="Work to earn money")
async def work(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = time.time()

    last_work = work_cooldowns.get(user_id, 0)

    if now - last_work < WORK_COOLDOWN:
        remaining = int(WORK_COOLDOWN - (now - last_work))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60

        await interaction.response.send_message(
            f"⏳ You already worked.\nTry again in {hours}h {minutes}m."
        )
        return

    user_roles = [r.name for r in interaction.user.roles]
    job = None

    for role in job_roles:
        if role in user_roles:
            job = role
            break

    if not job:
        await interaction.response.send_message("❌ You don't have a job. Buy one from /shop.")
        return

    if job in ["Broke", "Unemployed"]:
        await interaction.response.send_message(
            f"❌ As a **{job}**, you can't earn from /work.\nGet a better job from /shop."
        )
        return

    pay = max(1, job_roles[job] // 5)

    balances[user_id] = get_balance(user_id) + pay
    work_cooldowns[user_id] = now

    await interaction.response.send_message(
        f"💼 You worked as a **{job}** and earned {pay} coins!\nBalance: {balances[user_id]}"
    )

@bot.tree.command(name="budget", description="Set your daily spending budget")
async def budget(interaction: discord.Interaction, amount: int):
    user_id = str(interaction.user.id)
    balance = get_balance(user_id)

    if amount <= 0:
        await interaction.response.send_message("❌ Budget must be greater than 0.")
        return

    if amount > balance * 0.4:
        await interaction.response.send_message(
            f"❌ Budget cannot exceed 40% of your balance ({int(balance * 0.4)} max)."
        )
        return

    budgets[user_id] = {
        "limit": amount,
        "spent": 0
    }

    budget_reset[user_id] = time.time()

    await interaction.response.send_message(
        f"📊 Daily budget set to {amount} coins."
    )

@bot.tree.command(name="debt", description="Check your current debt")
async def debt(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    if user_id not in debts:
        await interaction.response.send_message("✅ You are not in debt.")
        return

    data = debts[user_id]

    lender_id = data["to"]
    amount = data["amount"]
    due_time = data["due_time"]

    remaining = int(due_time - time.time())

    if remaining < 0:
        remaining = 0

    days = remaining // 86400
    hours = (remaining % 86400) // 3600

    await interaction.response.send_message(
        f"💳 **In Debt:**\n"
        f"From: <@{lender_id}>\n"
        f"Debt: {amount} coins\n"
        f"Time left: {days}d {hours}h"
    )

async def check_debts():
    await bot.wait_until_ready()

    while not bot.is_closed():
        now = time.time()

        to_remove = []

        for user_id, data in debts.items():
            lender = data["to"]
            amount = data["amount"]
            due_time = data["due_time"]

            user = await bot.fetch_user(int(user_id))

            time_left = due_time - now

            warning_times = [
                (86400, "⏰ 1 DAY LEFT to repay your debt!"),
                (21600, "⚠️ 6 HOURS LEFT to repay your debt!"),
                (1200, "🚨 20 MINUTES LEFT to repay your debt!")
            ]

            for seconds, msg in warning_times:
                if time_left <= seconds and seconds not in data["warnings_sent"]:
                    try:
                        await user.send(msg)
                    except:
                        pass
                    data["warnings_sent"].append(seconds)

            if now >= due_time:
                user_balance = get_balance(user_id)

                if user_balance >= amount:
                    balances[user_id] -= amount
                    balances[lender] = get_balance(lender) + amount
                    to_remove.append(user_id)
                    continue

                days_late = int((now - due_time) // 86400)

                if now - data["last_penalty"] >= 86400:
                    data["amount"] = int(data["amount"] * 1.5)
                    data["last_penalty"] = now

                    try:
                        await user.send(
                            f"📈 Your debt increased! New debt: {data['amount']} coins."
                        )
                    except:
                        pass

                if now - due_time >= 2592000: 
                    guild = bot.guilds[0] 
                    member = guild.get_member(int(user_id))

                    if member:
                        try:
                            await member.timeout(discord.utils.utcnow() + timedelta(days=7))
                            reason="Unpaid debt"
                        except:
                            pass

                    channel = guild.system_channel
                    if channel:
                        await channel.send(
                            f"🚨 Admins, <@{user_id}> has not paid their debt within a month!"
                        )

                    to_remove.append(user_id)

        for user_id in to_remove:
            del debts[user_id]

        await asyncio.sleep(60)
bot.run("")
