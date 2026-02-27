"""
Generatore di Menu Settimanali
Genera menu bilanciati rispettando lo schema alimentare della nutrizionista
"""

import csv
import random
from datetime import datetime, timedelta
from schema_alimentare import (
    FREQUENZE_SETTIMANALI,
    identifica_categoria_proteica,
    verifica_frequenze_settimanali,
    stampa_report_frequenze
)

class MenuGenerator:
    """Generatore intelligente di menu settimanali bilanciati"""

    def __init__(self, csv_file='menu_database.csv'):
        self.csv_file = csv_file
        self.piatti_disponibili = []
        self.piatti_per_categoria = {}
        self.carica_piatti()

    def carica_piatti(self):
        """Carica e classifica tutti i piatti dal CSV"""
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')

                for row in reader:
                    if row['attivo'].upper() == 'SI':
                        # Identifica categoria proteica
                        ingredienti = row.get('ingredienti', '')
                        categoria = identifica_categoria_proteica(ingredienti)

                        piatto = {
                            'id': row['id'],
                            'nome': row['nome'],
                            'descrizione': row.get('descrizione', ''),
                            'categoria': row.get('categoria', ''),
                            'ingredienti': ingredienti,
                            'categoria_proteica': categoria
                        }

                        self.piatti_disponibili.append(piatto)

                        # Organizza per categoria proteica
                        if categoria:
                            if categoria not in self.piatti_per_categoria:
                                self.piatti_per_categoria[categoria] = []
                            self.piatti_per_categoria[categoria].append(piatto)

            print(f"✅ Caricati {len(self.piatti_disponibili)} piatti")
            print(f"\n📊 Distribuzione per categoria proteica:")
            for cat, piatti in sorted(self.piatti_per_categoria.items()):
                print(f"   • {cat:25} {len(piatti)} piatti")

        except FileNotFoundError:
            print(f"❌ File {self.csv_file} non trovato")
        except Exception as e:
            print(f"❌ Errore caricamento piatti: {e}")

    def genera_settimana_bilanciata(self, tentativi_max=100):
        """
        Genera una settimana di menu (7 giorni, pranzo e cena) 
        che rispetta le frequenze settimanali

        Returns:
            dict: {giorno: {'pranzo': piatto, 'cena': piatto}, ...}
            bool: valido
        """
        giorni = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']

        for tentativo in range(tentativi_max):
            menu_settimana = {}
            piatti_usati = []

            # Genera 14 pasti (7 pranzi + 7 cene)
            for giorno in giorni:
                pranzo = self._seleziona_piatto_casuale()
                cena = self._seleziona_piatto_casuale()

                menu_settimana[giorno] = {
                    'pranzo': pranzo,
                    'cena': cena
                }

                piatti_usati.append(pranzo)
                piatti_usati.append(cena)

            # Verifica se rispetta le frequenze
            conteggi, valido, errori = verifica_frequenze_settimanali(piatti_usati)

            if valido:
                print(f"\n✅ Menu valido trovato al tentativo {tentativo + 1}")
                return menu_settimana, conteggi, True

        print(f"\n⚠️  Non trovato menu valido in {tentativi_max} tentativi")
        print("Ritorno il miglior tentativo (potrebbe non rispettare tutte le frequenze)")
        return menu_settimana, conteggi, False

    def genera_settimana_intelligente(self):
        """
        Genera una settimana INTELLIGENTE rispettando le frequenze
        Metodo deterministico che costruisce il menu frequenza per frequenza
        """
        giorni = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
        menu_settimana = {giorno: {'pranzo': None, 'cena': None} for giorno in giorni}

        # Crea una lista di slot disponibili
        slot_disponibili = []
        for giorno in giorni:
            slot_disponibili.append((giorno, 'pranzo'))
            slot_disponibili.append((giorno, 'cena'))

        random.shuffle(slot_disponibili)

        # Assegna le categorie obbligatorie per prime
        piano = []

        # 1. Legumi (2 porzioni obbligatorie)
        piano.extend(['legumi'] * 2)

        # 2. Pesce bianco (almeno 2 porzioni)
        piano.extend(['pesce_bianco'] * 2)

        # 3. Carne bianca (fino a 3)
        piano.extend(['carne_bianca'] * 3)

        # 4. Uova (fino a 2)
        piano.extend(['uova'] * 2)

        # 5. Formaggi freschi (fino a 2)
        piano.extend(['formaggi_freschi'] * 2)

        # 6. Carne rossa (fino a 2)
        piano.extend(['carne_rossa'] * 1)

        # 7. Pesce grasso (1 porzione)
        piano.extend(['pesce_grasso'] * 1)

        # 8. Formaggi stagionati (1 porzione)
        piano.extend(['formaggi_stagionati'] * 1)

        # Totale: 14 pasti (perfetto!)

        random.shuffle(piano)

        # Assegna i piatti agli slot
        for i, (giorno, pasto) in enumerate(slot_disponibili):
            categoria = piano[i]
            piatto = self._seleziona_piatto_per_categoria(categoria)
            menu_settimana[giorno][pasto] = piatto

        # Verifica
        piatti_settimana = []
        for giorno in giorni:
            piatti_settimana.append(menu_settimana[giorno]['pranzo'])
            piatti_settimana.append(menu_settimana[giorno]['cena'])

        conteggi, valido, errori = verifica_frequenze_settimanali(piatti_settimana)

        return menu_settimana, conteggi, valido

    def _seleziona_piatto_casuale(self):
        """Seleziona un piatto casuale dal database"""
        if not self.piatti_disponibili:
            return None
        return random.choice(self.piatti_disponibili)

    def _seleziona_piatto_per_categoria(self, categoria):
        """Seleziona un piatto casuale di una specifica categoria proteica"""
        if categoria in self.piatti_per_categoria and self.piatti_per_categoria[categoria]:
            return random.choice(self.piatti_per_categoria[categoria])
        else:
            # Fallback: piatto casuale
            return self._seleziona_piatto_casuale()

    def stampa_menu_settimana(self, menu_settimana, conteggi):
        """Stampa il menu della settimana in formato leggibile"""
        print("\n" + "="*70)
        print("MENU SETTIMANALE BILANCIATO")
        print("="*70)

        for giorno, pasti in menu_settimana.items():
            print(f"\n📅 {giorno.upper()}")
            print("-" * 70)

            pranzo = pasti['pranzo']
            cena = pasti['cena']

            if pranzo:
                cat_p = pranzo.get('categoria_proteica', 'n/a')
                print(f"  🍽️  PRANZO: {pranzo['nome']}")
                print(f"      Categoria: {cat_p}")

            if cena:
                cat_c = cena.get('categoria_proteica', 'n/a')
                print(f"  🌙 CENA:   {cena['nome']}")
                print(f"      Categoria: {cat_c}")

        stampa_report_frequenze(conteggi)

    def esporta_menu_csv(self, menu_settimana, filename='menu_settimanale_generato.csv'):
        """Esporta il menu settimanale in un file CSV"""
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['giorno', 'pasto', 'nome', 'categoria', 'categoria_proteica', 'ingredienti']
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()

            for giorno, pasti in menu_settimana.items():
                for pasto, piatto in pasti.items():
                    if piatto:
                        writer.writerow({
                            'giorno': giorno,
                            'pasto': pasto,
                            'nome': piatto['nome'],
                            'categoria': piatto.get('categoria', ''),
                            'categoria_proteica': piatto.get('categoria_proteica', ''),
                            'ingredienti': piatto.get('ingredienti', '')
                        })

        print(f"\n💾 Menu esportato in {filename}")


# ============================================================================
# TEST DEL GENERATORE
# ============================================================================

if __name__ == '__main__':
    print("TEST GENERATORE MENU SETTIMANALI")
    print("="*70)

    generator = MenuGenerator()

    if generator.piatti_disponibili:
        print("\n🎲 Generazione menu settimanale INTELLIGENTE...")
        menu, conteggi, valido = generator.genera_settimana_intelligente()

        generator.stampa_menu_settimana(menu, conteggi)

        if valido:
            print("\n✅ Menu settimanale VALIDO e BILANCIATO!")
            generator.esporta_menu_csv(menu)
        else:
            print("\n⚠️  Menu generato ma potrebbe non rispettare tutte le frequenze")
    else:
        print("\n❌ Nessun piatto disponibile nel database")
