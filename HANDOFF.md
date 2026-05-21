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

## Fase 4 — Governance (PENDENTE)

Estes itens ainda não foram feitos:
- [ ] Verificar `.gitignore` (cobertura de `.env`, `*.log`, `.venv/`, `__pycache__/`, `*.wav`)
- [ ] Criar `VERSION` file (`1.0.0`)
- [ ] Criar/verificar `.env.example` com template

---

## Próxima sessão sugerida

1. Verificar ambiente: `.venv\Scripts\python.exe main.py` → 6 modos no tray
2. Testar toast: gravar algo → verificar se notificação aparece no Windows
3. Testar beep: ouvir sons em start/stop/error
4. Testar startup: `python scripts/setup_windows_startup.py` → verificar bat criado
5. Completar Fase 4: .gitignore + VERSION file
6. Opcional: testar `pyinstaller voice-macro.spec` (requer `pip install pyinstaller`)

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
