"""Pobierz czytelny tekst jednej publicznej strony wskazanej przez użytkownika."""

from contextlib import suppress
from http.client import HTTPConnection, HTTPException
from html.parser import HTMLParser
from ipaddress import ip_address, ip_network
from queue import Empty, SimpleQueue
import re
import socket
import ssl
from threading import BoundedSemaphore, Thread, Timer
from time import monotonic
from urllib.parse import quote, urljoin, urlsplit, urlunsplit


USER_AGENT = "AtlasEU4"
TIME_LIMIT = 15
PAGE_LIMIT = 2 * 1024 * 1024
ROBOTS_LIMIT = 512 * 1024
TEXT_LIMIT = 1_000_000
URL_LIMIT = 2048
REDIRECT_LIMIT = 5
REDIRECT_CODES = {301, 302, 303, 307, 308}
PORTS = {"http": 80, "https": 443}
DNS_SLOTS = BoundedSemaphore(4)
IPV6_UNICAST = ip_network("2000::/3")
IPV6_6TO4 = ip_network("2002::/16")
AZURE_WIRESERVER = ip_address("168.63.129.16")
NO_PUBLIC_ADDRESS = "Podaj adres publicznej strony internetowej."
TIMEOUT = "Pobieranie strony trwało zbyt długo. Spróbuj ponownie."


def _remaining(deadline):
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise ValueError(TIMEOUT)
    return remaining


def _web_url(url):
    url = url.strip()
    if len(url) > URL_LIMIT or re.search(r"[\x00-\x1f\x7f\\]", url):
        raise ValueError("Adres strony ma nieprawidłowy format.")
    try:
        parts = urlsplit(url)
        port = PORTS.get(parts.scheme)
        host = (parts.hostname or "").rstrip(".").encode("idna").decode("ascii")
        if not port or not host or parts.port not in (None, port) or parts.username is not None:
            raise ValueError
        if ":" in host:
            if "%" in host:
                raise ValueError
            host = str(ip_address(host))
        elif not re.fullmatch(r"[a-zA-Z0-9.-]+", host):
            raise ValueError
    except (UnicodeError, ValueError):
        raise ValueError("Podaj adres publicznej strony zaczynający się od http:// lub https://.") from None
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".home.arpa")):
        raise ValueError(NO_PUBLIC_ADDRESS)
    origin = f"[{host}]" if ":" in host else host
    path = quote(parts.path or "/", safe="/:@!$&'()*+,;=-._~%")
    if path.startswith("//"):
        raise ValueError("Adres strony ma nieprawidłowy format.")
    query = quote(parts.query, safe="/?:@!$&'()*+,;=-._~%")
    normalized = urlunsplit((parts.scheme, origin, path, query, ""))
    if len(normalized) > URL_LIMIT:
        raise ValueError("Adres strony jest za długi.")
    return normalized, host, port


def _public_ip(address):
    ip = ip_address(address)
    if not ip.is_global or ip.is_multicast or ip.is_reserved or ip == AZURE_WIRESERVER:
        return False
    return ip.version == 4 or (ip in IPV6_UNICAST and ip not in IPV6_6TO4)


