"""Word lists per language: courtesy titles, public roles, capitalised words that are not names."""

from __future__ import annotations

# Courtesy and professional titles that precede a person's name.
TITLES: dict[str, list[str]] = {
    "it": [r"sig\.(?:ra|na)?", r"sigg\.", r"signor[ae]?", r"sig\.ra", r"dott\.(?:ssa)?", r"dr\.(?:ssa)?",
           r"avv\.(?:to)?", r"geom\.", r"ing\.", r"arch\.", r"rag\.", r"per\.\s?ind\.", r"p\.\s?i\.",
           r"prof\.(?:ssa)?", r"cav\.", r"comm\.", r"on\.", r"egr\.", r"gent\.(?:mo|ma)?", r"spett\.(?:le)?"],
    "en": [r"mr\.?", r"mrs\.?", r"ms\.?", r"miss", r"mx\.?", r"dr\.?", r"prof\.?", r"sir", r"dame",
           r"lady", r"lord", r"cllr\.?", r"rev\.?"],
    "es": [r"d\.", r"dña\.", r"don", r"doña", r"sr\.", r"sra\.", r"srta\.", r"señor", r"señora"],
    "fr": [r"m\.", r"mme", r"mlle", r"monsieur", r"madame", r"mademoiselle", r"me", r"maître"],
    "de": [r"herr(?:n)?", r"frau", r"dr\.", r"prof\."],
}

# Words announcing that a public role holder is named next (the name may stay readable).
ROLES: dict[str, list[str]] = {
    "it": [r"sindac[oa]", r"vice\s*sindac[oa]", r"assessor[ei]", r"assessora", r"consiglier[ei]", r"consigliera",
           r"dirigente", r"segretari[oa]", r"president[ei]", r"presidentessa", r"responsabile",
           r"funzionari[oa]", r"r\.?u\.?p\.?", r"commissari[oa]", r"revisor[ei]", r"direttor[ei]", r"direttrice",
           r"comandante", r"istruttor[ei]", r"istruttrice", r"notaio", r"ufficiale\s+rogante", r"prefetto",
           r"questore", r"vicesegretari[oa]", r"capo\s*(?:settore|servizio|area)", r"titolare\s+di\s+p\.?o\.?",
           r"posizione\s+organizzativa", r"economo", r"ragioniere\s+capo", r"delegat[oa]\s+del\s+sindaco",
           r"dirigenza", r"incarico\s+dirigenziale", r"sostituit[oa]\s+in\s+caso\s+di\s+assenza",
           r"sostituzione,?\s+in\s+caso\s+di\s+assenza", r"(?:il\s+)?documento\s+[èe]\s+stato\s+firmato\s+da",
           r"parere\s+(?:favorevole|tecnico|contabile|di\s+regolarit[àa])", r"visto\s+di\s+regolarit[àa]",
           r"protezione\s+dei\s+dati", r"\bdpo\b", r"\brpd\b", r"firmato\s+digitalmente\s+da",
           r"sottoscritto\s+digitalmente\s+da", r"il\s+redattore", r"l['’]estensore", r"verbalizzante",
           r"rappresentante\s+legale\s+dell?['’]?\s*(?:ente|comune|amministrazione)", r"agente",
           r"ispettore", r"sovrintendente", r"assistente\s+sociale", r"educator[ei]", r"collaborator[ei]"],
    "en": [r"mayor", r"deputy\s+mayor", r"councillor", r"chief\s+executive", r"chair(?:man|woman|person)?",
           r"director", r"head\s+of\s+\w+", r"officer", r"clerk", r"secretary", r"treasurer", r"auditor",
           r"monitoring\s+officer", r"leader\s+of\s+the\s+council", r"cabinet\s+member"],
    "es": [r"alcalde(?:sa)?", r"concejal(?:a)?", r"teniente\s+de\s+alcalde", r"secretari[oa]", r"interventor(?:a)?",
           r"tesorer[oa]", r"director(?:a)?", r"jef[ea]\s+de\s+\w+", r"president[ea]"],
    "fr": [r"maire", r"adjoint(?:e)?\s+au\s+maire", r"conseill(?:er|ère)\s+municipal(?:e)?", r"secrétaire",
           r"directeur|directrice", r"président(?:e)?", r"préfet"],
    "de": [r"bürgermeister(?:in)?", r"stadtrat|stadträtin", r"gemeinderat|gemeinderätin", r"amtsleiter(?:in)?",
           r"dezernent(?:in)?", r"landrat|landrätin", r"kämmerer|kämmerin", r"vorsitzende(?:r)?"],
}

