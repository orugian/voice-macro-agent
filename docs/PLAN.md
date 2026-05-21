# PLAN — voice-macro

**Voice Macro Assistant** — ferramenta local de produtividade por push-to-talk para Windows.  
Localização: `C:\Users\orugi\Documents\Projetos\voice-macro`

---

## Contexto e Decisões Arquiteturais (Não Renegociar)

| Decisão | Escolha | Justificativa |
|---|---|---|
| STT | faster-whisper local + CUDA, modelo `large-v3-turbo` | RTX 2060 4GB VRAM suporta float16; latência sub-segundo; privacidade total; zero custo |
| Carregamento do modelo | **Lazy loading com toggle manual** | Usuário divide ambiente com jogos; modelo ocupa ~2GB VRAM — deve ser descarregável via tray sem fechar a app |
| LLM | OpenRouter API, modelo padrão `google/gemini-2.5-flash-lite` | Mais barato ($0.10/$0.40 por 1M tokens), latência ultra-baixa, 1M context |
| Hotkeys globais | `pynput.keyboard.Listener` | Mantido ativamente; `keyboard` lib está unmaintained |
| Paste trigger | `keyboard.send("ctrl+v")` | Evita conflito pynput Listener + Controller (lag documentado no issue #438) |
| Fallback typing | `pynput.keyboard.Controller().type(text)` | Suporta PT-BR e Unicode; usar apenas com Listener pausado |
| Seleção de modo | Tray icon (pystray) + modo persistido em config | Menor fricção; uma hotkey universal |
| Clipboard write | `pyperclip.copy(text)` | Simples, sem dependências extras no Windows |
| Audio capture | `sounddevice`: `sd.rec()` + `sd.stop()` para PTT | Idiomático para push-to-talk; integra direto com faster-whisper |
| Tray icon | `pystray`, rodando em `threading.Thread(daemon=True)` | Não bloqueia main thread; funciona no Windows sem run_detached |
| Privacidade | Áudio deletado pós-processamento; sem logs de conteúdo | Privacy-first por design |
| Linguagem | Python 3.11+ | Ecosistema maduro; compatibilidade confirmada com todas as libs |
| Plataforma | Windows 10/11 exclusivo | Sem abstração cross-platform no MVP |

---

## APIs Validadas (Documentation Discovery)

### faster-whisper
```python
from faster_whisper import WhisperModel

# Instanciar via Transcriber.enable() — NÃO no construtor (lazy loading)
model = WhisperModel(
    "large-v3-turbo",          # alias válido → mobiuslabsgmbh/faster-whisper-large-v3-turbo
    device="cuda",
    compute_type="float16",    # RTX 2060 CC 7.5 suporta; fallback: "int8_float16" se OOM
    num_workers=1,
)

# Transcrever
segments, info = model.transcribe(
    audio_1d_float32,          # np.ndarray float32, shape (N,), 16kHz, range [-1,1]
    language=None,             # None = auto-detect
    vad_filter=True,           # remove silêncio; reduz alucinações
    vad_parameters=dict(min_silence_duration_ms=500),
)

# CRÍTICO: segments é gerador lazy — transcription SÓ roda ao iterar
segment_list = list(segments)
full_text = " ".join(s.text for s in segment_list).strip()
detected_lang = info.language          # "pt", "en", etc.
lang_confidence = info.language_probability
```

**Instalação:**
```
pip install faster-whisper
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12==9.*
```

**Anti-pattern:** `info.language` antes de `list(segments)` pode retornar valores não finalizados para alguns atributos. Sempre iterar primeiro.

---

### sounddevice — PTT Capture
```python
import sounddevice as sd
import numpy as np

SAMPLERATE = 16000
CHANNELS = 1
DTYPE = "float32"
MAX_DURATION = 60  # segundos

# PTT START
recording = sd.rec(
    int(MAX_DURATION * SAMPLERATE),
    samplerate=SAMPLERATE,
    channels=CHANNELS,
    dtype=DTYPE,
)

# PTT STOP (quando hotkey é solta)
sd.stop()

# Preparar para faster-whisper (float32, 1D, 16kHz)
audio_1d = recording[:sd.get_stream().time * SAMPLERATE].flatten()
# Alternativa mais segura: capturar duração real com um contador de frames
```

**Padrão seguro com InputStream + queue (para duração real):**
```python
import queue, sounddevice as sd, numpy as np

audio_queue = queue.Queue()

def callback(indata, frames, time, status):
    audio_queue.put(indata.copy())  # .copy() obrigatório

stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=callback)

# PTT START
stream.start()
# PTT STOP
stream.stop(); stream.close()

chunks = []
while not audio_queue.empty():
    chunks.append(audio_queue.get())
audio_1d = np.concatenate(chunks, axis=0).flatten()
```

---

### pynput — Hotkey Listener (Push-to-Talk)
```python
from pynput import keyboard as pynput_keyboard
import queue

event_queue = queue.Queue()  # thread-safe; nunca fazer trabalho pesado no callback

HOTKEY = {pynput_keyboard.Key.ctrl_l, pynput_keyboard.KeyCode.from_char('r')}
# Configurável; exemplo: Ctrl+R

current_keys = set()

def on_press(key):
    current_keys.add(key)
    if HOTKEY.issubset(current_keys):
        event_queue.put("PTT_START")

def on_release(key):
    if key in current_keys:
        current_keys.discard(key)
    if key in HOTKEY:
        event_queue.put("PTT_STOP")

listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()  # roda em thread própria, não bloqueia
```

**Anti-pattern:** Fazer processamento pesado dentro de `on_press`/`on_release`. O callback roda na OS input thread — bloquear aqui congela o teclado do sistema inteiro.

---

### Clipboard Injection
```python
import pyperclip, keyboard, time

def inject_clipboard(text: str) -> None:
    pyperclip.copy(text)
    time.sleep(0.05)           # aguardar clipboard settle
    keyboard.send("ctrl+v")   # keyboard lib (boppreh) para o send
```

**Fallback (quando clipboard paste falha — ex: alguns terminais):**
```python
from pynput.keyboard import Controller as PynputController

def inject_typing(text: str) -> None:
    ctrl = PynputController()
    ctrl.type(text)            # suporta PT-BR e Unicode
```

**Anti-pattern:** Usar `keyboard.write()` para texto com acentos — falha em PT-BR. Sempre `pynput Controller.type()` para fallback.

---

### pystray — System Tray Icon

#### UX do Tray — Design Visual e Interação

O ícone vive na **área de notificação do Windows** (canto inferior direito, ao lado do relógio). O Windows pode escondê-lo no overflow (botão `^`); o usuário pode fixá-lo para sempre aparecer via: `Configurações da barra de tarefas → Ícones da bandeja do sistema → voice-macro → Ativar`.

**Estados visuais (7 estados):**

| Estado | Cor | Tooltip |
|---|---|---|
| `disabled` | Cinza `#666666` | `voice-macro — Desativado · clique para ativar` |
| `loading` | Azul `#2196F3` | `voice-macro — Carregando modelo...` |
| `idle` | Verde `#4CAF50` | `voice-macro — Pronto · [MODO ATUAL]` |
| `recording` | Vermelho `#F44336` | `voice-macro — Gravando...` |
| `processing` | Âmbar `#FF9800` | `voice-macro — Processando...` |
| `done` | Verde vivo `#00E676` | `voice-macro — Concluído` (exibido 0.5s, retorna a idle) |
| `error` | Vermelho escuro `#C62828` | `voice-macro — Erro · ver voice-macro.log` |

**Interação:**
- **Clique esquerdo (left-click):** Toggle Ativar/Desativar — ação mais frequente, sem abrir menu
- **Clique direito (right-click):** Abre o menu contextual completo

**Estrutura do menu (right-click):**
```
[✓ Desativar]  ou  [Ativar]    ← default=True (ativado também por left-click)
────────────────────────────────
Modo ▶
  ● DICTATE
  ○ CLEAN
  ○ SUMMARY
  ○ STRUCTURE
  ○ REFINE
  ○ ACTION
────────────────────────────────
Sair
```

O item de toggle usa `default=True` no pystray para capturar left-click:
```python
pystray.MenuItem(
    lambda item: "Desativar" if transcriber.is_enabled else "Ativar",
    on_toggle_enable,
    default=True,   # ativado por left-click além do right-click menu
)
```

---

```python
import pystray
from PIL import Image, ImageDraw
import threading

def make_icon(color: str) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=color)
    return img

ICONS = {
    "disabled":   make_icon("#666666"),
    "loading":    make_icon("#2196F3"),
    "idle":       make_icon("#4CAF50"),
    "recording":  make_icon("#F44336"),
    "processing": make_icon("#FF9800"),
    "done":       make_icon("#00E676"),
    "error":      make_icon("#C62828"),
}

current_mode = "DICTATE"
MODES = ["DICTATE", "CLEAN", "SUMMARY", "STRUCTURE", "REFINE", "ACTION"]

def make_mode_item(mode: str):
    def on_select(icon, item):
        global current_mode
        current_mode = mode
        icon.update_menu()
    return pystray.MenuItem(
        mode,
        on_select,
        checked=lambda item, m=mode: current_mode == m,
        radio=True,
    )

menu = pystray.Menu(
    pystray.MenuItem("Modo", pystray.Menu(*[make_mode_item(m) for m in MODES])),
    pystray.Menu.SEPARATOR,
    pystray.MenuItem("Sair", lambda icon, item: icon.stop()),
)

tray = pystray.Icon("voice-macro", ICONS["idle"], "voice-macro — idle", menu)

# Rodar em background (não bloqueia main thread)
tray_thread = threading.Thread(target=tray.run, daemon=True)
tray_thread.start()

# Atualizar ícone de qualquer thread:
def set_tray_state(state: str) -> None:
    tray.icon = ICONS[state]
    tray.title = f"voice-macro — {state}"
```

---

### OpenRouter — LLM Text Processing
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

def call_llm(system_prompt: str, user_text: str, model: str = "google/gemini-2.5-flash-lite") -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_text},
        ],
        max_tokens=1000,
        temperature=0.3,
    )
    return response.choices[0].message.content
