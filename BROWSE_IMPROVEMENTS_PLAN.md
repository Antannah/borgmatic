# Implementierungsplan: Borgmatic Browse TUI-Erweiterungen (Upstream-Ready)

## 1. Übersicht & Ziel
Borgmatic 2.x besitzt mit `borgmatic browse` eine moderne Konsolen-Oberfläche (TUI) basierend auf der Python-Bibliothek **Textual**.
Aktuell ist diese rein lesend ("Viewer-Only") und zeigt weder Archivgrößen noch Aktionsmöglichkeiten an.

Dieses Projekt rüstet `borgmatic browse` mit 3 wesentlichen Kernfeatures auf, die für saubere Upstream-PRs strukturiert sind:
1. **Feature 1:** Anzeige von Archivgrößen & Statistiken in `archives_list.py` / `repositories_list.py`. (✅ Erledigt, Tag: `show-archive-size`)
2. **Feature 2:** Interaktive Wiederherstellung (`[r]` Restore) von markierten Dateien/Verzeichnissen in `directory_list.py`. (✅ Erledigt, Tag: `add-restore`)
3. **Feature 3:** Sicheres Löschen (`[d]` Delete) von alten Archiven in `archives_list.py`. (⏳ Offen für nächste Session)

---

## 2. Detaillierte Feature-Spezifikation & Fortschritt

### Feature 1: Repository-Disk-Usage & Statistiken im Carousel anzeigen
* **Status:** ✅ **Abgeschlossen** (Git Tag: `show-archive-size`)
* **Betroffene Dateien:**
  * `borgmatic/actions/browse/archive.py`
  * `borgmatic/actions/browse/repositories_list.py`
  * `borgmatic/actions/browse/workers.py`
* **Umgesetzte Features:**
  * Hintergrund-Worker zur Abfrage des tatsächlichen Speicherplatzes (`borg info`).
  * Animierte Ladeanzeige `(calculating...)` mit periodischem Punkt-Update.
  * Anzeige der formatierten Gesamtgröße direkt in der Repository-Liste (`[145.2 GB]`).
  * Saubere Ausnahmebehandlung für Lock-Konflikte (`subprocess.CalledProcessError`).

### Feature 2: Interaktiver Restore von Dateien & Ordnern (`[r]`, `[Space]`, `[u]`)
* **Status:** ✅ **Abgeschlossen** (Git Tag: `add-restore`)
* **Betroffene Dateien:**
  * `borgmatic/actions/browse/bindings.py`
  * `borgmatic/actions/browse/directory_list.py`
  * `borgmatic/actions/browse/archive.py`
  * `borgmatic/actions/browse/restore_modal.py`
  * `borgmatic/actions/browse/workers.py`
* **Umgesetzte Features:**
  * **Mehrfachauswahl:** Tastaturbinding `[Space]` zum Markieren/Abwählen beliebiger Dateien und Verzeichnisse über Ordnergrenzen hinweg (mit grünem Häkchen `✓`).
  * **Alles abwählen:** `[u]` hebt alle Markierungen mit Benachrichtigung auf (`N item(s) unselected`).
  * **Live-Zähler:** Pane-Titel zeigt in Echtzeit die Anzahl markierter Elemente (`📁 aktuelles (N selected)`).
  * **Restore-Modal:**
    * Kompaktes Layout mit scrollbarer Liste markierter Pfade.
    * Auswahl: `Original path structure (Root /)` vs. `Destination directory`.
    * Bei Auswahl von `Original path structure` wird das Ziel-Eingabefeld sauber ausgeblendet.
    * Bei `Destination directory` wird ein editierbares Feld eingeblendet (Default auf erkanntem Host-Mount wie `/daten/restore`).
    * Tastatur-bedienbare und kontrastreich gestaltete `[Cancel]`- und `[Restore]`-Buttons.
  * **Hintergrund-Restore:** Asynchroner Worker verhindert UI-Blockierung; animierter Fortschritt im Fenstertitel (`(⏳ restoring N item(s)...)`), Erfolgs- bzw. Fehlermeldung per Notification.

### Feature 3: Löschen von Archiven (`[d]`)
* **Status:** ⏳ **Geplant für die nächste Session**
* **Betroffene Dateien:**
  * `borgmatic/actions/browse/archives_list.py`
  * `borgmatic/actions/browse/bindings.py`
  * `borgmatic/actions/browse/archive.py`
  * `borgmatic/actions/browse/workers.py`
* **Geplanter Ablauf:**
  1. Nutzer markiert ein Archiv in der Archivliste und drückt Taste **`d`**.
  2. Sicherheitsabfrage per Modal: *"Archiv '<name>' wirklich unwiderruflich löschen? [Abbrechen / Löschen]"*.
  3. Bei Bestätigung Aufruf von `borgmatic.borg.delete` / `borg delete` im Hintergrund-Worker mit animiertem Ladezustand.
  4. Entfernen des Eintrags aus der UI-Liste und Erfolgsbenachrichtigung.

---

## 3. Testumgebung auf `tiffy`
* **Docker-Kommando für Dev-Container (mit Mounts für `/daten` und `/opt`):**
  ```bash
  docker run --rm -it \
    --env-file /opt/borgmatic/.env \
    -v /daten/backup/borg:/repositories \
    -v /opt/borgmatic/config:/etc/borgmatic.d \
    -v /opt/borgmatic/ssh_keys:/root/.ssh:ro \
    -v /daten:/daten \
    -v /opt:/opt \
    -v /home/norman/projekte/borgmatic:/workspace \
    -w /workspace \
    --entrypoint python3 \
    borgmatic-dev -m borgmatic.commands.borgmatic browse
  ```
* **Automatisierte Tests:**
  ```bash
  docker run --rm -v /home/norman/projekte/borgmatic:/workspace -w /workspace --entrypoint pytest borgmatic-dev --no-cov tests/unit/actions/browse/ tests/integration/actions/browse/
  ```