# Capitalised words that are not names: they cut a sequence of name tokens.
NOT_NAMES: dict[str, str] = {
    "it": """
    il lo la i gli le un una uno in con per che del della dei degli delle dal dalla di da a e ed o al alla ai
    nel nella nei sul sulla tra fra su non si se come ove quale quali presso ne
    visto vista visti viste considerato considerata considerati preso dato atteso ritenuto rilevato richiamato
    richiamata accertato accertata dichiara dichiarato delibera deliberazione determina determinazione decreta
    ordina ordinanza dispone approva oggetto premesso precisato evidenziato sentito acquisito verificato
    comune citta città provincia regione stato repubblica italia italiana ufficio settore servizio servizi area
    sindaco sindaca vicesindaco assessore assessora consigliere consigliera consiglieri dirigente segretario
    segretaria generale presidente responsabile funzionario funzionaria direttore direttrice commissario
    commissaria revisore comandante istruttore procedimento giunta consiglio comunale municipale albo pretorio
    protocollo prot allegato allegati art artt articolo legge decreto regolamento euro eur iva totale importo
    pagina pag tel fax email mail pec via viale piazza piazzale corso borgo vicolo largo località frazione
    sig sigg signor signora signori dott avv geom ing arch rag prof spett gentile egregio egr nato nata
    residente cf codice fiscale partita cap tribunale corte tar ministero agenzia azienda ente enti istituto
    scuola università banca polizia carabinieri prefettura questura asl ulss inps inail anac srl spa snc sas
    coop società ditta impresa studio associazione fondazione cooperativa consorzio onlus aps odv asd ssd
    gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre lunedì
    martedì mercoledì giovedì venerdì sabato domenica parte parti numero data anno mese ore lavori opere
    progetto contratto convenzione accordo avviso bando gara lotto cig cup durc pnrr dpr dlgs tuel lgs
    elenco tabella totale unico unica primo prima secondo seconda terzo terza nuovo nuova vecchio
    santo santa san sant chiesa parrocchia veneto treviso venezia padova vicenza verona roma milano
    ufficiale gazzetta bollettino nord sud est ovest centro vice dirigenza dirigenziale beneficiario
    beneficiaria beneficiari debitore creditore fornitore fornitori capitolo missione programma titolo
    impegno accertamento liquidazione mandato reversale esercizio bilancio cassa quota spesa entrata
    piano ordinari ordinario straordinario generale generali tecnico tecnica finanziario finanziaria
    economico economica sociale sociali persona persone ambiente cultura istruzione sport turismo
    polizia locale civile difesa sicurezza protezione commissione esaminatrice selezione concorso
    procedura graduatoria allegato prova prove esame esami requisiti domanda domande termini scadenza
    sede sedi sito portale online note nota firma firmato digitalmente documento documenti informatico
    interviene intervengono risponde rispondono chiede chiedono dichiara dichiarano presenta presentano
    comunica replica precisa propone ringrazia evidenzia sottolinea ricorda afferma conclude illustra
    relaziona entra entrano esce escono assume apre chiude vota votano approvato approvata respinto
    respinta prende prendono passa interrompe riprende sospende saluta legge illustrano spiega
    bar carrozzeria officina autofficina pizzeria ristorante trattoria osteria gioielleria cartoleria
    cartolibreria libreria ferramenta farmacia panificio macelleria tabaccheria edicola parrucchiere
    estetica hotel albergo agriturismo bazar market supermercato negozio boutique gelateria pasticceria
    passaggio sottoportico galleria portico portici calle rampa
    """,
    "en": """
    the a an of and or in on at to for by with from as is are was were be been this that these those
    council borough county city district parish town village county mayor councillor officer director
    chief executive head department committee cabinet meeting minutes agenda item report decision notice
    order act regulations section schedule appendix annex page tel telephone fax email street road
    avenue lane drive close court place square way mr mrs ms miss dr prof sir born resident address
    january february march april may june july august september october november december monday tuesday
    wednesday thursday friday saturday sunday limited ltd plc llp inc company trust charity foundation
    association society bank police nhs hmrc dvla united kingdom england wales scotland northern ireland
    london
    """,
    "es": """
    el la los las un una de del y o en con por para que al se ayuntamiento consejo junta municipal
    alcalde alcaldesa concejal secretario secretaria interventor tesorero don doña sr sra calle avenida
    plaza paseo nacido nacida domicilio enero febrero marzo abril mayo junio julio agosto septiembre
    octubre noviembre diciembre resolución decreto acuerdo expediente sociedad limitada anónima
    """,
    "fr": """
    le la les un une de du des et ou en avec par pour que au aux se mairie conseil municipal maire
    adjoint secrétaire monsieur madame rue avenue boulevard place chemin né née domicilié janvier
    février mars avril mai juin juillet août septembre octobre novembre décembre arrêté décision
    délibération société sarl sas
    """,
    "de": """
    der die das ein eine und oder in mit von für zu am im an auf bei aus nach stadt gemeinde landkreis
    rat bürgermeister bürgermeisterin herr frau straße strasse platz weg allee geboren wohnhaft januar
    februar märz april mai juni juli august september oktober november dezember beschluss bescheid
    satzung gmbh ag kg ohg verein stiftung
    """,
}