```

**Modelos validados:**
| ID | Input $/1M | Output $/1M | Notas |
|---|---|---|---|
| `google/gemini-2.5-flash-lite` | $0.10 | $0.40 | **Padrão recomendado** — mais novo, ultra-baixa latência |
| `google/gemini-2.0-flash-001` | $0.10 | $0.40 | Stable fallback; deprecação prevista Jun/2026 |
| `anthropic/claude-haiku-4.5` | $1.00 | $5.00 | 10x mais caro; reservar para casos que exijam |

**Instalação:** `pip install openai`

---

## Estrutura de Pastas

```
voice-macro/
├── app/
│   ├── __init__.py
│   ├── orchestration/
│   │   ├── __init__.py
│   │   └── orchestrator.py       # loop principal, coordena todas as camadas
│   ├── audio/
│   │   ├── __init__.py
│   │   └── capture.py            # sounddevice PTT capture
│   ├── stt/
│   │   ├── __init__.py
│   │   └── transcriber.py        # faster-whisper wrapper
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py             # OpenRouter wrapper
│   ├── injection/
│   │   ├── __init__.py
│   │   └── injector.py           # clipboard + fallback typing
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py           # carrega .env e config.toml
│   ├── logging/
│   │   ├── __init__.py
│   │   └── logger.py             # configuração de logging
│   ├── modes/
│   │   ├── __init__.py
│   │   └── processors.py         # mapeamento modo → system prompt
│   └── tray/
│       ├── __init__.py
│       └── tray_icon.py          # pystray icon e menu
├── prompts/
│   ├── clean.txt
│   ├── summary.txt
│   ├── structure.txt
│   ├── refine.txt
│   └── action.txt
├── docs/
│   └── PLAN.md                   # este arquivo
├── tests/
│   ├── test_audio.py
│   ├── test_stt.py
│   ├── test_injection.py
│   └── test_modes.py
├── assets/
│   └── icons/                    # ícones PNG para os estados do tray
├── scripts/
│   └── setup_windows_startup.py  # registra auto-start no Windows
├── .env.example
├── config.toml
├── requirements.txt
├── main.py                       # entrypoint
└── README.md
```

---

## Modos Operacionais e Prompts

| Modo | LLM? | Comportamento |
|---|---|---|
| DICTATE | Não | Transcrição pura. Output = texto do STT direto. |
| CLEAN | Sim | Corrige pontuação, remove hesitações ("ã", "tipo", "né"), mantém sentido. |
| SUMMARY | Sim | Resume em bullet points estruturados. |
| STRUCTURE | Sim | Organiza em: Objetivo, Contexto, Problema, Arquitetura/Solução, Próximos Passos. |
| REFINE | Sim | Reescreve com clareza profissional; melhora argumentação; mantém voz. |
| ACTION | Sim | Extrai: Tarefas, Decisões, Responsáveis, Prazo (se mencionado). |

---

## Variáveis de Ambiente e Config

**`.env.example`:**
```
OPENROUTER_API_KEY=sk-or-...
```

**`config.toml` (valores padrão, sobrescritos por .env se necessário):**
```toml
[hotkey]
combination = "ctrl+alt+r"      # tecla de push-to-talk

