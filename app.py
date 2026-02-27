from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import csv
import json
import os
import re
from datetime import datetime, timedelta

# Carica variabili d'ambiente da .env
load_dotenv()

# Importa il modulo di validazione CSV
import csv_validator

# Importa il classificatore intelligente
from classificatore_ingredienti import get_classificatore

app = Flask(__name__)
app.secret_key = 'CAMBIA_QUESTA_CHIAVE_SEGRETA_CON_STRINGA_CASUALE'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Database utenti
USERS = {
    'riccardo': generate_password_hash('riccardo'),
    'carla': generate_password_hash('carla'),
    'umberto': generate_password_hash('umberto'),
    'dorotea': generate_password_hash('dorotea'),
    'admin': generate_password_hash('admin')
}

CSV_FILE = 'menu_database.csv'
VOTES_FILE = 'voti.json'

# ============================================================================
# FUNZIONE PER CALCOLARE SETTIMANA DA DATA
# ============================================================================

def calcola_settimana(data_str):
    """
    Calcola automaticamente il numero della settimana ISO da una data
    Args:
        data_str: data in formato ISO (AAAA-MM-GG) o italiano (GG/MM/AAAA)
    Returns:
        int: numero settimana (1-53)
    """
    try:
        # Converti a formato ISO se necessario
        data_iso = converti_data_italiana(data_str)
        
        # Parse della data
        if '-' in data_iso:
            parts = data_iso.split('-')
            anno = int(parts[0])
            mese = int(parts[1])
            giorno = int(parts[2])
        else:
            return 1  # Fallback
        
        # Calcola settimana ISO
        data_obj = datetime(anno, mese, giorno)
        settimana_iso = data_obj.isocalendar()[1]
        
        return settimana_iso
    
    except Exception as e:
        print(f"[ERROR] Errore calcolo settimana per data '{data_str}': {e}")
        return 1  # Fallback

# ============================================================================
# FUNZIONE PER GESTIRE DATE IN FORMATO ITALIANO
# ============================================================================

def converti_data_italiana(data_str):
    """
    Converte data da formato italiano (GG/MM/AAAA) a formato ISO (AAAA-MM-GG)
    Supporta entrambi i formati in input
    """
    try:
        data_str = data_str.strip()
        
        if '/' in data_str:
            parti = data_str.split('/')
            if len(parti) == 3:
                giorno = parti[0].zfill(2)
                mese = parti[1].zfill(2)
                anno = parti[2]
                return f"{anno}-{mese}-{giorno}"
        elif '-' in data_str:
            return data_str
        
        return data_str
    except Exception as e:
        print(f"[ERROR] Errore conversione data '{data_str}': {e}")
        return data_str

# ============================================================================
# FUNZIONI PER CALCOLARE QUANTITÀ
# ============================================================================

def parse_quantita(quantita_str):
    """
    Converte una stringa di quantità in un numero e unità
    Es: "350g" -> (350, "g"), "1.5 kg" -> (1500, "g"), "q.b." -> (0, "qb")
    """
    try:
        quantita_str = quantita_str.strip().lower()
        
        # Gestisci "q.b." o "quanto basta"
        if quantita_str in ['q.b.', 'qb', 'quanto basta', 'a piacere']:
            return (0, 'qb')
        
        # Cerca numero seguito da unità
        match = re.match(r'(\d+\.?\d*)\s*(kg|g|l|ml|cl|unità|pezzi|bicchiere|bustina|costa|stecca|foglio|fogli|piccola)?', quantita_str)
        
        if match:
            numero = float(match.group(1))
            unita = match.group(2) if match.group(2) else 'unità'
            
            # Converti tutto in unità base
            if unita == 'kg':
                return (numero * 1000, 'g')
            elif unita == 'l':
                return (numero * 1000, 'ml')
            elif unita == 'cl':
                return (numero * 10, 'ml')
            else:
                return (numero, unita)
        
        return (0, 'qb')
    except:
        return (0, 'qb')

