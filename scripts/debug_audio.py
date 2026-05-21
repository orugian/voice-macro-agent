"""
Diagnóstico: lista dispositivos de áudio disponíveis e grava 3 segundos.
Executar com: .venv\Scripts\python.exe scripts\debug_audio.py
"""
import numpy as np
import sounddevice as sd

print("=== Dispositivos de entrada (microfone) disponíveis ===\n")
devices = sd.query_devices()
for i, d in enumerate(devices):
    if d["max_input_channels"] > 0:
        marker = " <-- PADRÃO" if i == sd.default.device[0] else ""
        print(f"  [{i}] {d['name']}{marker}")
        print(f"       canais: {d['max_input_channels']}, sample rate padrão: {d['default_samplerate']:.0f} Hz")

print(f"\nDispositivo padrão de entrada: [{sd.default.device[0]}]")
print("\n=== Gravando 3 segundos no dispositivo padrão... ===")
print("Fale algo para testar a captura de áudio.\n")

try:
    audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype="float32")
    sd.wait()
    audio_flat = audio.flatten()

    peak = np.max(np.abs(audio_flat))
    rms = np.sqrt(np.mean(audio_flat ** 2))

    print(f"Gravação concluída: {len(audio_flat)} amostras")
    print(f"  Pico de amplitude: {peak:.4f}  (> 0.01 indica áudio real, < 0.001 = silêncio/sem microfone)")
    print(f"  RMS: {rms:.6f}")

    if peak < 0.001:
        print("\n⚠  ATENÇÃO: amplitude quase zero — nenhum áudio detectado.")
        print("   Possíveis causas:")
        print("   1. Nenhum microfone disponível na sessão VNC")
        print("   2. Microfone mudo ou desativado no Windows")
        print("   3. Dispositivo padrão incorreto — tente outro índice acima")
    else:
        print(f"\n✓ Áudio capturado com sucesso (pico={peak:.4f})")
except Exception as e:
    print(f"\nERRO ao gravar: {e}")
    print("Verifique se há um dispositivo de entrada disponível.")
