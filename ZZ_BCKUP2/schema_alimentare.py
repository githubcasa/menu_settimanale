"""
Schema Alimentare - Dott.ssa Gina Forrisi
Piano nutrizionale con frequenze settimanali e quantità precise
"""

# ============================================================================
# QUANTITÀ PER PASTO (in grammi)
# ============================================================================

QUANTITA = {
    'pranzo': {
        'carboidrati': {
            'pasta_riso_cereali': 80,
            'pane_integrale': 120,
            'patate': 250,
            'gnocchi': 150,
            'mais': 150
        },
        'proteine': {
            'legumi_scatola': 120,
            'legumi_secchi': 60,
            'uova': 2,
            'albume': 200,
            'formaggi_freschi': 100,
            'fiocchi_latte': 1,  # vasetto
            'formaggi_stagionati': 40,
            'carne_bianca': 150,
            'carne_rossa': 150,
            'carne_maiale': 120,
            'hamburger': 100,
            'pesce_bianco': 150,
            'pesce_grasso': 120,
            'crostacei_molluschi': 150,
            'tonno_scatola': 100,
            'affettati': 50
        },
        'verdure': 200,
        'olio_evo': 2  # cucchiai (20g)
    },
    'cena': {
        'carboidrati': {
            'pasta_riso_cereali': 100,  # +20g rispetto pranzo
            'pane_integrale': 150,       # +30g
            'patate': 300,               # +50g
            'gnocchi': 180,              # +30g
            'mais': 200                  # +50g
        },
        'proteine': {
            # Stesse quantità del pranzo
            'legumi_scatola': 120,
            'legumi_secchi': 60,
            'uova': 2,
            'albume': 200,
            'formaggi_freschi': 100,
            'fiocchi_latte': 1,
            'formaggi_stagionati': 40,
            'carne_bianca': 150,
            'carne_rossa': 150,
            'carne_maiale': 120,
            'hamburger': 100,
            'pesce_bianco': 150,
            'pesce_grasso': 120,
            'crostacei_molluschi': 150,
            'tonno_scatola': 100,
            'affettati': 50
        },
        'verdure': 200,
        'olio_evo': 2
    }
}

# ============================================================================
# FREQUENZE SETTIMANALI (numero di porzioni a settimana)
# ============================================================================

FREQUENZE_SETTIMANALI = {
    'legumi': {'min': 2, 'max': 2},
    'uova': {'min': 0, 'max': 2},
    'carne_bianca': {'min': 0, 'max': 3},
    'carne_rossa': {'min': 0, 'max': 2},
    'formaggi_freschi': {'min': 0, 'max': 3},
    'formaggi_stagionati': {'min': 0, 'max': 1},
    'pesce_bianco': {'min': 2, 'max': 4},
    'pesce_grasso': {'min': 0, 'max': 1},
    'crostacei_molluschi': {'min': 0, 'max': 1},
    'tonno_scatola': {'min': 0, 'max': 1},
    'affettati': {'min': 0, 'max': 1}
}

# ============================================================================
# MAPPATURA INGREDIENTI -> CATEGORIA PROTEICA
# ============================================================================

CATEGORIE_PROTEINE = {
    'legumi': [
        'legumi', 'fagioli', 'ceci', 'lenticchie', 'piselli', 'fave',
        'borlotti', 'cannellini', 'pasta di legumi'
    ],
    'uova': [
        'uova', 'uovo', 'albume', 'frittata'
    ],
    'carne_bianca': [
        'pollo', 'tacchino', 'petto di pollo', 'petto di tacchino',
        'fesa di tacchino', 'carne bianca'
    ],
    'carne_rossa': [
        'manzo', 'vitello', 'carne rossa', 'bistecca', 'tagliata',
        'lonza', 'hamburger di vitello'
    ],
    'formaggi_freschi': [
        'ricotta', 'mozzarella', 'fiocchi di latte', 'feta',
        'robiola', 'primo sale', 'caprino'
    ],
    'formaggi_stagionati': [
        'parmigiano', 'grana', 'pecorino', 'parmigiano reggiano',
        'grana padano'
    ],
    'pesce_bianco': [
        'merluzzo', 'nasello', 'platessa', 'sogliola', 'orata',
        'spigola', 'branzino'
    ],
    'pesce_grasso': [
        'salmone', 'trota', 'sgombro', 'tonno fresco', 'alici'
    ],
    'crostacei_molluschi': [
        'gamberi', 'gamberetti', 'calamari', 'vongole', 'cozze',
        'polpo', 'frutti di mare'
    ],
    'tonno_scatola': [
        'tonno in scatola', 'tonno al naturale', 'tonno sgocciolato'
    ],
    'affettati': [
        'bresaola', 'prosciutto', 'salmone affumicato'
    ]
}

# ============================================================================
# REGOLE IMPORTANTI
# ============================================================================

