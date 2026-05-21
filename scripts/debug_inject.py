"""
Diagnóstico: testa a injeção de texto via clipboard + Ctrl+V.
Executar com: .venv\Scripts\python.exe scripts\debug_inject.py
IMPORTANTE: clique em qualquer campo de texto (Notepad, browser, etc.)
            ANTES de pressionar Enter aqui para iniciar o teste.
"""
import time
import pyperclip
import keyboard

TEXT = "voice-macro teste de injeção — se você leu isso, funcionou!"

input("1. Abra um campo de texto qualquer (Notepad, browser, etc.)\n"
      "2. Clique nesse campo para dar foco a ele\n"
      "3. Pressione Enter AQUI para injetar o texto de teste: ")

print("Injetando em 2 segundos...")
time.sleep(2)

pyperclip.copy(TEXT)
time.sleep(0.05)
keyboard.send("ctrl+v")

print(f"Injeção enviada. O texto deveria ter aparecido no campo de texto.")
print(f"Texto injetado: '{TEXT}'")
