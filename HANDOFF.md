# Handoff — voice-macro

**Data:** 2026-05-20  
**Sessão encerrada em:** Fases 3, 5 e 6 concluídas  
**Próxima sessão inicia em:** Fase 4 — Governance (pendente) + testes de distribuição

---

## Estado atual do projeto

Pipeline completo, robusto e com UX melhorada. Pronto para uso diário.

```
voice-macro/
├── app/
│   ├── audio/capture.py          ✅
│   ├── config/settings.py        ✅
│   ├── injection/injector.py     ✅ fallback automático clipboard→typing
│   ├── llm/client.py             ✅ retry 3x + exponential backoff + timeout 10s
│   ├── logging/logger.py         ✅
│   ├── modes/processors.py       ✅
│   ├── orchestration/
│   │   └── orchestrator.py      ✅ beep start/stop/error, duração mínima 0.5s,
│   │                                  detecção silêncio, tracker duração gravação
│   ├── stt/transcriber.py        ✅
│   └── tray/tray_icon.py         ✅ ícone mic profissional, toast winotify,
│                                      set_recording_duration(), set_state(info="")
├── docs/
│   ├── PLAN.md                   ✅
│   └── ARCHITECTURE.md           ✅
├── prompts/
│   ├── clean.txt / summary.txt / instruct.txt / refine.txt / action.txt ✅
├── scripts/
│   ├── debug_keys.py / debug_audio.py / debug_inject.py / validate_cuda.py ✅
│   ├── setup.py                  ✅ NOVO — setup guiado para novos usuários
│   └── setup_windows_startup.py  ✅ NOVO — cria bat na pasta Startup do Windows
├── .env                          ✅
├── config.toml                   ✅ combination = "ctrl+shift+r"
├── launch.bat                    ✅
├── main.py                       ✅
├── requirements.txt              ✅ winotify adicionado
├── voice-macro.spec              ✅ NOVO — PyInstaller one-folder dist
└── README.md                     ✅
```

---

## Mudanças nesta sessão (2026-05-20)

### Fase 3 — Robustez ✅
| Item | Arquivo | Detalhe |
|---|---|---|
| Retry LLM 3x | `app/llm/client.py` | Exponential backoff 1s/2s/4s; `last_exc` reraise |
| Timeout OpenRouter | `app/llm/client.py` | `timeout=10.0` na chamada |
| Fallback injeção | `app/injection/injector.py` | Auto: clipboard → typing se falhar (sem param manual) |
| Duração mínima | `app/orchestration/orchestrator.py` | < 0.5s = ignorado silenciosamente |
| Detecção silêncio | `app/orchestration/orchestrator.py` | `np.max(np.abs) < 0.01` = skip pipeline |
| Beep start | `app/orchestration/orchestrator.py` | `winsound.Beep(1000, 100)` em thread |
| Beep stop | `app/orchestration/orchestrator.py` | `winsound.Beep(600, 150)` em thread |
| Beep error | `app/orchestration/orchestrator.py` | `winsound.Beep(400, 200)` em thread |

### Fase 5 — UX ✅
| Item | Arquivo | Detalhe |
|---|---|---|
| Ícone profissional | `app/tray/tray_icon.py` | Squircle + silhueta mic branca (Pillow) |
| Duração gravação tooltip | `app/tray/tray_icon.py` | `set_recording_duration()` atualiza tooltip a cada 0.5s |
| Toast no sucesso | `app/tray/tray_icon.py` | `winotify.Notification` com latência STT+LLM; silencioso se falhar |
| Latência no tooltip | `app/tray/tray_icon.py` | `set_state("done", "STT 1.2s · LLM 0.8s")` |

### Fase 6 — Distribuição ✅
| Item | Arquivo | Detalhe |
|---|---|---|
| Setup guiado | `scripts/setup.py` | 5 passos: Python check, venv, pip, .env, CUDA |
| Auto-start Windows | `scripts/setup_windows_startup.py` | Cria bat em %APPDATA%/Startup com pythonw.exe |
| PyInstaller spec | `voice-macro.spec` | One-folder dist, DLLs CUDA via collect_dynamic_libs |
| winotify | `requirements.txt` | Adicionado; instalado no venv |

---

## Fase 4 — Governance ✅

- [x] `.gitignore` — cobre `.env`, `*.log`, `.venv/`, `__pycache__/`, `*.wav`, `dist/`, `build/`
- [x] `.gitattributes` — normaliza LF no repo, CRLF para .bat
- [x] `VERSION` — `1.0.0`
- [x] `.env.example` — com comentários e link para obter chave
- [x] Repositório git inicializado — commit inicial `5979872` com 45 arquivos

---

## Projeto concluído — todas as fases implementadas

| Fase | Status |
|---|---|
| 0 — Setup | ✅ |
| 1 — MVP Core (DICTATE + tray) | ✅ |
| 2 — Intelligence Layer (5 modos LLM) | ✅ |
| 3 — Robustez | ✅ |
| 4 — Governance | ✅ |
| 5 — UX (toast, ícone, tooltip duração) | ✅ |
| 6 — Distribuição (setup.py, startup, spec) | ✅ |

---

## Próximos passos opcionais

- Fazer push para GitHub: `git remote add origin <url> && git push -u origin master`
- Testar build PyInstaller: `pip install pyinstaller && pyinstaller voice-macro.spec`
- Criar tag de release: `git tag v1.0.0`

---

## Bugs corrigidos (histórico)

| Bug | Causa | Fix |
|---|---|---|
| Hotkey nunca detectada | `Ctrl+R` chegava como `'\x12'` (control char) | `_normalize_key()` em orchestrator.py |
| `Key.shift` genérico não reconhecido | pynput reporta genérico em VNC | `Key.shift` adicionado ao set de alternativas |
| `language = null` no TOML | TOML 1.0 não tem null | Corrigido para `language = ""` |

---

## Modos disponíveis

| Modo | LLM | Prompt |
|---|---|---|
| DICTATE | Não | — transcrição pura |
| CLEAN | Sim | `prompts/clean.txt` |
| SUMMARY | Sim | `prompts/summary.txt` |
| INSTRUCT | Sim | `prompts/instruct.txt` |
| REFINE | Sim | `prompts/refine.txt` |
| ACTION | Sim | `prompts/action.txt` |
