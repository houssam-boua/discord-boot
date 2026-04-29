import discord
from discord.ext import commands
import json
import os

# ══════════════════════════════════════════════════════════════════
#  إعدادات البوت
# ══════════════════════════════════════════════════════════════════
TOKEN = os.environ.get("TOKEN")
PREFIX            = ".v "
SETUP_CHANNEL_NAME = "➕ إنشاء روم"
AFK_CHANNEL_NAME   = "🚫 المطرودون"
CATEGORY_NAME      = "🎙️ الغرف المؤقتة"
DATA_FILE          = "data.json"

# ══════════════════════════════════════════════════════════════════
#  تهيئة البوت
# ══════════════════════════════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states    = True
intents.members         = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ══════════════════════════════════════════════════════════════════
#  تحميل وحفظ البيانات
# ══════════════════════════════════════════════════════════════════
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"guilds": {}, "rooms": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

data = load_data()

def get_guild_data(guild_id):
    gid = str(guild_id)
    if gid not in data["guilds"]:
        data["guilds"][gid] = {
            "setup_channel": None,
            "afk_channel":   None,
            "category":      None,
            "log_channel":   None,
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

# ══════════════════════════════════════════════════════════════════
#  Embed Helpers
# ══════════════════════════════════════════════════════════════════
def success_embed(msg: str) -> discord.Embed:
    return discord.Embed(description=msg, color=0x2ecc71)

def error_embed(msg: str) -> discord.Embed:
    return discord.Embed(description=f"❌ {msg}", color=0xe74c3c)

def info_embed(title: str, msg: str) -> discord.Embed:
    return discord.Embed(title=title, description=msg, color=0x5865F2)

# ══════════════════════════════════════════════════════════════════
#  دالة الإعداد
# ══════════════════════════════════════════════════════════════════
async def setup_server(guild: discord.Guild):
    """إنشاء أو التحقق من قنوات البوت على السيرفر."""
    gd = get_guild_data(guild.id)

    # ─── الكاتيغوري ───
    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not category:
        category = await guild.create_category(CATEGORY_NAME)

    # ─── قناة الإنشاء ───
    setup_ch = guild.get_channel(gd.get("setup_channel") or 0)
    if not setup_ch or not isinstance(setup_ch, discord.VoiceChannel):
        setup_ch = discord.utils.get(guild.voice_channels, name=SETUP_CHANNEL_NAME)
        if not setup_ch:
            setup_ch = await guild.create_voice_channel(
                SETUP_CHANNEL_NAME, category=category, position=0
            )

    # ─── قناة المطرودين ───
    afk_ch = guild.get_channel(gd.get("afk_channel") or 0)
    if not afk_ch or not isinstance(afk_ch, discord.VoiceChannel):
        afk_ch = discord.utils.get(guild.voice_channels, name=AFK_CHANNEL_NAME)
        if not afk_ch:
            afk_ch = await guild.create_voice_channel(
                AFK_CHANNEL_NAME, category=category, position=1
            )

    gd["setup_channel"] = setup_ch.id
    gd["afk_channel"]   = afk_ch.id
    gd["category"]      = category.id
    save_data(data)
    print(f"✅ إعداد السيرفر: {guild.name}")
    return category, setup_ch, afk_ch

# ══════════════════════════════════════════════════════════════════
#  دالة السجل
# ══════════════════════════════════════════════════════════════════
async def log_action(guild: discord.Guild, message: str):
    gd = get_guild_data(guild.id)
    if gd.get("log_channel"):
        ch = guild.get_channel(gd["log_channel"])
        if ch:
            try:
                embed = discord.Embed(description=message, color=0x7289da)
                import datetime
                embed.timestamp = datetime.datetime.utcnow()
                await ch.send(embed=embed)
            except discord.HTTPException:
                pass

# ══════════════════════════════════════════════════════════════════
#  on_ready
# ══════════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    print(f"✅ البوت شغال: {bot.user} | {len(bot.guilds)} سيرفر")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, name=".v help"
    ))

    # تنظيف الغرف المنتهية من ملف البيانات
    stale = [
        cid for cid in list(data["rooms"].keys())
        if not any(g.get_channel(int(cid)) for g in bot.guilds)
    ]
    for cid in stale:
        data["rooms"].pop(cid, None)
    if stale:
        save_data(data)
        print(f"🧹 حُذف {len(stale)} غرفة منتهية من البيانات.")

    # إعادة إعداد السيرفرات التي فُقدت قنواتها
    for guild in bot.guilds:
        gd = get_guild_data(guild.id)
        ch = guild.get_channel(gd.get("setup_channel") or 0)
        if not ch:
            try:
                await setup_server(guild)
            except discord.Forbidden:
                print(f"⚠️ لا صلاحية لإعداد: {guild.name}")

