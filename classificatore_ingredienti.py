"""
Modulo intelligente per classificare ingredienti in categorie merceologiche
Usa cache locale + Groq AI GRATUITA per ingredienti sconosciuti
"""

import json
import os
import re
import requests

# File cache locale
CACHE_FILE = 'ingredienti_cache.json'

# Dizionario base per ingredienti comuni (fallback se offline)
CATEGORIE_BASE = {
    'Frutta e Verdura': [
        'pomodoro', 'cipolla', 'aglio', 'carota', 'sedano', 'prezzemolo', 'basilico',
        'rucola', 'insalata', 'lattuga', 'zucchina', 'melanzana', 'peperone', 'patata',
        'spinaci', 'funghi', 'limone', 'arancia', 'mela', 'fragola', 'frutti rossi',
        'pomodorini', 'ciliegino', 'datterini'
    ],
    'Macelleria e Pescheria': [
        'carne', 'manzo', 'vitello', 'maiale', 'pollo', 'tacchino', 'costoletta',
        'filetto', 'salsiccia', 'pancetta', 'guanciale', 'prosciutto', 'bresaola',
        'pesce', 'branzino', 'salmone', 'tonno', 'gamberi', 'vongole', 'carne macinata'
    ],
    'Latticini e Uova': [
        'latte', 'panna', 'burro', 'mascarpone', 'ricotta', 'mozzarella',
        'parmigiano', 'grana', 'pecorino', 'formaggio', 'yogurt', 'uova', 'uovo',
        'grana padano', 'parmigiano reggiano'
    ],
    'Dispensa e Cereali': [
        'pasta', 'riso', 'farina', 'pane', 'pangrattato', 'olio', 'aceto', 'sale',
        'pepe', 'zucchero', 'zafferano', 'brodo', 'passata', 'pelati', 'fagioli',
        'ceci', 'lenticchie', 'lasagne', 'besciamella', 'sugo', 'olio evo',
        'riso carnaroli', 'riso arborio'
    ],
    'Bevande': [
        'vino', 'birra', 'acqua', 'caffè', 'tè', 'succo', 'vino bianco', 'vino rosso'
    ],
    'Dolci e Dessert': [
        'cioccolato', 'cacao', 'gelatina', 'vaniglia', 'mandorle', 'nocciole',
        'savoiardi', 'biscotti', 'miele', 'marmellata', 'cacao amaro', 'zucchero a velo'
    ],
    'Surgelati': [
        'piselli surgelati', 'spinaci surgelati', 'gelato'
    ]
}


