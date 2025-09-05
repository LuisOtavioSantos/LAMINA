# LAMINA — Leitor e Anotador de Microimagens e Análises

Visualizador (e futura ferramenta de anotação) para **imagens de lâminas digitais**.
Backend em Flask gera **tiles Deep Zoom on-the-fly** a partir de arquivos **CZI** (Zeiss) via `pylibCZIrw`.
Frontend em React usa **OpenSeadragon** para navegação/zoom em nível de microscopia.

> Camada de anotações virá em breve.

---

## 🌟 Recursos

* 🔎 Zoom e pan suaves com OpenSeadragon.
* 🧩 Geração de tiles sob demanda (`/czirw/tile/{level}/{x}_{y}.jpeg`).
* 🧠 Suporte nativo a **CZI** (pylibCZIrw).
* 🪵 Observabilidade: logs estruturados + **crash dumps** (faulthandler).
* 🛡️ Leituras **thread-safe** (lock) e servidor Flask **single-thread** para evitar crash nativo no Windows.
* 🧪 Endpoints de **debug** para inspecionar ROI/níveis.

---

## 🗂️ Estrutura do projeto

```
SIAT/
├─ server/
│  └─ openslide_api/
│     ├─ app.py
│     ├─ services/
│     │  ├─ pyczi_tiles.py
│     │  └─ openslide_tiles.py
│     ├─ utils/
│     │  └─ obs.py
│     ├─ slides/
│     │  └─ slide_one.czi
│     └─ logs/
│        ├─ server.log
│        └─ crash.log
└─ siat-viewer/
   ├─ src/
   │  ├─ App.jsx
   │  └─ components/CziViewer.jsx
   ├─ public/
   ├─ index.html
   └─ package.json
```

---

## 🧰 Pré-requisitos

### Backend

* Python 3.10+ (recomendado)
* Pip/virtualenv
* Dependências:

  * `flask`, `flask-cors`
  * `pillow`
  * `numpy`
  * `pylibCZIrw` (leitor CZI)
  * (opcional) `openslide-python` + binários do OpenSlide

> **Windows:** o `pylibCZIrw` usa componentes nativos. Mantenha o servidor **single-thread** (já configurado) e evite o **reloader** do Flask.

### Frontend

* Node.js 18+ (Vite)
* npm ou pnpm

---

## 🚀 Como executar

### 1) Backend (Flask)

Abra um terminal em `server/openslide_api`:

```powershell
# Windows PowerShell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -U pip

# instale as libs (ex.: requirements manuais)
pip install flask flask-cors pillow numpy pylibCZIrw

# opcional, se quiser testar OpenSlide:
# pip install openslide-python

# copie/coloque seu .czi em server/openslide_api/slides/
# ou ajuste o caminho em app.py (variável SLIDE_PATH)
python app.py
```

O servidor sobe em `http://127.0.0.1:5000` com:

* **logs** em `server/openslide_api/logs/server.log`
* **crash dumps nativos** em `server/openslide_api/logs/crash.log`

### 2) Frontend (Vite + React)

Abra outro terminal em `siat-viewer`:

```bash
npm install
npm run dev
```

Acesse `http://localhost:5173`.

> O viewer consome a API em `http://127.0.0.1:5000`.
> CORS já permite `localhost:5173` e `127.0.0.1:5173`.

---

## 🔌 Endpoints principais

### CZI (pylibCZIrw)

* `GET /czirw/info` → `{ width, height, tileSize, maxLevel, scene }`
* `GET /czirw/dzi` → XML DeepZoom (compatível com OSD)
* `GET /czirw/tile/<level>/<col>_<row>.jpeg` → tile JPEG
* `GET /czirw/debug/<level>/<col>_<row>` → infos de ROI/escala para inspeção

### OpenSlide (opcional; pode retornar 422 com CZI)

* `GET /osd/dzi`
* `GET /osd/tile/<level>/<col>_<row>.jpeg`

### Health

* `GET /healthz` → `{ status, pid }`

---

## ⚙️ Configuração & ajustes

* **Arquivo de slide:** `server/openslide_api/app.py` → `SLIDE_PATH`
* **Tamanho do tile (CZI):** `PyCziDZ(..., tile_size=512)` em `app.py`
* **Qualidade JPEG:** `pyczi_tiles.py` → `img.save(..., quality=90)`
* **Logs:** `utils/obs.py` (formatação, níveis, arquivos)
* **CORS:** ajuste origens permitidas em `app.py` (CORS)

---

## 🧭 Como funciona (resumo técnico)

1. O frontend pergunta `GET /czirw/info` para obter dimensões/níveis.
2. OpenSeadragon configura um **tile source custom** com `getTileUrl(level, x, y)`.
3. O backend calcula a **ROI** correspondente ao par (nível, coluna, linha), mapeia para **full-res** e lê via `pylibCZIrw.read(...)`.
4. O buffer é convertido **BGR → RGB** e retornado como **JPEG**.
5. Leituras são **serializadas** com `threading.Lock()` para evitar race/crash no driver nativo (especialmente no Windows).
6. Se a ROI sai dos limites, o código **clampa** ao bound da cena e retorna tile “preto” quando necessário — evitando falhas nativas.

---

## 🧑‍🔧 Dicas de debug

* **API “sumiu” / crash sem log:**
  Veja `logs/crash.log`. O faulthandler registra stacktraces de falhas nativas (ex.: “a memória não pôde ser read”).
* **422 em `/osd/dzi`:**
  Normal para CZI em OpenSlide. Use os endpoints `/czirw/*`.
* **CORS bloqueado:**
  Garanta que a origem (porta/host do Vite) está listada no CORS do `app.py`.
* **Tiles vazios/preto nas bordas:**
  Esperado quando o tile sai do bounds — OSD ainda pede grid “incompleto”. O clamping evita segfault.
* **Performance:**
  Ajuste `tile_size` (512 é bom compromisso), `JPEG quality`, e os limites do OSD (`imageLoaderLimit`, etc).

---

## 🗺️ Roadmap (curto prazo)

* [ ] Camada de **anotações** (desenho de ROIs, pontos, polígonos) no OSD
* [ ] Persistência de anotações (JSON/DB)
* [ ] Ferramentas de medição (escala, área, comprimento)
* [ ] Suporte a múltiplas cenas/canais (CZI)
* [ ] Export (screenshots, crops, pirâmides)

---

## 🤝 Contribuindo

* Issues e PRs são bem-vindos.
* Por favor, descreva ambiente (SO, Python/Node), logs relevantes e passos para reproduzir.

---

## 📜 Licença

Defina a licença que preferir para o repositório (ex.: **MIT**).
Enquanto não houver arquivo `LICENSE`, considere o código “todos os direitos reservados”.

---

## 🙏 Agradecimentos

* [OpenSeadragon](https://openseadragon.github.io/)
* `pylibCZIrw` (Zeiss CZI Reader)

---

### Comandos rápidos (tl;dr)

**Backend**

```bash
cd server/openslide_api
python -m venv venv
.\venv\Scripts\Activate.ps1
pip -r requirements.txt
python app.py
```

**Frontend**

```bash
cd siat-viewer
npm i
npm run dev
```

Abra: `http://localhost:5173` ✅
