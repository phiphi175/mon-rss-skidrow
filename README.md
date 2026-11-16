# Mon Fil — Site + RSS indépendant

Un petit site web en français qui affiche les **titres, dates disponibles et liens des publications publiques** de SkidrowReloaded, et produit une URL `feed.xml` pour ton lecteur RSS.

**Aucune image, jeu, archive, torrent, lien de téléchargement ou texte intégral n’est copié.** Le site et le flux RSS peuvent toutefois **afficher des miniatures via leurs URLs d’origine**, sans héberger ces images. Le projet n'est pas affilié au site d'origine.

## Installation facile (GitHub, sans hébergement à payer)

### 1. Créer ton compte et ton dépôt GitHub

1. Ouvre [github.com](https://github.com) et connecte-toi ou crée un compte.
2. Clique sur **+** en haut à droite, puis **New repository**.
3. Dans **Repository name**, indique `mon-rss-skidrow` (ou un autre nom de ton choix).
4. Choisis **Public** (nécessaire pour GitHub Pages gratuit sur un compte gratuit).
5. Clique sur **Create repository**.

### 2. Envoyer le ZIP décompressé

1. Décompresse `mon-rss-skidrow-COMPLET-images-5min.zip` sur ton PC.
2. Dans le dépôt GitHub que tu viens de créer, clique sur **uploading an existing file** (ou **Add file → Upload files**).
3. Glisse **tous les fichiers ET dossiers à l'intérieur du dossier décompressé**, en conservant l'arborescence (`.github`, `docs`, `examples`, `tests`, `generer.py`...).
4. Clique sur **Commit changes**.

**Attention :** le fichier `.github/workflows/actualisation.yml` est indispensable pour la mise à jour automatique. Si GitHub refuse le glisser-déposer de dossiers, utilise GitHub Desktop pour ajouter tout le dossier du projet, puis publie-le.

### 3. Activer ton site

1. Dans ton dépôt, ouvre **Settings → Pages**.
2. Sous **Build and deployment → Source**, choisis **GitHub Actions**.
3. Le site pourra ensuite être publié par le workflow automatique.

### 4. Lancer la première mise à jour

1. Dans ton dépôt, clique sur **Actions**.
2. Choisis **Actualisation du RSS et du site** à gauche.
3. Clique **Run workflow** → sélectionne `main` → **Run workflow**.
4. Vérifie que le workflow se termine en vert. Sur **Settings → Pages**, l'adresse publique sera indiquée, normalement :

   - **Site** : `https://TON-PSEUDO.github.io/mon-rss-skidrow/`
   - **Flux RSS** : `https://TON-PSEUDO.github.io/mon-rss-skidrow/feed.xml`

Remplace `TON-PSEUDO` par ton identifiant GitHub et, si tu as renommé le dépôt, adapte aussi le nom de dossier dans l'URL.

### 5. Ajouter le RSS dans ton lecteur

Ouvre le site, clique **Copier l'adresse du RSS**, puis colle-la dans Feedly, Inoreader, FreshRSS ou ton lecteur préféré. Le flux est au format RSS 2.0.

## Mise à jour du dépôt existant (sans perdre les publications)

Si ton site fonctionne déjà sur `phiphi175/mon-rss-skidrow`, **conserve tes fichiers existants `docs/items.json` et `docs/feed.xml`**. Ils ne sont volontairement pas fournis dans le ZIP complet. Fais-en une copie de sauvegarde avant l'installation.

Décompresse le ZIP, puis envoie **tout son contenu** à la racine de ton dépôt GitHub via **Code → Add file → Upload files**, en conservant l’arborescence des dossiers. Confirme avec **Commit changes**, puis lance une fois **Actions → Actualisation du RSS et du site → Run workflow**. Ton adresse de site et ton adresse RSS restent identiques.

## Miniatures et compatibilité

Le programme cherche des URLs d’images sur le flux RSS, la page d'accueil et (si l’accès est permis) les pages des articles. Les miniatures peuvent apparaître dans le site et dans les lecteurs RSS qui interprètent `media:thumbnail` ou le HTML des descriptions. Elles sont chargées chez l’hébergeur d’origine, **pas téléchargées ni recopiées**. Certaines peuvent ne pas apparaître si leur hébergeur bloque l’affichage externe. Au maximum quatre pages d’articles sont consultées pour les images par passage, et une image manquante n’est retentée qu’après 24 heures.

## Actualisation automatique

Le robot GitHub tente de vérifier les nouvelles publications **environ toutes les 5 minutes**, grâce à `.github/workflows/actualisation.yml` (planification `*/5 * * * *`). Les exécutions peuvent être retardées ou interrompues par GitHub ; elles ne sont pas garanties à l'heure précise. GitHub peut également désactiver les workflows planifiés d'un dépôt public resté inactif pendant 60 jours (à réactiver alors dans l'onglet Actions).

Le programme essaie successivement un flux FeedBurner associé au site, son RSS WordPress, un autre point d'entrée RSS, puis **sa page d'accueil HTML si robots.txt l'autorise**. Les nouvelles entrées sont enregistrées dans `docs/items.json`, les anciennes restent disponibles, et le flux RSS est écrit dans `docs/feed.xml`. **Ces deux fichiers de données sont générés automatiquement : ils ne sont pas dans le ZIP pour ne pas écraser l’historique si tu mets à jour un dépôt existant.**

**Limitation importante :** le site d'origine utilise parfois des protections anti-robots (HTTP 403). Ce logiciel **ne contourne pas** les refus d'accès, ne résout aucun CAPTCHA et ne garantit pas que les publications puissent être récupérées depuis les serveurs de GitHub. Si toutes les sources sont bloquées, le site indique « Source inaccessible » et conserve les anciennes entrées. La première exécution peut donc afficher 0 publication. L'absence d'erreur dans le workflow ne garantit pas que la récupération ait réussi : regarde l'état sur ton site ou les étapes dans **Actions**.

## Vérifier que cela fonctionne avec des données fictives

Sur un PC avec Python :

```bash
pip install -r requirements.txt
python generer.py --demo
python -m http.server 8000 --directory docs
```

Puis visite `http://localhost:8000`. Ce mode crée 2 titres **fictifs** et n'interroge pas le site d'origine ; il sert uniquement à vérifier le design et le RSS. **Ne publie pas les résultats de démonstration comme s'il s'agissait de vraies publications.**

Pour une vraie mise à jour depuis ton PC, exécute `python generer.py` sans `--demo`. Les requêtes peuvent être refusées selon le réseau.

Pour les tests automatiques : `python -m unittest discover -s tests -v`.

## Dépannage

- **Page GitHub 404 :** assure-toi d'avoir choisi **GitHub Actions** dans Settings → Pages et d'avoir lancé le workflow dans Actions. Vérifie que le nom du dépôt dans l'URL est correct.
- **Workflow rouge :** ouvre **Actions → exécution → update-and-publish** pour lire l'étape en erreur. Selon tes paramètres, l'autorisation de créer des pages GitHub Pages ou d'écrire dans le dépôt peut manquer.
- **Le site s'affiche, mais aucun article :** le site source bloque peut-être les requêtes, ou sa structure HTML a changé. Le message d'état et les journaux du workflow précisent le problème.
- **Échec d'écriture dans le dépôt :** consulte Settings → Actions → General → Workflow permissions. Le workflow demande `contents: write`, sous réserve des politiques applicables au dépôt.
- **Tu as renommé le dépôt :** les URLs RSS sont calculées automatiquement grâce à `GITHUB_REPOSITORY` au prochain lancement.
- **Domaine personnalisé :** ajoute le domaine dans Settings → Pages et définis la variable d'environnement `SITE_URL` dans le workflow avec l'URL complète si tu veux des URLs de flux basées sur ce domaine.

## Technologie

Python 3.12+, requests, BeautifulSoup, RSS 2.0, HTML/CSS/JavaScript et GitHub Actions + GitHub Pages. Le code et les exemples sont libres à modifier pour un usage personnel ; respecte les droits et les règles d'accès du site source.
