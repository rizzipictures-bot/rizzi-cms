# Guida al Deploy e all'Uso del CMS Rizzi

Questa guida fornisce tutte le informazioni necessarie per pubblicare il sito su internet, caricare i progetti reali e comprendere il funzionamento dettagliato delle logiche di visualizzazione e gestione delle immagini.

## 1. Risposte alle domande operative

Prima di procedere con il deploy, ecco le risposte dettagliate a tutte le tue domande sul funzionamento attuale del sistema.

### Caricamento foto in alta risoluzione
Sì, puoi caricare foto in alta risoluzione. Il CMS è programmato per ottimizzarle automaticamente durante l'upload. Nello specifico, il sistema legge l'immagine originale e, se il lato più lungo supera i 2500 pixel, la ridimensiona mantenendo le proporzioni. Successivamente, salva l'immagine in formato JPEG ottimizzato con una qualità dell'88%, garantendo un perfetto equilibrio tra qualità visiva e velocità di caricamento web. Inoltre, il sistema genera automaticamente una miniatura (thumbnail) di 400 pixel per le visualizzazioni a griglia.

### Drag & Drop e ordinamento delle foto
Attualmente il CMS supporta il drag & drop per **caricare** le foto (puoi trascinare un gruppo di foto dal tuo computer direttamente nel riquadro di upload), ma **non supporta ancora** il drag & drop per riordinare la sequenza delle foto già caricate all'interno di un progetto. Le foto vengono mostrate nell'ordine in cui sono state caricate. Se desideri questa funzionalità, possiamo implementarla facilmente aggiungendo una libreria di ordinamento (come SortableJS) nel pannello di amministrazione.

### Funzionamento della sezione Overview
La sezione Overview è progettata per offrire una visione d'insieme dinamica e curata del tuo lavoro. Ecco come funziona:
- **Da dove prende le foto**: Raccoglie tutte le immagini di tutti i progetti caricati nel CMS.
- **Quante foto visualizza**: Mostra tutte le immagini disponibili, ma inserisce in modo intelligente degli spazi vuoti (blank) per creare un layout arioso e non opprimente.
- **Logica di visualizzazione**: Non è puramente casuale. Il sistema segue una regola compositiva: inserisce al massimo uno spazio vuoto per riga e non più di 3 spazi vuoti ogni 36 foto. La posizione dello spazio vuoto all'interno della riga è casuale, creando un effetto "muratura" dinamico ma controllato.
- **Controllo utente**: Attualmente la composizione è generata automaticamente dal codice per garantire sempre un buon risultato estetico senza richiedere intervento manuale. Se desideri un controllo manuale su quali foto appaiono in Overview, dovremmo aggiungere un interruttore "Mostra in Overview" per ogni singola foto nel CMS.

### Gestione delle Keywords (IPTC e AI)
Hai compreso perfettamente. Il flusso è stato progettato esattamente come hai richiesto:
- **Keywords IPTC**: Vengono lette ed estratte automaticamente e obbligatoriamente nel momento in cui carichi la foto.
- **Keywords AI**: Non vengono mai generate in automatico. Sei tu ad avere il controllo totale. Puoi decidere di generarle cliccando il bottone "Tag AI" per una singola foto, per un intero progetto, o globalmente per tutto l'archivio.
- **Integrazione**: Le keywords AI e quelle manuali si sommano a quelle IPTC, senza mai sovrascriverle o cancellarle.

---

## 2. Passi per il Deploy su Internet

Per trasformare questo prototipo locale in un sito vero e proprio accessibile a tutti, dobbiamo separare il progetto in due componenti e pubblicarli su piattaforme adeguate.

### Architettura consigliata
Il sistema attuale è un'applicazione monolitica Flask (Python) che fa sia da backend (API e salvataggio dati) sia da frontend (serve le pagine HTML). Per un sito di fotografia professionale, l'architettura migliore è:

1. **Frontend (Il sito pubblico)**: Ospitato su **Vercel** o **Netlify**. Queste piattaforme offrono una CDN globale (Content Delivery Network) che garantisce il caricamento istantaneo delle immagini in tutto il mondo.
2. **Backend & CMS (L'area amministrativa)**: Ospitato su **Render** o **Railway** (piattaforme per app Python), collegato a un servizio di storage cloud come **Amazon S3** o **Cloudinary** per salvare le immagini in modo permanente e sicuro.

### Passo 1: Configurazione dello Storage Cloud
Attualmente le immagini vengono salvate nella cartella locale `uploads/`. Su un server cloud, il disco viene azzerato ad ogni riavvio. È quindi fondamentale attivare un servizio come Amazon S3 (o un'alternativa più semplice come Cloudinary o Supabase Storage) dove il CMS invierà le foto caricate.

### Passo 2: Pubblicazione del Backend (Render)
1. Creeremo un account su Render.com.
2. Collegheremo il repository GitHub del progetto.
3. Renderizzeremo l'applicazione Flask, configurando le variabili d'ambiente per connettersi allo storage cloud scelto al Passo 1.

### Passo 3: Pubblicazione del Frontend (Vercel)
1. Creeremo un account su Vercel.com.
2. Collegheremo la cartella `static/site` del repository GitHub.
3. Configureremo il frontend affinché punti all'URL pubblico del backend (creato al Passo 2) invece che a `localhost`.

---

## 3. Workflow consigliato per il caricamento dei progetti

Per mantenere il CMS ordinato e sfruttare al massimo le potenzialità del sito, ti consiglio di seguire questo flusso di lavoro per ogni nuovo progetto:

1. **Preparazione dei file**: Assicurati che le foto abbiano i metadati IPTC corretti (titolo, descrizione, keywords) inseriti tramite Lightroom o Photoshop prima dell'upload.
2. **Creazione del Progetto**: Nel CMS, clicca su "+ Progetto". Compila accuratamente tutti i campi del tab "Info" (Titolo, Luogo, Anno, Tecnica, Supporto, Stampe, Edizioni). Assegna la categoria corretta.
3. **Upload delle Immagini**: Passa al tab "Foto" e trascina le immagini. Il sistema estrarrà automaticamente le keywords IPTC.
4. **Integrazione AI (Opzionale)**: Se ritieni che le keywords IPTC non siano sufficienti per la ricerca, clicca su "Tag AI (questo progetto)" per arricchire i metadati.
5. **Verifica**: Controlla i badge colorati sulle foto (Verde = IPTC, Blu = AI, Viola = Entrambi) per assicurarti che l'indicizzazione sia completa.
6. **Salvataggio**: Clicca su "Salva" per confermare tutte le modifiche.

Se sei d'accordo con questa architettura e con le risposte fornite, possiamo procedere con l'implementazione del drag & drop per l'ordinamento delle foto (se lo desideri) e iniziare la configurazione dei servizi cloud per il deploy.
