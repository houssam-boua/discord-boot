import discord
from discord.ext import commands
import json
import os
import asyncio

# ── إعدادات البوت ──────────────────────────────────────────────
TOKEN = os.environ.get("TOKEN")
PREFIX = ".v "                          # بادئة الأوامر
SETUP_CHANNEL_NAME = "➕ إنشاء روم"     # اسم قناة الانضمام لإنشاء روم
AFK_CHANNEL_NAME = "🚫 المطرودون"       # اسم قناة المطرودين
CATEGORY_NAME = "🎙️ الغرف المؤقتة"     # اسم الكاتيغوري
DATA_FILE = "data.json"                # ملف حفظ البيانات

# ── تهيئة البوت ────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ── تحميل وحفظ البيانات ────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"guilds": {}, "rooms": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()

def get_guild_data(guild_id):
    gid = str(guild_id)
    if gid not in data["guilds"]:
        data["guilds"][gid] = {
            "setup_channel": None,
            "afk_channel": None,
            "category": None
        }
    return data["guilds"][gid]

def get_room(channel_id):
    return data["rooms"].get(str(channel_id))

def set_room(channel_id, room_data):
    data["rooms"][str(channel_id)] = room_data
    save_data(data)

def delete_room(channel_id):
    data["rooms"].pop(str(channel_id), None)
    save_data(data)

# ── دالة مساعدة: هل المستخدم مالك الروم؟ ──────────────────────
def is_owner(channel_id, user_id):
    room = get_room(channel_id)
    return room and room["owner"] == user_id

# ── إيفنت: عند تشغيل البوت ─────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ البوت شغال: {bot.user}")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening,
        name=".v help"
    ))

# ── إيفنت: إعداد السيرفر تلقائياً ─────────────────────────────
@bot.event
async def on_guild_join(guild):
    await setup_server(guild)

async def setup_server(guild):
    gd = get_guild_data(guild.id)

    # تحقق إن الكاتيغوري موجود
    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not category:
        category = await guild.create_category(CATEGORY_NAME)

    # قناة الانضمام لإنشاء روم
    setup_ch = discord.utils.get(guild.voice_channels, name=SETUP_CHANNEL_NAME)
    if not setup_ch:
        setup_ch = await guild.create_voice_channel(
            SETUP_CHANNEL_NAME,
            category=category,
            position=0
        )

    # قناة المطرودين
    afk_ch = discord.utils.get(guild.voice_channels, name=AFK_CHANNEL_NAME)
    if not afk_ch:
        afk_ch = await guild.create_voice_channel(
            AFK_CHANNEL_NAME,
            category=category,
            position=1
        )

    gd["setup_channel"] = setup_ch.id
    gd["afk_channel"] = afk_ch.id
    gd["category"] = category.id
    save_data(data)
    print(f"✅ تم إعداد السيرفر: {guild.name}")

# ── أمر الإعداد اليدوي ─────────────────────────────────────────
@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_cmd(ctx):
    await setup_server(ctx.guild)
    embed = discord.Embed(
        title="✅ تم الإعداد بنجاح!",
        description=(
            f"تم إنشاء:\n"
            f"📁 كاتيغوري: **{CATEGORY_NAME}**\n"
            f"🎙️ قناة الإنشاء: **{SETUP_CHANNEL_NAME}**\n"
            f"🚫 قناة المطرودين: **{AFK_CHANNEL_NAME}**\n\n"
            f"الأعضاء الآن يدخلون قناة **{SETUP_CHANNEL_NAME}** لإنشاء غرفتهم!"
        ),
        color=0x2ecc71
    )
    await ctx.send(embed=embed)