class ClassificatoreIngredienti:
    """
    Classificatore intelligente di ingredienti con cache e Groq AI GRATUITA
    """
    
    def __init__(self, use_ai=True):
        self.use_ai = use_ai
        self.cache = self._load_cache()
        self.groq_api_key = os.environ.get('GROQ_API_KEY')
        self.stats = {
            'cache_hits': 0,
            'base_hits': 0,
            'ai_queries': 0,
            'unknown': 0
        }
    
    def _load_cache(self):
        """Carica la cache degli ingredienti già classificati"""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARNING] Errore caricamento cache: {e}")
                return {}
        return {}
    
    def _save_cache(self):
        """Salva la cache su file"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Errore salvataggio cache: {e}")
    
    def _normalize_ingredient(self, ingrediente):
        """Normalizza il nome dell'ingrediente per il matching"""
        return ingrediente.lower().strip()
    
    def _cerca_in_dizionario_base(self, ingrediente_norm):
        """Cerca l'ingrediente nel dizionario base"""
        for categoria, keywords in CATEGORIE_BASE.items():
            for keyword in keywords:
                if keyword in ingrediente_norm or ingrediente_norm in keyword:
                    return categoria
        return None
    
    def _classifica_con_ai(self, ingrediente):
        """
        Classifica l'ingrediente usando Groq AI (GRATUITA)
        """
        if not self.use_ai:
            return None
        
        try:
            # Prova con Groq se disponibile
            if self.groq_api_key:
                result = self._classifica_groq(ingrediente)
                if result:
                    return result
        except Exception as e:
            print(f"[DEBUG] Groq non disponibile: {e}")
        
        # Fallback: classificazione euristica intelligente
        return self._classifica_euristica(ingrediente)
    
    def _classifica_groq(self, ingrediente):
        """
        Classifica usando Groq API (GRATUITA E VELOCISSIMA)
        """
        if not self.groq_api_key:
            return None
        
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            
            payload = {
                "model": "llama-3.1-8b-instant",  # Modello veloce e gratuito
                "messages": [
                    {
                        "role": "system",
                        "content": "Sei un esperto di alimenti. Classifica gli ingredienti in categorie merceologiche. Rispondi SOLO con il nome della categoria."
                    },
                    {
                        "role": "user",
                        "content": f"""Classifica questo ingrediente in UNA di queste categorie:
- Frutta e Verdura
- Macelleria e Pescheria
- Latticini e Uova
- Dispensa e Cereali
- Bevande
- Dolci e Dessert
- Surgelati
- Altri

Ingrediente: {ingrediente}

Rispondi SOLO con il nome della categoria."""
                    }
                ],
                "max_tokens": 50,
                "temperature": 0
            }
            
            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                categoria = data['choices'][0]['message']['content'].strip()
                
                # Valida la risposta
                categorie_valide = [
                    'Frutta e Verdura', 'Macelleria e Pescheria', 'Latticini e Uova',
                    'Dispensa e Cereali', 'Bevande', 'Dolci e Dessert', 'Surgelati', 'Altri'
                ]
                
                if categoria in categorie_valide:
                    return categoria
                
                # Prova a estrarre la categoria dalla risposta
                for cat in categorie_valide:
                    if cat.lower() in categoria.lower():
                        return cat
            
        except Exception as e:
            print(f"[DEBUG] Errore Groq API: {e}")
        
        return None
    
    def _classifica_euristica(self, ingrediente):
        """
        Classificazione euristica MIGLIORATA basata su pattern comuni
        """
        ing_norm = self._normalize_ingredient(ingrediente)
        
        # Pattern MOLTO più completi per riconoscimento
        patterns = {
            'Frutta e Verdura': [
                r'\bfrutta\b', r'\bverdura\b', r'\binsalata\b', r'\bortaggi\b',
                r'\bfoglie\b', r'\bverdi\b', r'\bfresco\b', r'\bpomodor\w+',
                r'\bcipolle?\b', r'\baglio\b', r'\bcarote?\b', r'\bsedano\b',
                r'\bzucchine?\b', r'\bmelanzane?\b', r'\bpeperon\w+', r'\bpatate?\b',
                r'\bspinaci\b', r'\bfunghi\b', r'\blimone\b', r'\barancia\b',
                r'\bmela\b', r'\bfragol\w+', r'\bfrutti\b', r'\bverdure\b',
                r'\bbasilic\w+', r'\bprezzem\w+', r'\brucola\b', r'\blattuga\b',
                r'\bradicchio\b', r'\bbroccoli\b', r'\bcavolfiore\b', r'\basparagi\b',
                r'\bfinocchio\b', r'\bcetriolo\b', r'\bpeperoncin\w+', r'\bciliegin\w+',
                r'\bdatterini\b', r'\brosmarino\b', r'\bsalvia\b', r'\btimo\b',
                r'\borigano\b', r'\bmenta\b'
            ],
            'Macelleria e Pescheria': [
                r'\bcarne\b', r'\bpesce\b', r'\bfiletto\b', r'\bfetta\b',
                r'\bmacinato\b', r'\btrancio\b', r'\bfesa\b', r'\btagliata\b',
                r'\bvitello\b', r'\bmanzo\b', r'\bmaiale\b', r'\bpollo\b',
                r'\btacchino\b', r'\bcostoletta\b', r'\bsalsiccia\b', r'\bpancetta\b',
                r'\bguanciale\b', r'\bprosciutto\b', r'\bbresaola\b', r'\bspeck\b',
                r'\bsalmone\b', r'\btonno\b', r'\bgamberi\b', r'\bvongole\b',
                r'\bcozze\b', r'\bcalamari\b', r'\bpolpo\b', r'\bbranzino\b',
                r'\borata\b', r'\bmerluzzo\b', r'\bacciughe\b', r'\balici\b'
            ],
            'Latticini e Uova': [
                r'\blatte\b', r'\bformaggi?o?\b', r'\buova?\b', r'\bpanna\b',
                r'\bburro\b', r'\byogurt\b', r'\balbume\b', r'\btuorlo\b',
                r'\bmascarpone\b', r'\bricotta\b', r'\bmozzarella\b',
                r'\bparmigiano\b', r'\bgrana\b', r'\bpecorino\b', r'\bscamorza\b',
                r'\bprovola\b', r'\bfontina\b', r'\bgorgonzola\b', r'\btaleggio\b',
                r'\bstracchino\b', r'\bcrescenza\b', r'\bcream\b'
            ],
            'Dispensa e Cereali': [
                r'\bpasta\b', r'\briso\b', r'\bfarina\b', r'\bcereali\b',
                r'\bscatola\b', r'\bconserva\b', r'\bsott.*olio\b', r'\bsecco\b',
                r'\bolio\b', r'\baceto\b', r'\bsale\b', r'\bpepe\b', r'\bspezie\b',
                r'\blasagne\b', r'\bpane\b', r'\bpangrattato\b', r'\bbrodo\b',
                r'\bfagioli\b', r'\bceci\b', r'\blenticchie\b', r'\bpelati\b',
                r'\bpassata\b', r'\bconcentrato\b', r'\bsugo\b', r'\bpesto\b',
                r'\bzafferano\b', r'\bcurry\b', r'\bpaprika\b', r'\bcurcuma\b',
                r'\bpeperoncino\b', r'\bzenzero\b', r'\bcannella\b', r'\bnoc\w+\s+moscata\b',
                r'\balloro\b', r'\bdado\b', r'\bolive\b', r'\bcapperi\b',
                r'\bfarro\b', r'\borzo\b', r'\bquinoa\b', r'\bcouscous\b',
                r'\bpolenta\b', r'\bspaghetti\b', r'\bpenne\b', r'\brigatoni\b',
                r'\btagliatelle\b', r'\bbesciamella\b', r'\bragù\b', r'\bevo\b',
                r'\bextravergine\b', r'\bbalsamico\b'
            ],
            'Bevande': [
                r'\bvino\b', r'\bbirra\b', r'\bacqua\b', r'\bbevanda\b',
                r'\bliquore\b', r'\bcaffè\b', r'\btè\b', r'\bsucco\b',
                r'\bbianco\b.*\bvino\b', r'\brosso\b.*\bvino\b', r'\bmarsala\b'
            ],
            'Dolci e Dessert': [
                r'\bdolce\b', r'\bcioccolat\b', r'\bcacao\b', r'\bzucchero\b',
                r'\bmiele\b', r'\bcrema\b', r'\bgelat\b', r'\bbiscott\b',
                r'\btorta\b', r'\bdessert\b', r'\bsavoiardi\b', r'\bvaniglia\b',
                r'\bmandorle\b', r'\bnocciole\b', r'\bgelatina\b', r'\bnoci\b',
                r'\bpistacchi\b', r'\bpinoli\b', r'\buvetta\b', r'\bcanditi\b',
                r'\bamarett\w+', r'\bcantucc\w+', r'\ba\s+velo\b', r'\bamaro\b',
                r'\bfondente\b', r'\bgocce\b.*\bcioccolat\b'
            ],
            'Surgelati': [
                r'\bsurgelat\b', r'\bcongelat\b', r'\bfrozen\b', r'\bghiaccio\b'
            ]
        }
        
        # Cerca pattern con priorità
        for categoria, pattern_list in patterns.items():
            for pattern in pattern_list:
                if re.search(pattern, ing_norm, re.IGNORECASE):
                    return categoria
        
        return 'Altri'
    
    def classifica(self, ingrediente):
        """
        Classifica un ingrediente (metodo principale)
        
        Returns:
            tuple: (categoria, fonte) dove fonte è 'cache', 'base', 'ai', o 'unknown'
        """
        ing_norm = self._normalize_ingredient(ingrediente)
        
        # 1. Controlla cache
        if ing_norm in self.cache:
            self.stats['cache_hits'] += 1
            return (self.cache[ing_norm], 'cache')
        
        # 2. Controlla dizionario base
        categoria = self._cerca_in_dizionario_base(ing_norm)
        if categoria:
            self.stats['base_hits'] += 1
            # Salva in cache per la prossima volta
            self.cache[ing_norm] = categoria
            self._save_cache()
            return (categoria, 'base')
        
        # 3. Usa AI (Groq)
        categoria = self._classifica_con_ai(ingrediente)
        if categoria and categoria != 'Altri':
            self.stats['ai_queries'] += 1
            # Salva in cache
            self.cache[ing_norm] = categoria
            self._save_cache()
            return (categoria, 'ai')
        
        # 4. Fallback
        self.stats['unknown'] += 1
        categoria = 'Altri'
        self.cache[ing_norm] = categoria
        self._save_cache()
        return (categoria, 'unknown')
    
    def classifica_lista(self, ingredienti):
        """
        Classifica una lista di ingredienti
        
        Returns:
            dict: {ingrediente: categoria}
        """
        risultati = {}
        for ingrediente in ingredienti:
            categoria, fonte = self.classifica(ingrediente)
            risultati[ingrediente] = categoria
        return risultati
    
    def get_stats(self):
        """Restituisce statistiche di utilizzo"""
        total = sum(self.stats.values())
        return {
            **self.stats,
            'total': total,
            'cache_size': len(self.cache)
        }
    
    def print_stats(self):
        """Stampa statistiche"""
        stats = self.get_stats()
        print("\n" + "=" * 50)
        print("STATISTICHE CLASSIFICATORE INGREDIENTI")
        print("=" * 50)
        print(f"Ricerche totali: {stats['total']}")
        print(f"  • Cache hits: {stats['cache_hits']}")
        print(f"  • Dizionario base: {stats['base_hits']}")
        print(f"  • Groq AI queries: {stats['ai_queries']}")
        print(f"  • Sconosciuti: {stats['unknown']}")
        print(f"Dimensione cache: {stats['cache_size']} ingredienti")
        print("=" * 50 + "\n")


