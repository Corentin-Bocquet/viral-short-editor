# 📱 Viral Short Editor

**Transforme tes vidéos brutes en Shorts viraux 9:16 prêts à publier.**

Application locale complète avec IA : recadrage automatique, sous-titres viral-style, B-rolls intelligents, mixage audio pro.

---

## ✨ Features

### 🎬 **Étape A : Recadrage + Nettoyage**
- Recadrage automatique en format **9:16 vertical** (TikTok/Reels/Shorts)
- Détection et suppression intelligente des **silences** (jump cuts pro)
- Optimisation de la durée et du rythme

### 💬 **Étape B : Sous-titres Viral Style**
- Transcription audio via **Whisper AI** (local)
- Sous-titres **colorés par sentiment** :
  - 🟢 **Vert** : mots positifs (argent, cerveau, feu, up, oui)
  - 🔴 **Rouge** : mots négatifs (non, stop, erreur, perte)
  - 🟡 **Jaune** : mots neutres/importants (attention, secret, temps)
- Effet **karaôké mot par mot** (le mot actif s'agrandit de 10%)
- **Emojis automatiques** insérés tous les 4 lignes (mapping thématique)
- Export SRT séparé pour montage externe

### 🎥 **Étape C : B-rolls IA (optionnel)**
- Analyse sémantique automatique du contenu
- Recherche de clips visuels via **Pexels API** (gratuite)
- Insertion intelligente sur **2 secondes** avec hard cut
- Fallback texte si API indisponible

### 🎵 **Étape D : Mixage Audio Pro**
- **Auto-ducking** intelligent : baisse la musique pendant la voix
- Transitions fluides (300ms) entre niveaux
- Balance parfaite voix/musique
- Support de n'importe quel format audio

---

## 💻 Installation

### Prérequis

1. **Python 3.11+**  
   Télécharge sur [python.org](https://www.python.org/downloads/)

2. **FFmpeg** (obligatoire pour le traitement vidéo)  
   - **macOS** : `brew install ffmpeg`
   - **Ubuntu/Debian** : `sudo apt install ffmpeg`
   - **Windows** : [ffmpeg.org/download.html](https://ffmpeg.org/download.html)

3. **Git** (pour cloner le repo)  
   Télécharge sur [git-scm.com](https://git-scm.com/)

### Installation rapide

```bash
# 1. Clone le repo
git clone https://github.com/Corentin-Bocquet/viral-short-editor.git
cd viral-short-editor

# 2. Rends le script exécutable (macOS/Linux)
chmod +x start.sh

# 3. Lance l'app (1 commande)
./start.sh
```

**C'est tout !** Le script gère tout automatiquement :
- Création de l'environnement virtuel
- Installation des dépendances
- Lancement du backend
- Ouverture automatique dans le navigateur

---

## 🚀 Utilisation

### Interface Web

1. **Upload ta vidéo brute** (n'importe quel format : MP4, MOV, AVI, MKV...)
2. **Ajoute une musique de fond** (optionnel, n'importe quel format audio)
3. **Règle le volume musique** (0-100%, défaut : 10%)
4. **Active les B-rolls IA** si tu as une clé Pexels (voir ci-dessous)
5. **Clique sur "🚀 Générer mon Short"**

Le traitement se fait en **4 étapes** avec une barre de progression en temps réel (Server-Sent Events).

### Récupérer tes fichiers

Une fois terminé :
- **⬇️ Télécharger MP4** : vidéo finale prête à publier
- **📝 Télécharger SRT** : fichier sous-titres pour montage externe

---

## 🔧 Configuration Avancée

### Activer les B-rolls Pexels (gratuit)

1. Crée un compte gratuit sur [pexels.com](https://www.pexels.com/)
2. Génère une **API Key** sur [pexels.com/api](https://www.pexels.com/api/)
3. Crée un fichier `.env` à la racine du projet :

```bash
PEXELS_API_KEY=ta_cle_api_ici
```

4. Les B-rolls seront maintenant actifs ! 🎥

### Modifier la qualité Whisper

Par défaut, le modèle **"base"** est utilisé (bon compromis vitesse/précision).

Pour changer, modifie dans `backend/main.py` ligne 193 :

```python
segments = transcribe_audio(str(cut_path), model_size="medium")  # ou "small", "large"
```

**Modèles disponibles** :
- `tiny` : ultra-rapide, précision moyenne (39M paramètres)
- `base` : **recommandé** (74M)
- `small` : meilleure qualité (244M)
- `medium` : très précis, plus lent (769M)
- `large` : précision maximale, très lent (1550M)

---

## 📚 Architecture du Code

```
viral-short-editor/
├── backend/
│   ├── main.py               # FastAPI backend (endpoints + SSE)
│   ├── processor/
│   │   ├── reframe.py        # Étape A : recadrage 9:16 + silence remover
│   │   ├── subtitles.py      # Étape B : transcription + ASS/SRT generation
│   │   ├── brolls.py         # Étape C : B-rolls IA (Pexels)
│   │   └── audio_mix.py      # Étape D : mixage + auto-ducking
│   ├── utils/
│   │   ├── ffmpeg_helpers.py # Wrappers FFmpeg + gestion temp dirs
│   │   └── nlp_keywords.py   # Analyse sentiment (pos/neg/neutral)
│   └── requirements.txt
├── frontend/
│   └── index.html         # App complète (HTML + CSS + JS inline)
├── start.sh              # Lanceur 1-click
└── README.md
```

### Modules Clés

#### **reframe.py** - Recadrage Intelligent
- `reframe_to_vertical()` : détecte zones d'intérêt, recadre en 1080x1920
- `remove_silences()` : détecte silences > 0.5s, génère jump cuts

#### **subtitles.py** - Sous-titres IA
- `transcribe_audio()` : Whisper avec timestamps word-level
- `generate_ass_subtitles()` : génère fichier ASS avec :
  - Couleurs par sentiment (classify_keywords)
  - Animation karaôké (`\k` tags)
  - Emojis automatiques (mapping thématique)
- `burn_subtitles()` : incruste via FFmpeg ASS filter

#### **brolls.py** - B-rolls Intelligents
- `extract_visual_concepts()` : analyse POS tagging, extrait noms/verbes filmables
- `fetch_broll()` : API Pexels, fallback texte overlay
- `overlay_brolls()` : insertion temporisée avec FFmpeg filter_complex

#### **audio_mix.py** - Mixage Pro
- `mix_with_ducking()` : sidechaincompress FFmpeg
  - Musique à 20% pendant la voix
  - Remonte à 80% dans les silences
  - Transitions 300ms

---

## 🛠️ Dépannage

### "FFmpeg not found"
**Problème** : FFmpeg n'est pas dans le PATH.

**Solution** :
- **macOS** : `brew install ffmpeg`
- **Ubuntu/Debian** : `sudo apt install ffmpeg`
- **Windows** : Télécharge le build statique [ici](https://www.gyan.dev/ffmpeg/builds/), décompresse et ajoute au PATH

### "Whisper not installed"
**Problème** : Module Whisper absent.

**Solution** :
```bash
pip install openai-whisper
```

**Note** : Sur macOS avec Apple Silicon (M1/M2/M3), installe aussi :
```bash
pip install --upgrade --no-deps --force-reinstall torch torchvision torchaudio
```

### "B-rolls not working"
**Problème** : Pas de clé Pexels ou API limitée.

**Solution** :
1. Vérifie le fichier `.env` avec `PEXELS_API_KEY=...`
2. Pexels gratuit : **200 requêtes/heure**, **20 000/mois**
3. Fallback automatique sur overlay texte si quota dépassé

### "Port 8000 already in use"
**Problème** : Un autre process utilise le port 8000.

**Solution** :
```bash
# Trouver le process
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Tuer le process ou change le port dans start.sh :
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001
```

### Vidéo de sortie trop lourde
**Problème** : Le fichier final est très gros.

**Solution** : Modifie le CRF dans les modules processor (plus haut = plus compressé) :
```python
# Dans reframe.py, subtitles.py, etc.
"-crf", "28",  # au lieu de 23 (défaut)
```

CRF **18** = qualité visuelle parfaite, lourd  
CRF **23** = excellent compromis (défaut)  
CRF **28** = bonne qualité, léger pour upload rapide

---

## 📊 Performance

**Traitement typique** (vidéo 60s, MacBook Pro M1) :
- Étape A (recadrage) : **15s**
- Étape B (sous-titres) : **30s** (modèle `base`)
- Étape C (B-rolls) : **20s** (si activé)
- Étape D (mixage) : **10s**

**Total : ~1-1.5 minutes** pour une vidéo de 1 minute.

**Optimisations** :
- Utilise `tiny` Whisper pour transcription ultra-rapide
- Désactive les B-rolls si pas nécessaire
- Le silence remover peut réduire la durée finale de 20-40%

---

## 📦 API Endpoints

Si tu veux intégrer l'app dans un autre outil :

### `POST /api/process`
Lance un job de traitement.

**Form Data** :
- `video` : fichier vidéo (multipart)
- `music` : fichier audio (optionnel)
- `music_volume` : float 0.0-1.0
- `enable_brolls` : bool

**Response** :
```json
{
  "job_id": "uuid4-string"
}
```

### `GET /api/progress/{job_id}`
Stream SSE de progression en temps réel.

**Events** :
```json
{
  "step": "A|B|C|D|done|error",
  "progress": 0-100,
  "message": "Description...",
  "status": "processing|done|error",
  "error": "..."
}
```

### `GET /api/result/{job_id}`
Télécharge la vidéo finale (MP4).

### `GET /api/subtitles/{job_id}`
Télécharge le fichier SRT.

### `DELETE /api/cleanup/{job_id}`
Nettoie les fichiers temporaires.

---

## 👨‍💻 Contribution

Pull requests bienvenues ! Quelques idées d'amélioration :

- [ ] Support GPU pour Whisper (CUDA/MPS)
- [ ] Prévisualisation vidéo avant export
- [ ] Templates de sous-titres prédéfinis (styles différents)
- [ ] Détection automatique de scènes pour B-rolls plus précis
- [ ] Support de plusieurs langues (Whisper multilingue)
- [ ] Compression automatique pour TikTok/Reels (< 60s)
- [ ] Intégration directe APIs TikTok/Instagram pour upload auto

---

## 📜 Licence

MIT License - Libre d'utilisation pour tout projet (perso ou commercial).

---

## 🔥 Made by Coco

Créé pour les content creators qui veulent produire des Shorts viraux en mode industriel.

Si ce projet t'aide à cartonner sur TikTok/Reels/Shorts, n'hésite pas à ⭐ **star le repo** !

**Questions / Bugs ?** Ouvre une issue sur GitHub.

---

### Stack Technique

- **Backend** : Python 3.11, FastAPI, uvicorn
- **Vidéo** : FFmpeg, moviepy
- **IA** : OpenAI Whisper, spaCy (NLP)
- **Frontend** : HTML5, Vanilla JS, CSS3
- **B-rolls** : Pexels API (gratuite)
- **Communication** : REST API + Server-Sent Events (SSE)

### Credits

- **Whisper** : [OpenAI](https://github.com/openai/whisper)
- **FFmpeg** : [ffmpeg.org](https://ffmpeg.org/)
- **Pexels** : [pexels.com](https://www.pexels.com/)
- **FastAPI** : [fastapi.tiangolo.com](https://fastapi.tiangolo.com/)

---

**Let's make viral content at scale. 🚀**