@bot.event
async def on_guild_join(guild: discord.Guild):
    await setup_server(guild)

# ══════════════════════════════════════════════════════════════════
#  أوامر الإدارة
# ══════════════════════════════════════════════════════════════════
@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_cmd(ctx):
    try:
        category, setup_ch, afk_ch = await setup_server(ctx.guild)
        embed = discord.Embed(title="✅ تم الإعداد بنجاح!", color=0x2ecc71)
        embed.add_field(name="📁 الكاتيغوري",     value=f"**{CATEGORY_NAME}**",  inline=False)
        embed.add_field(name="🎙️ قناة الإنشاء",  value=setup_ch.mention,        inline=True)
        embed.add_field(name="🚫 قناة المطرودين", value=afk_ch.mention,          inline=True)
        embed.set_footer(text="ادخل قناة الإنشاء لتفعيل غرفتك!")
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send(embed=error_embed("ليس لدي صلاحية لإنشاء القنوات!"))

@bot.command(name="setlog")
@commands.has_permissions(administrator=True)
async def setlog(ctx, channel: discord.TextChannel = None):
    gd = get_guild_data(ctx.guild.id)
    target = channel or ctx.channel
    gd["log_channel"] = target.id
    save_data(data)
    await ctx.send(embed=success_embed(f"📋 قناة السجل: {target.mention}"))

# ══════════════════════════════════════════════════════════════════
#  إيفنت تغيير حالة الصوت
# ══════════════════════════════════════════════════════════════════
@bot.event
async def on_voice_state_update(member: discord.Member, before, after):
    gd = get_guild_data(member.guild.id)

    # ── دخل قناة الإنشاء → إنشاء غرفة ──────────────────────────
    if after.channel and after.channel.id == gd.get("setup_channel"):
        category = member.guild.get_channel(gd.get("category"))
        room_name = f"🎙️ غرفة {member.display_name}"

        overwrites = {
            member.guild.default_role: discord.PermissionOverwrite(
                connect=True, view_channel=True
            ),
            member: discord.PermissionOverwrite(
                connect=True, view_channel=True,
                manage_channels=True, move_members=True, mute_members=True
            ),
        }

        try:
            new_channel = await member.guild.create_voice_channel(
                room_name, category=category, overwrites=overwrites
            )
        except discord.Forbidden:
            return

        set_room(new_channel.id, {
            "owner":     member.id,
            "banned":    [],
            "permitted": [],
        })

        try:
            await member.move_to(new_channel)
        except discord.HTTPException:
            pass

        await log_action(
            member.guild,
            f"🎙️ **{member.display_name}** أنشأ غرفة جديدة: **{room_name}**"
        )

    # ── خرج من غرفة مؤقتة ───────────────────────────────────────
    if (
        before.channel
        and before.channel.id != gd.get("setup_channel")
        and before.channel.id != gd.get("afk_channel")
    ):
        room = get_room(before.channel.id)
        if not room:
            return

        # الغرفة فارغة → احذفها
        if len(before.channel.members) == 0:
            delete_room(before.channel.id)
            try:
                await before.channel.delete(reason="غرفة مؤقتة فارغة")
            except (discord.NotFound, discord.Forbidden):
                pass
            await log_action(
                member.guild,
                f"🗑️ حُذفت الغرفة الفارغة: **{before.channel.name}**"
            )
            return

        # المالك غادر → انقل الملكية لأول عضو
        if room["owner"] == member.id:
            new_owner = before.channel.members[0]
            room["owner"] = new_owner.id
            set_room(before.channel.id, room)

            notify_ch = member.guild.system_channel
            if notify_ch:
                try:
                    await notify_ch.send(embed=info_embed(
                        "👑 تغيير الملكية",
                        f"ملكية **{before.channel.name}** انتقلت إلى "
                        f"{new_owner.mention} بعد مغادرة المالك."
                    ))
                except discord.HTTPException:
                    pass

            await log_action(
                member.guild,
                f"👑 ملكية **{before.channel.name}** → {new_owner.display_name}"
            )