def _resolve(host, port, deadline):
    # Systemowy DNS nie ma ustawianego timeoutu. Limit utrzymuje liczbę zapytań,
    # które mogą jeszcze kończyć się po zwróceniu błędu użytkownikowi.
    if not DNS_SLOTS.acquire(timeout=_remaining(deadline)):
        raise ValueError(TIMEOUT)
    result = SimpleQueue()

    def lookup():
        try:
            result.put(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
        except OSError as error:
            result.put(error)
        finally:
            DNS_SLOTS.release()

    try:
        Thread(target=lookup, daemon=True).start()
    except RuntimeError:
        DNS_SLOTS.release()
        raise ValueError("Nie udało się rozpocząć pobierania strony.") from None
    try:
        addresses = result.get(timeout=_remaining(deadline))
    except Empty:
        raise ValueError(TIMEOUT) from None
    if isinstance(addresses, OSError):
        raise ValueError("Nie znaleziono adresu tej strony.") from None
    if not addresses or any(not _public_ip(entry[4][0]) for entry in addresses):
        raise ValueError(NO_PUBLIC_ADDRESS)
    return addresses


def _connect(host, port, secure, deadline):
    for family, socktype, protocol, _, address in _resolve(host, port, deadline):
        try:
            connection = socket.socket(family, socktype, protocol)
        except OSError:
            continue
        try:
            # Używamy zatwierdzonego sockaddr. Ponowny DNS mógłby wskazać inny adres.
            connection.settimeout(min(4, _remaining(deadline)))
            connection.connect(address)
            if secure:
                context = ssl.create_default_context()
                connection.settimeout(_remaining(deadline))
                connection = context.wrap_socket(connection, server_hostname=host)
            return connection
        except ssl.SSLCertVerificationError:
            connection.close()
            raise ValueError("Nie udało się potwierdzić certyfikatu HTTPS strony.") from None
        except OSError:
            connection.close()
        except ValueError:
            connection.close()
            raise
    _remaining(deadline)
    raise ValueError("Nie udało się połączyć ze stroną.")


def _request(url, deadline, byte_limit, policy=False):
    url, host, port = _web_url(url)
    parts = urlsplit(url)
    transport = _connect(host, port, parts.scheme == "https", deadline)
    connection = HTTPConnection(parts.netloc, port)
    connection.sock = transport
    connection.auto_open = False

    def interrupt():
        with suppress(OSError):
            transport.shutdown(socket.SHUT_RDWR)

    timer = None
    try:
        # Timeout pojedynczego odczytu nie zatrzyma serwera dosyłającego bajty
        # powoli. Zamknięcie połączenia pilnuje wspólnego terminu całego importu.
        remaining = _remaining(deadline)
        transport.settimeout(remaining)
        timer = Timer(remaining, interrupt)
        timer.daemon = True
        timer.start()
        target = urlunsplit(("", "", parts.path, parts.query, ""))
        connection.request("GET", target, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/plain" if policy else "text/html, application/xhtml+xml, text/plain",
            "Accept-Encoding": "identity",
            "Connection": "close",
        })
        with connection.getresponse() as response:
            _remaining(deadline)
            status, headers = response.status, response.headers
            if (headers.get("CF-Mitigated") or "").casefold() == "challenge":
                raise ValueError("Serwis wymaga potwierdzenia w przeglądarce.")
            if status != 200:
                return status, headers, b""
            if (headers.get("Content-Encoding") or "identity").strip().casefold() != "identity":
                raise ValueError("Serwis przesłał treść w nieobsługiwanym kodowaniu.")
            media_type = headers.get_content_type()
            if not policy and media_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                raise ValueError("Z tego adresu można zaimportować stronę HTML lub zwykły tekst.")
            if response.length is not None and response.length > byte_limit:
                raise ValueError("Strona jest za duża, aby wczytać ją do podglądu.")
            body = response.read(byte_limit + 1)
            _remaining(deadline)
            if len(body) > byte_limit:
                raise ValueError("Strona jest za duża, aby wczytać ją do podglądu.")
            return status, headers, body
    except (OSError, HTTPException):
        _remaining(deadline)
        raise ValueError("Nie udało się pobrać strony. Sprawdź adres i połączenie.") from None
    finally:
        if timer is not None:
            timer.cancel()
        connection.close()
        transport.close()


def _redirect(url, headers):
    location = headers.get("Location")
    if not location:
        raise ValueError("Serwis zwrócił przekierowanie bez adresu docelowego.")
    try:
        return _web_url(urljoin(url, location))[0]
    except (UnicodeError, ValueError):
        raise ValueError("Serwis przekierowuje poza obsługiwany publiczny adres.") from None


_ESCAPED_BYTE = re.compile(r"%([0-9a-fA-F]{2})")
_UNRESERVED = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~")


def _robot_path(path):
    def normalize(match):
        char = chr(int(match[1], 16))
        return char if char in _UNRESERVED else match[0].upper()

    return _ESCAPED_BYTE.sub(normalize, quote(path, safe="/?:@!$&'()*+,;=-._~%"))


def _matches_rule(path, rule):
    pattern = rule.removesuffix("$")
    segments = pattern.split("*")
    if not path.startswith(segments[0]):
        return False
    if len(segments) == 1:
        return not rule.endswith("$") or path == pattern
    start = len(segments[0])
    end = len(path)
    remaining = segments[1:]
    if rule.endswith("$"):
        suffix = remaining.pop()
        if not path.endswith(suffix):
            return False
        end -= len(suffix)
    for segment in remaining:
        index = path.find(segment, start, end)
        if index == -1:
            return False
        start = index + len(segment)
    return start <= end


