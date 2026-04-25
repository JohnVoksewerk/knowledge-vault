# Voksewerk Strategisk Assistent

En Streamlit-app til strategisk sparring og case-audit med Groq og en lokal Obsidian knowledge vault.

## Opsaetning

1. Opret et virtuelt miljoe.
2. Installer afhængigheder:

```powershell
python -m pip install -r requirements.txt
```

3. Opret `.env` ud fra [`.env.example`](C:\Users\JohnMartinussen\OneDrive - Voksewerk\Dokumenter\New project\Gemma-project\.env.example) og udfyld vaerdierne.
4. Bekraeft at `VAULT_PATH` peger paa en lokal mappe med markdown-filer.

## Start appen

```powershell
python -m streamlit run app.py
```

Appen har to moduler:

- `Strategisk Sparring` bruger dit vault-indeks som kontekst til almindelig chat.
- `Case Analyse (Audit)` kombinerer vault-kontekst med en uploadet `pdf`, `txt` eller `md`.

## Hardening-status

Projektet er nu gjort mere robust med:

- miljovariabler for konfiguration frem for hardcodede vaerdier
- tydelig validering af manglende API-noegle og ugyldig vault-sti
- sikrere haandtering af uploads og midlertidige PDF-filer
- separat afhængighedsfil og ignorerede hemmeligheder/logfiler
- grundlaeggende tests for konfiguration og filindlaesning
- systemstatus i UI'et og lokal logfil i `.streamlit/app.log`
- defensiv prompt-validering og roligere Streamlit-standarder via `.streamlit/config.toml`

## Koer tests

```powershell
python -m unittest discover -s tests -p "test_*.py"
```