# ── إيفنت: عند تغيير حالة الصوت (الدخول/الخروج) ────────────────
@bot.event
async def on_voice_state_update(member, before, after):
    gd = get_guild_data(member.guild.id)

    # ── المستخدم انضم لقناة الإنشاء → صنع روم جديدة ──
    if after.channel and after.channel.id == gd.get("setup_channel"):
        category = member.guild.get_channel(gd.get("category"))
        room_name = f"🎙️ غرفة {member.display_name}"

        overwrites = {
            member.guild.default_role: discord.PermissionOverwrite(connect=True),
            member: discord.PermissionOverwrite(
                connect=True, manage_channels=True,
                move_members=True, mute_members=True
            )
        }

        new_channel = await member.guild.create_voice_channel(
            room_name,
            category=category,
            overwrites=overwrites
        )

        set_room(new_channel.id, {
            "owner": member.id,
            "banned": [],
            "permitted": []
        })

        try:
            await member.move_to(new_channel)
        except Exception:
            pass

    # ── المستخدم خرج من روم → تحقق إن كانت فارغة فاحذفها ──
    if before.channel and before.channel.id != gd.get("setup_channel"):
        room = get_room(before.channel.id)
        if room:
            # إن الروم فارغة احذفها
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                except Exception:
                    pass
                delete_room(before.channel.id)
            # إن صاحب الروم خرج، انقل الملكية لأول شخص
            elif room["owner"] == member.id and before.channel.members:
                new_owner = before.channel.members[0]
                room["owner"] = new_owner.id
                set_room(before.channel.id, room)
                try:
                    await before.channel.send(
                        f"👑 تم نقل ملكية الغرفة إلى {new_owner.mention} لأن المالك السابق غادر."
                    )
                except Exception:
                    pass

