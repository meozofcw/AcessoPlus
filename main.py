import tkinter as tk
import asyncio
import edge_tts
import speech_recognition as sr
import pygame
import os
import uuid
import time
import collections # Importar collections para usar deque para o BFS
from typing import Tuple, Dict

class SupermercadoComAssistente:
    """
    Classe principal que gerencia o mapa do supermercado e o assistente de voz.
    Combina a visualização do mapa com a funcionalidade de reconhecimento de voz e síntese.
    """
    def __init__(self):
        """
        Inicializa a janela do Tkinter, o canvas, as configurações do mapa,
        e os componentes do assistente de voz (pygame, speech_recognition, edge_tts).
        """
        # Configurações da janela Tkinter
        self.janela = tk.Tk()
        self.janela.title("Mapa do Supermercado com Assistente")
        self.canvas = tk.Canvas(self.janela, width=720, height=600, bg="white")
        self.canvas.pack()

        # Configurações do mapa
        self.tamanho_celula = 40
        self.largura = 18  # Células de largura
        self.altura = 15   # Células de altura

        self.prateleiras = set()  # Armazena as coordenadas das prateleiras (agora obstáculos)
        self.produtos: Dict[str, Tuple[int, int]] = {
            # Produtos e suas coordenadas no mapa
            "arroz": (2, 2),
            "feijao": (2, 3),
            "oleo": (5, 2),
            "leite": (2, 10),
            "achocolatado": (2, 11),
            "cafe": (5, 10),
            "pao": (11, 12),
            "queijo": (11, 13),
            "manteiga": (14, 12),
        }

        self.posicao_atual = (0, 0)  # Posição inicial do usuário no mapa

        # Configurações do assistente de voz
        pygame.mixer.init()  # Inicializa o mixer do pygame para reprodução de áudio
        self.recognizer = sr.Recognizer()  # Inicializa o reconhecedor de fala
        self.audio_lock = asyncio.Lock()  # Bloqueio para evitar sobreposição de áudio
        self.arquivos_temp = set()  # Conjunto para rastrear arquivos de áudio temporários

        # Botão para iniciar o assistente de voz
        self.btn_iniciar_assistente = tk.Button(
            self.janela,
            text="Iniciar Assistente de Voz",
            command=self._start_assistant_task # Chama um método auxiliar para iniciar a tarefa assíncrona
        )
        self.btn_iniciar_assistente.pack(pady=10)

        # Inicializa o loop de eventos do asyncio explicitamente
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop) # Define este loop como o loop atual para este thread

        self.janela.protocol("WM_DELETE_WINDOW", self.on_closing) # Garante o fechamento correto da janela

    def _start_assistant_task(self):
        """
        Método auxiliar para iniciar a tarefa do assistente no loop asyncio.
        Isso permite que a tarefa assíncrona seja agendada sem bloquear o Tkinter.
        """
        self.loop.create_task(self.executar_assistente())

    def on_closing(self):
        """
        Lida com o evento de fechamento da janela, garantindo que os recursos
        do Pygame sejam liberados e arquivos temporários sejam removidos.
        Também garante que o loop asyncio seja parado e fechado corretamente.
        """
        pygame.mixer.quit()
        for arquivo in list(self.arquivos_temp):
            if os.path.exists(arquivo):
                os.remove(arquivo)
        self.janela.destroy()
        # Para o loop asyncio suavemente
        if self.loop.is_running():
            self.loop.stop()
        # Cancela todas as tarefas pendentes antes de fechar o loop
        for task in asyncio.all_tasks(self.loop):
            task.cancel()
        self.loop.close()


    def adicionar_prateleiras(self):
        """
        Define as posições das prateleiras no mapa.
        Cria corredores verticais com "prateleiras abertas" (com espaços entre eles).
        Essas prateleiras são consideradas obstáculos intransponíveis.
        """
        for x in range(2, self.largura - 2, 3):  # Colunas das prateleiras
            for y in range(1, self.altura - 1):  # Linhas das prateleiras
                self.prateleiras.add((x, y))

    def desenhar_mapa(self):
        """
        Desenha o mapa no canvas do Tkinter, incluindo a posição atual do usuário,
        as prateleiras e os produtos.
        """
        self.canvas.delete("all")  # Limpa o canvas antes de redesenhar

        for y in range(self.altura):
            for x in range(self.largura):
                cor = "white"  # Cor padrão para células vazias
                if (x, y) == self.posicao_atual:
                    cor = "blue"  # Cor para a posição atual do usuário
                elif (x, y) in self.prateleiras:
                    cor = "grey"  # Cor para as prateleiras (obstáculos)
                elif (x, y) in self.produtos.values():
                    cor = "orange"  # Cor para os produtos
                
                # Se a posição atual for um produto, mas também uma prateleira, o produto tem prioridade visual
                if (x, y) == self.posicao_atual:
                    cor = "blue"
                elif (x, y) in self.produtos.values():
                    cor = "orange"
                elif (x, y) in self.prateleiras:
                    cor = "grey"

                self.canvas.create_rectangle(
                    x * self.tamanho_celula,
                    y * self.tamanho_celula,
                    (x + 1) * self.tamanho_celula,
                    (y + 1) * self.tamanho_celula,
                    fill=cor,
                    outline="black"
                )

        # Desenha os nomes dos produtos no mapa
        for nome, (x, y) in self.produtos.items():
            self.canvas.create_text(
                x * self.tamanho_celula + self.tamanho_celula // 2,
                y * self.tamanho_celula + self.tamanho_celula // 2,
                text=nome,
                font=("Arial", 8, "bold"),
                fill="black"
            )

        self.janela.update_idletasks()  # Atualiza a janela imediatamente

    async def sintetizar_voz(self, texto: str):
        """
        Sintetiza o texto fornecido em fala e o reproduz.
        Usa um bloqueio para garantir que apenas um áudio seja reproduzido por vez.
        """
        async with self.audio_lock:
            try:
                print(f"[VOZ] {texto}")
                audio_file = f"temp_{uuid.uuid4().hex}.mp3"  # Gera um nome de arquivo único
                self.arquivos_temp.add(audio_file)
                # Usa edge_tts para converter texto em fala em português (Brasil)
                communicate = edge_tts.Communicate(texto, "pt-BR-FranciscaNeural")
                await communicate.save(audio_file)

                pygame.mixer.music.load(audio_file)  # Carrega o arquivo de áudio
                pygame.mixer.music.play()  # Inicia a reprodução

                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)  # Espera a reprodução terminar

                await self._remover_arquivo_seguro(audio_file)  # Remove o arquivo temporário
            except Exception as e:
                print(f"[ERRO VOZ] Ocorreu um erro ao sintetizar a voz: {e}")

    async def _remover_arquivo_seguro(self, arquivo: str):
        """
        Remove um arquivo de áudio temporário de forma segura após um pequeno atraso.
        """
        await asyncio.sleep(0.5)  # Pequeno atraso para garantir que o arquivo não esteja em uso
        try:
            if os.path.exists(arquivo):
                # Descarrega o áudio antes de remover o arquivo
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                os.remove(arquivo)
                self.arquivos_temp.discard(arquivo) # Remove do conjunto de arquivos temporários
        except Exception as e:
            print(f"[ERRO ARQUIVO] Ocorreu um erro ao remover o arquivo: {e}")

    def ouvir_comando(self) -> str:
        """
        Ouve o comando de voz do usuário usando o microfone e o reconhece.
        Retorna o comando reconhecido em minúsculas.
        """
        with sr.Microphone() as source:
            print("[MIC] Ouvindo...")
            try:
                # Ajusta para o ruído ambiente para melhor reconhecimento
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
                # Ouve o áudio do microfone
                audio = self.recognizer.listen(source, timeout=4, phrase_time_limit=5)
                # Reconhece o áudio usando o Google Speech Recognition em português
                comando = self.recognizer.recognize_google(audio, language="pt-BR").lower()
                print(f"[COMANDO] {comando}")
                return comando
            except sr.WaitTimeoutError:
                print("[ERRO RECONHECIMENTO] Nenhuma fala detectada.")
                return ""
            except sr.UnknownValueError:
                print("[ERRO RECONHECIMENTO] Não foi possível entender o áudio.")
                return ""
            except sr.RequestError as e:
                print(f"[ERRO RECONHECIMENTO] Erro de serviço de reconhecimento de fala; {e}")
                return ""
            except Exception as e:
                print(f"[ERRO RECONHECIMENTO] Ocorreu um erro inesperado: {e}")
                return ""

    async def mover_para(self, destino: Tuple[int, int]):
        """
        Move a posição atual do usuário no mapa em direção ao destino,
        fornecendo instruções de voz a cada passo, evitando prateleiras.
        """
        x_start, y_start = self.posicao_atual
        x_product, y_product = destino # Localização original do produto

        # Determinar o destino real para o BFS
        # Se o produto está em uma prateleira, encontrar uma célula adjacente não-prateleira
        final_destination = (x_product, y_product)
        if (x_product, y_product) in self.prateleiras:
            found_adjacent = False
            # Tentar encontrar uma célula adjacente válida (não-prateleira)
            for dx_adj, dy_adj in [(0, 1), (0, -1), (1, 0), (-1, 0)]: # Vizinhos: baixo, cima, direita, esquerda
                adj_x, adj_y = x_product + dx_adj, y_product + dy_adj
                if (0 <= adj_x < self.largura and
                    0 <= adj_y < self.altura and
                    (adj_x, adj_y) not in self.prateleiras):
                    final_destination = (adj_x, adj_y)
                    found_adjacent = True
                    break
            if not found_adjacent:
                await self.sintetizar_voz("Não foi possível encontrar um local acessível para este produto.")
                return

        # Implementar BFS para encontrar o caminho mais curto até final_destination
        queue = collections.deque([(x_start, y_start, [])])  # (x, y, caminho_percorrido)
        visited = set([(x_start, y_start)])

        path_found = None

        while queue:
            current_x, current_y, path_taken = queue.popleft()

            if (current_x, current_y) == final_destination:
                path_found = path_taken + [(current_x, current_y)]
                break

            # Possíveis movimentos: cima, baixo, esquerda, direita
            moves = [(0, 1), (0, -1), (1, 0), (-1, 0)]

            for dx, dy in moves:
                next_x, next_y = current_x + dx, current_y + dy

                # Verificar se o próximo movimento é válido (dentro dos limites, não é uma prateleira e não visitado)
                if (0 <= next_x < self.largura and
                    0 <= next_y < self.altura and
                    (next_x, next_y) not in self.prateleiras and # Verifica se não é uma prateleira
                    (next_x, next_y) not in visited):

                    visited.add((next_x, next_y))
                    queue.append((next_x, next_y, path_taken + [(current_x, current_y)]))

        if not path_found:
            await self.sintetizar_voz("Não foi possível encontrar um caminho para o produto.")
            return

        # Seguir o caminho encontrado
        for i in range(1, len(path_found)):
            prev_x, prev_y = path_found[i-1]
            current_x, current_y = path_found[i]

            # Determinar a direção para o comando de voz
            if current_x > prev_x:
                direction_text = "Siga para a direita"
            elif current_x < prev_x:
                direction_text = "Siga para a esquerda"
            elif current_y > prev_y:
                direction_text = "Siga em frente"
            elif current_y < prev_y:
                direction_text = "Volte"
            else:
                direction_text = "" # Não deve acontecer se o caminho tiver passos distintos

            if direction_text: # Apenas sintetiza se houver uma direção válida
                await self.sintetizar_voz(direction_text)

            self.posicao_atual = (current_x, current_y)
            self.desenhar_mapa()
            await asyncio.sleep(0.5)

        await self.sintetizar_voz(f"Você chegou ao seu destino.")


    async def executar_assistente(self):
        """
        Loop principal do assistente de voz. Ouve comandos, encontra produtos
        e guia o usuário.
        """
        await self.sintetizar_voz("Assistente ativado. Qual produto você quer encontrar?")

        while True:
            comando = self.ouvir_comando()
            if "sair" in comando:
                await self.sintetizar_voz("Saindo do assistente. Até mais!")
                break

            produto_encontrado = False
            for produto_nome, coords in self.produtos.items():
                if produto_nome in comando:
                    await self.sintetizar_voz(f"{produto_nome} encontrado. Direcionando você agora.")
                    await self.mover_para(coords)
                    await self.sintetizar_voz(f"Você chegou ao {produto_nome}. Deseja outro item?")
                    produto_encontrado = True
                    break

            if not produto_encontrado and comando: # Se houve comando, mas não produto
                await self.sintetizar_voz("Produto não encontrado ou comando inválido. Tente novamente.")

    def iniciar(self):
        """
        Inicia a aplicação, configurando o mapa e iniciando o loop principal do Tkinter.
        """
        self.adicionar_prateleiras()
        self.desenhar_mapa()
        # Agenda a execução das tarefas assíncronas periodicamente para integrar com o Tkinter
        self._process_async_events() # Chamada inicial
        self.janela.mainloop()

    def _process_async_events(self):
        """
        Processa tarefas assíncronas pendentes sem bloquear o mainloop do Tkinter.
        Esta função é chamada periodicamente pelo método after do Tkinter.
        """
        # Executa as tarefas pendentes do loop asyncio até que não haja mais tarefas prontas
        # ou até que o tempo limite seja atingido (0 segundos, para não bloquear).
        self.loop.call_soon(self.loop.stop)
        self.loop.run_forever() # Executa até que `stop()` seja chamado, que ocorre imediatamente após processar as tarefas prontas.
        self.janela.after(10, self._process_async_events) # Agenda a próxima verificação após 10ms


if __name__ == "__main__":
    app = SupermercadoComAssistente()
    app.iniciar()