# Istanza globale singleton
_classificatore_instance = None

def get_classificatore(use_ai=True):
    """Restituisce l'istanza singleton del classificatore"""
    global _classificatore_instance
    if _classificatore_instance is None:
        _classificatore_instance = ClassificatoreIngredienti(use_ai=use_ai)
    return _classificatore_instance


# Per compatibilità con il codice esistente
def classifica_ingrediente(ingrediente):
    """Funzione di compatibilità"""
    classificatore = get_classificatore()
    categoria, fonte = classificatore.classifica(ingrediente)
    return categoria


# Test del modulo
if __name__ == '__main__':
    print("TEST CLASSIFICATORE INGREDIENTI CON GROQ AI GRATUITA\n")
    
    classificatore = ClassificatoreIngredienti(use_ai=True)
    
    # Test con ingredienti vari
    test_ingredienti = [
        'Pomodori datterini',
        'Filetto di branzino',
        'Grana Padano DOP',
        'Olio extravergine toscano',
        'Aceto balsamico di Modena',
        'Curcuma in polvere',
        'Quinoa tricolore',
        'Edamame'
    ]
    
    print("Classificazione ingredienti:\n")
    for ingrediente in test_ingredienti:
        categoria, fonte = classificatore.classifica(ingrediente)
        print(f"  {ingrediente:35} → {categoria:25} [{fonte}]")
    
    classificatore.print_stats()