[stt]
model = "large-v3-turbo"
device = "cuda"
compute_type = "float16"        # fallback: "int8_float16"
language = null                  # null = auto-detect

[llm]
model = "google/gemini-2.5-flash-lite"
max_tokens = 1000
temperature = 0.3

[audio]
samplerate = 16000
channels = 1
max_duration_seconds = 60

[app]
default_mode = "DICTATE"
start_enabled = false           # false = app inicia desativada; VRAM livre por padrão
log_level = "INFO"
delete_audio_after_processing = true
```

---

---

# Fase 0 — Setup do Ambiente

**Contexto para execução:** Este é o ponto de partida do projeto. O diretório `C:\Users\orugi\Documents\Projetos\voice-macro` já foi criado.

## Objetivos
- Criar estrutura completa de pastas
- Configurar ambiente virtual Python 3.11+
- Instalar todas as dependências
- Validar CUDA e faster-whisper no hardware local
- Criar arquivos base de configuração

## Tarefas

### 0.1 — Criar estrutura de pastas
Criar todos os subdiretórios conforme "Estrutura de Pastas" acima. Criar `__init__.py` vazio em cada `app/*/` subpasta.

### 0.2 — Criar `requirements.txt`
```
faster-whisper>=1.2.1
nvidia-cublas-cu12
nvidia-cudnn-cu12==9.*
sounddevice>=0.4.6
numpy>=1.24
scipy>=1.10
pyperclip>=1.8
keyboard>=0.13.5
pynput>=1.7.6
pystray>=0.19.5
Pillow>=10.0
openai>=1.0
python-dotenv>=1.0
tomllib>=2.0; python_version < "3.11"
```

### 0.3 — Criar ambiente virtual e instalar
```powershell
cd C:\Users\orugi\Documents\Projetos\voice-macro
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 0.4 — Criar `.env.example`, `.env` e `.gitignore`
Criar `.env.example` com o template. Criar `.env` real com a chave OpenRouter do usuário.
Criar `.gitignore` com o conteúdo da Fase 4 desde já — nunca commitar `.env` ou áudios.

### 0.5 — Criar `config.toml`
Criar com todos os valores padrão listados acima.

### 0.6 — Script de validação CUDA + faster-whisper
Criar `scripts/validate_cuda.py`:
```python
# Valida CUDA, carrega modelo, faz transcrição de arquivo de teste
from faster_whisper import WhisperModel
model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
print(f"Modelo carregado. Device: cuda")
# Transcrever arquivo de teste (silêncio ou áudio curto)
```
Executar e confirmar que o modelo carrega sem erros de CUDA/cuDNN.

## Verificação
- [ ] `python scripts/validate_cuda.py` executa sem erro
- [ ] Modelo `large-v3-turbo` faz download (~1.5GB, cache em `~/.cache/huggingface/hub`)
- [ ] `import pystray; import sounddevice; import keyboard; import pynput` sem erro
- [ ] `.env` existe e não está no git (adicionar ao `.gitignore`)

## Anti-patterns
- Não commitar `.env` com a chave real
- Se `compute_type="float16"` lançar `CTranslate2 not compiled with CUDA`, verificar versão do `ctranslate2` e instalar CUDA Toolkit 12.x
- Se cuDNN não encontrado (erro 126), adicionar pasta `bin` do cuDNN ao PATH do Windows

---

# Fase 1 — MVP Core (Pipeline Completo + DICTATE mode)

**Contexto para execução:** Fase 0 concluída. Ambiente configurado, dependências instaladas, CUDA validado. Implementar o pipeline completo de gravação → STT → injeção com o modo DICTATE. Tray icon com estados visuais.

**Arquivos do PLAN.md:** Todas as assinaturas de API estão na seção "APIs Validadas" acima.

## Objetivos
- Pipeline ponta-a-ponta funcionando
- Push-to-talk com pynput
- Captura com sounddevice
- Transcrição com faster-whisper CUDA
- Injeção via clipboard
- Tray icon com 7 estados (disabled, loading, idle, recording, processing, done, error)
- Left-click no tray: toggle Ativar/Desativar
- App inicia sempre no estado `disabled` (VRAM livre)
- Seleção de modo via tray (apenas DICTATE ativo, outros desabilitados)

## Tarefas

### 1.1 — `app/config/settings.py`
```python
import os, tomllib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # carrega .env

ROOT = Path(__file__).parent.parent.parent

def load_config() -> dict:
    config_path = ROOT / "config.toml"
    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)
    cfg["llm"]["api_key"] = os.getenv("OPENROUTER_API_KEY", "")
    return cfg

CONFIG = load_config()
```

### 1.2 — `app/logging/logger.py`
Configurar `logging.basicConfig` com nível de `CONFIG["app"]["log_level"]`. Output: arquivo `voice-macro.log` + console. Sem logar conteúdo de transcrições (privacidade).

### 1.3 — `app/audio/capture.py`
Implementar `AudioCapture` com:
- `start_recording()` → inicia `sd.InputStream` com queue callback
- `stop_recording() -> np.ndarray` → para stream, concatena chunks, retorna float32 1D 16kHz
- Usar o padrão `InputStream + queue` das APIs Validadas (padrão seguro para duração variável)
- Deletar referência ao array após uso (privacidade)

### 1.4 — `app/stt/transcriber.py`
Implementar `Transcriber` com **lazy loading** — modelo NÃO carrega no `__init__`:

```python
import gc
from faster_whisper import WhisperModel

class Transcriber:
    def __init__(self, config: dict):
        self._config = config
        self._model = None          # VRAM não consumida até enable()

    def enable(self) -> None:
        """Carrega modelo na VRAM (~10-15s a partir do cache local)."""
        if self._model is None:
            self._model = WhisperModel(
                self._config["stt"]["model"],
                device=self._config["stt"]["device"],
                compute_type=self._config["stt"]["compute_type"],
                num_workers=1,
            )

    def disable(self) -> None:
        """Descarrega modelo da VRAM — libera ~2GB para jogos."""
        if self._model is not None:
            del self._model
            self._model = None
            gc.collect()            # força liberação imediata pelo GC

    @property
    def is_enabled(self) -> bool:
        return self._model is not None

    def transcribe(self, audio_1d) -> tuple[str, str]:
        if self._model is None:
            raise RuntimeError("Transcriber desativado. Ative via tray antes de gravar.")
        segments, info = self._model.transcribe(
            audio_1d,
            language=None,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        segment_list = list(segments)   # força execução do gerador lazy
        full_text = " ".join(s.text for s in segment_list).strip()
        return full_text, info.language
```

**Estado inicial:** desativado por padrão. Usuário ativa manualmente via tray quando entra no ambiente de desenvolvimento.

### 1.5 — `app/injection/injector.py`
```python
def inject(text: str, use_fallback: bool = False) -> None:
    if use_fallback:
        _inject_typing(text)
    else:
        _inject_clipboard(text)

def _inject_clipboard(text: str) -> None:
    pyperclip.copy(text)
    time.sleep(0.05)
    keyboard.send("ctrl+v")

def _inject_typing(text: str) -> None:
    from pynput.keyboard import Controller
    Controller().type(text)
```

### 1.6 — `app/tray/tray_icon.py`
Implementar `TrayIcon` com:
- Ícones PIL para os 6 estados: `idle`, `recording`, `processing`, `done`, `error`, `disabled`
- Menu com submenu de modos (todos `enabled=False` exceto DICTATE no MVP)
- **Toggle Ativar/Desativar** no topo do menu:
  ```python
  MenuItem(
      lambda item: "Desativar" if transcriber.is_enabled else "Ativar",
      on_toggle_enable,
  )
  ```
  - Ao **desativar**: chama `transcriber.disable()`, desativa hotkey, `set_state("disabled")`
  - Ao **ativar**: `set_state("loading")` (feedback visual), chama `transcriber.enable()` em thread separada, depois `set_state("idle")` e reativa hotkey
- `set_state(state: str)` chamável de qualquer thread
- `start()` → lança em `threading.Thread(target=self._icon.run, daemon=True)`
- `stop()` → chama `self._icon.stop()`

**Estado inicial da app:** `disabled`. Hotkey inativa. Usuário ativa manualmente.

**Feedback durante carregamento** (~10-15s): tray mostra estado `"loading"` com tooltip "Carregando modelo..." para o usuário saber que não está travado.

### 1.7 — `app/orchestration/orchestrator.py`
Pipeline principal:
```python
class Orchestrator:
    def __init__(self, config, tray, audio, stt, injector):
        self._event_queue = queue.Queue()
        self._recording = False
        self._setup_hotkey()

    def _setup_hotkey(self):
        # pynput Listener — dispatch para event_queue
        # NÃO fazer processamento aqui; apenas enfileirar eventos
        ...

    def run(self):
        while True:
            event = self._event_queue.get()
            if event == "PTT_START" and not self._recording:
                self._on_ptt_start()
            elif event == "PTT_STOP" and self._recording:
                self._on_ptt_stop()
            elif event == "QUIT":
                break

    def _on_ptt_start(self):
        if not self.stt.is_enabled:
            return          # guard: ignora PTT silenciosamente quando desativado
        self._recording = True
        self.tray.set_state("recording")
        self.audio.start_recording()

    def _on_ptt_stop(self):
        self._recording = False
        self.tray.set_state("processing")
        audio = self.audio.stop_recording()
        try:
            text, lang = self.stt.transcribe(audio)
            self.injector.inject(text)
            self.tray.set_state("done")
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self.tray.set_state("error")
        finally:
            time.sleep(0.5)
            self.tray.set_state("idle")
```

### 1.8 — `main.py`
Entrypoint: carrega config, instancia todas as camadas, inicia tray, inicia orchestrator loop.

## Verificação
- [ ] App inicia → ícone cinza (`disabled`) na área de notificação do Windows
- [ ] Left-click no ícone → ícone azul (`loading`) → ~10-15s → ícone verde (`idle`)
- [ ] Pressionar hotkey com app desativada → nenhuma ação (guard funcionando)
- [ ] Segurar hotkey com app ativa → ícone vermelho (`recording`)
- [ ] Soltar hotkey → ícone âmbar (`processing`)
- [ ] Texto transcrito aparece no campo ativo (Notepad, browser, VS Code)
- [ ] Ícone verde vivo (`done`) por 0.5s → volta para verde (`idle`)
- [ ] Left-click no ícone ativo → ícone cinza (`disabled`), ~2GB VRAM liberados (verificar via GPU-Z)
- [ ] Log mostra latência de transcrição (deve ser < 2s para clips curtos com CUDA)
- [ ] Arquivo de áudio não persiste no disco após processamento
- [ ] Right-click → menu mostra toggle e submenu de modos

## Anti-patterns
- `on_press` e `on_release` do pynput **nunca** devem chamar STT ou LLM diretamente — apenas `event_queue.put()`
- `list(segments)` é obrigatório antes de `" ".join(...)` — o gerador lazy não executa até ser iterado
- Não usar `keyboard.write()` para PT-BR — usar `pynput Controller.type()`
- `transcriber.enable()` é bloqueante (~10-15s) — chamar em `threading.Thread` separada, nunca na thread do tray

---

# Fase 2 — Intelligence Layer (Modos LLM)

**Contexto para execução:** Fase 1 concluída. Pipeline DICTATE funcionando. Adicionar os 5 modos LLM via OpenRouter, prompts por modo, e UI de seleção de modo no tray.

**Arquivos do PLAN.md:** Ver seção "OpenRouter" e "Modos Operacionais e Prompts" acima.

## Objetivos
- Integração OpenRouter com `openai` SDK
- Prompts para os 5 modos LLM (CLEAN, SUMMARY, STRUCTURE, REFINE, ACTION)
- Seleção de modo via tray menu (radio buttons)
- Modo persistido em memória (e em config.toml na próxima sessão)
- Pipeline condicional: DICTATE pula LLM, outros passam por LLM

## Tarefas

### 2.1 — `app/llm/client.py`
```python
from openai import OpenAI

class LLMClient:
    def __init__(self, config: dict):
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config["llm"]["api_key"],
        )
        self._model = config["llm"]["model"]
        self._max_tokens = config["llm"]["max_tokens"]
        self._temperature = config["llm"]["temperature"]

    def process(self, system_prompt: str, text: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": text},
            ],
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        return response.choices[0].message.content
```

### 2.2 — `app/modes/processors.py`
Carregar prompts de `prompts/*.txt`. Mapear modo → system prompt. Expor `process(mode, text, llm_client)`.

```python
MODES_REQUIRING_LLM = {"CLEAN", "SUMMARY", "STRUCTURE", "REFINE", "ACTION"}

def process(mode: str, text: str, llm_client) -> str:
    if mode == "DICTATE":
        return text
    prompt = load_prompt(mode)   # lê prompts/{mode.lower()}.txt
    return llm_client.process(prompt, text)
```

### 2.3 — Criar arquivos de prompt em `prompts/`

**`prompts/clean.txt`:**
```
Você é um editor de texto preciso. Receba uma transcrição de fala e:
- Corrija pontuação e capitalização
- Remova hesitações verbais ("tipo", "né", "ã", "hmm", "como assim")
- Mantenha o sentido original exato
- Retorne apenas o texto corrigido, sem explicações
- Preserve o idioma original (PT-BR ou EN)
```

**`prompts/summary.txt`:**
```
Você é um assistente de síntese. Receba uma transcrição de fala e retorne um resumo em bullet points:
- Use bullets (•) para cada ponto principal
- Máximo de 8 bullets
- Seja objetivo e direto
- Preserve o idioma original
- Retorne apenas os bullets, sem introdução ou conclusão
```

**`prompts/structure.txt`:**
```
Você é um arquiteto de raciocínio. Receba ideias faladas e organize em seções:
## Objetivo
## Contexto
## Problema / Desafio
## Solução / Arquitetura
## Próximos Passos

Use apenas as seções relevantes ao conteúdo fornecido.
Preserve o idioma original.
```

**`prompts/refine.txt`:**
```
Você é um editor profissional. Receba um texto transcrito e reescreva com:
- Clareza e precisão profissional
- Melhor estrutura de argumentação
- Eliminação de redundâncias
- Manutenção da voz e intenção original
- Preserve o idioma original
Retorne apenas o texto refinado.
```

**`prompts/action.txt`:**
```
Você é um extrator de ações. Receba uma transcrição e extraia:

**Tarefas:**
- [lista de tarefas identificadas]

**Decisões:**
- [decisões tomadas ou mencionadas]

**Próximos Passos:**
- [o que deve ser feito a seguir]

**Responsáveis** (se mencionado):
- [quem faz o quê]

Use apenas as seções com conteúdo relevante. Preserve o idioma original.
```

### 2.4 — Atualizar `app/tray/tray_icon.py`
Habilitar todos os modos no menu (remover `enabled=False`). Expor `get_current_mode() -> str`.

### 2.5 — Atualizar `app/orchestration/orchestrator.py`
No `_on_ptt_stop`, após STT, chamar `modes.process(current_mode, text, llm_client)`.
Log de latência LLM separado do STT.

## Verificação
- [ ] Tray menu mostra 6 modos com radio button; selecionar um persiste entre gravações
- [ ] DICTATE: injeção imediata sem chamada de rede
- [ ] CLEAN: remove "né" e "tipo" corretamente de fala PT-BR
- [ ] SUMMARY: retorna bullets coerentes para 30s de fala
- [ ] STRUCTURE: organiza brainstorming em seções com headers
- [ ] REFINE: reescreve mantendo a essência
- [ ] ACTION: extrai tarefas de uma lista verbal
- [ ] Latência total (STT + LLM + inject) < 5s para clips de até 30s

## Anti-patterns
- Não usar `model="google/gemini-2.0-flash"` sem o sufixo `-001` — alias não confirmado no OpenRouter
- `response.choices[0].message.content` pode ser `None` se o modelo falhar — adicionar guard: `or ""`
- Não logar o conteúdo do texto transcrito ou processado (privacidade)

---

# Fase 3 — Robustez

**Contexto para execução:** Fases 1 e 2 concluídas. Pipeline funcionando com todos os modos. Adicionar resiliência, tratamento de erros e melhorias de UX.

## Objetivos
- Retry automático em falhas de rede (LLM)
- Timeouts em chamadas de API
- Fallback typing quando clipboard falha
- Detecção e tratamento de silêncio/áudio vazio
- Feedback sonoro (beep em start/stop de gravação)
- Tratamento de erros com mensagens claras no log

## Tarefas

### 3.1 — Retry na camada LLM
```python
import time

def process_with_retry(self, system_prompt: str, text: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            return self.process(system_prompt, text)
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)   # exponential backoff: 1s, 2s, 4s
```

### 3.2 — Timeout em chamadas OpenRouter
Adicionar `timeout=10.0` na chamada `client.chat.completions.create(... timeout=10.0)`.

### 3.3 — Detecção de áudio vazio/silêncio
```python
def is_audio_empty(audio: np.ndarray, threshold: float = 0.01) -> bool:
    return np.max(np.abs(audio)) < threshold
```
Se vazio: pular pipeline, log warning, tray volta para idle sem injetar.

### 3.4 — Fallback automático de injection
```python
def inject(text: str) -> None:
    try:
        _inject_clipboard(text)
    except Exception:
        logger.warning("Clipboard injection failed, using typing fallback")
        _inject_typing(text)
```

### 3.5 — Feedback sonoro
```python
import winsound
winsound.Beep(1000, 100)  # start recording: 1kHz, 100ms
winsound.Beep(600, 150)   # stop recording: 600Hz, 150ms
winsound.Beep(400, 200)   # error: 400Hz, 200ms
```
Executar em thread para não bloquear: `threading.Thread(target=winsound.Beep, args=(1000, 100), daemon=True).start()`

### 3.6 — Tratamento de duração mínima
Se áudio < 0.5 segundos: ignorar. Usuário provavelmente apertou a tecla por acidente.

## Verificação
- [ ] Desconectar internet → LLM falha → retry 3x → log de erro → tray mostra "error" → volta idle
- [ ] Gravar silêncio → nenhuma injeção → log "áudio vazio"
- [ ] Testar em campo que bloqueia Ctrl+V → fallback typing funciona
- [ ] Beep soa ao iniciar e ao parar gravação
- [ ] Gravação < 0.5s → ignorada silenciosamente

## Anti-patterns
- Não usar `except:` genérico sem logar o erro — sempre `except Exception as e: logger.error(e)`
- Retry com backoff fixo (não exponencial) pode sobrecarregar a API em outage
- `winsound.Beep` bloqueia a thread por `duration` ms — sempre executar em thread separada

---

# Fase 4 — Governance & Packaging

**Contexto para execução:** Fases 1-3 concluídas. Ferramenta funcionando e robusta. Preparar para uso diário sustentável.

## Objetivos
- README com instalação e uso
- Script de setup automatizado
- Auto-start opcional no Windows (pasta Startup)
- Versionamento semântico (MAJOR.MINOR.PATCH)
- `.gitignore` correto

## Tarefas

### 4.1 — `README.md`
Seções: Requisitos, Instalação, Configuração, Uso (hotkey + modos), Troubleshooting (CUDA, cuDNN).

### 4.2 — `scripts/setup.py`
Script interativo que:
1. Verifica Python 3.11+
2. Cria `.venv`
3. Instala `requirements.txt`
4. Cria `.env` se não existir (solicita chave OpenRouter ao usuário)
5. Executa `validate_cuda.py`

### 4.3 — `scripts/setup_windows_startup.py`
```python
import winreg, sys
from pathlib import Path

# Adiciona main.py ao registro de startup do Windows
# HKCU\Software\Microsoft\Windows\CurrentVersion\Run
key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
    r"Software\Microsoft\Windows\CurrentVersion\Run",
    0, winreg.KEY_SET_VALUE)
venv_python = Path(sys.executable)
main_py = Path(__file__).parent.parent / "main.py"
winreg.SetValueEx(key, "voice-macro", 0, winreg.REG_SZ,
    f'"{venv_python}" "{main_py}"')
winreg.CloseKey(key)
```

### 4.4 — `.gitignore`
```
.venv/
.env
*.pyc
__pycache__/
*.log
*.wav
*.mp3
voice-macro.log
```

### 4.5 — `VERSION` file
```
1.0.0
```

## Verificação
- [ ] `python scripts/setup.py` instala tudo do zero em máquina limpa
- [ ] `python scripts/setup_windows_startup.py` aparece no Task Manager → Startup
- [ ] `git status` não mostra `.env` ou arquivos de áudio
- [ ] README cobre o troubleshooting de CUDA/cuDNN

---

## Dependências Entre Fases

```
Fase 0 (Setup) 
    └── Fase 1 (MVP Core + DICTATE)
            └── Fase 2 (Modos LLM)
                    └── Fase 3 (Robustez)
                            └── Fase 4 (Governance)
```

Cada fase é pré-requisito da seguinte. Não pular.

---

## Troubleshooting CUDA (Referência Rápida)

| Erro | Causa | Fix |
|---|---|---|
| `Could not load cudnn_ops_infer64_8.dll (error 126)` | cuDNN não está no PATH | Adicionar `C:\Program Files\NVIDIA\CUDNN\v9\bin` ao PATH |
| `CTranslate2 not compiled with CUDA support` | Wheel CPU instalado | Verificar CUDA Toolkit instalado antes do pip install |
| `CUDA out of memory` | 4GB VRAM insuficiente para float16 | Mudar `compute_type` para `"int8_float16"` no config.toml |
| `ctranslate2` versão incompatível | CUDA 11 ou cuDNN 8 | `pip install --force-reinstall ctranslate2==4.4.0` |

---

*Plano gerado em 2026-05-20. Baseado em faster-whisper 1.2.1, pystray 0.19.5, pynput 1.7.6, sounddevice 0.4.6, openai SDK, OpenRouter API.*
