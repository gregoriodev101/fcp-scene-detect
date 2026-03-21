# SceneDetect for Final Cut Pro

Detecta cenas automaticamente em um vídeo e gera um arquivo `.fcpxml` pronto para importar no **Final Cut Pro X** — sem precisar cortar nenhum arquivo, sem upload para nuvem, tudo local na sua máquina.

---

## O que ele faz

O app analisa frame a frame o seu vídeo, identifica os pontos onde há mudança de cena e gera uma timeline no formato FCPXML com cada cena já posicionada como um clip separado. Ao importar no Final Cut Pro, você terá o vídeo inteiro fatiado na timeline, pronto para editar.

O arquivo de vídeo original **não é modificado**. O FCPXML apenas referencia o arquivo e define os pontos de entrada e saída de cada cena.

---

## Requisitos

- macOS
- [Python 3](https://www.python.org/downloads/)
- [Homebrew](https://brew.sh) — gerenciador de pacotes para macOS

O `install.sh` verifica e instala o restante automaticamente.

---

## Instalação

> Você só precisa fazer isso uma vez.

Abra o Terminal, navegue até a pasta do projeto e rode:

```bash
chmod +x install.sh run.sh
./install.sh
```

O `chmod +x` é necessário para dar permissão de execução aos arquivos `.sh` antes de rodá-los pela primeira vez.

O `install.sh` vai verificar e instalar automaticamente:

| O que | Para que |
|---|---|
| **python-tk** | Interface gráfica (Tkinter) |
| **Homebrew** | Necessário para instalar o FFmpeg |
| **FFmpeg** | Leitura e processamento do vídeo |
| **scenedetect[opencv]** | Detecção de cenas frame a frame |
| **customtkinter** | Interface moderna do app |

Se o Homebrew não estiver instalado, o script vai mostrar o comando de instalação e parar. Instale o Homebrew, depois rode `./install.sh` novamente.

---

## Como usar

### 1. Exportar o template do Final Cut Pro

O app precisa de um arquivo `.fcpxml` exportado do seu projeto no Final Cut Pro para herdar as configurações corretas de frame rate, resolução e timecode.

No Final Cut Pro, com um projeto aberto:
```
File → Export XML…
```

Salve o arquivo na pasta do projeto. Se o arquivo gerado for uma pasta `.fcpxmld`, o arquivo que você precisa selecionar está dentro dela com extensão `.fcpxml`.

> Você só precisa fazer isso uma vez por projeto. O mesmo template pode ser reutilizado para vários vídeos do mesmo projeto.

### 2. Abrir o app

```bash
./run.sh
```

### 3. Selecionar os arquivos

- **Vídeo** — o arquivo `.mov`, `.mp4` ou similar que você quer analisar
- **Template FCPXML** — o arquivo `.fcpxml` exportado do Final Cut Pro

### 4. Ajustar as configurações

**Sensibilidade (Threshold)**
Controla o quão diferente dois frames precisam ser para o app considerar uma mudança de cena.
- Valores baixos (ex: 10–15) → detecta mais cenas, inclusive cortes sutis
- Valores altos (ex: 40–60) → detecta só mudanças bruscas, menos cenas
- Padrão: `27` — funciona bem para a maioria dos vídeos

**Duração mínima (s)**
Ignora cenas mais curtas que esse valor em segundos. Útil para evitar falsos positivos em vídeos com flashes ou movimentos rápidos de câmera.
- Padrão: `1.0s`

**Método**
- `content` — detecta mudanças no conteúdo visual do frame (cor, brilho, movimento). Recomendado para a maioria dos casos.
- `threshold` — detecta mudanças baseadas apenas no brilho médio do frame. Útil para vídeos com transições em fade para preto/branco.

### 5. Gerar o FCPXML

Clique em **🎬 Detectar Cenas e Gerar FCPXML**.

O log vai mostrar o progresso da análise e listar cada cena detectada com seus timecodes. Ao terminar, a pasta com o arquivo gerado abre automaticamente no Finder.

### 6. Importar no Final Cut Pro

```
File → Import → XML…
```

Selecione o arquivo `_scenes.fcpxml` gerado na mesma pasta do vídeo.

---

## Arquivos do projeto

```
scene-detect/
├── SceneDetect.py          ← app principal (interface + lógica)
├── scene_detect_fcpxml.py  ← versão linha de comando (CLI)
├── install.sh              ← instalação automática de dependências
├── run.sh                  ← abre o app
└── README.md               ← este arquivo
```

---

## Versão linha de comando (opcional)

Se preferir usar sem interface gráfica:

```bash
source venv/bin/activate
python scene_detect_fcpxml.py --video meu_video.mov --template Info.fcpxml
```

Opções disponíveis:

```
--video           Caminho para o arquivo de vídeo (obrigatório)
--template        Caminho para o .fcpxml do Final Cut Pro (obrigatório)
--output          Nome do arquivo de saída (padrão: <video>_scenes.fcpxml)
--threshold       Sensibilidade (padrão: 27.0)
--min-scene       Duração mínima de cena em segundos (padrão: 1.0)
--method          content ou threshold (padrão: content)
--project-name    Nome do projeto no Final Cut Pro
--event-name      Nome do evento no Final Cut Pro
```

---

## Compilar App
Você precisa empacotar como um .app com o PyInstaller. Ele transforma o script Python num bundle que o macOS reconhece como aplicativo nativo.

### Instala o PyInstaller
python3 -m venv venv
source venv/bin/activate
python -m pip install "scenedetect[opencv]" customtkinter pyinstaller

### Gera o .app
pyinstaller --onefile --windowed --name "SceneDetect" SceneDetect.py

O --onedir gera uma pasta dist/SceneDetect.app que abre muito mais rápido porque não precisa descompactar a cada vez. O --onefile empacota tudo num único executável mas paga um custo de inicialização alto.

---

## Licença

MIT — livre para usar, modificar e distribuir.