def somma_quantita(q1_str, q2_str):
    """Somma due quantità"""
    val1, unit1 = parse_quantita(q1_str)
    val2, unit2 = parse_quantita(q2_str)
    
    # Se una è q.b., mantieni l'altra
    if unit1 == 'qb':
        return formatta_quantita(val2, unit2)
    if unit2 == 'qb':
        return formatta_quantita(val1, unit1)
    
    # Se unità diverse, mantieni la prima
    if unit1 != unit2:
        return formatta_quantita(val1, unit1)
    
    return formatta_quantita(val1 + val2, unit1)

def moltiplica_quantita(quantita_str, moltiplicatore):
    """Moltiplica una quantità per un numero"""
    val, unit = parse_quantita(quantita_str)
    
    if unit == 'qb':
        return 'q.b.'
    
    return formatta_quantita(val * moltiplicatore, unit)

def formatta_quantita(valore, unita):
    """Formatta una quantità per la visualizzazione"""
    if unita == 'qb':
        return 'q.b.'
    
    # Converti grammi in kg se > 1000
    if unita == 'g' and valore >= 1000:
        return f"{valore/1000:.1f} kg"
    
    # Converti ml in litri se > 1000
    if unita == 'ml' and valore >= 1000:
        return f"{valore/1000:.1f} l"
    
    # Se è un numero intero, mostra senza decimali
    if valore == int(valore):
        return f"{int(valore)} {unita}"
    else:
        return f"{valore:.1f} {unita}"

# ============================================================================
# FUNZIONI PER GESTIRE IL MENU DA CSV
# ============================================================================

def load_menu_from_csv(data_richiesta=None, include_ingredienti=False):
    """
    Carica il menu dal file CSV filtrando per data
    Calcola automaticamente la settimana dalla data
    include_ingredienti: se True, include ingredienti e quantità (solo per admin)
    """
    if not os.path.exists(CSV_FILE):
        return {
            "data": datetime.now().strftime("%Y-%m-%d"),
            "piatti": [],
            "error": f"File {CSV_FILE} non trovato"
        }
    
    try:
        if data_richiesta is None:
            data_richiesta = datetime.now().strftime("%Y-%m-%d")
        
        piatti = []
        date_disponibili = set()
        
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            
            for row in reader:
                try:
                    data_piatto = converti_data_italiana(row['data'])
                    date_disponibili.add(data_piatto)
                    
                    if data_piatto == data_richiesta and row['attivo'].strip().upper() == 'SI':
                        piatto = {
                            'id': int(row['id']),
                            'nome': row['nome'].strip(),
                            'descrizione': row['descrizione'].strip(),
                            'categoria': row['categoria'].strip(),
                            'prezzo': f"€{float(row['prezzo']):.2f}"
                        }
                        
                        # Aggiungi ricetta se presente
                        if 'ricetta' in row and row['ricetta'].strip():
                            piatto['ricetta'] = row['ricetta'].strip()
                        
                        # CALCOLA AUTOMATICAMENTE LA SETTIMANA DALLA DATA
                        piatto['settimana'] = calcola_settimana(data_piatto)
                        
                        # Aggiungi ingredienti e quantità SOLO se richiesto (per admin)
                        if include_ingredienti:
                            if 'ingredienti' in row and row['ingredienti'].strip():
                                ingredienti_list = [i.strip() for i in row['ingredienti'].split('|')]
                                piatto['ingredienti'] = ingredienti_list
                            
                            if 'quantita' in row and row['quantita'].strip():
                                quantita_list = [q.strip() for q in row['quantita'].split('|')]
                                piatto['quantita'] = quantita_list
                        
                        piatti.append(piatto)
                except Exception as e:
                    print(f"[ERROR] Errore lettura riga CSV: {e}")
                    continue
        
        return {
            "data": data_richiesta,
            "piatti": piatti,
            "date_disponibili": sorted(list(date_disponibili)),
            "totale_piatti": len(piatti)
        }
    
    except Exception as e:
        print(f"[ERROR] Errore caricamento menu: {e}")
        return {
            "data": data_richiesta or datetime.now().strftime("%Y-%m-%d"),
            "piatti": [],
            "error": f"Errore nella lettura del file CSV: {str(e)}"
        }

