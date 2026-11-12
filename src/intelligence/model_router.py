"""Multi-model routing: cheap/fast model for routine work, strong model for reasoning, vision
model for images, with ordered fallback, per-provider circuit breaking, a daily call budget and
usage logging. Prompts are scrubbed of secrets; context from MemoryStore can be injected.
Returns None when no provider is usable so callers fall back to deterministic rules.
"""
import json
import os
import time
from pathlib import Path

from src.intelligence.healing import CircuitOpen, circuit_check, _record
from src.intelligence.memory import get_memory, scrub

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'config' / 'model_strategy.json'
USAGE = ROOT / 'data' / 'model_usage.jsonl'
ENV_KEYS = {'anthropic': 'ANTHROPIC_API_KEY', 'openai': 'OPENAI_API_KEY', 'openrouter': 'OPENROUTER_API_KEY'}


def load_config():
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def _key(provider):
    name = ENV_KEYS.get(provider)
    if not name:
        return None
    if os.environ.get(name):
        return os.environ[name]
    try:
        from dotenv import dotenv_values
        return dotenv_values(ROOT / '.env').get(name)
    except Exception:
        return None


def _calls_today():
    try:
        day = time.strftime('%Y-%m-%d')
        return sum(1 for line in USAGE.read_text(encoding='utf-8').splitlines() if f'"{day}' in line[:40])
    except OSError:
        return 0


# USD per 1M tokens (in, out). Unknown models fall back to the most expensive row (conservative).
# 1 USD is counted as 1 EUR on purpose: slightly overestimates spend, never underestimates.
PRICES = {'claude-haiku-4-5': (1.0, 5.0), 'claude-sonnet-4-5': (3.0, 15.0), 'gpt-4o-mini': (0.15, 0.60), 'gpt-4o': (2.5, 10.0)}


def _cost(model, tin, tout):
    pin, pout = PRICES.get(model, (3.0, 15.0))
    return (tin * pin + tout * pout) / 1_000_000


def _spent(day=None):
    """Return (total_eur, today_eur) from the usage ledger."""
    total = today = 0.0
    day = day or time.strftime('%Y-%m-%d')
    try:
        lines = USAGE.read_text(encoding='utf-8').splitlines()
    except OSError:
        return 0.0, 0.0
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        c = float(e.get('cost_eur') or 0)
        total += c
        if str(e.get('at', '')).startswith(day):
            today += c
    return total, today


def budget_status():
    cfg = load_config().get('budget', {})
    total, today = _spent()
    left = cfg.get('total_eur', 0) - total
    return {'spent_total': round(total, 4), 'spent_today': round(today, 4), 'left': round(left, 4),
            'daily_cap': cfg.get('daily_eur'), 'reserve': cfg.get('reserve_eur')}


def _budget_ok(cfg, model, prompt, max_tokens, task):
    b = cfg.get('budget')
    if not b:
        return False  # no budget configured -> no LLM spend at all
    total, today = _spent()
    worst = _cost(model, len(prompt) // 3 + 50, max_tokens)  # worst case for THIS call
    if b['total_eur'] - total - worst < b['reserve_eur']:
        return False
    if today + worst > b['daily_eur']:
        return False
    if task in b.get('critical_only_below_eur', {}).get('tasks_blocked', []) and \
            b['total_eur'] - total < b['critical_only_below_eur']['left']:
        return False
    return True


def _log(entry):
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    with USAGE.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')


def _call(provider, model, system, prompt, max_tokens, timeout):
    key = _key(provider)
    if provider == 'anthropic':
        import anthropic
        r = anthropic.Anthropic(api_key=key, timeout=timeout).messages.create(
            model=model, max_tokens=max_tokens, system=system, messages=[{'role': 'user', 'content': prompt}])
        return ''.join(b.text for b in r.content if getattr(b, 'text', None)), r.usage.input_tokens, r.usage.output_tokens
    from openai import OpenAI
    client = OpenAI(api_key=key, timeout=timeout,
                    base_url='https://openrouter.ai/api/v1' if provider == 'openrouter' else None)
    r = client.chat.completions.create(model=model, max_tokens=max_tokens, messages=[
        {'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}])
    return r.choices[0].message.content, r.usage.prompt_tokens, r.usage.completion_tokens


def route(task, prompt, *, system='You are an assistant for an eBay/AliExpress dropshipping automation. Be concise and factual.',
          use_memory=True, caller=_call):
    """Return {'text','provider','model','tier'} or None if nothing is usable."""
    cfg = load_config()
    tier_name = cfg['task_to_tier'].get(task)
    if not tier_name:
        raise ValueError(f'unknown task {task!r}')
    tier = cfg['tiers'][tier_name]
    if _calls_today() >= cfg['limits']['daily_calls']:
        return None
    full = scrub(prompt)
    if use_memory:
        ctx = get_memory().context_for(prompt)
        if ctx:
            full = f'Relevant history:\n{ctx}\n\nTask:\n{full}'
    for provider, model in tier['chain']:
        if not _key(provider):
            continue
        name = f'model:{provider}:{model}'
        if not _budget_ok(cfg, model, full, tier['max_tokens'], task):
            continue
        try:
            circuit_check(name, threshold=3, cooldown=900)
        except CircuitOpen:
            continue
        t0 = time.time()
        try:
            text, tin, tout = caller(provider, model, system, full, tier['max_tokens'], cfg['limits']['timeout_seconds'])
            _record(name, True)
            _log({'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'task': task, 'tier': tier_name, 'provider': provider,
                  'model': model, 'in': tin, 'out': tout, 'cost_eur': round(_cost(model, tin, tout), 6),
                  'sec': round(time.time() - t0, 2), 'ok': True})
            return {'text': text, 'provider': provider, 'model': model, 'tier': tier_name}
        except Exception as exc:  # noqa: BLE001
            _record(name, False)
            _log({'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'task': task, 'tier': tier_name, 'provider': provider,
                  'model': model, 'ok': False, 'error': type(exc).__name__})
    return None


def available():
    cfg = load_config()
    return {t: [f'{p}/{m}' for p, m in v['chain'] if _key(p)] for t, v in cfg['tiers'].items()}
