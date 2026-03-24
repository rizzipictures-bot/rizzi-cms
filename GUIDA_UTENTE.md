# Guida Utente: Gestione Portfolio Alessandro Rizzi

Questa guida spiega come utilizzare il nuovo CMS (Content Management System) per gestire i progetti, le fotografie e le sezioni del portfolio di Alessandro Rizzi.

## 1. Avvio del Sistema

Il sistema è composto da due parti: il **CMS** (dove si inseriscono i dati) e il **Prototipo** (il sito web visibile al pubblico).

### Avviare il CMS
1. Aprire il terminale e navigare nella cartella del CMS: `cd /home/ubuntu/rizzi-cms`
2. Eseguire lo script di avvio: `./start.sh` (su Mac/Linux) oppure `start.bat` (su Windows)
3. Il CMS sarà accessibile all'indirizzo: **http://localhost:5151**

### Avviare il Prototipo (Sito Web)
1. Aprire un nuovo terminale e navigare nella cartella del prototipo: `cd /home/ubuntu/rizzi-prototype`
2. Avviare un server web locale: `python3 -m http.server 8080`
3. Il sito sarà accessibile all'indirizzo: **http://localhost:8080**

---

## 2. Gestione delle Sezioni (Categorie)

Il nuovo sistema utilizza un approccio dinamico: le voci del menu principale (es. Cities, Archive, Interview) non sono più fisse, ma possono essere create, modificate e riordinate direttamente dal CMS.

### Creare una nuova Sezione
1. Nel CMS, cliccare sul pulsante **"+ Nuova sezione"** (in alto a destra o nel pannello centrale se non ci sono progetti selezionati).
2. Inserire il nome della sezione (es. "Portraits" o "Exhibitions").
3. La nuova sezione apparirà immediatamente nel menu laterale come filtro e nel menu a tendina dei progetti.

### Modificare o Eliminare una Sezione
1. Deselezionare qualsiasi progetto (cliccando su uno spazio vuoto o ricaricando la pagina).
2. Nel pannello centrale apparirà la **Gestione Sezioni**.
3. Per ogni sezione è possibile:
   - **Rinominare**: Cambia il nome visualizzato nel menu del sito.
   - **Riordinare (↑ / ↓)**: Cambia l'ordine in cui le sezioni appaiono nel menu del sito.
   - **Eliminare**: Rimuove la sezione. *Nota: i progetti assegnati a questa sezione non verranno eliminati, ma rimarranno "senza sezione".*

---

## 3. Gestione dei Progetti

Un "Progetto" è una raccolta di fotografie (o un'intervista) che appartiene a una specifica Sezione.

### Creare un nuovo Progetto
1. Cliccare su **"+ Progetto"** in alto a destra.
2. Inserire il Titolo, l'Anno e scegliere la Sezione di appartenenza.
3. Il progetto verrà creato e selezionato automaticamente per la modifica.

### Compilare le Informazioni (Tab "Info")
Nel pannello di modifica, la scheda "Info" permette di inserire i metadati del progetto:
- **Titolo e Sottotitolo**: Vengono mostrati nell'intestazione della galleria.
- **Anno, Luogo, Pubblicazione**: Appaiono come metadati sopra la linea di separazione.
- **Sezione (Categoria)**: Determina in quale voce del menu apparirà il progetto.
- **Descrizione breve**: Testo introduttivo (opzionale).
*Ricordarsi di cliccare su **"Salva"** dopo aver modificato questi campi.*

### Caricare le Fotografie (Tab "Foto")
1. Selezionare la scheda **"Foto"**.
2. Trascinare le immagini nel riquadro tratteggiato, oppure cliccare sul riquadro per selezionarle dal computer.
3. Formati supportati: JPG, PNG, WEBP, TIFF.
4. Il sistema genererà automaticamente le miniature (thumbnails) ottimizzate per la griglia inferiore della galleria.
5. Per eliminare una foto, passare il mouse sopra di essa e cliccare sulla "×".

### Inserire Testi e Interviste (Tab "Testi")
Questa sezione è particolarmente utile per i progetti assegnati alla sezione "Interview" o per progetti testuali.
1. Cliccare su uno dei pulsanti per aggiungere un blocco di testo:
   - **+ Testo**: Paragrafo normale.
   - **+ Pull quote**: Citazione in evidenza (testo più grande, corsivo, con barra laterale).
   - **+ Domanda / + Risposta**: Formattazione specifica per le interviste.
2. Scrivere il contenuto nel riquadro testuale. Il salvataggio avviene automaticamente quando si clicca fuori dal riquadro.

---

## 4. Come creare layout personalizzati (Domanda Frequente)

Attualmente, il prototipo decide quale layout visivo utilizzare in base al **nome della sezione**:

- Se la sezione si chiama **"Cities"** o **"Gallery"**: Il sito utilizzerà il layout a galleria (foto grande a tutto schermo con miniature in basso e scorrimento fluido).
- Se la sezione si chiama **"Interview"**: Il sito utilizzerà il layout testuale ad espansione.
- Per **tutti gli altri nomi** (es. "Archive", "Portraits", "Exhibitions"): Il sito utilizzerà il layout ad elenco espandibile standard.

### Procedura per aggiungere un nuovo comportamento visivo
Se in futuro si desidera che una nuova sezione (es. "Journal") abbia un layout visivo completamente diverso da quelli esistenti, sarà necessario l'intervento di uno sviluppatore sul codice del prototipo:

1. **Nel file `index.html` (Prototipo)**:
   - Aggiungere un nuovo contenitore HTML per la vista (es. `<div id="view-journal" class="view">...</div>`).
   - Nella funzione `buildDynamicMenu()`, aggiungere una regola per instradare i click verso la nuova vista:
     ```javascript
     if (catLower === 'journal') targetView = 'journal';
     ```
   - Creare una funzione JavaScript dedicata per renderizzare i dati (es. `buildJournal()`) simile a `buildArchive()` o `buildInterview()`.

2. **Nel file `styles.css`**:
   - Aggiungere le regole CSS specifiche per il nuovo layout `#view-journal`.

Il CMS, invece, **non richiederà alcuna modifica**: è già in grado di fornire tutti i dati (testi, immagini, metadati) necessari per qualsiasi tipo di layout.
