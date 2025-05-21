import asyncio
import edge_tts
import speech_recognition as sr
import pygame
import os
import uuid
import time
from typing import Dict, Tuple

class AssistenteCompras:
    def __init__(self):
        pygame.mixer.init()
        self.recognizer = sr.Recognizer()
        self.audio_lock = asyncio.Lock()
        self.arquivos_temp = set()

        self.produtos = {
            "arroz": {"corredor": "A", "posicao": (2, 3), "sugestoes": ["feijão", "óleo"]},
            "leite": {"corredor": "B", "posicao": (5, 1), "sugestoes": ["achocolatado", "café"]},
            "pão": {"corredor": "C", "posicao": (1, 4), "sugestoes": ["queijo", "manteiga"]}
        }
        self.posicao_atual = (0, 0)

    async def sintetizar_voz(self, texto: str):
        async with self.audio_lock:
            try:
                audio_file = f"temp_audio_{uuid.uuid4().hex}.mp3"
                self.arquivos_temp.add(audio_file)

                communicate = edge_tts.Communicate(texto, "pt-BR-FranciscaNeural")
                await communicate.save(audio_file)

                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()

                start_time = time.time()
                while pygame.mixer.music.get_busy() and (time.time() - start_time) < 10:
                    await asyncio.sleep(0.1)

                pygame.mixer.music.unload()  # Libera o arquivo antes de excluir

                await self._remover_arquivo_seguro(audio_file, delay=1.0)

            except Exception as e:
                print(f"[ERRO] Falha na síntese: {e}")
                print(f"[ASSISTENTE]: {texto}")

    async def _remover_arquivo_seguro(self, arquivo: str, delay: float = 0.0, tentativas: int = 3):
        await asyncio.sleep(delay)
        for tentativa in range(tentativas):
            try:
                if os.path.exists(arquivo):
                    os.remove(arquivo)
                    self.arquivos_temp.discard(arquivo)
                    break
            except PermissionError:
                if tentativa == tentativas - 1:
                    print(f"[AVISO] Arquivo {arquivo} não removido")
                await asyncio.sleep(1)

    def ouvir_comando(self) -> str:
        with sr.Microphone() as source:
            print("\n🎤 Ouvindo... (diga 'arroz', 'leite', 'pão' ou 'sair')")
            try:
                print("🔧 Ajustando para ruído ambiente...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1.5)
                print("🎤 Pode falar agora...")

                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=5)

                comando = self.recognizer.recognize_google(audio, language='pt-BR').lower()
                return comando

            except sr.WaitTimeoutError:
                print("[INFO] Tempo de espera excedido. Nenhum som detectado.")
                return ""

            except sr.UnknownValueError:
                print("[INFO] Não foi possível entender o que foi dito.")
                return ""

            except sr.RequestError as e:
                print(f"[ERRO] Problema com o serviço de reconhecimento: {e}")
                return ""

            except Exception as e:
                print(f"[ERRO] Erro inesperado ao ouvir: {e}")
                return ""

    async def guiar_ate_produto(self, destino: Tuple[int, int]):
        x, y = self.posicao_atual
        dest_x, dest_y = destino

        while (x, y) != (dest_x, dest_y):
            if x < dest_x:
                x += 1
                await self.sintetizar_voz(f"Siga para o corredor {chr(65 + x)}")
            elif x > dest_x:
                x -= 1
                await self.sintetizar_voz(f"Volte para o corredor {chr(65 + x)}")

            if y < dest_y:
                y += 1
                await self.sintetizar_voz("Continue em frente")
            elif y > dest_y:
                y -= 1
                await self.sintetizar_voz("Vire à esquerda")

            self.posicao_atual = (x, y)
            await asyncio.sleep(1)

    async def executar(self):
        await self.sintetizar_voz("Assistente de compras ativado. Como posso ajudar?")

        while True:
            comando = self.ouvir_comando()

            if not comando:
                await self.sintetizar_voz("Não entendi, poderia repetir?")
                continue

            print(f"Você disse: {comando}")

            if comando == "sair":
                await self.sintetizar_voz("Até logo! Volte sempre.")
                break

            if comando in self.produtos:
                produto = self.produtos[comando]
                await self.sintetizar_voz(f"{comando} está no corredor {produto['corredor']}. Guiando você...")
                await self.guiar_ate_produto(produto["posicao"])
                await self.sintetizar_voz(f"Você chegou ao {comando}. Deseja algo mais?")
            else:
                await self.sintetizar_voz(f"Produto não encontrado. Diga: {', '.join(self.produtos.keys())}")

    async def limpar_arquivos_temp(self):
        for arquivo in list(self.arquivos_temp):
            await self._remover_arquivo_seguro(arquivo, delay=0.0, tentativas=5)

async def main():
    assistente = AssistenteCompras()
    try:
        await assistente.executar()
    except KeyboardInterrupt:
        print("\nPrograma interrompido")
    finally:
        await assistente.limpar_arquivos_temp()

if __name__ == "__main__":
    asyncio.run(main())
