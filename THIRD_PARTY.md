# Componenti e attribuzioni

- **UCI HAR**: Reyes-Ortiz J., Anguita D., Ghio A., Oneto L., Parra X. (2013),
  Human Activity Recognition Using Smartphones, UCI Machine Learning Repository,
  https://doi.org/10.24432/C54S4K, CC BY 4.0. I campioni distribuiti e i modelli
  derivano dalle feature pubbliche; attribuzione dettagliata in data/ATTRIBUTION.md.
- **Contiki-NG v5.1**: sorgenti recuperati da GitHub al commit fissato. Non incluso
  il checkout completo; restano gli avvisi nei sorgenti e nelle dipendenze ottenute
  da setup_contiki.sh. Le patch del progetto sono distribuite in patches/.
- **Eclipse Mosquitto 2.0.22**: incluso archivio sorgenti ufficiale, patch CMake
  senza TLS, eseguibile Mac Intel verificato e testi di licenza in
  third_party/mosquitto/. Consultare LICENSE.txt, edl-v10 ed epl-v20 per la scelta
  di licenza e gli avvisi originali. Il checksum dell'archivio è nel manifest e
  in scripts/setup_mosquitto.sh; fonte https://mosquitto.org/files/source/mosquitto-2.0.22.tar.gz.
- **MySQL Community 8.0.31 e Grafana OSS 11.6.0**: non inclusi i binari nello ZIP.
  Gli script scaricano gli archivi ufficiali con SHA-256 fissato; URL e checksum
  in scripts/setup_native_stack.py e docs/NATIVE_MAC_STACK.md. Le licenze originali
  restano negli archivi scaricati.
- **Python e librerie**: dipendenze non incorporate nel pacchetto; versioni runtime
  e ML in requirements*.txt e nei freeze conservati con le evidenze. Le licenze
  sono distribuite dai rispettivi pacchetti.
- **Logo Università di Pisa**: versione orizzontale blu dal sito ufficiale
  https://www.unipi.it/wp-content/uploads/Raggruppa-3020.svg, conservata in SVG
  e convertita in PDF vettoriale per il frontespizio. Fonte e dettagli in
  docs/report/assets-en/unipi-logo.SOURCE.md. I diritti sul marchio restano
  dell'Università; l'inclusione identifica il contesto accademico della relazione.

Le slide del corso sono fonti didattiche locali: non sono redistribuite nello ZIP.
La specifica viene citata nella relazione e nella matrice requisiti.
