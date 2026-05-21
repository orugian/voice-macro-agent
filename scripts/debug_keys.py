"""
Diagnóstico: imprime todos os eventos de teclado que o pynput consegue capturar.
Executar com: .venv\Scripts\python.exe scripts\debug_keys.py
Pressionar algumas teclas e observar o output.
Ctrl+C para sair.
"""
from pynput import keyboard

print("Listener iniciado. Pressione teclas para ver o que o pynput captura.")
print("Ctrl+C para sair.\n")

def on_press(key):
    print(f"  PRESS:   {key!r}")

def on_release(key):
    print(f"  RELEASE: {key!r}")
    if key == keyboard.Key.esc:
        return False  # para o listener se ESC for pressionado

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    try:
        listener.join()
    except KeyboardInterrupt:
        print("\nEncerrado.")