# ══════════════════════════════════════════════════════════════════
#  دالة التحقق من الغرفة والملكية
# ══════════════════════════════════════════════════════════════════
async def check_room(ctx) -> tuple[discord.VoiceChannel | None, dict | None]:
    """
    يُعيد (channel, room) إذا كان المستخدم في غرفة مؤقتة يملكها،
    أو (None, None) مع إرسال رسالة الخطأ.
    """
    if not ctx.author.voice:
        await ctx.send(embed=error_embed("يجب أن تكون في غرفة صوتية!"))
        return None, None

    channel = ctx.author.voice.channel
    room = get_room(channel.id)

    if not room:
        await ctx.send(embed=error_embed("غرفتك ليست غرفة مؤقتة!"))
        return None, None

    if room["owner"] != ctx.author.id:
        owner = ctx.guild.get_member(room["owner"])
        name = owner.display_name if owner else "شخص آخر"
        await ctx.send(embed=error_embed(f"أنت لست مالك هذه الغرفة! المالك: **{name}**"))
        return None, None

    return channel, room

# ══════════════════════════════════════════════════════════════════
#  🔒 التحكم بالوصول
# ══════════════════════════════════════════════════════════════════
@bot.command(name="lock")
@commands.cooldown(1, 5, commands.BucketType.user)
async def lock(ctx):
    channel, _ = await check_room(ctx)
    if not channel: return
    ow = channel.overwrites_for(ctx.guild.default_role)
    ow.connect = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=ow)
    await ctx.send(embed=success_embed("🔒 تم **قفل** الغرفة! لا أحد يستطيع الدخول الآن."))
    await log_action(ctx.guild, f"🔒 {ctx.author.display_name} قفل غرفته **{channel.name}**")

@bot.command(name="unlock")
@commands.cooldown(1, 5, commands.BucketType.user)
async def unlock(ctx):
    channel, _ = await check_room(ctx)
    if not channel: return
    ow = channel.overwrites_for(ctx.guild.default_role)
    ow.connect = True
    await channel.set_permissions(ctx.guild.default_role, overwrite=ow)
    await ctx.send(embed=success_embed("🔓 تم **فتح** الغرفة!"))
    await log_action(ctx.guild, f"🔓 {ctx.author.display_name} فتح غرفته **{channel.name}**")

@bot.command(name="hide")
@commands.cooldown(1, 5, commands.BucketType.user)
async def hide(ctx):
    channel, _ = await check_room(ctx)
    if not channel: return
    ow = channel.overwrites_for(ctx.guild.default_role)
    ow.view_channel = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=ow)
    await ctx.send(embed=success_embed("🙈 تم **إخفاء** الغرفة من القائمة!"))

@bot.command(name="unhide")
@commands.cooldown(1, 5, commands.BucketType.user)
async def unhide(ctx):
    channel, _ = await check_room(ctx)
    if not channel: return
    ow = channel.overwrites_for(ctx.guild.default_role)
    ow.view_channel = True
    await channel.set_permissions(ctx.guild.default_role, overwrite=ow)
    await ctx.send(embed=success_embed("👁️ تم **إظهار** الغرفة!"))

# ══════════════════════════════════════════════════════════════════
#  ⚙️ إعدادات الغرفة
# ══════════════════════════════════════════════════════════════════
@bot.command(name="name")
@commands.cooldown(1, 10, commands.BucketType.user)   # Discord يُقيّد تغيير الأسماء
async def name_cmd(ctx, *, new_name: str):
    channel, _ = await check_room(ctx)
    if not channel: return
    if len(new_name) > 100:
        await ctx.send(embed=error_embed("الاسم يجب أن لا يتجاوز **100 حرف**!"))
        return
    if len(new_name) < 1:
        await ctx.send(embed=error_embed("الاسم لا يمكن أن يكون فارغاً!"))
        return
    await channel.edit(name=new_name)
    await ctx.send(embed=success_embed(f"✏️ تم تغيير اسم الغرفة إلى: **{new_name}**"))

