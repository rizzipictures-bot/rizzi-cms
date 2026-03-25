-- ============================================================
-- Rizzi CMS Launcher v4
-- Apri con Script Editor → File → Esporta → Applicazione
-- ============================================================

set CMS_DIR to (POSIX path of (path to home folder)) & "Library/Application Support/RizziCMS/rizzi-cms"
set SITE_URL to "http://localhost:5151/"
set CMS_URL to "http://localhost:5151/cms"
set REPO_URL to "https://github.com/rizzipictures-bot/rizzi-cms.git"

-- Controlla installazione
try
	do shell script "test -d " & quoted form of CMS_DIR
on error
	display alert "Rizzi CMS non installato" message "Esegui prima 'Installa Rizzi CMS.command' dalla cartella dello zip." as critical
	return
end try

-- Trova python3
set pyPath to ""
repeat with p in {"/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"}
	try
		do shell script "test -x " & p
		set pyPath to p
		exit repeat
	end try
end repeat

if pyPath is "" then
	display alert "Python 3 non trovato" message "Installa Python 3 da python.org e riprova." as critical
	return
end if

-- Controlla stato server
on checkServer()
	try
		set result to do shell script "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 http://localhost:5151/ 2>/dev/null"
		if result is not "" and result is not "000" then
			return true
		end if
	end try
	return false
end checkServer

-- Aggiorna da GitHub (git pull)
on updateFromGitHub(cmsDir)
	-- Controlla se git è disponibile
	try
		do shell script "which git"
	on error
		display alert "Git non trovato" message "Installa Xcode Command Line Tools con: xcode-select --install" as warning
		return false
	end try

	-- Controlla se è un repo git
	try
		do shell script "test -d " & quoted form of (cmsDir & "/.git")
	on error
		-- Non è un repo git, inizializza e collega
		try
			do shell script "cd " & quoted form of cmsDir & " && git init && git remote add origin https://github.com/rizzipictures-bot/rizzi-cms.git && git fetch origin && git reset --hard origin/main 2>&1"
		on error errMsg
			display alert "Errore configurazione Git" message errMsg as warning
			return false
		end try
		return true
	end try

	-- Aggiorna solo static/ e app.py, preserva data/db.json
	try
		do shell script "cd " & quoted form of cmsDir & " && git fetch origin main 2>&1"
		set checkoutResult to do shell script "cd " & quoted form of cmsDir & " && git checkout origin/main -- static/ app.py RizziCMS_launcher.applescript 2>&1"
		-- Aggiorna HEAD senza toccare i file locali
		do shell script "cd " & quoted form of cmsDir & " && git update-ref refs/heads/main origin/main 2>&1"
		display alert "Aggiornamento completato!" message "Sito aggiornato con successo." buttons {"OK"} default button "OK"
		return true
	on error errMsg
		display alert "Errore aggiornamento" message errMsg as warning
		return false
	end try
end updateFromGitHub

set serverRunning to checkServer()

-- Loop principale
repeat
	if serverRunning then
		set statoMsg to "● Server ATTIVO — tutto funziona"
		set scelta to button returned of (display dialog "Rizzi CMS

" & statoMsg & "

  Sito:   " & SITE_URL & "
  CMS:    " & CMS_URL with title "Rizzi CMS" buttons {"Altro...", "Apri CMS", "Apri Sito"} default button "Apri Sito" with icon note)

		if scelta is "Apri Sito" then
			open location SITE_URL

		else if scelta is "Apri CMS" then
			open location CMS_URL

		else if scelta is "Altro..." then
			set scelta2 to button returned of (display dialog "Rizzi CMS — Opzioni" with title "Rizzi CMS" buttons {"Indietro", "Aggiorna sito", "Ferma server"} default button "Aggiorna sito")

			if scelta2 is "Aggiorna sito" then
				-- Ferma il server, aggiorna, riavvia
				try
					do shell script "lsof -ti:5151 | xargs kill -9 2>/dev/null; echo done"
				end try
				set serverRunning to false
				set ok to updateFromGitHub(CMS_DIR)
				if ok then
					-- Riavvia il server
					try
						do shell script "cd " & quoted form of CMS_DIR & " && " & pyPath & " app.py > /tmp/rizzi_cms.log 2>&1 &"
					end try
					set avviato to false
					repeat 20 times
						delay 0.5
						try
							set code to do shell script "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 1 http://localhost:5151/ 2>/dev/null"
							if code is not "" and code is not "000" then
								set avviato to true
								exit repeat
							end if
						end try
					end repeat
					set serverRunning to true
					open location SITE_URL
				end if

			else if scelta2 is "Ferma server" then
				set conf to button returned of (display dialog "Fermare il server?" buttons {"Annulla", "Ferma"} default button "Ferma" with title "Rizzi CMS")
				if conf is "Ferma" then
					try
						do shell script "lsof -ti:5151 | xargs kill -9 2>/dev/null; echo done"
					end try
					set serverRunning to false
				end if
			end if
		end if

	else
		set statoMsg to "● Server FERMO"
		set scelta to button returned of (display dialog "Rizzi CMS

" & statoMsg & "

Clicca Avvia per accendere il server
e aprire il sito nel browser." with title "Rizzi CMS" buttons {"Esci", "Avvia il server"} default button "Avvia il server" with icon note)

		if scelta is "Avvia il server" then
			try
				do shell script "cd " & quoted form of CMS_DIR & " && " & pyPath & " app.py > /tmp/rizzi_cms.log 2>&1 &"
			on error errMsg
				display alert "Errore avvio" message errMsg as warning
			end try

			set avviato to false
			repeat 20 times
				delay 0.5
				try
					set code to do shell script "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 1 http://localhost:5151/ 2>/dev/null"
					if code is not "" and code is not "000" then
						set avviato to true
						exit repeat
					end if
				end try
			end repeat

			set serverRunning to true
			open location SITE_URL

		else if scelta is "Esci" then
			exit repeat
		end if
	end if
end repeat
