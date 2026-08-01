# Journal des décisions — Argus

Registre des décisions d'architecture non évidentes (ADR léger). Le plus récent en haut.

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