@bot.command(name="limit")
@commands.cooldown(1, 5, commands.BucketType.user)
async def limit(ctx, num: int):
    channel, _ = await check_room(ctx)
    if not channel: return
    if not (0 <= num <= 99):
        await ctx.send(embed=error_embed("العدد يجب أن يكون بين **0** (غير محدود) و **99**!"))
        return
    await channel.edit(user_limit=num)
    text = f"**{num}** شخص" if num > 0 else "**غير محدود**"
    await ctx.send(embed=success_embed(f"👥 تم تحديد السعة إلى: {text}"))

@bot.command(name="bitrate")
@commands.cooldown(1, 5, commands.BucketType.user)
async def bitrate(ctx, rate: int):
    channel, _ = await check_room(ctx)
    if not channel: return
    rate_bps  = rate * 1000
    max_br    = ctx.guild.bitrate_limit
    if not (8000 <= rate_bps <= max_br):
        await ctx.send(embed=error_embed(
            f"الجودة يجب أن تكون بين **8** و **{int(max_br / 1000)} kbps**!"
        ))
        return
    await channel.edit(bitrate=rate_bps)
    await ctx.send(embed=success_embed(f"🎵 تم تغيير جودة الصوت إلى: **{rate} kbps**"))

# ══════════════════════════════════════════════════════════════════
#  👥 إدارة الأعضاء
# ══════════════════════════════════════════════════════════════════
@bot.command(name="reject")
@commands.cooldown(1, 5, commands.BucketType.user)
async def reject(ctx, member: discord.Member):
    """طرد عضو مؤقتاً (يمكنه العودة بعد السماح له)."""
    channel, _ = await check_room(ctx)
    if not channel: return
    if member == ctx.author:
        await ctx.send(embed=error_embed("لا تستطيع طرد نفسك!")); return
    if member.guild_permissions.administrator:
        await ctx.send(embed=error_embed("لا تستطيع طرد مشرف!")); return

    gd    = get_guild_data(ctx.guild.id)
    afk_ch = ctx.guild.get_channel(gd.get("afk_channel"))

    if member.voice and member.voice.channel == channel:
        try:
            await member.move_to(afk_ch if afk_ch else None)
        except discord.HTTPException:
            pass

    # منع الدخول مؤقتاً حتى يُرفع بأمر permit
    await channel.set_permissions(member, connect=False)
    await ctx.send(embed=success_embed(f"👢 تم طرد {member.mention} من الغرفة مؤقتاً!"))
    await log_action(ctx.guild,
        f"👢 {ctx.author.display_name} طرد {member.display_name} من **{channel.name}**"
    )

@bot.command(name="ban")
@commands.cooldown(1, 5, commands.BucketType.user)
async def ban_cmd(ctx, member: discord.Member):
    """حظر عضو نهائياً من الغرفة (لا يرى ولا يدخل)."""
    channel, room = await check_room(ctx)
    if not channel: return
    if member == ctx.author:
        await ctx.send(embed=error_embed("لا تستطيع حظر نفسك!")); return
    if member.guild_permissions.administrator:
        await ctx.send(embed=error_embed("لا تستطيع حظر مشرف!")); return
    if member.id == room["owner"]:
        await ctx.send(embed=error_embed("لا تستطيع حظر المالك!")); return

    if member.id not in room["banned"]:
        room["banned"].append(member.id)
    room["permitted"] = [x for x in room["permitted"] if x != member.id]
    set_room(channel.id, room)

    gd    = get_guild_data(ctx.guild.id)
    afk_ch = ctx.guild.get_channel(gd.get("afk_channel"))

    if member.voice and member.voice.channel == channel:
        try:
            await member.move_to(afk_ch if afk_ch else None)
        except discord.HTTPException:
            pass

    await channel.set_permissions(member, connect=False, view_channel=False)
    await ctx.send(embed=success_embed(f"🔨 تم **حظر** {member.mention} نهائياً من الغرفة!"))
    await log_action(ctx.guild,
        f"🔨 {ctx.author.display_name} حظر {member.display_name} من **{channel.name}**"
    )

