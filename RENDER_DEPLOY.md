# 🚀 Deploy Backend na Render.com (24/7)

Render poskytuje free tier web service, ktorý beží 24/7.

## 1. Prepojiť GitHub

1. Otvor: https://dashboard.render.com/
2. Klikni **"New +" → "Web Service"**
3. Vyber **"Build and deploy from a Git repository"**
4. Pripoj GitHub a vyber repo: **`Marek-maker/advert-generator`**

## 2. Nastaviť Web Service

Render automaticky načíta `render.yaml` a predvyplní:

| Pole | Hodnota |
|------|---------|
| Name | `advert-generator-backend` |
| Runtime | `Python 3` |
| Branch | `main` |
| Start Command | `python server.py` |

## 3. Pridať Environment Variables

V sekcii **"Environment"** pridaj:

| Key | Value | Poznámka |
|-----|-------|----------|
| `GOOGLE_API_KEY` | *(tvoj Gemini API kľúč)* | Povinný — bez neho nefunguje AI analýza |

## 4. Deploy

Klikni **"Create Web Service"** → Render automaticky:
- Stiahne kód z GitHubu
- Spustí server na `https://advert-generator-backend.onrender.com`
- Automaticky redeployuje pri každom pushi do `main`

## 5. Prepojiť s Mini App

Po deployi otvor `webapp.html` na Netlify a nastav backend URL:

1. Otvor: https://github.com/Marek-maker/advert-generator/blob/main/webapp.html
2. Klikni **"Edit this file"** (ceruzka)
3. Nájdi riadok:
   ```javascript
   var RENDER_BACKEND = 'https://advertgen4.loca.lt';
   ```
4. Nahraď URL za tvoju Render URL:
   ```javascript
   var RENDER_BACKEND = 'https://advert-generator-backend.onrender.com';
   ```
5. Commitni zmeny → Netlify auto-deployne

---

### 🧪 Otestovať

Po nasadení:
1. Otvor Mini App: https://advertgenerator.netlify.app/webapp.html
2. Odfoť položku (napr. RAM, matičnú dosku)
3. Po analýze by sa mala zobraziť **zelená karta s návrhom na spárovanie**

---

### ⚙️ Udržiavať

- Render free tier uspí service po 15 minútach nečinnosti
- Prvý request po spánku trvá ~30s (spin-up)
- Pre 24/7 bez spánku → upgrade na **Starter** ($7/mesiac) v dashboarde Renderu
