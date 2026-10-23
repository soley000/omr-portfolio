"""Client LLM commun a tous les fournisseurs (interface compatible OpenAI).

- Un seul format d'appel : changer de fournisseur = changer d'entree dans llm.yaml.
- Cache sur disque : un appel identique (meme modele, memes messages, memes
  outils, meme numero de repetition) n'est jamais refait. Une evaluation
  interrompue (quota du jour atteint) reprend la ou elle s'etait arretee.
- Respect des quotas par minute (requetes et jetons) et nouvelles tentatives
  en cas de limite atteinte ; quota du jour epuise -> QuotaExhausted.
- Chaque appel renvoie sa latence et ses jetons.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from chargedesk.config import PROJECT_ROOT, data_dir, load_config

LLM_CONFIG_PATH = PROJECT_ROOT / "configs" / "llm.yaml"


class QuotaExhausted(RuntimeError):
    """Quota du jour atteint : relancer plus tard, le cache garde ce qui est fait."""


class ToolCallRejected(RuntimeError):
    """Le fournisseur a refuse l'appel d'outil genere par le modele (ex. Groq : outil inexistant,
    argument du mauvais type). L'agent renvoie le message au modele pour qu'il corrige."""
    def __init__(self, message: str, latency_s: float = 0.0):
        super().__init__(message)
        self.latency_s = latency_s


class TransientError(RuntimeError):
    """Le fournisseur n'a pas repondu (delai depasse, coupure) malgre les nouvelles tentatives.
    Ce n'est pas une mauvaise reponse : c'est une erreur technique, comptee a part."""


TRANSIENT_NAMES = {"APITimeoutError", "APIConnectionError", "InternalServerError",
                   "ServiceUnavailableError", "Timeout", "ReadTimeout", "ConnectTimeout"}


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[dict]
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    cached: bool
    model: str
    raw_tool_calls: list | None = None
    reasoning_tokens: int = 0


def load_llm_config(path: Path | None = None) -> dict:
    with open(path or LLM_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _estimate_tokens(messages: list[dict], tools: list[dict] | None) -> int:
    return int(len(json.dumps(messages, ensure_ascii=False) + json.dumps(tools or [])) / 3.5) + 200


def _is_daily_quota(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(k in text for k in ("per day", "perday", "requests per day", "tokens per day", "daily"))


@dataclass
class LLMClient:
    """Client pour un modele de llm.yaml. `transport` permet d'injecter un faux LLM dans les tests."""
    name: str
    model: str
    rpm: int
    tpm: int
    cache_dir: Path | None
    temperature: float = 0
    transport: Any = None
    max_retries: int = 6
    timeout_s: float = 120
    max_timeouts: int = 2
    extra: dict = field(default_factory=dict)   # options du fournisseur (ex. reasoning_effort)
    max_wait_s: float | None = None             # API : attente maximale pour la limite par minute
    _calls: deque = field(default_factory=deque, repr=False)

    @classmethod
    def from_config(cls, name: str, llm_cfg: dict | None = None, use_cache: bool = True,
                    timeout_s: float | None = None, max_retries: int | None = None,
                    max_timeouts: int | None = None, max_wait_s: float | None = None) -> "LLMClient":
        """timeout_s / max_retries / max_timeouts : patience reduite pour l'API (un exploitant n'attend pas
        une minute) ; l'evaluation garde les valeurs par defaut, plus patientes."""
        llm_cfg = llm_cfg or load_llm_config()
        spec = llm_cfg["models"][name]
        prov = llm_cfg["providers"][spec["provider"]]
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / llm_cfg.get("env_file", ".env"))
        key = os.environ.get(prov["key_env"])
        if not key:
            raise RuntimeError(f"cle {prov['key_env']} absente du fichier .env")
        from openai import OpenAI
        timeout = timeout_s or spec.get("timeout_s", 120)
        transport = OpenAI(base_url=prov["base_url"], api_key=key, max_retries=0, timeout=timeout)
        cache = data_dir(load_config()) / llm_cfg.get("cache_subdir", "llm_cache") / name if use_cache else None
        return cls(name=name, model=spec["model"], rpm=spec["rpm"], tpm=spec["tpm"], cache_dir=cache,
                   temperature=llm_cfg.get("temperature", 0), transport=transport, timeout_s=timeout,
                   extra=dict(spec.get("options") or {}),
                   **({"max_retries": max_retries} if max_retries is not None else {}),
                   **({"max_timeouts": max_timeouts} if max_timeouts is not None else {}),
                   max_wait_s=max_wait_s)

    # --- cache -----------------------------------------------------------
    def _key(self, messages, tools, rep) -> str:
        key = {"model": self.model, "messages": messages, "tools": tools,
               "temperature": self.temperature, "rep": rep}
        if self.extra:          # absent quand vide : les appels deja en cache restent valides
            key["options"] = self.extra
        payload = json.dumps(key,
                             ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path | None:
        return self.cache_dir / key[:2] / f"{key}.json" if self.cache_dir else None

    # --- quotas par minute ----------------------------------------------
    def _wait_for_budget(self, est_tokens: int) -> None:
        while True:
            now = time.monotonic()
            while self._calls and now - self._calls[0][0] > 60:
                self._calls.popleft()
            n = len(self._calls)
            used = sum(t for _, t in self._calls)
            if n < self.rpm and used + est_tokens <= self.tpm or not self._calls:
                return
            pause = max(0.5, 60 - (now - self._calls[0][0]) + 0.5)
            if self.max_wait_s is not None and pause > self.max_wait_s:
                raise TransientError(f"{self.name} : limite par minute atteinte (il faudrait attendre {pause:.0f} s)")
            time.sleep(pause)

    # --- appel -------------------------------------------------------------
    def chat(self, messages: list[dict], tools: list[dict] | None = None, rep: int = 0,
             timeout: float | None = None) -> LLMResponse:
        """timeout : delai de CET appel (l'API s'en sert pour respecter son budget par question)."""
        key = self._key(messages, tools, rep)
        path = self._cache_path(key)
        if path and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return LLMResponse(**{**data, "cached": True})

        est = _estimate_tokens(messages, tools)
        timeouts = conn_errors = attempt = 0
        while attempt < self.max_retries:
            self._wait_for_budget(est)
            t0 = time.monotonic()
            try:
                kwargs = {"model": self.model, "messages": messages, "temperature": self.temperature}
                if tools:
                    kwargs["tools"] = tools
                kwargs.update(self.extra)
                if timeout is not None:
                    kwargs["timeout"] = timeout
                r = self.transport.chat.completions.create(**kwargs)
            except Exception as exc:  # erreurs du fournisseur
                status = getattr(exc, "status_code", None)
                if status == 400 and "tool call validation failed" in str(exc).lower():
                    self._calls.append((time.monotonic(), est))
                    raise ToolCallRejected(str(exc)[:500], round(time.monotonic() - t0, 3)) from exc
                if status == 429 and _is_daily_quota(exc):
                    raise QuotaExhausted(f"{self.name} : quota du jour atteint ({str(exc)[:160]})") from exc
                is_conn = type(exc).__name__ == "APIConnectionError" and "timed out" not in str(exc).lower()
                if is_conn:
                    # coupure de connexion (rapide, souvent passagere) : 2 nouveaux essais immediats,
                    # puis traitee comme les autres erreurs passageres
                    conn_errors += 1
                    if conn_errors <= 2:
                        time.sleep(0.5)
                        continue
                transient = type(exc).__name__ in TRANSIENT_NAMES or "timed out" in str(exc).lower()
                if transient:
                    timeouts += 1
                    if timeouts > self.max_timeouts:
                        what = "connexion impossible" if is_conn else "pas de reponse dans le delai"
                        raise TransientError(f"{self.name} : {what} ({type(exc).__name__})") from exc
                if transient or status in (429, 500, 502, 503, 504):
                    self._calls.append((time.monotonic(), est))
                    pause = min(60, 5 * 2 ** attempt)
                    if self.max_wait_s is not None and pause > self.max_wait_s:
                        raise TransientError(f"{self.name} : fournisseur occupe ({status or type(exc).__name__})") from exc
                    time.sleep(pause)
                    attempt += 1
                    continue
                raise
            latency = time.monotonic() - t0
            msg = r.choices[0].message
            usage = getattr(r, "usage", None)
            pt = getattr(usage, "prompt_tokens", 0) or 0
            ct = getattr(usage, "completion_tokens", 0) or 0
            details = getattr(usage, "completion_tokens_details", None)
            rt = getattr(details, "reasoning_tokens", 0) or 0   # jetons de "reflexion" caches, s'il y en a
            self._calls.append((time.monotonic(), pt + ct or est))
            calls = [{"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                     for tc in (msg.tool_calls or [])]
            # appels bruts, renvoyes tels quels au tour suivant (certains fournisseurs y glissent
            # des champs a retourner, ex. signatures de raisonnement)
            keep = ("id", "type", "function", "extra_content")
            raw = [{k: v for k, v in (tc.model_dump(exclude_none=True) if hasattr(tc, "model_dump")
                                      else dict(tc)).items() if k in keep}
                   for tc in (msg.tool_calls or [])] or None
            resp = LLMResponse(content=msg.content, tool_calls=calls, prompt_tokens=pt,
                               completion_tokens=ct, latency_s=round(latency, 3), cached=False,
                               model=self.model, raw_tool_calls=raw, reasoning_tokens=rt)
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                data = {k: v for k, v in resp.__dict__.items() if k != "cached"}
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return resp
        raise TransientError(f"{self.name} : echec apres {self.max_retries} tentatives")