@bot.command(name="permit")
@commands.cooldown(1, 5, commands.BucketType.user)
async def permit(ctx, member: discord.Member):
    """رفع الحظر أو الطرد والسماح للعضو بالدخول."""
    channel, room = await check_room(ctx)
    if not channel: return

    room["banned"]    = [x for x in room["banned"]    if x != member.id]
    room["permitted"] = [x for x in room["permitted"] if x != member.id]
    room["permitted"].append(member.id)
    set_room(channel.id, room)

    await channel.set_permissions(member, connect=True, view_channel=True)
    await ctx.send(embed=success_embed(f"✅ تم السماح لـ {member.mention} بالدخول!"))

# ══════════════════════════════════════════════════════════════════
#  👑 الملكية
# ══════════════════════════════════════════════════════════════════
@bot.command(name="claim")
@commands.cooldown(1, 5, commands.BucketType.user)
async def claim(ctx):
    """أخذ ملكية الغرفة إذا غاب صاحبها."""
    if not ctx.author.voice:
        await ctx.send(embed=error_embed("يجب أن تكون في غرفة صوتية!")); return

    channel = ctx.author.voice.channel
    room    = get_room(channel.id)

    if not room:
        await ctx.send(embed=error_embed("غرفتك ليست غرفة مؤقتة!")); return

    if room["owner"] == ctx.author.id:
        await ctx.send(embed=error_embed("أنت بالفعل مالك الغرفة!")); return

    current_owner = ctx.guild.get_member(room["owner"])
    if current_owner and current_owner in channel.members:
        await ctx.send(embed=error_embed(
            f"المالك {current_owner.mention} لا يزال في الغرفة!"
        )); return

    room["owner"] = ctx.author.id
    set_room(channel.id, room)
    await ctx.send(embed=success_embed(f"👑 أصبحت مالك الغرفة {ctx.author.mention}!"))
    await log_action(ctx.guild,
        f"👑 {ctx.author.display_name} أخذ ملكية **{channel.name}**"
    )

@bot.command(name="transfer")
@commands.cooldown(1, 5, commands.BucketType.user)
async def transfer(ctx, member: discord.Member):
    """نقل ملكية الغرفة لعضو آخر داخلها."""
    channel, room = await check_room(ctx)
    if not channel: return

    if member == ctx.author:
        await ctx.send(embed=error_embed("أنت بالفعل المالك!")); return
    if member not in channel.members:
        await ctx.send(embed=error_embed("هذا الشخص ليس في الغرفة!")); return

    room["owner"] = member.id
    set_room(channel.id, room)
    await ctx.send(embed=success_embed(f"👑 تم نقل الملكية إلى {member.mention}!"))
    await log_action(ctx.guild,
        f"👑 {ctx.author.display_name} نقل ملكية **{channel.name}** إلى {member.display_name}"
    )

# ══════════════════════════════════════════════════════════════════
#  ℹ️ معلومات الغرفة
# ══════════════════════════════════════════════════════════════════
@bot.command(name="info")
async def info_cmd(ctx):
    """عرض معلومات الغرفة الحالية."""
    if not ctx.author.voice:
        await ctx.send(embed=error_embed("يجب أن تكون في غرفة صوتية!")); return

    channel = ctx.author.voice.channel
    room    = get_room(channel.id)

    if not room:
        await ctx.send(embed=error_embed("غرفتك ليست غرفة مؤقتة!")); return

    owner    = ctx.guild.get_member(room["owner"])
    ow       = channel.overwrites_for(ctx.guild.default_role)
    locked   = "🔒 مقفلة"   if ow.connect    is False else "🔓 مفتوحة"
    hidden   = "🙈 مخفية"   if ow.view_channel is False else "👁️ ظاهرة"
    capacity = f"{channel.user_limit}" if channel.user_limit > 0 else "∞"

    embed = discord.Embed(title=f"🎙️ {channel.name}", color=0x5865F2)
    embed.add_field(name="👑 المالك",
        value=owner.mention if owner else "غير معروف", inline=True)
    embed.add_field(name="👥 الأعضاء",
        value=f"{len(channel.members)} / {capacity}", inline=True)
    embed.add_field(name="🎵 الجودة",
        value=f"{channel.bitrate // 1000} kbps", inline=True)
    embed.add_field(name="🔒 الحالة", value=locked,  inline=True)
    embed.add_field(name="👁️ الظهور", value=hidden,  inline=True)
    embed.add_field(name="🚫 محظورون",
        value=f"{len(room['banned'])} شخص", inline=True)

    members_list = "\n".join(
        f"{'👑' if m.id == room['owner'] else '👤'} {m.display_name}"
        for m in channel.members
    ) or "لا أحد"
    embed.add_field(name="📋 الأعضاء الحاليون", value=members_list, inline=False)
    await ctx.send(embed=embed)