def calcola_lista_spesa(date_selezionate, num_persone):
    """
    Calcola la lista della spesa aggregata per più date, organizzata per categoria merceologica
    Usa il classificatore intelligente con Groq AI
    """
    lista_spesa = {}  # {ingrediente: quantità_totale}
    
    for data in date_selezionate:
        menu = load_menu_from_csv(data, include_ingredienti=True)
        
        for piatto in menu['piatti']:
            if 'ingredienti' in piatto and 'quantita' in piatto:
                for idx, ingrediente in enumerate(piatto['ingredienti']):
                    quantita = piatto['quantita'][idx] if idx < len(piatto['quantita']) else 'q.b.'
                    
                    # Moltiplica per numero persone
                    quantita_moltiplicata = moltiplica_quantita(quantita, num_persone)
                    
                    # Aggrega con quantità esistente
                    if ingrediente in lista_spesa:
                        lista_spesa[ingrediente] = somma_quantita(lista_spesa[ingrediente], quantita_moltiplicata)
                    else:
                        lista_spesa[ingrediente] = quantita_moltiplicata
    
    # Usa il classificatore intelligente con Groq AI
    classificatore = get_classificatore(use_ai=True)
    
    # Organizza per categoria merceologica
    categorie = {}
    
    for ingrediente, quantita in lista_spesa.items():
        # Classifica usando il sistema intelligente
        categoria, fonte = classificatore.classifica(ingrediente)
        
        if categoria not in categorie:
            categorie[categoria] = []
        
        categorie[categoria].append({
            'ingrediente': ingrediente,
            'quantita': quantita
        })
    
    # Ordina ingredienti dentro ogni categoria
    for categoria in categorie:
        categorie[categoria].sort(key=lambda x: x['ingrediente'])
    
    # Converti in lista ordinata di categorie
    ordine_categorie = [
        'Frutta e Verdura',
        'Macelleria e Pescheria',
        'Latticini e Uova',
        'Dispensa e Cereali',
        'Bevande',
        'Dolci e Dessert',
        'Surgelati',
        'Altri'
    ]
    
    risultato = []
    for categoria in ordine_categorie:
        if categoria in categorie:
            risultato.append({
                'categoria': categoria,
                'ingredienti': categorie[categoria]
            })
    
    # Stampa statistiche per debug (solo in console)
    classificatore.print_stats()
    
    return risultato

def get_available_dates():
    """Restituisce tutte le date per cui ci sono piatti nel database"""
    if not os.path.exists(CSV_FILE):
        return []
    
    try:
        date_disponibili = set()
        
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                data_iso = converti_data_italiana(row['data'])
                date_disponibili.add(data_iso)
        
        return sorted(list(date_disponibili))
    except Exception as e:
        print(f"[ERROR] Errore caricamento date: {e}")
        return []

# ============================================================================
# FUNZIONI PER GESTIRE I VOTI
# ============================================================================

