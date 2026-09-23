"""Strażnik operacji AstralJet — hook PreToolUse dla Claude Code.

Claude Code działa tu w trybie auto, więc polecenia wykonują się bez pytania.
Hook egzekwuje zasady z AGENTS.md i konstytucji:

- deny: szerokie dodanie plików do Git (add -A/./--all/-u, commit -a),
  wymuszony lub kasujący push, odczyt i edycja .env (poza .env.example);
- ask: zwykły git push, zatrzymywanie i uruchamianie procesów, skrypty
  operacyjne (restart, deploy, publish, launch, recover, start, stop,
  connector, worker), MT5/MetaTrader, zlecenia i live API Alpaca,
  publikacja witryny (wrangler, npm run deploy, vercel).

Bez dopasowania hook nic nie wypisuje i decyduje zwykły tryb uprawnień.
Błąd analizy kończy się decyzją ask, nie cichym przepuszczeniem.
"""
from __future__ import annotations

import json
import re
import shlex
import sys

DENY = "deny"
ASK = "ask"

# ".env" i ".env.<cokolwiek>" poza ".env.example"; nie łapie process.env, $env:, .venv, .envrc.
ENV_REF = re.compile(r"(?<![\w.$-])\.env((?:\.[\w-]+)*)(?![\w-])")

# Polecenia tylko do odczytu: w ich segmencie nie sprawdzamy procesów, skryptów ani MT5.
READERS = frozenset({
    "cat", "type", "gc", "get-content", "head", "tail", "less", "more",
    "grep", "egrep", "fgrep", "rg", "select-string", "sls", "findstr",
    "ls", "dir", "gci", "get-childitem", "wc", "file", "stat", "test-path",
    "get-filehash", "sha256sum", "md5sum", "echo", "write-output", "write-host", "printf",
})

PROCESS_FIRST_TOKEN = frozenset({"kill", "pkill", "killall", "spps"})
PROCESS_ANYWHERE = re.compile(
    r"(?<![\w-])(stop-process|start-process|taskkill|stop-service|start-service|"
    r"restart-service|restart-computer|stop-computer)(?![\w-])",
    re.IGNORECASE,
)
OPS_SCRIPT = re.compile(
    r"(?<![\w.-])([\w.-]*(?:restart|deploy|publish|launch|recover|start|stop|connector|worker)"
    r"[\w.-]*\.(?:ps1|pyw?|mjs|cjs|js|cmd|bat|sh))(?!\w)",
    re.IGNORECASE,
)
MT5 = re.compile(r"(?<![a-z0-9])(mt5|metatrader\d*|terminal64)(?![a-z0-9])", re.IGNORECASE)
ALPACA_ORDERS = re.compile(r"alpaca\.markets\S*/(orders|positions)", re.IGNORECASE)
ALPACA_LIVE = re.compile(r"(?<![\w.-])api\.alpaca\.markets", re.IGNORECASE)
SITE_DEPLOY = re.compile(
    r"\bwrangler\b.*\b(deploy|publish|secret)\b|\bwrangler\b.*\bd1\b.*--remote"
    r"|\bnpm\s+run\s+(deploy|publish|release)\b|\bvercel\b.*(--prod\b|\bdeploy\b)",
    re.IGNORECASE,
)
# Awaryjnie, gdy git jest zagnieżdżony w innym poleceniu (np. bash -c "git push").
NESTED_GIT_PUSH = re.compile(r"(?<![\w-])git(?:\.exe)?\s+(?:\S+\s+)*?push\b", re.IGNORECASE)
NESTED_GIT_BROAD_ADD = re.compile(
    r"(?<![\w-])git(?:\.exe)?\s+add\s+(?:\S+\s+)*?(-A|--all|\.)(?=\s|$|[\"'])"
)

GIT_OPTS_WITH_VALUE = frozenset({
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env",
})
BROAD_PATHSPECS = frozenset({".", "./", ".\\", "*", ":/", ":/*", ":(top)", ":(top)."})


class Findings:
    def __init__(self) -> None:
        self.deny: list[str] = []
        self.ask: list[str] = []

    def add(self, decision: str, reason: str) -> None:
        bucket = self.deny if decision == DENY else self.ask
        if reason not in bucket:
            bucket.append(reason)