# ══════════════════════════════════════════════════════════════════
#  📖 المساعدة
# ══════════════════════════════════════════════════════════════════
@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="🎙️ بوت الغرف المؤقتة",
        description=(
            f"ادخل قناة **{SETUP_CHANNEL_NAME}** لإنشاء غرفتك تلقائياً!\n"
            "البادئة: **`.v `** (نقطة v مسافة)\n\u200b"
        ),
        color=0x5865F2,
    )
    embed.add_field(name="🔒 التحكم بالوصول", value=(
        "`.v lock`     — قفل الغرفة (لا أحد يدخل)\n"
        "`.v unlock`   — فتح الغرفة\n"
        "`.v hide`     — إخفاء الغرفة من القائمة\n"
        "`.v unhide`   — إظهار الغرفة"
    ), inline=False)
    embed.add_field(name="⚙️ إعدادات الغرفة", value=(
        "`.v name [اسم]`    — تغيير اسم الغرفة\n"
        "`.v limit [عدد]`   — تحديد السعة (0 = غير محدود)\n"
        "`.v bitrate [رقم]` — جودة الصوت بالـ kbps"
    ), inline=False)
    embed.add_field(name="👥 إدارة الأعضاء", value=(
        "`.v reject @user` — طرد مؤقت (يمنع إعادة الدخول)\n"
        "`.v ban @user`    — حظر نهائي (لا يرى الغرفة)\n"
        "`.v permit @user` — رفع الحظر والسماح بالدخول"
    ), inline=False)
    embed.add_field(name="👑 الملكية", value=(
        "`.v claim`          — أخذ الملكية إذا غاب صاحبها\n"
        "`.v transfer @user` — نقل الملكية لشخص آخر في الغرفة"
    ), inline=False)
    embed.add_field(name="ℹ️ أخرى", value=(
        "`.v info`              — معلومات الغرفة الحالية\n"
        "`.v setup`             — إعداد البوت (مشرف)\n"
        "`.v setlog [#قناة]`    — تعيين قناة السجل (مشرف)"
    ), inline=False)
    embed.set_footer(
        text="الغرف تُحذف تلقائياً عند إخلائها • الملكية تنتقل تلقائياً عند مغادرة المالك"
    )
    await ctx.send(embed=embed)

# ══════════════════════════════════════════════════════════════════
#  معالجة الأخطاء
# ══════════════════════════════════════════════════════════════════
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(embed=error_embed(
            f"انتظر **{error.retry_after:.1f}** ثانية قبل إعادة هذا الأمر!"
        ))
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(embed=error_embed("لم يُعثر على هذا العضو! تأكد من @mention الصحيح."))
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=error_embed(
            f"ناقص المدخل: **{error.param.name}** — راجع `.v help`"
        ))
    elif isinstance(error, commands.BadArgument):
        await ctx.send(embed=error_embed("صيغة غير صحيحة! مثال: `.v limit 5` أو `.v ban @user`"))
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=error_embed("ليس لديك صلاحية لهذا الأمر!"))
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send(embed=error_embed("ليس لدي الصلاحيات الكافية لتنفيذ هذا!"))
    elif isinstance(error, commands.CommandNotFound):
        pass  # تجاهل الأوامر غير الموجودة
    else:
        print(f"[ERROR] {type(error).__name__}: {error}")

# ══════════════════════════════════════════════════════════════════
#  تشغيل البوت
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    bot.run(TOKEN)
