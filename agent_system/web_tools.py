"""Herramientas web opcionales, desactivadas y restringidas por defecto."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
import threading
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
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
WEB_SYNC_LOCAL_ON_DIFFERENCE = os.getenv(
    "WEB_SYNC_LOCAL_ON_DIFFERENCE", "true"
).strip().lower() in {"1", "true", "yes", "on", "si", "sí"}
WEB_SYNC_MAX_PAGES = int(os.getenv("WEB_SYNC_MAX_PAGES", "2"))
WEB_SYNC_SOURCE_PATH = Path(
    os.getenv("WEB_SYNC_SOURCE_PATH", "./knowledge_base/actualizaciones_web.md")
)
WEB_SYNC_STATE_PATH = Path(
    os.getenv("WEB_SYNC_STATE_PATH", "./data/web_sync_state.json")
)
_SYNC_LOCK = threading.Lock()


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


def _local_context(query: str, local_source: str, top_k: int) -> str:
    if local_source == "complex":
        from rag.pipeline import retrieve_context

        return retrieve_context(query=query, top_k=top_k)
    from rag.knowledge_pipeline import retrieve_knowledge_context

    return retrieve_knowledge_context(query=query, top_k=top_k)


def _normalize_for_comparison(value: str) -> str:
    return " ".join((value or "").lower().split())


def _sync_web_sources(query: str, pages: list[dict[str, Any]], local_context: str) -> bool:
    """Persiste fuentes web distintas sin sobrescribir los manuales canónicos."""
    if not WEB_SYNC_LOCAL_ON_DIFFERENCE or not pages:
        return False
    local_normalized = _normalize_for_comparison(local_context)
    changed = False
    with _SYNC_LOCK:
        try:
            state = json.loads(WEB_SYNC_STATE_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            state = {"sources": {}}
        sources = state.setdefault("sources", {})
        for page in pages:
            content = str(page.get("content") or page.get("snippet") or "").strip()
            url = str(page.get("url", "")).strip()
            if not url or not content:
                continue
            normalized = _normalize_for_comparison(content)
            if normalized and normalized in local_normalized:
                continue
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if sources.get(url, {}).get("content_hash") == content_hash:
                continue
            sources[url] = {
                "title": str(page.get("title", "")),
                "query": query,
                "content": content,
                "content_hash": content_hash,
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }
            changed = True
        if not changed:
            return False

        WEB_SYNC_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        WEB_SYNC_SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        state_tmp = WEB_SYNC_STATE_PATH.with_suffix(".tmp")
        source_tmp = WEB_SYNC_SOURCE_PATH.with_suffix(".tmp")
        state_tmp.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        sections = [
            "# Actualizaciones provenientes de fuentes web autorizadas",
            "",
            "Este archivo es generado automáticamente. Cada entrada conserva "
            "su URL y fecha de sincronización.",
            "",
        ]
        for url, item in sorted(sources.items()):
            sections.extend(
                [
                    f"## {item.get('title') or url}",
                    f"Fuente: {url}",
                    f"Sincronizado: {item['synced_at']}",
                    f"Consulta: {item['query']}",
                    "",
                    item["content"],
                    "",
                ]
            )
        source_tmp.write_text("\n".join(sections), encoding="utf-8")
        os.replace(state_tmp, WEB_SYNC_STATE_PATH)
        os.replace(source_tmp, WEB_SYNC_SOURCE_PATH)

        from rag.knowledge_documents import (
            get_knowledge_chunks,
            load_knowledge_documents,
        )
        from rag.knowledge_vector_store import get_knowledge_vector_store

        load_knowledge_documents.cache_clear()
        get_knowledge_chunks.cache_clear()
        get_knowledge_vector_store.cache_clear()
        get_knowledge_vector_store()
    return True


@tool("primary_retrieve_context")
def primary_retrieve_context(
    query: str, local_source: str = "knowledge", top_k: int = 2
) -> str:
    """Usa Web como fuente principal y RAG como respaldo automático."""
    clean_query = (query or "").strip()
    source = "complex" if local_source == "complex" else "knowledge"
    limit = max(1, min(top_k, WEB_SEARCH_MAX_RESULTS))
    if not clean_query:
        return _json({"error": "La consulta no puede estar vacía."})

    if not retrieval_policy.WEB_SEARCH_ENABLED:
        return _json(
            {
                "source_type": "rag_fallback",
                "fallback_reason": "La búsqueda web está desactivada.",
                "content": _local_context(clean_query, source, limit),
            }
        )

    try:
        search = _tavily_search(clean_query, limit)
        results = search.get("results", [])
        if not results:
            raise RuntimeError("Tavily no devolvió resultados autorizados.")
        pages: list[dict[str, Any]] = []
        for result in results[: max(1, WEB_SYNC_MAX_PAGES)]:
            try:
                page = _fetch_page(str(result["url"]))
                page["title"] = page.get("title") or result.get("title", "")
                pages.append(page)
            except (PermissionError, ValueError, RuntimeError):
                pages.append(result)
        local = _local_context(clean_query, source, limit)
        synchronized = _sync_web_sources(clean_query, pages, local)
        return _json(
            {
                "source_type": "web_primary",
                "provider": "tavily",
                "results": pages,
                "local_source_updated": synchronized,
            }
        )
    except (PermissionError, ValueError, RuntimeError, OSError) as exc:
        return _json(
            {
                "source_type": "rag_fallback",
                "fallback_reason": str(exc),
                "content": _local_context(clean_query, source, limit),
            }
        )


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
