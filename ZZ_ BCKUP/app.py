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
# FUNZIONI PER CALCOLARE QUANTITÃ€
# ============================================================================

def parse_quantita(quantita_str):
    """
    Converte una stringa di quantitÃ  in un numero e unitÃ 
    Es: "350g" -> (350, "g"), "1.5 kg" -> (1500, "g"), "q.b." -> (0, "qb")
    """
    try:
        quantita_str = quantita_str.strip().lower()
        
        # Gestisci "q.b." o "quanto basta"
        if quantita_str in ['q.b.', 'qb', 'quanto basta', 'a piacere']:
            return (0, 'qb')
        
        # Cerca numero seguito da unitÃ 
        match = re.match(r'(\d+\.?\d*)\s*(kg|g|l|ml|cl|unitÃ |pezzi|bicchiere|bustina|costa|stecca|foglio|fogli|piccola)?', quantita_str)
        
        if match:
            numero = float(match.group(1))
            unita = match.group(2) if match.group(2) else 'unitÃ '
            
            # Converti tutto in unitÃ  base
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
    """Somma due quantitÃ """
    val1, unit1 = parse_quantita(q1_str)
    val2, unit2 = parse_quantita(q2_str)
    
    # Se una Ã¨ q.b., mantieni l'altra
    if unit1 == 'qb':
        return formatta_quantita(val2, unit2)
    if unit2 == 'qb':
        return formatta_quantita(val1, unit1)
    
    # Se unitÃ  diverse, mantieni la prima
    if unit1 != unit2:
        return formatta_quantita(val1, unit1)
    
    return formatta_quantita(val1 + val2, unit1)

def moltiplica_quantita(quantita_str, moltiplicatore):
    """Moltiplica una quantitÃ  per un numero"""
    val, unit = parse_quantita(quantita_str)
    
    if unit == 'qb':
        return 'q.b.'
    
    return formatta_quantita(val * moltiplicatore, unit)

def formatta_quantita(valore, unita):
    """Formatta una quantitÃ  per la visualizzazione"""
    if unita == 'qb':
        return 'q.b.'
    
    # Converti grammi in kg se > 1000
    if unita == 'g' and valore >= 1000:
        return f"{valore/1000:.1f} kg"
    
    # Converti ml in litri se > 1000
    if unita == 'ml' and valore >= 1000:
        return f"{valore/1000:.1f} l"
    
    # Se Ã¨ un numero intero, mostra senza decimali
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
    include_ingredienti: se True, include ingredienti e quantitÃ  (solo per admin)
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
                            'prezzo': f"â‚¬{float(row['prezzo']):.2f}"
                        }
                        
                        # Aggiungi ricetta se presente
                        if 'ricetta' in row and row['ricetta'].strip():
                            piatto['ricetta'] = row['ricetta'].strip()
                        
                        # CALCOLA AUTOMATICAMENTE LA SETTIMANA DALLA DATA
                        piatto['settimana'] = calcola_settimana(data_piatto)
                        
                        # Aggiungi ingredienti e quantitÃ  SOLO se richiesto (per admin)
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
    Calcola la lista della spesa aggregata per piÃ¹ date, organizzata per categoria merceologica
    Usa il classificatore intelligente con Groq AI
    """
    lista_spesa = {}  # {ingrediente: quantitÃ _totale}
    
    for data in date_selezionate:
        menu = load_menu_from_csv(data, include_ingredienti=True)
        
        for piatto in menu['piatti']:
            if 'ingredienti' in piatto and 'quantita' in piatto:
                for idx, ingrediente in enumerate(piatto['ingredienti']):
                    quantita = piatto['quantita'][idx] if idx < len(piatto['quantita']) else 'q.b.'
                    
                    # Moltiplica per numero persone
                    quantita_moltiplicata = moltiplica_quantita(quantita, num_persone)
                    
                    # Aggrega con quantitÃ  esistente
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
    
    return render_template('login.html')

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
    
    # Admin non puÃ² votare
    if session['username'] == 'admin':
        return jsonify({'error': 'Admin non puÃ² votare'}), 403
    
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

if __name__ == '__main__':
    if not os.path.exists(CSV_FILE):
        print("âš ï¸  ATTENZIONE: File CSV non trovato!")
        print("Crea il file menu_database.csv con i dati del menu")
    else:
        print("âœ… File CSV trovato!")
    
    print("=" * 60)
    print("ðŸ½ï¸  APP MENU RISTORANTE")
    print("=" * 60)
    print(f"ðŸ“Š Database: {CSV_FILE}")
    print(f"ðŸ“… Formato date: GG/MM/AAAA o AAAA-MM-GG")
    print(f"ðŸ‘¥ Utenti configurati: {len(USERS)}")
    print()
    print("FunzionalitÃ  disponibili:")
    print("  â€¢ Menu giornaliero con ricette")
    print("  â€¢ Sistema di votazione a stelle (utenti normali)")
    print("  â€¢ Statistiche voti (admin)")
    print("  â€¢ Lista spesa con AI classificazione (admin)")
    print("  â€¢ Selezione per settimana o date specifiche (admin)")
    print("  â€¢ Validazione e correzione CSV (admin)")
    print("  â€¢ Calcolo automatico settimana da data")
    print()
    
    # Verifica se Groq API Ã¨ configurata
    if os.environ.get('GROQ_API_KEY'):
        print("âœ… Groq AI: ATTIVO (classificazione intelligente)")
    else:
        print("âš ï¸  Groq AI: Non configurato (usa classificazione euristica)")
    
    print()
    print("Accedi da:")
    print("  â€¢ PC locale: http://localhost:5000")
    print("  â€¢ Smartphone: http://[IP-TUO-PC]:5000")
    print()
    print("Premi CTRL+C per fermare il server")
    print("=" * 60)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000)