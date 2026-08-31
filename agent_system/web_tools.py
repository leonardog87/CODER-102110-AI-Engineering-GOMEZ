"""Herramientas web opcionales, desactivadas y restringidas por defecto."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from langchain_core.tools import tool

from agent_system import retrieval_policy

USER_AGENT = os.getenv(
    "WEB_SEARCH_USER_AGENT",
    "AgenteCorporativo/1.0 (+busqueda-institucional-controlada)",
)
WEB_TIMEOUT_SECONDS = float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "10"))
WEB_MAX_CONTENT_CHARS = int(os.getenv("WEB_SEARCH_MAX_CONTENT_CHARS", "12000"))
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
WEB_MAX_DOWNLOAD_BYTES = int(os.getenv("WEB_MAX_DOWNLOAD_BYTES", "1000000"))


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _domain_allowed(hostname: str) -> bool:
    host = (hostname or "").lower().rstrip(".")
    return bool(host) and any(
        host == domain or host.endswith(f".{domain}")
        for domain in retrieval_policy.WEB_SEARCH_ALLOWED_DOMAINS
    )


def _validate_public_url(url: str) -> str:
    if not retrieval_policy.WEB_SEARCH_ENABLED:
        raise PermissionError("La búsqueda web está desactivada.")
    if not retrieval_policy.WEB_SEARCH_ALLOWED_DOMAINS:
        raise PermissionError("WEB_SEARCH_ALLOWED_DOMAINS no tiene dominios autorizados.")

    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("La URL debe usar http o https e incluir un dominio.")
    if parsed.username or parsed.password:
        raise ValueError("No se permiten credenciales dentro de la URL.")
    if not _domain_allowed(parsed.hostname):
        raise PermissionError(f"Dominio no autorizado: {parsed.hostname}")

    try:
        default_port = 443 if parsed.scheme == "https" else 80
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or default_port)
    except socket.gaierror as exc:
        raise ValueError(f"No se pudo resolver el dominio: {parsed.hostname}") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise PermissionError("La URL resuelve a una red privada o reservada.")
    return parsed.geturl()


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text or self._ignored_depth:
            return
        self.parts.append(text)
        if self._in_title:
            self.title_parts.append(text)


def _fetch_page(url: str) -> dict[str, Any]:
    safe_url = _validate_public_url(url)
    request = Request(
        safe_url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/json"},
    )
    opener = build_opener(_SafeRedirectHandler())
    try:
        with opener.open(request, timeout=WEB_TIMEOUT_SECONDS) as response:
            final_url = _validate_public_url(response.geturl())
            content_type = response.headers.get_content_type().lower()
            if content_type not in {"text/html", "text/plain", "application/json"}:
                raise ValueError(f"Tipo de contenido no admitido: {content_type}")
            raw = response.read(WEB_MAX_DOWNLOAD_BYTES + 1)
            if len(raw) > WEB_MAX_DOWNLOAD_BYTES:
                raise ValueError("La página supera WEB_MAX_DOWNLOAD_BYTES.")
            charset = response.headers.get_content_charset() or "utf-8"
            decoded = raw.decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"No se pudo descargar la página: {exc}") from exc

    title = ""
    text = decoded
    if content_type == "text/html":
        parser = _VisibleTextParser()
        parser.feed(decoded)
        title = " ".join(parser.title_parts)
        text = "\n".join(parser.parts)
    text = text[:WEB_MAX_CONTENT_CHARS]
    return {"title": title, "url": final_url, "content": text, "source_type": "web"}


def _tavily_search(query: str, max_results: int) -> dict[str, Any]:
    if not retrieval_policy.WEB_SEARCH_API_KEY:
        raise ValueError("Falta WEB_SEARCH_API_KEY para el proveedor Tavily.")
    endpoint = os.getenv("WEB_SEARCH_ENDPOINT", "https://api.tavily.com/search")
    payload = json.dumps(
        {
            "query": query,
            "max_results": max_results,
            "include_domains": list(retrieval_policy.WEB_SEARCH_ALLOWED_DOMAINS),
            "include_answer": False,
            "include_raw_content": False,
        }
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {retrieval_policy.WEB_SEARCH_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with build_opener().open(request, timeout=WEB_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read(WEB_MAX_DOWNLOAD_BYTES).decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Falló la búsqueda web: {exc}") from exc

    results = []
    for item in data.get("results", []):
        url = str(item.get("url", ""))
        parsed = urlparse(url)
        if not _domain_allowed(parsed.hostname or ""):
            continue
        results.append(
            {
                "title": str(item.get("title", "")),
                "url": url,
                "snippet": str(item.get("content", ""))[:2000],
                "source_type": "web",
            }
        )
    return {"query": query, "provider": "tavily", "results": results}


@tool("web_search_allowed")
def web_search_allowed(query: str, max_results: int = 5) -> str:
    """Busca en la web únicamente dentro de los dominios autorizados."""
    if not retrieval_policy.WEB_SEARCH_ENABLED:
        return _json({"error": "La búsqueda web está desactivada."})
    if not query or not query.strip():
        return _json({"error": "La consulta web no puede estar vacía."})
    if not retrieval_policy.WEB_SEARCH_ALLOWED_DOMAINS:
        return _json({"error": "No hay dominios web autorizados."})
    provider = retrieval_policy.WEB_SEARCH_PROVIDER.lower()
    limit = max(1, min(max_results, WEB_SEARCH_MAX_RESULTS))
    try:
        if provider == "tavily":
            return _json(_tavily_search(query.strip(), limit))
        return _json({"error": "WEB_SEARCH_PROVIDER no soportado. Use tavily."})
    except (PermissionError, ValueError, RuntimeError) as exc:
        return _json({"error": str(exc)})


@tool("web_retrieve_allowed_url")
def web_retrieve_allowed_url(url: str) -> str:
    """Descarga texto de una URL perteneciente a un dominio autorizado."""
    try:
        return _json(_fetch_page(url))
    except (PermissionError, ValueError, RuntimeError) as exc:
        return _json({"error": str(exc)})
