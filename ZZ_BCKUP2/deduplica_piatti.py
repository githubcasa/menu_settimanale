"""
Modulo per identificare e rimuovare piatti duplicati usando AI (Groq)
"""

import csv
import os
import json
from datetime import datetime
from groq import Groq

def carica_piatti_csv(csv_file):
    """Carica tutti i piatti dal CSV"""
    piatti = []

    if not os.path.exists(csv_file):
        return piatti

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                piatti.append(row)

        return piatti
    except Exception as e:
        print(f"[ERROR] Errore lettura CSV: {e}")
        return []

def identifica_duplicati_con_ai(piatti, groq_api_key):
    """
    Usa Groq AI per identificare piatti duplicati o molto simili.
    Restituisce: lista di tuple (id_originale, [id_duplicati])
    """
    if not groq_api_key:
        print("[WARNING] Groq API key non configurata, uso confronto semplice")
        return identifica_duplicati_semplice(piatti)

    try:
        client = Groq(api_key=groq_api_key)

        # Prepara lista piatti per l'AI (solo ID, nome, descrizione, ingredienti)
        piatti_info = []
        for p in piatti:
            piatti_info.append({
                'id': p['id'],
                'nome': p['nome'].strip(),
                'descrizione': p.get('descrizione', '').strip(),
                'ingredienti': p.get('ingredienti', '').strip()
            })

        # Dividi in batch se troppi piatti (max ~50 alla volta)
        batch_size = 50
        tutti_duplicati = []

        for i in range(0, len(piatti_info), batch_size):
            batch = piatti_info[i:i+batch_size]

            # Prepara prompt per l'AI
            piatti_text = "\n".join([
                f"ID {p['id']}: {p['nome']} - {p['descrizione'][:100]}"
                for p in batch
            ])

            prompt = f"""Analizza questi piatti di un ristorante e identifica i DUPLICATI o piatti MOLTO SIMILI.

Piatti:
{piatti_text}

Due piatti sono duplicati se:
- Hanno lo stesso nome (anche con piccole variazioni, es. "Pasta al pomodoro" vs "Pasta pomodoro")
- Hanno ingredienti identici o quasi identici
- Sono la stessa ricetta con nome diverso

IMPORTANTE: Rispondi SOLO con un JSON array di oggetti nel formato:
[
  {{"originale": "ID_ORIGINALE", "duplicati": ["ID_DUP1", "ID_DUP2"]}},
  ...
]

Se NON trovi duplicati rispondi SOLO con: []

NON aggiungere spiegazioni, SOLO il JSON."""

            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",  # Modello più potente per confronti
                messages=[
                    {
                        "role": "system",
                        "content": "Sei un esperto chef che identifica piatti duplicati nei menu. Rispondi SOLO con JSON valido, niente altro."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
                max_tokens=2000
            )

            risposta = response.choices[0].message.content.strip()

            # Estrai JSON dalla risposta
            try:
                # Rimuovi eventuali markdown code blocks
                if risposta.startswith('```'):
                    risposta = risposta.split('```')[1]
                    if risposta.startswith('json'):
                        risposta = risposta[4:]
                    risposta = risposta.strip()

                duplicati_batch = json.loads(risposta)

                if isinstance(duplicati_batch, list):
                    tutti_duplicati.extend(duplicati_batch)

            except json.JSONDecodeError as e:
                print(f"[WARNING] Errore parsing JSON AI: {e}")
                print(f"Risposta: {risposta}")
                continue

        return tutti_duplicati

    except Exception as e:
        print(f"[ERROR] Errore Groq AI: {e}")
        return identifica_duplicati_semplice(piatti)

def identifica_duplicati_semplice(piatti):
    """
    Fallback: identifica duplicati con confronto semplice nome+ingredienti
    """
    duplicati_map = {}
    visti = {}

    for p in piatti:
        # Chiave: nome normalizzato + ingredienti normalizzati
        chiave = (
            p['nome'].strip().lower().replace(' ', ''),
            p.get('ingredienti', '').strip().lower().replace(' ', '')
        )

        if chiave in visti:
            # Duplicato trovato
            id_originale = visti[chiave]
            if id_originale not in duplicati_map:
                duplicati_map[id_originale] = []
            duplicati_map[id_originale].append(p['id'])
        else:
            visti[chiave] = p['id']

    # Converti in formato compatibile
    risultato = []
    for originale, dups in duplicati_map.items():
        risultato.append({
            'originale': originale,
            'duplicati': dups
        })

    return risultato

def rimuovi_duplicati(csv_file, duplicati_info, backup=True):
    """
    Rimuove i piatti duplicati dal CSV.
    duplicati_info: lista di dict {'originale': id, 'duplicati': [ids]}
    """
    if not duplicati_info:
        return {
            'success': True,
            'rimossi': 0,
            'messaggio': 'Nessun duplicato trovato'
        }

    try:
        # Backup del CSV originale
        if backup:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"{csv_file}.backup_{timestamp}"

            with open(csv_file, 'r', encoding='utf-8') as f:
                contenuto = f.read()

            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(contenuto)

            print(f"[INFO] Backup creato: {backup_file}")

        # Carica tutti i piatti
        piatti = carica_piatti_csv(csv_file)

        # Crea set di ID da rimuovere
        ids_da_rimuovere = set()
        for info in duplicati_info:
            ids_da_rimuovere.update(info['duplicati'])

        # Filtra i piatti mantenendo solo quelli non duplicati
        piatti_filtrati = [
            p for p in piatti
            if p['id'] not in ids_da_rimuovere
        ]

        # Scrivi CSV aggiornato
        if piatti_filtrati:
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                fieldnames = piatti[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
                writer.writeheader()
                writer.writerows(piatti_filtrati)

        num_rimossi = len(piatti) - len(piatti_filtrati)

        return {
            'success': True,
            'rimossi': num_rimossi,
            'totale_prima': len(piatti),
            'totale_dopo': len(piatti_filtrati),
            'messaggio': f'Rimossi {num_rimossi} piatti duplicati',
            'backup': backup_file if backup else None,
            'dettagli_duplicati': duplicati_info
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'messaggio': f'Errore durante la rimozione: {str(e)}'
        }

def analizza_e_rimuovi_duplicati(csv_file, groq_api_key=None, auto_remove=False):
    """
    Funzione principale: analizza duplicati e opzionalmente li rimuove.

    Args:
        csv_file: path del file CSV
        groq_api_key: chiave API Groq (opzionale)
        auto_remove: se True, rimuove automaticamente i duplicati

    Returns:
        dict con risultati analisi e eventuale rimozione
    """
    # Carica piatti
    piatti = carica_piatti_csv(csv_file)

    if not piatti:
        return {
            'success': False,
            'error': 'File CSV vuoto o non trovato'
        }

    # Identifica duplicati con AI
    print(f"[INFO] Analisi di {len(piatti)} piatti per trovare duplicati...")
    duplicati_info = identifica_duplicati_con_ai(piatti, groq_api_key)

    num_duplicati = sum(len(d['duplicati']) for d in duplicati_info)

    risultato = {
        'success': True,
        'totale_piatti': len(piatti),
        'gruppi_duplicati': len(duplicati_info),
        'num_duplicati': num_duplicati,
        'duplicati': duplicati_info
    }

    # Rimuovi se richiesto
    if auto_remove and duplicati_info:
        risultato_rimozione = rimuovi_duplicati(csv_file, duplicati_info)
        risultato.update(risultato_rimozione)

    return risultato


# ============================================================================
# TEST DEL MODULO
# ============================================================================

if __name__ == '__main__':
    import sys

    csv_file = 'menu_database.csv'
    groq_key = os.environ.get('GROQ_API_KEY')

    if not groq_key:
        print("⚠️  GROQ_API_KEY non configurata, uso confronto semplice")

    print("=" * 70)
    print("ANALISI DUPLICATI NEL MENU")
    print("=" * 70)

    risultato = analizza_e_rimuovi_duplicati(
        csv_file,
        groq_api_key=groq_key,
        auto_remove=False  # Solo analisi, non rimuove
    )

    if risultato['success']:
        print(f"\n📊 Piatti totali: {risultato['totale_piatti']}")
        print(f"🔍 Gruppi di duplicati trovati: {risultato['gruppi_duplicati']}")
        print(f"❌ Piatti duplicati da rimuovere: {risultato['num_duplicati']}")

        if risultato['duplicati']:
            print("\n📋 Dettagli duplicati:\n")
            for idx, dup in enumerate(risultato['duplicati'], 1):
                print(f"{idx}. Originale ID: {dup['originale']}")
                print(f"   Duplicati: {', '.join(dup['duplicati'])}")
        else:
            print("\n✅ Nessun duplicato trovato!")
    else:
        print(f"\n❌ Errore: {risultato.get('error', 'Sconosciuto')}")

    print("=" * 70)
