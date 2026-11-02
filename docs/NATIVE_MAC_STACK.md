# Stack Mac verificato

| Servizio | Versione e accesso |
|---|---|
| Mosquitto |2.0.22 senza TLS, IPv6/IPv4:1883|
| MySQL Community |8.0.31 macos12-x86_64,127.0.0.1:13306|
| Backend |Python, MQTT→validazione→SQL→controllo|
| Grafana OSS |11.6.0 darwin-amd64,http://127.0.0.1:3000/d/activitylink|

Avvio con `scripts/native_stack.py start`; SLIP resta in un terminale separato.
Utente Grafana `admin`; password generata nel campo `grafana_admin` di
`runtime/native-stack/credentials.json`. Tale directory contiene lo storico DB:
non eliminarla per un normale riavvio.

Il backend riconnette MQTT e SQL. Durante l'assenza SQL conserva timestamp e coda
RAM limitata a1000messaggi; il watchdog del feedback può segnalare rosso.
Il provisioning Grafana imposta la sessione SQL aUTC per allineare i grafici.
Per cambiare run_id di un controller già attivo usare stop-cloud/start-cloud.

Gli URL ufficiali, i checksum e le versioni dei servizi sono fissati in
`scripts/setup_native_stack.py`. La procedura completa è in [REPRODUCE.md](REPRODUCE.md).
