# utils/identity.py — Centralized Identity Resolver untuk Mirai
"""
Satu-satunya tempat untuk resolve dan membersihkan nama user.
Semua modul HARUS pakai ini, tidak boleh ambil nama langsung dari ctx/author.

Aturan:
- Server (ctx.guild ada): pakai display_name (nickname server)
- DM (ctx.guild None):  pakai author.name (global name)
"""

import discord
from typing import Union


def resolve_name(ctx_or_author: Union[discord.Interaction, discord.Message, discord.Member, discord.User]) -> str:
    """
    Resolve nama user dari context apapun.
    
    Aturan:
    - Jika ada guild (server): gunakan display_name (nickname di server itu)
    - Jika tidak (DM): gunakan author.name (global username)
    
    Args:
        ctx_or_author: Bisa berupa discord.Interaction, discord.Message, 
                       discord.Member, atau discord.User
    
    Returns:
        str: Nama user yang sudah di-resolve
    
    Contoh:
        # Dari slash command (Interaction)
        name = resolve_name(interaction)  # -> display_name di server, atau name di DM
        
        # Dari message event
        name = resolve_name(message)      # -> display_name di server, atau name di DM
        
        # Dari member/user langsung
        name = resolve_name(member)       # -> display_name
        name = resolve_name(user)         # -> name (DM context)
    """
    # Ekstrak author dari berbagai tipe context
    if isinstance(ctx_or_author, discord.Interaction):
        author = ctx_or_author.user
        guild = ctx_or_author.guild
    elif isinstance(ctx_or_author, discord.Message):
        author = ctx_or_author.author
        guild = ctx_or_author.guild
    elif isinstance(ctx_or_author, discord.Member):
        author = ctx_or_author
        guild = ctx_or_author.guild
    elif isinstance(ctx_or_author, discord.User):
        author = ctx_or_author
        guild = None  # User object tidak punya guild
    else:
        # Fallback: coba ambil dari attribute name
        return str(getattr(ctx_or_author, 'name', 'teman'))

    # Resolve: guild -> display_name, DM -> global name
    if guild is not None:
        # Di server: pakai nickname (display_name)
        # display_name selalu ada (default-nya name kalau tidak ada nickname)
        return author.display_name
    else:
        # Di DM: pakai global username
        return author.name


def clean_name(name: str) -> str:
    """
    Bersihkan dan normalisasi nama user.
    
    - Trim whitespace
    - Fallback ke "teman" jika kosong
    
    Args:
        name: Nama mentah dari resolve_name()
    
    Returns:
        str: Nama yang sudah bersih
    
    Contoh:
        clean_name("  Ridho  ")   # -> "Ridho"
        clean_name("")            # -> "teman"
        clean_name("   ")         # -> "teman"
    """
    name = name.strip()
    return name if name else "teman"


def build_user_context(ctx_or_author, extra_info: dict = None) -> str:
    """
    Bangun context string untuk di-inject ke AI prompt.
    Ini SATU-SATUNYA tempat yang membentuk nama user untuk AI.
    
    Args:
        ctx_or_author: Context Discord (Interaction, Message, Member, atau User)
        extra_info: Dictionary opsional dengan info tambahan 
                    (misal: channel_name, server_name, dll)
    
    Returns:
        str: Context string siap pakai untuk AI prompt
    
    Contoh output:
        Nama user: Ridho
        Context: server
        Gunakan nama ini saja.
        Jangan gunakan nama lain atau variasi.
    """
    user_name = clean_name(resolve_name(ctx_or_author))
    
    # Tentukan tipe context
    if isinstance(ctx_or_author, discord.Interaction):
        guild = ctx_or_author.guild
    elif isinstance(ctx_or_author, discord.Message):
        guild = ctx_or_author.guild
    elif isinstance(ctx_or_author, discord.Member):
        guild = ctx_or_author.guild
    else:
        guild = None
    
    context_type = "server" if guild else "dm"
    
    lines = [
        f"Nama user: {user_name}",
        f"Context: {context_type}",
    ]
    
    # Tambahkan info ekstra jika ada
    if extra_info:
        for key, value in extra_info.items():
            lines.append(f"{key}: {value}")
    
    lines.extend([
        "",
        "Gunakan nama ini saja.",
        "Jangan gunakan nama lain atau variasi.",
        "Jangan gunakan dua nama sekaligus.",
        "Gunakan hanya satu nama user dan jangan mengulang atau menggabungkannya.",
    ])
    
    return "\n".join(lines)