def _robot_allows(lines, url):
    agents = set()
    listed_agents = set()
    seen_rules = False
    product = USER_AGENT.casefold()
    rules = {product: [], "*": []}
    for line in lines:
        name, separator, value = line.partition("#")[0].partition(":")
        value = value.strip()
        if not separator:
            continue
        name = name.strip().lower()
        if name == "user-agent":
            if seen_rules:
                agents.clear()
                seen_rules = False
            agent = value.casefold()
            agents.add(agent)
            listed_agents.add(agent)
        elif name in {"allow", "disallow"} and agents:
            seen_rules = True
            for agent in agents & rules.keys():
                rules[agent].append((name == "allow", value))
    parts = urlsplit(url)
    path = _robot_path(urlunsplit(("", "", parts.path, parts.query, "")))
    matches = []
    for allow, pattern in rules[product if product in listed_agents else "*"]:
        if pattern.startswith("/"):
            pattern = _robot_path(pattern)
            if _matches_rule(path, pattern):
                matches.append((len(pattern), allow))
    return max(matches, default=(0, True))[1]


def _check_robots(url, deadline, cache):
    # Plik po przekierowaniu dotyczy serwisu, który wskazał adres z zasadami.
    origin = urljoin(url, "/")
    if url == urljoin(origin, "robots.txt"):
        return
    if origin not in cache:
        robots_url = urljoin(origin, "robots.txt")
        for _ in range(REDIRECT_LIMIT + 1):
            status, headers, body = _request(robots_url, deadline, ROBOTS_LIMIT, policy=True)
            if status in REDIRECT_CODES:
                robots_url = _redirect(robots_url, headers)
                continue
            if status in {404, 410}:
                cache[origin] = []
            elif status == 200:
                if headers.get_content_type() in {"text/html", "application/xhtml+xml"}:
                    raise ValueError("Serwis nie udostępnił zasad pobierania (robots.txt).")
                cache[origin] = body.decode("utf-8-sig", errors="replace").splitlines()
            else:
                _check_response(status)
            break
        else:
            raise ValueError("Nie udało się sprawdzić zasad pobierania tej strony.")
    if not _robot_allows(cache[origin], url):
        raise ValueError("Serwis nie zezwala na automatyczne pobranie tej strony (robots.txt).")


def _check_response(status):
    if status == 429:
        raise ValueError("Serwis ogranicza liczbę pobrań. Spróbuj później.")
    if status in (401, 403, 451):
        raise ValueError("Serwis odmówił dostępu do strony.")
    if status in (404, 410):
        raise ValueError("Pod tym adresem nie ma już strony.")
    if status != 200:
        raise ValueError(f"Serwis zwrócił błąd HTTP {status}.")


