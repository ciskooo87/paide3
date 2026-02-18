# -*- coding: utf-8 -*-
"""
IRIS - Email Tools
Leitura de emails via IMAP (Gmail e corporativo)
"""

import re
import imaplib
import email as email_lib
from email.header import decode_header

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import GMAIL_EMAIL, GMAIL_APP_PASSWORD, CORP_EMAIL, CORP_PASSWORD, CORP_IMAP_SERVER


# ============================================================
# HELPERS
# ============================================================

def decode_mime_header(raw):
    """Decodifica cabeçalhos MIME."""
    if not raw:
        return ""
    
    parts = decode_header(raw)
    decoded = []
    
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except:
                decoded.append(part.decode("utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    
    return " ".join(decoded)


def get_email_body(msg):
    """Extrai corpo do email (texto ou HTML)."""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            
            if ct == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    break
                except:
                    pass
            elif ct == "text/html" and not body:
                try:
                    payload = part.get_payload(decode=True)
                    html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    body = re.sub(r'<[^>]+>', ' ', html)
                    body = re.sub(r'\s+', ' ', body).strip()
                except:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        except:
            body = str(msg.get_payload())
    
    return body[:1500]


# ============================================================
# EMAIL READING
# ============================================================

def fn_read_emails(conta="gmail", n=5):
    """Lê emails recentes (gmail ou corp)."""
    if conta == "gmail":
        if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
            return "Gmail nao configurado. Configure GMAIL_EMAIL e GMAIL_APP_PASSWORD no Render."
        addr, pwd, srv = GMAIL_EMAIL, GMAIL_APP_PASSWORD, "imap.gmail.com"
    else:
        if not CORP_EMAIL or not CORP_PASSWORD:
            return "Email corporativo nao configurado."
        addr, pwd, srv = CORP_EMAIL, CORP_PASSWORD, CORP_IMAP_SERVER or "imap.gmail.com"
    
    try:
        mail = imaplib.IMAP4_SSL(srv)
        mail.login(addr, pwd)
        mail.select("INBOX", readonly=True)
        
        _, data = mail.search(None, "ALL")
        ids = data[0].split()
        
        if not ids:
            mail.logout()
            return "Caixa vazia."
        
        results = []
        for eid in list(reversed(ids[-n:])):
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email_lib.message_from_bytes(msg_data[0][1])
            
            results.append(
                f"De: {decode_mime_header(msg.get('From',''))[:80]}\n"
                f"Assunto: {decode_mime_header(msg.get('Subject',''))[:120]}\n"
                f"Data: {msg.get('Date','')[:25]}\n"
                f"Corpo: {get_email_body(msg)[:300]}\n"
            )
        
        mail.logout()
        return "\n---\n".join(results) if results else "Nenhum email."
    
    except Exception as e:
        return f"ERRO email: {e}"