# ── دالة مساعدة: التحقق من الروم والملكية ─────────────────────
async def check_room(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ يجب أن تكون في غرفة صوتية!")
        return None
    channel = ctx.author.voice.channel
    room = get_room(channel.id)
    if not room:
        await ctx.send("❌ غرفتك ليست غرفة مؤقتة!")
        return None
    if room["owner"] != ctx.author.id:
        await ctx.send("❌ أنت لست مالك هذه الغرفة!")
        return None
    return channel, room

# ══════════════════════════════════════════════════════════════
#  الأوامر
# ══════════════════════════════════════════════════════════════

# .v lock ─────────────────────────────────────────────────────
@bot.command(name="lock")
async def lock(ctx):
    result = await check_room(ctx)
    if not result: return
    channel, room = result
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.connect = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 تم قفل الغرفة!")

# .v unlock ───────────────────────────────────────────────────
@bot.command(name="unlock")
async def unlock(ctx):
    result = await check_room(ctx)
    if not result: return
    channel, room = result
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.connect = True
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 تم فتح الغرفة!")

# .v hide ─────────────────────────────────────────────────────
@bot.command(name="hide")
async def hide(ctx):
    result = await check_room(ctx)
    if not result: return
    channel, room = result
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.view_channel = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("👁️ تم إخفاء الغرفة!")

# .v unhide ───────────────────────────────────────────────────
@bot.command(name="unhide")
async def unhide(ctx):
    result = await check_room(ctx)
    if not result: return
    channel, room = result
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.view_channel = True
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("👁️ تم إظهار الغرفة!")

# .v name [اسم] ───────────────────────────────────────────────
@bot.command(name="name")
async def name_cmd(ctx, *, new_name: str):
    result = await check_room(ctx)
    if not result: return
    channel, room = result
    await channel.edit(name=new_name)
    await ctx.send(f"✏️ تم تغيير اسم الغرفة إلى: **{new_name}**")

# .v limit [عدد] ──────────────────────────────────────────────
@bot.command(name="limit")
async def limit(ctx, num: int):
    result = await check_room(ctx)
    if not result: return
    channel, room = result
    if num < 0 or num > 99:
        await ctx.send("❌ العدد يجب أن يكون بين 0 و 99!")
        return
    await channel.edit(user_limit=num)
    limit_text = f"**{num}**" if num > 0 else "غير محدود"
    await ctx.send(f"👥 تم تحديد عدد الأشخاص إلى: {limit_text}")

# .v bitrate [رقم] ────────────────────────────────────────────
@bot.command(name="bitrate")
async def bitrate(ctx, rate: int):
    result = await check_room(ctx)
    if not result: return
    channel, room = result
    rate_bps = rate * 1000
    max_bitrate = ctx.guild.bitrate_limit
    if rate_bps < 8000 or rate_bps > max_bitrate:
        await ctx.send(f"❌ الجودة يجب أن تكون بين 8 و {int(max_bitrate/1000)} kbps!")
        return
    await channel.edit(bitrate=rate_bps)
    await ctx.send(f"🎵 تم تغيير جودة الصوت إلى: **{rate} kbps**")

# .v reject @user ─────────────────────────────────────────────
@bot.command(name="reject")
async def reject(ctx, member: discord.Member):
    result = await check_room(ctx)
    if not result: return
    channel, room = result
    if member == ctx.author:
        await ctx.send("❌ لا تستطيع طرد نفسك!")
        return
    gd = get_guild_data(ctx.guild.id)
    afk_channel = ctx.guild.get_channel(gd.get("afk_channel"))
    if member.voice and member.voice.channel == channel:
        if afk_channel:
            await member.move_to(afk_channel)
        else:
            await member.move_to(None)
    await channel.set_permissions(member, connect=False)
    await ctx.send(f"👢 تم طرد {member.mention} من الغرفة!")

# .v ban @user ────────────────────────────────────────────────
@bot.command(name="ban")
async def ban_cmd(ctx, member: discord.Member):
    result = await check_room(ctx)
    if not result: return
    channel, room = result
    if member == ctx.author:
        await ctx.send("❌ لا تستطيع حظر نفسك!")
        return
    if member.id not in room["banned"]:
        room["banned"].append(member.id)
    set_room(channel.id, room)
    gd = get_guild_data(ctx.guild.id)
    afk_channel = ctx.guild.get_channel(gd.get("afk_channel"))
    if member.voice and member.voice.channel == channel:
        if afk_channel:
            await member.move_to(afk_channel)
        else:
            await member.move_to(None)
    await channel.set_permissions(member, connect=False, view_channel=False)
    await ctx.send(f"🔨 تم حظر {member.mention} من الغرفة!")

# .v permit @user ─────────────────────────────────────────────
@bot.command(name="permit")
async def permit(ctx, member: discord.Member):
    result = await check_room(ctx)
    if not result: return
    channel, room = result
    if member.id in room["banned"]:
        room["banned"].remove(member.id)
    if member.id not in room["permitted"]:
        room["permitted"].append(member.id)
    set_room(channel.id, room)
    await channel.set_permissions(member, connect=True, view_channel=True)
    await ctx.send(f"✅ تم السماح لـ {member.mention} بالدخول!")

# .v claim ────────────────────────────────────────────────────
@bot.command(name="claim")
async def claim(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ يجب أن تكون في غرفة صوتية!")
        return
    channel = ctx.author.voice.channel
    room = get_room(channel.id)
    if not room:
        await ctx.send("❌ غرفتك ليست غرفة مؤقتة!")
        return
    current_owner = ctx.guild.get_member(room["owner"])
    if current_owner and current_owner in channel.members:
        await ctx.send(f"❌ المالك الحالي {current_owner.mention} لا يزال في الغرفة!")
        return
    room["owner"] = ctx.author.id
    set_room(channel.id, room)
    await ctx.send(f"👑 تم نقل ملكية الغرفة إليك {ctx.author.mention}!")

# .v transfer @user ───────────────────────────────────────────
@bot.command(name="transfer")
async def transfer(ctx, member: discord.Member):
    result = await check_room(ctx)
    if not result: return
    channel, room = result
    if member == ctx.author:
        await ctx.send("❌ أنت بالفعل المالك!")
        return
    if member not in channel.members:
        await ctx.send("❌ هذا الشخص ليس في الغرفة!")
        return
    room["owner"] = member.id
    set_room(channel.id, room)
    await ctx.send(f"👑 تم نقل ملكية الغرفة إلى {member.mention}!")

# .v help ─────────────────────────────────────────────────────
@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="🎙️ أوامر الغرف المؤقتة",
        description="ادخل قناة **➕ إنشاء روم** لتبدأ!",
        color=0x5865F2
    )
    embed.add_field(name="🔒 التحكم بالوصول", value=(
        "`.v lock` — قفل الغرفة\n"
        "`.v unlock` — فتح الغرفة\n"
        "`.v hide` — إخفاء الغرفة\n"
        "`.v unhide` — إظهار الغرفة"
    ), inline=False)
    embed.add_field(name="⚙️ إعدادات الغرفة", value=(
        "`.v name [اسم]` — تغيير الاسم\n"
        "`.v limit [عدد]` — تحديد العدد\n"
        "`.v bitrate [رقم]` — جودة الصوت (kbps)"
    ), inline=False)
    embed.add_field(name="👥 إدارة الأعضاء", value=(
        "`.v reject @user` — طرد عضو\n"
        "`.v ban @user` — حظر عضو\n"
        "`.v permit @user` — السماح لعضو"
    ), inline=False)
    embed.add_field(name="👑 الملكية", value=(
        "`.v claim` — أخذ الملكية (إن غاب المالك)\n"
        "`.v transfer @user` — نقل الملكية"
    ), inline=False)
    embed.set_footer(text="البوت يحذف الغرف تلقائياً عند إخلائها")
    await ctx.send(embed=embed)

# ── تشغيل البوت ────────────────────────────────────────────────
bot.run(TOKEN)