_CHARSET = re.compile(rb"""<meta\b[^>]{0,1000}?\bcharset\s*=\s*["']?([a-z0-9._:-]+)""", re.I)
_HTML_START = re.compile(r"^\s*(?:<!doctype\s+html\b|<html\b|<\?xml\b)", re.I)
_CHALLENGE_TITLE = re.compile(r"just a moment[.… ]*|attention required[ !|]+cloudflare|verify you are human[.! ]*", re.I)
_HIDDEN_STYLE = re.compile(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\b", re.I)
_HTML_SPACE = re.compile(r"[ \t\r\n\f]+")
_SPACE = re.compile(r"[^\S\n]+")
_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BLOCKS = set("article blockquote br dd div dl dt figcaption h1 h2 h3 h4 h5 h6 hr li main p pre section tr".split())
_CLOSE_PARAGRAPH = _BLOCKS - {"br"}
_HEAD_TAGS = {"base", "link", "meta", "noscript", "script", "style", "template", "title"}
_VOID = set("area base br col embed hr img input link meta param source track wbr".split())
_HIDDEN = set("aside button canvas dialog footer form iframe menu nav noscript script style svg template".split())
_CHROME = set(
    "ad advertisement cookie-banner menu mw-editsection navbox navigation sidebar "
    "site-footer site-header site-menu site-nav toc vector-toc".split()
)
_CONTENT = {"mw-content-text", "mw-parser-output"}


def _decode(body, charset, html):
    if body.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return body.decode("utf-32", errors="replace")
    if body.startswith((b"\xff\xfe", b"\xfe\xff")):
        return body.decode("utf-16", errors="replace")
    if body.startswith(b"\xef\xbb\xbf"):
        return body.decode("utf-8-sig", errors="replace")
    meta = _CHARSET.search(body[:4096]) if html else None
    for encoding in (charset, meta[1].decode("ascii") if meta else None, "utf-8"):
        if encoding:
            try:
                return body.decode(encoding)
            except (LookupError, UnicodeError):
                continue
    return body.decode("cp1252", errors="replace")


def _clean_text(text):
    text = _CONTROLS.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = (_SPACE.sub(" ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.body = []
        self.title = []
        self.heading = []
        self.candidates = []

    def _write(self, data):
        if not self.stack:
            self.body.append(data)
            return
        _, hidden, candidate, in_title, in_heading = self.stack[-1]
        if in_title:
            self.title.append(data)
        elif not hidden:
            self.body.append(data)
            if candidate is not None:
                candidate.append(data)
            if in_heading:
                self.heading.append(data)

    def handle_starttag(self, tag, attrs):
        if len(self.stack) >= 256:
            raise ValueError("Strona ma zbyt złożony układ HTML.")
        if self.stack:
            parent = self.stack[-1][0]
            if (parent == "p" and tag in _CLOSE_PARAGRAPH) or (parent == "head" and tag not in _HEAD_TAGS):
                self.handle_endtag(parent)
        if tag in _BLOCKS:
            self._write("\n")
        if tag in _VOID:
            return
        if self.stack:
            _, hidden, candidate, in_title, in_heading = self.stack[-1]
        else:
            hidden = in_title = in_heading = False
            candidate = None
        attrs = dict(attrs)
        markers = set((attrs.get("class") or "").lower().split())
        markers.add((attrs.get("id") or "").lower())
        role = (attrs.get("role") or "").lower()
        hidden = (hidden or tag in _HIDDEN or tag == "head" or role in {"navigation", "banner", "contentinfo", "complementary"}
                  or bool(markers & _CHROME) or "hidden" in attrs or attrs.get("aria-hidden") == "true"
                  or bool(_HIDDEN_STYLE.search(attrs.get("style") or ""))
                  or (tag == "header" and candidate is None))
        if not hidden and (tag in {"main", "article"} or role == "main" or markers & _CONTENT):
            if candidate is None:
                candidate = []
                self.candidates.append(candidate)
        in_heading = in_heading or (tag == "h1" and not self.heading)
        self.stack.append((tag, hidden, candidate, in_title or tag == "title", in_heading))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                if tag in _BLOCKS:
                    self._write("\n")
                elif tag in {"th", "td"}:
                    self._write("  ")
                break

    def handle_data(self, data):
        if not any(frame[0] == "pre" for frame in self.stack):
            data = _HTML_SPACE.sub(" ", data)
        self._write(data)


def fetch_page(url: str) -> dict[str, str]:
    """Zwróć tytuł, tekst i końcowy URL. Oczekiwane błędy mają postać ValueError."""
    url = _web_url(url)[0]
    deadline = monotonic() + TIME_LIMIT
    robots_cache = {}
    for _ in range(REDIRECT_LIMIT + 1):
        _check_robots(url, deadline, robots_cache)
        status, headers, body = _request(url, deadline, PAGE_LIMIT)
        if status not in REDIRECT_CODES:
            break
        url = _redirect(url, headers)
    else:
        raise ValueError("Strona przekierowuje zbyt wiele razy.")
    _check_response(status)
    html = headers.get_content_type() != "text/plain"
    content = _decode(body, headers.get_content_charset(), html)
    if not headers.get("Content-Type") and _HTML_START.match(content):
        html = True
        content = _decode(body, headers.get_content_charset(), html)
    title = ""
    if html:
        parser = _PageText()
        parser.feed(content)
        parser.close()
        title = _clean_text("".join(parser.title or parser.heading))
        if _CHALLENGE_TITLE.fullmatch(title):
            raise ValueError("Serwis wymaga potwierdzenia w przeglądarce.")
        candidates = (_clean_text("".join(chunks)) for chunks in parser.candidates)
        text = max(candidates, key=len, default="") or _clean_text("".join(parser.body))
    else:
        text = _clean_text(content)
    if not text:
        raise ValueError("Pod tym adresem nie znaleziono tekstu do wczytania.")
    if len(text) > TEXT_LIMIT:
        raise ValueError("Strona zawiera za dużo tekstu, aby wczytać ją do podglądu.")
    return {"title": (title or urlsplit(url).netloc)[:200], "text": text, "url": url}
