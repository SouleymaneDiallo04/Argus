# Journal des décisions — Argus

Registre des décisions d'architecture non évidentes (ADR léger). Le plus récent en haut.

## 2026-08-06 — RTSP : ingestion serveur headless, source unique (V1)
**Contexte.** Le cahier des charges demande « 1 RTSP ». Le navigateur ne lit pas le RTSP ;
le serveur doit tirer le flux. Le modèle YOLO + tracker est partagé et non concurrent-safe.
**Décision.** Worker serveur en thread (`cv2.VideoCapture`) qui alimente le pipeline via le
**sink partagé** (`ingest_frame`) → journal/preuves/notifications visibles dans le **dashboard**
(headless, pas de vidéo live). Contrôle REST (`/sources/rtsp`), **un seul flux à la fois**.
**Conséquence.** RTSP et la console live WS ne doivent pas tourner en même temps (tracks
mélangées) ; multi-caméras + vue annotée live = V2. Lectures du `Journal` verrouillées
(worker écrit / API lit sur la même connexion sqlite).

## 2026-08-04 — P3-c : notifier sur chaque infraction confirmée (pas de routage par sévérité serveur)
**Contexte.** La sévérité vit côté front (`localStorage`), jamais côté serveur (décision P3-a).
Router les notifications « par sévérité » exigerait de la réintroduire côté serveur.
**Décision.** On notifie (email + Teams, fan-out webhook-first) sur chaque `ViolationEvent`
confirmé ; le **debounce (3 s) + cooldown (30 s/personne)** du moteur est le filtre anti-flood
(esprit **ISA-18.2**). Envoi non bloquant (`run_in_threadpool`), no-op si non configuré.
**Conséquence.** Aucune duplication du modèle de risque côté serveur. Escalade/astreinte,
acquittement, SMS et passerelle MQTT/OPC-UA→PLC restent en V2.

## 2026-08-01 — P3-b : floutage RGPD par heuristique région-tête (pas de détecteur de visage)
**Contexte.** Le floutage des preuves exige de localiser la tête, mais le modèle n'a pas de
classe tête/visage. Un détecteur de visage (Haar/DNN) échoue précisément sur casque, angle
et occlusion — le cas industriel.
**Décision.** Flouter par **pixelisation** le **haut 30 % du bbox de chaque personne** (bande
`helmet` de `association.py`). Zéro dépendance, robuste, **garantit** le floutage. Snapshot
plein cadre, écrit uniquement après floutage (aucune image nette sur disque).
**Conséquence.** Sur-floutage léger accepté (côté sûr RGPD). Un vrai détecteur tête/visage
reste envisageable en V2 via l'active-learning.

## 2026-07-29 — P3-a : sémantique temps du journal = horloge murale serveur
**Contexte.** Le journal d'infractions et les agrégats de conformité ont besoin d'un axe temps.
Le client envoie un `timestamp` **relatif au flux** (repart de 0 à chaque connexion).
**Décision.** L'axe principal est l'**horloge murale serveur (UTC)** : c'est ce qu'un
déploiement réel (caméras live/RTSP) consigne, et c'est stable entre sessions. Le
`stream_ts` du flux est conservé en colonne pour recouper la timeline vidéo.
**Conséquence.** Sur une vidéo uploadée de démo, toutes les infractions tombent dans
« maintenant » — acceptable : le système consigne *quand il observe*.

## 2026-07-29 — P3-a : la sévérité n'est pas persistée
**Contexte.** La sévérité d'une alerte dépend du **risque de zone**, choisi côté front
et stocké en `localStorage` (P2-a), jamais envoyé au backend.
**Décision.** Le backend reste **factuel** : il persiste zone + EPI manquants. La sévérité
est recalculée à l'affichage (`severityFor`).
**Conséquence.** Séparation front/back nette ; le journal ne dépend pas d'un réglage front.

## 2026-07-15 — V1 : exclusion de `gloves` / `glasses`
Objets minuscules et déformables (pire précision de la littérature) + données publiques
rares : le coût d'un modèle honnête dépasse la valeur démonstrative. Réintroduction en V2
via active-learning ciblé. (cf. `argus-design.md` §3.)
