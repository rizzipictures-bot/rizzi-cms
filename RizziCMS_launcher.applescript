-- Rizzi CMS Launcher
-- Interfaccia grafica nativa Mac tramite AppleScript
-- Non richiede Tkinter né dipendenze esterne

property CMS_DIR : (POSIX path of (path to home folder)) & "Library/Application Support/RizziCMS/rizzi-cms"
property PORT : 5151
property SITE_URL : "http://localhost:5151/"
property CMS_URL : "http://localhost:5151/cms"

-- Controlla se il server è già in esecuzione
on isServerRunning()
	try
		do shell script "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 1 http://localhost:5151/ | grep -q '200\\|304' && echo yes || echo no"
		return true
	on error
		return false
	end try
end isServerRunning

-- Trova python3
on findPython()
	repeat with p in {"/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"}
		try
			do shell script "test -x " & p & " && echo yes"
			return p
		end try
	end repeat
	return ""
end findPython

-- Avvia il server
on startServer()
	set pyPath to findPython()
	if pyPath is "" then
		display alert "Python 3 non trovato" message "Installa Python 3 da python.org e riprova." as critical
		return false
	end if
	
	-- Installa dipendenze se mancanti
	try
		do shell script pyPath & " -c 'import flask' 2>/dev/null || " & pyPath & " -m pip install flask pillow -q"
	end try
	
	-- Avvia il server in background
	do shell script "cd " & quoted form of CMS_DIR & " && " & pyPath & " app.py > /tmp/rizzi_cms.log 2>&1 &"
	
	-- Aspetta che risponda (max 8 secondi)
	repeat 16 times
		delay 0.5
		try
			do shell script "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 1 http://localhost:5151/"
			return true
		end try
	end repeat
	
	return false
end startServer

-- Ferma il server
on stopServer()
	try
		do shell script "lsof -ti:5151 | xargs kill -9 2>/dev/null; echo done"
	end try
end stopServer

-- Loop principale
on run
	-- Controlla se la cartella CMS esiste
	try
		do shell script "test -d " & quoted form of CMS_DIR & " && echo ok"
	on error
		display alert "Rizzi CMS non installato" message "Esegui prima 'Installa Rizzi CMS.command' dalla cartella dello zip." as critical
		return
	end try
	
	-- Controlla stato iniziale
	set serverRunning to false
	try
		set result to do shell script "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 1 http://localhost:5151/ 2>/dev/null"
		if result is "200" or result is "304" then
			set serverRunning to true
		end if
	end try
	
	-- Menu principale
	repeat
		if serverRunning then
			set btnLabel to "Ferma il server"
			set statusMsg to "● Server attivo — tutto funziona"
		else
			set btnLabel to "Avvia il server"
			set statusMsg to "● Server fermo"
		end if
		
		set scelta to button returned of (display dialog "Rizzi CMS — Gestione Portfolio

" & statusMsg & "

Sito:  " & SITE_URL & "
CMS:   " & CMS_URL with title "Rizzi CMS" buttons {btnLabel, "Apri Sito", "Apri CMS", "Esci"} default button 1 with icon note)
		
		if scelta is "Avvia il server" then
			display dialog "Avvio in corso..." with title "Rizzi CMS" buttons {} giving up after 0
			set ok to startServer()
			if ok then
				set serverRunning to true
				open location SITE_URL
			else
				display alert "Errore avvio" message "Il server non si è avviato. Controlla che Python 3 sia installato." as warning
			end if
			
		else if scelta is "Ferma il server" then
			stopServer()
			set serverRunning to false
			
		else if scelta is "Apri Sito" then
			if serverRunning then
				open location SITE_URL
			else
				display alert "Server non attivo" message "Prima avvia il server." as warning
			end if
			
		else if scelta is "Apri CMS" then
			if serverRunning then
				open location CMS_URL
			else
				display alert "Server non attivo" message "Prima avvia il server." as warning
			end if
			
		else if scelta is "Esci" then
			if serverRunning then
				set conf to button returned of (display dialog "Vuoi fermare il server prima di uscire?" buttons {"Ferma ed esci", "Esci senza fermare"} default button 1)
				if conf is "Ferma ed esci" then
					stopServer()
				end if
			end if
			exit repeat
		end if
	end repeat
end run