def load_votes():
    if os.path.exists(VOTES_FILE):
        with open(VOTES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_votes(votes):
    with open(VOTES_FILE, 'w', encoding='utf-8') as f:
        json.dump(votes, f, indent=2, ensure_ascii=False)

# ============================================================================
# ROUTE PRINCIPALI
# ============================================================================

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if username in USERS and check_password_hash(USERS[username], password):
            session['username'] = username
            session.permanent = True
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Credenziali non valide'})
    
    # === TEST_RICCARDO_START (DA RIMUOVERE) ===
    html = render_template('login.html')

    banner = '<div style="margin: 12px 0; font-weight: 700; text-align: center;">RICCARDO</div>'

    # Inserisci il banner subito dopo il tag <body ...> (se presente)
    html2, n = re.subn(r'(<body[^>]*>)', r'\1\n' + banner, html, count=1, flags=re.IGNORECASE)

    # Fallback: se non trova <body>, aggiunge il banner in testa alla pagina
    if n == 0:
        html2 = banner + html

    return html2
    # === TEST_RICCARDO_END (DA RIMUOVERE) ===

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if 'username' not in session:
        return redirect(url_for('login'))
    if session['username'] != 'admin':
        return redirect(url_for('index'))
    return render_template('admin.html')

@app.route('/ingredienti')
def ingredienti():
    if 'username' not in session:
        return redirect(url_for('login'))
    if session['username'] != 'admin':
        return redirect(url_for('index'))
    return render_template('ingredienti.html')

@app.route('/valida_csv')
def valida_csv_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    if session['username'] != 'admin':
        return redirect(url_for('index'))
    return render_template('valida_csv.html')


@app.route('/genera_menu')
def genera_menu_page():
    if 'username' not in session:
        return redirect(url_for('login'))
    if session['username'] != 'admin':
        return redirect(url_for('index'))
    return render_template('genera_menu.html')

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/menu')
def get_menu():
    """Restituisce il menu (SENZA ingredienti per utenti normali)"""
    if 'username' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    data_richiesta = request.args.get('data', None)
    menu = load_menu_from_csv(data_richiesta, include_ingredienti=False)
    return jsonify(menu)

@app.route('/api/date_disponibili')
def get_dates():
    """Restituisce tutte le date per cui ci sono menu disponibili"""
    if 'username' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    date = get_available_dates()
    return jsonify({'date': date})

@app.route('/api/settimane_disponibili')
def get_settimane():
    """Restituisce le settimane per cui ci sono menu disponibili"""
    if 'username' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    if session['username'] != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    try:
        date_disponibili = get_available_dates()
        
        # Raggruppa date per settimana
        settimane = {}
        for data in date_disponibili:
            settimana = calcola_settimana(data)
            anno = int(data.split('-')[0])
            chiave = f"{anno}-W{settimana:02d}"
            
            if chiave not in settimane:
                settimane[chiave] = {
                    'anno': anno,
                    'settimana': settimana,
                    'date': [],
                    'label': f"Settimana {settimana} del {anno}"
                }
            
            settimane[chiave]['date'].append(data)
        
        # Ordina per anno e settimana
        settimane_lista = sorted(settimane.values(), key=lambda x: (x['anno'], x['settimana']))
        
        return jsonify({'settimane': settimane_lista})
    
    except Exception as e:
        print(f"[ERROR] Errore caricamento settimane: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/date_da_settimana')
def get_date_da_settimana():
    """Restituisce tutte le date di una specifica settimana"""
    if 'username' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    if session['username'] != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    try:
        anno = int(request.args.get('anno', datetime.now().year))
        settimana = int(request.args.get('settimana', 1))
        
        # Ottieni tutte le date disponibili
        date_disponibili = get_available_dates()
        
        # Filtra per settimana
        date_settimana = []
        for data in date_disponibili:
            data_anno = int(data.split('-')[0])
            data_settimana = calcola_settimana(data)
            
            if data_anno == anno and data_settimana == settimana:
                date_settimana.append(data)
        
        return jsonify({
            'anno': anno,
            'settimana': settimana,
            'date': sorted(date_settimana)
        })
    
    except Exception as e:
        print(f"[ERROR] Errore calcolo date settimana: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/lista_spesa', methods=['POST'])
def get_lista_spesa():
    """Calcola la lista della spesa per le date selezionate"""
    if 'username' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    if session['username'] != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    data = request.json
    date_selezionate = data.get('date', [])
    num_persone = int(data.get('num_persone', 1))
    
    if not date_selezionate:
        return jsonify({'error': 'Nessuna data selezionata'}), 400
    
    lista = calcola_lista_spesa(date_selezionate, num_persone)
    
    # Calcola totale ingredienti
    totale_ingredienti = sum(len(cat['ingredienti']) for cat in lista)
    
    return jsonify({
        'lista_spesa': lista,
        'date': date_selezionate,
        'num_persone': num_persone,
        'totale_ingredienti': totale_ingredienti
    })

@app.route('/api/vota', methods=['POST'])
def vota():
    if 'username' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    # Admin non può votare
    if session['username'] == 'admin':
        return jsonify({'error': 'Admin non può votare'}), 403
    
    data = request.json
    piatto_id = data.get('piatto_id')
    voto = data.get('voto')
    commento = data.get('commento', '')
    data_menu = data.get('data_menu', datetime.now().strftime('%Y-%m-%d'))
    username = session['username']
    
    votes = load_votes()
    vote_key = f"{username}_{piatto_id}_{data_menu}"
    
    votes[vote_key] = {
        'piatto_id': piatto_id,
        'voto': voto,
        'commento': commento,
        'username': username,
        'data_menu': data_menu,
        'timestamp': datetime.now().isoformat()
    }
    
    save_votes(votes)
    return jsonify({'success': True})

@app.route('/api/miei_voti')
def get_my_votes():
    if 'username' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    username = session['username']
    
    # Admin non ha voti
    if username == 'admin':
        return jsonify({})
    
    data_richiesta = request.args.get('data', datetime.now().strftime('%Y-%m-%d'))
    all_votes = load_votes()
    
    my_votes = {}
    for key, vote in all_votes.items():
        if vote['username'] == username and vote.get('data_menu') == data_richiesta:
            my_votes[vote['piatto_id']] = vote
    
    return jsonify(my_votes)

@app.route('/api/statistiche')
def get_statistics():
    if 'username' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    if session['username'] != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    data_richiesta = request.args.get('data', datetime.now().strftime('%Y-%m-%d'))
    votes = load_votes()
    stats = {}
    
    for vote in votes.values():
        if vote.get('data_menu') != data_richiesta:
            continue
        
        piatto_id = vote['piatto_id']
        if piatto_id not in stats:
            stats[piatto_id] = {
                'voti': [], 
                'media': 0, 
                'count': 0,
                'commenti': []
            }
        stats[piatto_id]['voti'].append(vote['voto'])
        
        if vote.get('commento'):
            stats[piatto_id]['commenti'].append({
                'username': vote['username'],
                'commento': vote['commento']
            })
    
    for piatto_id in stats:
        voti = stats[piatto_id]['voti']
        if voti:
            stats[piatto_id]['media'] = round(sum(voti) / len(voti), 2)
            stats[piatto_id]['count'] = len(voti)
    
    return jsonify(stats)

@app.route('/api/valida_csv', methods=['POST'])
def api_valida_csv():
    """Valida e corregge il file CSV"""
    if 'username' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    if session['username'] != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    # Richiama la funzione dal modulo esterno
    risultato = csv_validator.valida_e_correggi_csv(CSV_FILE)
    return jsonify(risultato)

@app.route('/api/ripristina_csv', methods=['POST'])
def api_ripristina_csv():
    """Ripristina il CSV dal backup"""
    if 'username' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    if session['username'] != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    risultato = csv_validator.ripristina_backup(CSV_FILE)
    return jsonify(risultato)

# ============================================================================
# AVVIO APPLICAZIONE
# ============================================================================


# ============================================================================
# API PER GENERATORE MENU SETTIMANALE
# ============================================================================

@app.route('/api/genera_menu_settimanale', methods=['POST'])
def genera_menu_settimanale():
    """Genera un menu settimanale bilanciato"""
    if 'username' not in session or session['username'] != 'admin':
        return jsonify({'error': 'Non autorizzato'}), 401

    try:
        from menu_generator import MenuGenerator

        # Calcola data di inizio (lunedì prossimo)
        oggi = datetime.now()
        giorni_da_lunedi = oggi.weekday()
        lunedi_questa_settimana = oggi - timedelta(days=giorni_da_lunedi)
        lunedi_prossimo = lunedi_questa_settimana + timedelta(days=7)
        data_proposta_str = lunedi_prossimo.strftime('%Y-%m-%d')

        # Genera menu con MenuGenerator
        generator = MenuGenerator(CSV_FILE)
        menu_settimana, conteggi, valido = generator.genera_settimana_intelligente()

        # Prepara output per frontend
        giorni_ordine = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
        menu_array = []

        for idx, giorno in enumerate(giorni_ordine):
            data_giorno = lunedi_prossimo + timedelta(days=idx)
            data_giorno_str = data_giorno.strftime('%Y-%m-%d')

            pasti = menu_settimana[giorno]

            menu_array.append({
                'giorno': giorno,
                'data': data_giorno_str,
                'pranzo': {
                    'id': pasti['pranzo']['id'],
                    'nome': pasti['pranzo']['nome'],
                    'categoria_proteica': pasti['pranzo'].get('categoria_proteica', 'N/A')
                },
                'cena': {
                    'id': pasti['cena']['id'],
                    'nome': pasti['cena']['nome'],
                    'categoria_proteica': pasti['cena'].get('categoria_proteica', 'N/A')
                }
            })

        return jsonify({
            'success': True,
            'menu': menu_array,
            'data_inizio': data_proposta_str,
            'conteggi': conteggi,
            'valido': valido
        })

    except Exception as e:
        print(f"[ERROR] Errore generazione menu: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/piatti_per_categoria')
def get_piatti_per_categoria():
    """Restituisce tutti i piatti disponibili raggruppati per categoria proteica"""
    if 'username' not in session or session['username'] != 'admin':
        return jsonify({'error': 'Non autorizzato'}), 401

    try:
        from schema_alimentare import identifica_categoria_proteica

        # Carica tutti i piatti
        piatti = []
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                if row['attivo'].strip().upper() == 'SI':
                    ingredienti = row.get('ingredienti', '')
                    categoria_proteica = identifica_categoria_proteica(ingredienti)

                    piatti.append({
                        'id': int(row['id']),
                        'nome': row['nome'].strip(),
                        'descrizione': row.get('descrizione', '').strip(),
                        'categoria_proteica': categoria_proteica
                    })

        # Raggruppa per categoria proteica
        piatti_per_categoria = {}
        for piatto in piatti:
            cat = piatto.get('categoria_proteica', 'altro')
            if cat not in piatti_per_categoria:
                piatti_per_categoria[cat] = []

            piatti_per_categoria[cat].append({
                'id': piatto['id'],
                'nome': piatto['nome'],
                'descrizione': piatto.get('descrizione', ''),
                'categoria_proteica': cat
            })

        return jsonify({
            'success': True,
            'piatti': piatti_per_categoria
        })

    except Exception as e:
        print(f"[ERROR] Errore: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/salva_menu_settimanale', methods=['POST'])
def salva_menu_settimanale():
    """Salva il menu settimanale nel database CSV"""
    if 'username' not in session or session['username'] != 'admin':
        return jsonify({'error': 'Non autorizzato'}), 401

    try:
        data = request.get_json()
        menu = data.get('menu', [])

        if not menu:
            return jsonify({'error': 'Menu vuoto'}), 400

        # Carica CSV esistente
        righe_esistenti = []
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            fieldnames = reader.fieldnames
            for row in reader:
                righe_esistenti.append(row)

        # Crea dizionario piatti esistenti per ID
        piatti_db = {}
        for row in righe_esistenti:
            piatti_db[int(row['id'])] = row

        # Funzione helper per convertire data ISO in italiana
        def converti_data_iso_italiana(data_iso):
            if '-' in data_iso:
                parti = data_iso.split('-')
                if len(parti) == 3:
                    return f"{parti[2]}/{parti[1]}/{parti[0]}"
            return data_iso

        # Calcola prossimo ID disponibile
        max_id = max(int(row['id']) for row in righe_esistenti)
        prossimo_id = max_id + 1

        # Prepara nuove righe
        nuove_righe = []
        for giorno_data in menu:
            data_iso = giorno_data['data']
            data_italiana = converti_data_iso_italiana(data_iso)

            # Pranzo
            id_pranzo = giorno_data['pranzo']['id']
            if id_pranzo in piatti_db:
                piatto_pranzo = piatti_db[id_pranzo].copy()
                piatto_pranzo['id'] = str(prossimo_id)
                piatto_pranzo['data'] = data_italiana
                nuove_righe.append(piatto_pranzo)
                prossimo_id += 1

            # Cena
            id_cena = giorno_data['cena']['id']
            if id_cena in piatti_db:
                piatto_cena = piatti_db[id_cena].copy()
                piatto_cena['id'] = str(prossimo_id)
                piatto_cena['data'] = data_italiana
                nuove_righe.append(piatto_cena)
                prossimo_id += 1

        # Aggiungi nuove righe
        righe_esistenti.extend(nuove_righe)

        # Scrivi CSV aggiornato
        with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(righe_esistenti)

        return jsonify({
            'success': True,
            'piatti_aggiunti': len(nuove_righe),
            'messaggio': f'Menu settimanale salvato! Aggiunti {len(nuove_righe)} piatti.'
        })

    except Exception as e:
        print(f"[ERROR] Errore salvataggio: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API PER GESTIONE DUPLICATI
# ============================================================================

@app.route('/api/analizza_duplicati', methods=['POST'])
def analizza_duplicati():
    """Analizza il database CSV per trovare piatti duplicati (stesso nome)"""
    if 'username' not in session or session['username'] != 'admin':
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        import csv
        from collections import defaultdict
        
        # Carica tutti i piatti dal CSV
        piatti_per_nome = defaultdict(list)
        
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                nome = row['nome'].strip().lower()
                piatto_id = int(row['id'])
                piatti_per_nome[nome].append({
                    'id': piatto_id,
                    'nome': row['nome'].strip()
                })
        
        # Trova duplicati (piatti con lo stesso nome)
        duplicati = []
        for nome, piatti_lista in piatti_per_nome.items():
            if len(piatti_lista) > 1:
                # Ordina per ID (il più basso è l'originale)
                piatti_lista.sort(key=lambda x: x['id'])
                
                duplicati.append({
                    'nome': piatti_lista[0]['nome'],
                    'originale': piatti_lista[0]['id'],
                    'duplicati': [p['id'] for p in piatti_lista[1:]]
                })
        
        # Conta totale piatti e duplicati
        totale_piatti = sum(len(lista) for lista in piatti_per_nome.values())
        num_duplicati = sum(len(d['duplicati']) for d in duplicati)
        
        return jsonify({
            'success': True,
            'duplicati': duplicati,
            'num_duplicati': num_duplicati,
            'gruppi_duplicati': len(duplicati),
            'totale_piatti': totale_piatti
        })
        
    except Exception as e:
        print(f"[ERROR] Errore analisi duplicati: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/rimuovi_duplicati', methods=['POST'])
def rimuovi_duplicati():
    """Rimuove i piatti duplicati dal CSV, mantenendo solo l'originale"""
    if 'username' not in session or session['username'] != 'admin':
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        import csv
        import shutil
        from datetime import datetime
        
        data = request.get_json()
        duplicati = data.get('duplicati', [])
        
        if not duplicati:
            return jsonify({'error': 'Nessun duplicato specificato'}), 400
        
        # Crea lista di ID da rimuovere
        id_da_rimuovere = set()
        for gruppo in duplicati:
            id_da_rimuovere.update(gruppo['duplicati'])
        
        # Crea backup del file originale
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_file = f"menu_database_backup_{timestamp}.csv"
        shutil.copy(CSV_FILE, backup_file)
        
        # Leggi il CSV e filtra i duplicati
        righe_da_mantenere = []
        totale_prima = 0
        
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            fieldnames = reader.fieldnames
            
            for row in reader:
                totale_prima += 1
                piatto_id = int(row['id'])
                
                # Mantieni solo se l'ID NON è nella lista da rimuovere
                if piatto_id not in id_da_rimuovere:
                    righe_da_mantenere.append(row)
        
        totale_dopo = len(righe_da_mantenere)
        
        # Scrivi il CSV aggiornato
        with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(righe_da_mantenere)
        
        return jsonify({
            'success': True,
            'messaggio': f'Duplicati rimossi con successo!',
            'totale_prima': totale_prima,
            'totale_dopo': totale_dopo,
            'rimossi': totale_prima - totale_dopo,
            'backup': backup_file
        })
        
    except Exception as e:
        print(f"[ERROR] Errore rimozione duplicati: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# GESTIONE IMPOSTAZIONI (SETTINGS)
# ============================================================================

SETTINGS_FILE = 'settings.json'

def load_settings():
    """Carica le impostazioni dal file JSON"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    # Impostazioni default
    return {
        'mostra_prezzi': True,
        'nome_ristorante': 'Ristorante',
        'valuta': '€'
    }

def save_settings(settings):
    """Salva le impostazioni nel file JSON"""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

@app.route('/api/settings')
def get_settings():
    """Restituisce le impostazioni correnti (tutti possono leggere)"""
    if 'username' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401

    settings = load_settings()

    # Gli utenti normali vedono solo impostazioni pubbliche
    if session['username'] != 'admin':
        return jsonify({
            'mostra_prezzi': settings.get('mostra_prezzi', True),
            'valuta': settings.get('valuta', '€')
        })

    # Admin vede tutto
    return jsonify(settings)

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Aggiorna le impostazioni (solo admin)"""
    if 'username' not in session or session['username'] != 'admin':
        return jsonify({'error': 'Non autorizzato'}), 401

    try:
        data = request.get_json()
        settings = load_settings()

        # Aggiorna solo i campi forniti
        if 'mostra_prezzi' in data:
            settings['mostra_prezzi'] = bool(data['mostra_prezzi'])
        if 'nome_ristorante' in data:
            settings['nome_ristorante'] = data['nome_ristorante']
        if 'valuta' in data:
            settings['valuta'] = data['valuta']

        save_settings(settings)

        return jsonify({
            'success': True,
            'message': 'Impostazioni aggiornate',
            'settings': settings
        })

    except Exception as e:
        print(f"[ERROR] Errore aggiornamento settings: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# AVVIO APPLICAZIONE
# ============================================================================

if __name__ == '__main__':
    if not os.path.exists(CSV_FILE):
        print("⚠️  ATTENZIONE: File CSV non trovato!")
        print("Crea il file menu_database.csv con i dati del menu")
    else:
        print("✅ File CSV trovato!")
    
    print("=" * 60)
    print("🍽️  APP MENU RISTORANTE")
    print("=" * 60)
    print(f"📊 Database: {CSV_FILE}")
    print(f"📅 Formato date: GG/MM/AAAA o AAAA-MM-GG")
    print(f"👥 Utenti configurati: {len(USERS)}")
    print()
    print("Funzionalità disponibili:")
    print("  • Menu giornaliero con ricette")
    print("  • Sistema di votazione a stelle (utenti normali)")
    print("  • Statistiche voti (admin)")
    print("  • Lista spesa con AI classificazione (admin)")
    print("  • Selezione per settimana o date specifiche (admin)")
    print("  • Validazione e correzione CSV (admin)")
    print("  • Calcolo automatico settimana da data")
    print()
    
    # Verifica se Groq API è configurata
    if os.environ.get('GROQ_API_KEY'):
        print("✅ Groq AI: ATTIVO (classificazione intelligente)")
    else:
        print("⚠️  Groq AI: Non configurato (usa classificazione euristica)")
    
    print()
    print("Accedi da:")
    print("  • PC locale: http://localhost:5000")
    print("  • Smartphone: http://[IP-TUO-PC]:5000")
    print()
    print("Premi CTRL+C per fermare il server")
    print("=" * 60)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
