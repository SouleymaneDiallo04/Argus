# P3-c — Notifications (email + Teams) — Design

**Date :** 2026-08-04
**Phase :** P3 (Alertes, RGPD, preuves, rapports) — sous-projet **c**
**Dépend de :** P3-a (journal/persistance, mergé). Indépendant du front.
**Statut :** validé

## 1. Objectif

À chaque **infraction confirmée**, prévenir les équipes par **email** (trace / responsable
HSE) et **Microsoft Teams** (visibilité équipe temps réel), en **webhook-first / fan-out**,
sans jamais bloquer le flux vidéo ni le journal.

Répond au cahier des charges (§ alertes temps réel dashboard + email/Telegram) — canaux
retenus : **email + Teams**.

## 2. Décisions de conception (validées)

- **Déclenchement : sur chaque `ViolationEvent` confirmé.** Le **debounce** (confirm 3 s) +
  **cooldown** (30 s/personne) du moteur EST déjà le filtre anti-flood (esprit **ISA-18.2**).
  Pas de routage « par sévérité » : la sévérité vit **côté front** (décision P3-a, jamais
  côté serveur) — on ne la réintroduit pas.
- **Zéro nouvelle dépendance** : email via `smtplib` (stdlib), Teams via `urllib` (stdlib).
- **Non bloquant** : dispatch via `run_in_threadpool` ; une panne de notif ne tue ni le flux
  ni le journal.
- **Sûr par défaut** : rien de configuré → dispatcher **no-op** (aucun secret requis en
  CI/dev ; jamais de secret en dur).

## 3. Périmètre

**Dans P3-c :**
- Package `app/notify/` : protocole `Notifier`, `NotificationDispatcher`, `EmailNotifier`,
  `TeamsNotifier`, fabrique depuis l'env.
- Câblage au chemin WS (dispatch non bloquant sur `result.events`).

**Hors P3-c (V2, mentionné non codé) :**
- Escalade / astreinte (PagerDuty, Opsgenie), acquittement **ISA-18.2**.
- Passerelle industrielle **MQTT / OPC-UA → PLC** (andon, sirène, interlock).
- SMS (Twilio/Vonage), ticket **ServiceNow**.
- Rapports PDF/CSV → **P3-d**.

## 4. Composants (`app/notify/`)

### `base.py`
```
class Notifier(Protocol):
    def notify(self, event: ViolationEvent) -> None: ...

def format_lines(event, public_url: str | None) -> dict
    # -> {title, subject, text, facts:[(k,v)...], link?} : contenu commun (zone, #id,
    #    EPI manquants, heure, caméra + lien dashboard optionnel). Pur, testable.

class NotificationDispatcher:
    def __init__(self, notifiers: list[Notifier]): ...
    def notify(self, event: ViolationEvent) -> None
        # fan-out ; chaque notifier en try/except (un canal en panne n'arrête pas les autres).
```

### `email.py`
```
class EmailNotifier:
    def __init__(self, host, port, user, password, sender, recipients: list[str],
                 send=_smtp_send)   # `send(msg, host, port, user, password)` injectable
    def notify(self, event) -> None   # construit un EmailMessage (sujet+corps) et l'envoie
```

### `teams.py`
```
class TeamsNotifier:
    def __init__(self, webhook_url: str, public_url=None, poster=_urllib_post)
        # `poster(url, json_bytes)` injectable
    def notify(self, event) -> None   # POST d'une carte (MessageCard/Adaptive) au webhook
```

### `factory.py`
```
def build_dispatcher(env=os.environ) -> NotificationDispatcher
    # ajoute EmailNotifier si ARGUS_SMTP_HOST + ARGUS_SMTP_TO présents,
    # ajoute TeamsNotifier si ARGUS_TEAMS_WEBHOOK présent ; sinon liste vide (no-op).
```

## 5. Configuration (env — jamais en dur)

| Variable | Rôle |
|---|---|
| `ARGUS_SMTP_HOST` / `ARGUS_SMTP_PORT` | serveur SMTP (port défaut 587) |
| `ARGUS_SMTP_USER` / `ARGUS_SMTP_PASSWORD` | auth SMTP (optionnel) |
| `ARGUS_SMTP_FROM` / `ARGUS_SMTP_TO` | expéditeur / destinataires (`,`-séparés) |
| `ARGUS_TEAMS_WEBHOOK` | URL du webhook Teams (connecteur ou Power Automate) |
| `ARGUS_PUBLIC_URL` | base pour le lien dashboard (optionnel) |

## 6. Intégration WS (non bloquante)

`app.state.notifier` = `NotificationDispatcher`, ouvert au `lifespan` (défaut `None`,
**injectable en test** comme `journal`/`snapshots`). Dans le handler `/ws/stream`, après la
persistance :
```
for event in result.events:
    try:
        await run_in_threadpool(app.state.notifier.notify, event)
    except Exception:
        pass  # une panne de notification ne tue pas le flux
```

## 7. Contenu de la notification

Par événement : **zone**, **personne #track_id**, **EPI manquants**, **heure**, **caméra**,
et (si `ARGUS_PUBLIC_URL`) un **lien vers le dashboard**. `format_lines` centralise ce
contenu ; email et Teams le mettent en forme (sujet+corps ; carte JSON).

## 8. Structure de fichiers

```
backend/app/notify/
  __init__.py
  base.py       # Notifier, NotificationDispatcher, format_lines
  email.py      # EmailNotifier (smtplib)
  teams.py      # TeamsNotifier (urllib)
  factory.py    # build_dispatcher(env)
backend/app/api/app.py            # lifespan notifier + dispatch WS
backend/tests/
  test_notify_base.py             # format_lines + dispatcher fan-out/robustesse
  test_notify_email.py            # EmailNotifier (send injecté)
  test_notify_teams.py            # TeamsNotifier (poster injecté)
  test_notify_factory.py          # build_dispatcher selon l'env
  test_notify_ws.py               # dispatch sur infraction confirmée (notifier injecté)
```

## 9. Tests (TDD)

- **`base`** : `format_lines` contient zone/#id/EPI/heure ; `NotificationDispatcher.notify`
  appelle chaque notifier ; **un notifier qui lève n'empêche pas les autres**.
- **`email`** : `send` injecté → capture le `EmailMessage` ; sujet+corps contiennent les
  faits ; destinataires = `recipients`.
- **`teams`** : `poster` injecté → capture URL + payload ; le JSON contient zone/#id/EPI.
- **`factory`** : email seul si SMTP configuré ; Teams seul si webhook ; **vide si rien**
  (no-op) ; les deux si les deux.
- **`ws`** : `app.state.notifier` = dispatcher avec un notifier espion ; un flux produisant
  une infraction confirmée déclenche `notify(event)` exactement une fois.
- Suite backend existante (**90**) reste verte ; aucun secret requis (dispatcher vide).

## 10. Critères d'acceptation

1. Une infraction confirmée déclenche un email (si SMTP configuré) et un POST Teams (si
   webhook configuré), en `run_in_threadpool`, sans bloquer le flux.
2. Un canal en panne n'empêche ni l'autre canal, ni le journal, ni le flux.
3. Sans configuration, aucun envoi et aucune erreur (dispatcher no-op).
4. Aucun secret en dur ; tout par env.
5. Zéro nouvelle dépendance ; suite backend verte (90 + nouveaux).
