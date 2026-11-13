"""Pre-send email sanity checks: format, disposable domains, common typos, and DNS.

This can tell that an address is *plausible* (the domain exists and accepts mail). It cannot
prove a mailbox exists; the confirmation code does that, because only the owner receives it.
"""
import re

try:
    import dns.exception
    import dns.resolver
except ImportError:  # DNS check is skipped if dnspython isn't installed
    dns = None

LOCAL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}$")
LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")

# A partial list of well-known throwaway-mail providers.
DISPOSABLE = {
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "guerrillamail.org", "sharklasers.com",
    "grr.la", "10minutemail.com", "10minutemail.net", "tempmail.com", "temp-mail.org", "temp-mail.io",
    "tempmail.net", "tempail.com", "yopmail.com", "yopmail.net", "trashmail.com", "trashmail.net",
    "getnada.com", "nada.email", "dispostable.com", "maildrop.cc", "throwawaymail.com", "fakeinbox.com",
    "mintemail.com", "mohmal.com", "emailondeck.com", "burnermail.io", "mailnesia.com", "spambox.us",
    "spamgourmet.com", "mytemp.email", "tmpmail.org", "tmpmail.net", "discard.email", "mailcatch.com",
    "inboxkitten.com", "moakt.com", "tempinbox.com", "fakemail.net", "mail-temp.com", "emailfake.com",
    "crazymailing.com", "dropmail.me", "getairmail.com", "mailforspam.com", "harakirimail.com",
    "33mail.com", "anonbox.net", "jetable.org", "mailtemp.net", "owlymail.com", "spam4.me",
}

# Common misspellings of big providers -> the likely intended domain.
TYPOS = {
    "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gamil.com": "gmail.com", "gnail.com": "gmail.com",
    "gmail.co": "gmail.com", "gmail.con": "gmail.com", "gmail.cm": "gmail.com", "gmil.com": "gmail.com",
    "gmaill.com": "gmail.com", "gmali.com": "gmail.com", "googlemail.con": "googlemail.com",
    "yahooo.com": "yahoo.com", "yaho.com": "yahoo.com", "yahoo.co": "yahoo.com", "yahoo.con": "yahoo.com",
    "hotmial.com": "hotmail.com", "hotmai.com": "hotmail.com", "hotmail.con": "hotmail.com",
    "outlok.com": "outlook.com", "outlook.con": "outlook.com", "outllook.com": "outlook.com",
    "icloud.con": "icloud.com", "iclould.com": "icloud.com",
}


def _dns_problem(domain, resolver=None):
    """Return an error string if DNS proves the domain can't receive mail, else ''.

    Network trouble (timeouts etc.) is NOT treated as a failure, so a DNS hiccup never
    blocks a real user.
    """
    if dns is None and resolver is None:
        return ""
    r = resolver
    if r is None:
        r = dns.resolver.Resolver()
        r.lifetime = 4.0
    try:
        answers = r.resolve(domain, "MX")
        hosts = [str(a.exchange).rstrip(".") for a in answers]
        if hosts and all(h == "" for h in hosts):  # "null MX": domain explicitly accepts no mail
            return "That email domain doesn't accept mail."
        return ""
    except dns.resolver.NXDOMAIN:
        return "That email domain doesn't exist. Check for typos."
    except dns.resolver.NoAnswer:
        pass  # no MX record; mail can still go to the domain's A/AAAA record
    except Exception:
        return ""
    for rtype in ("A", "AAAA"):
        try:
            r.resolve(domain, rtype)
            return ""
        except dns.resolver.NXDOMAIN:
            return "That email domain doesn't exist. Check for typos."
        except dns.resolver.NoAnswer:
            continue
        except Exception:
            return ""
    return "That email domain doesn't accept mail."


def problem(email: str, resolver=None) -> str:
    """Return a user-facing reason the address looks wrong or fake, or '' if it looks fine."""
    email = (email or "").strip().lower()
    if email.count("@") != 1 or len(email) > 254:
        return "Enter a valid email address."
    local, domain = email.split("@")
    if not LOCAL_RE.match(local) or local.startswith(".") or local.endswith(".") or ".." in local:
        return "Enter a valid email address."
    labels = domain.split(".")
    if len(labels) < 2 or not all(LABEL_RE.match(l) for l in labels) or not re.match(r"^[a-z]{2,24}$", labels[-1]):
        return "Enter a valid email address."
    if domain in TYPOS:
        return f"Did you mean @{TYPOS[domain]}? Please check your email address."
    if domain in DISPOSABLE or ".".join(labels[-2:]) in DISPOSABLE:
        return "Disposable email addresses aren't allowed. Please use your real email."
    return _dns_problem(domain, resolver)