def _strip_quotes(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        return token[1:-1]
    return token


def _cmd_name(token: str) -> str:
    name = _strip_quotes(token).replace("\\", "/").rsplit("/", 1)[-1].lower()
    for ext in (".exe", ".cmd", ".bat"):
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


def _tokens(segment: str) -> list[str]:
    try:
        lexer = shlex.shlex(segment, posix=False)
        lexer.whitespace_split = True
        lexer.commenters = ""
        return [_strip_quotes(t) for t in lexer]
    except ValueError:
        return [_strip_quotes(t) for t in segment.split()]


def split_segments(command: str, tool: str) -> list[str]:
    """Dzieli polecenie na segmenty po && || ; | & z uwzględnieniem cudzysłowów.

    Nowa linia zawsze kończy segment i zamyka cudzysłów: treść heredoców
    i wieloliniowych komunikatów trafia wtedy do kontroli jako osobne
    segmenty, zamiast ukryć dalsze polecenia w niezamkniętym cudzysłowie.
    """
    escape = "`" if tool == "PowerShell" else "\\"
    segments: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(command):
        ch = command[i]
        if ch == "\n":
            segments.append("".join(buf))
            buf, quote = [], None
        elif quote:
            if ch == escape and quote == '"' and i + 1 < len(command) and command[i + 1] == '"':
                buf.append(command[i : i + 2])
                i += 2
                continue
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif command.startswith(("&&", "||"), i):
            segments.append("".join(buf))
            buf = []
            i += 2
            continue
        elif ch in ";|&":
            segments.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    segments.append("".join(buf))
    return [s.strip() for s in segments if s.strip()]


def env_hits(text: str) -> bool:
    return any(m.group(1) != ".example" for m in ENV_REF.finditer(text))


def _short_flags(arg: str) -> str:
    return arg[1:] if arg.startswith("-") and not arg.startswith("--") else ""


def check_git(args: list[str], findings: Findings) -> None:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in GIT_OPTS_WITH_VALUE else 1
    if i >= len(args):
        return
    sub, rest = args[i].lower(), args[i + 1 :]

    if sub == "add":
        dry_run = any(a in ("-n", "--dry-run") for a in rest)
        flags, pathspecs, after_dashdash = [], [], False
        for a in rest:
            if after_dashdash or not a.startswith("-"):
                pathspecs.append(a)
            elif a == "--":
                after_dashdash = True
            else:
                flags.append(a)
        all_flag = any(
            a in ("--all", "--update", "--no-ignore-removal")
            or "A" in _short_flags(a)
            or "u" in _short_flags(a)
            for a in flags
        )
        broad_path = any(p in BROAD_PATHSPECS for p in pathspecs)
        if not dry_run and (broad_path or (all_flag and not pathspecs)):
            findings.add(DENY, "Szerokie dodanie plików do Git (add -A/./--all/-u) jest zabronione "
                               "przez AGENTS.md. Obejrzyj listę (git status) i dodaj konkretne pliki.")

    elif sub == "commit":
        skip_next = False
        for a in rest:
            if skip_next:
                skip_next = False
                continue
            if a in ("-m", "-F", "-C", "-c", "--author", "--date", "--message", "--file"):
                skip_next = True
                continue
            short = _short_flags(a)
            if a == "--all" or "a" in short:
                findings.add(DENY, "git commit -a zatwierdza wszystkie zmienione pliki bez przeglądu "
                                   "(AGENTS.md). Dodaj konkretne pliki i zatwierdź bez -a.")
                break
            if short and short[-1] in "mFCc":
                skip_next = True

    elif sub == "push":
        dry_run = any(a in ("-n", "--dry-run") for a in rest)
        destructive = any(
            a in ("--force", "--mirror", "--delete", "--prune", "--force-if-includes")
            or a.startswith("--force-with-lease")
            or "f" in _short_flags(a)
            or "d" in _short_flags(a)
            or (not a.startswith("-") and (a.startswith("+") or a.startswith(":")))
            for a in rest
        )
        if destructive and not dry_run:
            findings.add(DENY, "Wymuszony lub kasujący git push jest zabroniony (AGENTS.md: nie "
                               "nadpisujemy historii). Rozwiąż rozbieżność bez --force.")
        else:
            findings.add(ASK, "git push publikuje zmiany w zdalnym repozytorium. Potwierdź gałąź i zakres.")


def check_segment(segment: str, findings: Findings) -> None:
    tokens = _tokens(segment)
    while tokens and re.match(r"^[A-Za-z_]\w*=", tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return
    head = _cmd_name(tokens[0])

    if head == "git":
        check_git(tokens[1:], findings)
        return
    if head in READERS:
        return

    if NESTED_GIT_BROAD_ADD.search(segment):
        findings.add(DENY, "Zagnieżdżone szerokie dodanie plików do Git (add -A/.) jest zabronione.")
    elif NESTED_GIT_PUSH.search(segment):
        findings.add(ASK, "Zagnieżdżony git push. Potwierdź gałąź i zakres.")

    if head in PROCESS_FIRST_TOKEN or PROCESS_ANYWHERE.search(segment):
        findings.add(ASK, "Polecenie zatrzymuje lub uruchamia procesy albo usługi. Upewnij się, że "
                          "nie dotyczy działających wykonawców, łącznika MT5 ani workera badań.")
    script = OPS_SCRIPT.search(segment)
    if script and not script.group(1).lower().startswith("test"):
        findings.add(ASK, f"Uruchomienie skryptu operacyjnego {script.group(1)}. "
                          "Restart, wdrożenie i publikacja wymagają zgody Karola.")
    if MT5.search(segment):
        findings.add(ASK, "Polecenie dotyczy MT5/MetaTrader. Nie zmieniamy procesów, ryzyka "
                          "ani rachunku bez uzgodnionego zakresu.")
    if ALPACA_ORDERS.search(segment) or ALPACA_LIVE.search(segment):
        findings.add(ASK, "Polecenie dotyczy zleceń/pozycji lub live API Alpaca.")
    if SITE_DEPLOY.search(segment):
        findings.add(ASK, "Publikacja witryny lub zapis do zdalnej bazy D1. Potwierdź wydanie.")


def check_shell(command: str, tool: str, findings: Findings) -> None:
    if env_hits(command):
        findings.add(DENY, "Polecenie odwołuje się do pliku .env z sekretami (klucze Alpaca). "
                           "Claude nie czyta ani nie zmienia .env; poproś Karola.")
    for segment in split_segments(command, tool):
        check_segment(segment, findings)


def check_file_tool(tool_input: dict, findings: Findings) -> None:
    for key in ("file_path", "notebook_path", "path", "glob"):
        value = tool_input.get(key)
        if isinstance(value, str) and env_hits(value.replace("\\", "/")):
            findings.add(DENY, "Plik .env zawiera sekrety (klucze Alpaca). Claude go nie czyta "
                               "ani nie zmienia; wzorzec jest w .env.example.")
            return


def check_gitkraken(tool: str, tool_input: dict, findings: Findings) -> None:
    if tool.endswith("__git_add"):
        files = tool_input.get("files") or []
        if not files or any(str(f).strip() in BROAD_PATHSPECS | {"-A", "--all"} for f in files):
            findings.add(DENY, "GitKraken git_add bez listy plików dodaje wszystko (AGENTS.md "
                               "zabrania). Podaj konkretne pliki.")
    elif tool.endswith("__git_push"):
        findings.add(ASK, "GitKraken git_push publikuje zmiany w zdalnym repozytorium. Potwierdź.")


def decide(payload: dict) -> tuple[str, str] | None:
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    findings = Findings()
    if tool in ("Bash", "PowerShell"):
        check_shell(str(tool_input.get("command") or ""), tool, findings)
    elif tool in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Grep"):
        check_file_tool(tool_input, findings)
    elif tool.startswith("mcp__GitKraken__"):
        check_gitkraken(tool, tool_input, findings)
    if findings.deny:
        return DENY, " ".join(findings.deny)
    if findings.ask:
        return ASK, " ".join(findings.ask)
    return None


def emit(decision: str, reason: str) -> None:
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": f"[Strażnik AstralJet] {reason}",
        }
    }))


def main() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        result = decide(payload)
    except Exception as exc:  # noqa: BLE001 — błąd analizy nie może przepuścić operacji po cichu
        emit(ASK, f"Nie udało się przeanalizować wywołania ({type(exc).__name__}: {exc}). Potwierdź ręcznie.")
        return 0
    if result:
        emit(*result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
