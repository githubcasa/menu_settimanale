"""
Modulo per validare e correggere il file CSV del menu
Usa csv.DictReader per leggere per NOME colonna, non per posizione
"""

import csv
import os
import shutil
from datetime import datetime

def valida_e_correggi_csv(csv_file):
    """
    Valida il file CSV e corregge eventuali errori
    Usa DictReader quindi l'ordine delle colonne NON importa
    """

    if not os.path.exists(csv_file):
        return {
            'success': False,
            'error': f'File {csv_file} non trovato'
        }

    # Crea backup
    backup_file = f"{csv_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        shutil.copy2(csv_file, backup_file)
    except Exception as e:
        return {
            'success': False,
            'error': f'Errore creazione backup: {str(e)}'
        }

    errori = []
    warnings = []
    righe_valide = []
    righe_scartate = []

    # Colonne richieste
    colonne_richieste = ['id', 'data', 'nome', 'descrizione', 'categoria', 'prezzo', 'attivo']
    colonne_opzionali = ['ricetta', 'ingredienti', 'quantita']

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            # Usa DictReader per leggere per NOME colonna
            reader = csv.DictReader(f, delimiter=';')

            # Verifica che ci siano le intestazioni
            if not reader.fieldnames:
                return {
                    'success': False,
                    'error': 'File CSV vuoto o senza intestazioni'
                }

            # Verifica colonne richieste
            colonne_mancanti = [col for col in colonne_richieste if col not in reader.fieldnames]
            if colonne_mancanti:
                return {
                    'success': False,
                    'error': f'Colonne mancanti: {", ".join(colonne_mancanti)}'
                }

            riga_num = 1
            for row in reader:
                riga_num += 1
                errori_riga = []

                # Valida ID
                try:
                    id_val = int(row['id'])
                    if id_val <= 0:
                        errori_riga.append('ID deve essere > 0')
                except ValueError:
                    errori_riga.append(f'ID non valido: {row["id"]}')

                # Valida data (supporta formato GG/MM/AAAA e AAAA-MM-GG)
                data = row['data'].strip()
                if not data:
                    errori_riga.append('Data mancante')
                else:
                    # Accetta entrambi i formati
                    if '/' in data:
                        parti = data.split('/')
                        if len(parti) != 3:
                            errori_riga.append(f'Data non valida: {data}')
                    elif '-' in data:
                        parti = data.split('-')
                        if len(parti) != 3:
                            errori_riga.append(f'Data non valida: {data}')
                    else:
                        errori_riga.append(f'Data non valida: {data}')

                # Valida nome
                if not row['nome'].strip():
                    errori_riga.append('Nome piatto mancante')

                # Valida categoria
                categorie_valide = ['Primi', 'Secondi', 'Contorni', 'Dolci', 'Antipasti', 'Vegetariani', 'Vegani', 'Zuppe']
                if row['categoria'].strip() not in categorie_valide:
                    warnings.append(f"Riga {riga_num}: Categoria '{row['categoria']}' non standard")

                # Valida prezzo
                try:
                    prezzo = float(row['prezzo'])
                    if prezzo < 0:
                        errori_riga.append('Prezzo negativo')
                except ValueError:
                    errori_riga.append(f'Prezzo non valido: {row["prezzo"]}')

                # Valida attivo
                attivo = row['attivo'].strip().upper()
                if attivo not in ['SI', 'NO']:
                    errori_riga.append(f'Campo attivo deve essere SI o NO, trovato: {attivo}')
                    row['attivo'] = 'SI'  # Correggi automaticamente

                # Valida ingredienti e quantità (se presenti)
                if 'ingredienti' in row and row['ingredienti'].strip():
                    ingredienti = row['ingredienti'].split('|')
                    if 'quantita' in row and row['quantita'].strip():
                        quantita = row['quantita'].split('|')
                        if len(ingredienti) != len(quantita):
                            warnings.append(f"Riga {riga_num}: Numero ingredienti ({len(ingredienti)}) diverso da quantità ({len(quantita)})")

                # Se ci sono errori, scarta la riga
                if errori_riga:
                    righe_scartate.append({
                        'riga': riga_num,
                        'errori': errori_riga,
                        'dati': row
                    })
                else:
                    righe_valide.append(row)

        # Se ci sono righe scartate, crea file corretto
        if righe_scartate:
            # Scrivi file corretto con solo righe valide
            file_corretto = f"{csv_file}.corretto"
            with open(file_corretto, 'w', encoding='utf-8', newline='') as f:
                # Usa tutte le colonne presenti nel file originale
                writer = csv.DictWriter(f, fieldnames=reader.fieldnames, delimiter=';')
                writer.writeheader()
                writer.writerows(righe_valide)

            return {
                'success': True,
                'errori_trovati': len(righe_scartate),
                'righe_valide': len(righe_valide),
                'righe_scartate': righe_scartate,
                'warnings': warnings,
                'backup': backup_file,
                'file_corretto': file_corretto,
                'messaggio': f'Trovati {len(righe_scartate)} errori. File corretto salvato come {file_corretto}'
            }
        else:
            return {
                'success': True,
                'errori_trovati': 0,
                'righe_valide': len(righe_valide),
                'warnings': warnings,
                'backup': backup_file,
                'messaggio': 'Nessun errore trovato. CSV valido!'
            }

    except Exception as e:
        return {
            'success': False,
            'error': f'Errore durante la validazione: {str(e)}'
        }


def ripristina_backup(csv_file):
    """
    Ripristina il CSV dal backup più recente
    """

    # Cerca il backup più recente
    directory = os.path.dirname(csv_file) or '.'
    base_name = os.path.basename(csv_file)

    backups = []
    for file in os.listdir(directory):
        if file.startswith(f"{base_name}.backup_"):
            backup_path = os.path.join(directory, file)
            backups.append((backup_path, os.path.getmtime(backup_path)))

    if not backups:
        return {
            'success': False,
            'error': 'Nessun backup trovato'
        }

    # Ordina per data (più recente prima)
    backups.sort(key=lambda x: x[1], reverse=True)
    backup_recente = backups[0][0]

    try:
        # Crea backup del file corrente prima di ripristinare
        if os.path.exists(csv_file):
            backup_pre_ripristino = f"{csv_file}.pre_ripristino_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(csv_file, backup_pre_ripristino)

        # Ripristina il backup
        shutil.copy2(backup_recente, csv_file)

        return {
            'success': True,
            'backup_ripristinato': backup_recente,
            'messaggio': f'CSV ripristinato dal backup: {os.path.basename(backup_recente)}'
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Errore durante il ripristino: {str(e)}'
        }


if __name__ == '__main__':
    # Test del validatore
    print("TEST VALIDATORE CSV")
    print("=" * 60)

    test_file = 'menu_database.csv'

    if os.path.exists(test_file):
        risultato = valida_e_correggi_csv(test_file)

        if risultato['success']:
            print(f"✅ {risultato['messaggio']}")
            print(f"📊 Righe valide: {risultato['righe_valide']}")

            if risultato['errori_trovati'] > 0:
                print(f"⚠️  Righe scartate: {risultato['errori_trovati']}")

            if risultato.get('warnings'):
                print(f"\n⚠️  Warning ({len(risultato['warnings'])}):")
                for w in risultato['warnings'][:5]:  # Mostra solo i primi 5
                    print(f"   - {w}")
        else:
            print(f"❌ Errore: {risultato['error']}")
    else:
        print(f"❌ File {test_file} non trovato")