# Legal-form and organisation words: a "name" followed or preceded by these is an organisation.
ORGANISATION_MARKERS = (
    r"s\.?r\.?l\.?s?|s\.?p\.?a\.?|s\.?n\.?c\.?|s\.?a\.?s\.?|s\.?c\.?(?:a\.?)?r\.?l\.?|soc\.?\s*coop\.?"
    r"|coop(?:erativa)?|onlus|o\.?d\.?v\.?|a\.?p\.?s\.?|a\.?s\.?d\.?|s\.?s\.?d\.?|ltd|limited|plc|llp|inc"
    r"|gmbh|ag|kg|sarl|s\.?l\.?|s\.?a\.?|b\.?v\.?|n\.?v\.?|& c\.?|e figli|fratelli|f\.lli"
    r"|societ[àa]|associazione|fondazione|istituto|consorzio|impresa|azienda|ente\s+del\s+terzo|cooperativa"
    r"|studio\s+(?:legale|tecnico|associato)|& partners|group|holding"
)

# Words hinting at special-category data (health, minors, judicial): the document is flagged.
SENSITIVE: dict[str, list[str]] = {
    "it": [r"invalidit[àa]", r"disabilit[àa]", r"handicap", r"l\.?\s*104/92", r"diagnosi", r"patologi[ae]",
           r"malatti[ae]", r"sanitari[oe]\s+(?:certificat|document)", r"certificato\s+medico", r"ricover[oi]",
           r"tossicodipenden", r"alcoldipenden", r"\bminor[ei]\b", r"minorenn[ei]", r"tutel[ae]\s+del\s+minore",
           r"affido", r"trattamento\s+sanitario\s+obbligatorio", r"\bT\.?S\.?O\.?\b", r"casellario\s+giudiziale",
           r"condann[ae]", r"reato", r"orientamento\s+sessuale", r"etnia", r"religios",
           r"sussidi[oi]", r"contribut[oi]\s+economic", r"disagio\s+(?:economico|sociale)", r"indigen",
           r"assistenza\s+sociale", r"servizi\s+sociali", r"isee"],
    "en": [r"disabilit", r"diagnos", r"medical\s+condition", r"mental\s+health", r"\bminor\b", r"child\s+protection",
           r"criminal\s+conviction", r"safeguarding", r"benefits?\s+claim", r"housing\s+benefit"],
    "es": [r"discapacidad", r"diagn[óo]stico", r"menor(?:es)?\s+de\s+edad", r"antecedentes\s+penales"],
    "fr": [r"handicap", r"diagnostic", r"mineur", r"casier\s+judiciaire"],
    "de": [r"behinderung", r"diagnose", r"minderjährig", r"vorstrafe"],
}