REGOLE = {
    'piselli_sono_legumi': True,
    'patate_non_sono_verdure': True,
    'quantita_a_crudo': True,
    'olio_cucchiaio': 10,  # grammi
    'pasto_libero_settimana': 1,
    'acqua_litri_giorno': 2,
    'caffe_max_giorno': 3,
    'verdure_cottura_preferita': 'vapore'
}

# ============================================================================
# FUNZIONI DI UTILITÀ
# ============================================================================

def identifica_categoria_proteica(ingredienti_list):
    """
    Identifica la categoria proteica di un piatto basandosi sugli ingredienti
    Args:
        ingredienti_list: lista di ingredienti (stringa separata da |)
    Returns:
        str: categoria proteica o None
    """
    if isinstance(ingredienti_list, str):
        ingredienti_list = [i.strip().lower() for i in ingredienti_list.split('|')]
    else:
        ingredienti_list = [i.lower() for i in ingredienti_list]

    # Controlla ogni categoria
    for categoria, keywords in CATEGORIE_PROTEINE.items():
        for ingrediente in ingredienti_list:
            for keyword in keywords:
                if keyword in ingrediente:
                    return categoria

    return None


def verifica_frequenze_settimanali(piatti_settimana):
    """
    Verifica se i piatti della settimana rispettano le frequenze
    Args:
        piatti_settimana: lista di dict con 'ingredienti' o 'categoria_proteica'
    Returns:
        dict: {categoria: count, ...}, bool: valido
    """
    conteggi = {cat: 0 for cat in FREQUENZE_SETTIMANALI.keys()}

    for piatto in piatti_settimana:
        if 'categoria_proteica' in piatto:
            cat = piatto['categoria_proteica']
        else:
            cat = identifica_categoria_proteica(piatto.get('ingredienti', ''))

        if cat and cat in conteggi:
            conteggi[cat] += 1

    # Verifica se rispetta i limiti
    valido = True
    errori = []

    for categoria, freq in FREQUENZE_SETTIMANALI.items():
        count = conteggi.get(categoria, 0)
        if count < freq['min']:
            valido = False
            errori.append(f"{categoria}: {count} (minimo {freq['min']})")
        if count > freq['max']:
            valido = False
            errori.append(f"{categoria}: {count} (massimo {freq['max']})")

    return conteggi, valido, errori


def stampa_report_frequenze(conteggi):
    """Stampa un report leggibile delle frequenze"""
    print("\n" + "="*60)
    print("REPORT FREQUENZE SETTIMANALI")
    print("="*60)

    for categoria, freq in FREQUENZE_SETTIMANALI.items():
        count = conteggi.get(categoria, 0)
        target = f"{freq['min']}-{freq['max']}" if freq['min'] != freq['max'] else str(freq['min'])
        status = "✅" if freq['min'] <= count <= freq['max'] else "❌"
        print(f"{status} {categoria:25} {count} / {target}")

    print("="*60)


# ============================================================================
# TEST DEL MODULO
# ============================================================================

if __name__ == '__main__':
    print("TEST SCHEMA ALIMENTARE")
    print("="*60)

    # Test identificazione categorie
    test_ingredienti = [
        "Pasta Integrale|Petto di Pollo|Zucchine|Olio EVO",
        "Riso|Salmone fresco|Broccoli|Olio EVO",
        "Pane|Parmigiano|Cetrioli|Olio EVO",
        "Pasta|Ceci|Pomodorini|Olio EVO"
    ]

    print("\nTest identificazione categorie proteiche:")
    for ing in test_ingredienti:
        cat = identifica_categoria_proteica(ing)
        print(f"  {ing[:40]:40} -> {cat}")

    # Test frequenze
    print("\n\nTest verifica frequenze:")
    piatti_test = [
        {'ingredienti': 'Pasta|Ceci|Pomodoro'},
        {'ingredienti': 'Riso|Lenticchie|Carote'},
        {'ingredienti': 'Pane|Uova|Spinaci'},
        {'ingredienti': 'Pasta|Pollo|Zucchine'},
        {'ingredienti': 'Riso|Pollo|Peperoni'},
        {'ingredienti': 'Patate|Orata|Fagiolini'},
        {'ingredienti': 'Pasta|Merluzzo|Pomodorini'},
        {'ingredienti': 'Riso|Manzo|Insalata'},
        {'ingredienti': 'Gnocchi|Mozzarella|Pomodoro'},
        {'ingredienti': 'Pasta|Salmone|Asparagi'},
        {'ingredienti': 'Riso|Gamberetti|Zucchine'},
        {'ingredienti': 'Pane|Ricotta|Verdure'},
        {'ingredienti': 'Pasta|Tonno in scatola|Cetrioli'},
        {'ingredienti': 'Patate|Tacchino|Cavolfiore'}
    ]

    conteggi, valido, errori = verifica_frequenze_settimanali(piatti_test)
    stampa_report_frequenze(conteggi)

    if valido:
        print("\n✅ Menu settimanale VALIDO!")
    else:
        print("\n❌ Menu settimanale NON valido:")
        for err in errori:
            print(f"   - {err}")
