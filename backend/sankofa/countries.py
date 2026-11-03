"""Les pays dont SANKOFA sait reconstituer l'histoire.

Les anciens noms servent à retrouver les photos d'archives : on ne photographiait pas
« le Bénin » en 1900, mais « le Dahomey ».
"""

COUNTRIES = [
    {"id": "benin", "name": "Bénin", "flag": "🇧🇯", "fr": "Histoire du Bénin", "en": "History of Benin",
     "old_names": ["Dahomey", "Porto-Novo", "Abomey", "Ouidah"], "places": ["porto-novo-marche", "cotonou-wharf"]},
    {"id": "senegal", "name": "Sénégal", "flag": "🇸🇳", "fr": "Histoire du Sénégal", "en": "History of Senegal",
     "old_names": ["Sénégal", "Dakar", "Saint-Louis du Sénégal", "Gorée"], "places": ["dakar-goree"]},
    {"id": "mali", "name": "Mali", "flag": "🇲🇱", "fr": "Histoire du Mali", "en": "History of Mali",
     "old_names": ["Soudan français", "Tombouctou", "Bamako", "Djenné"], "places": ["djenne-mosquee"]},
    {"id": "ghana", "name": "Ghana", "flag": "🇬🇭", "fr": "Histoire du Ghana", "en": "History of Ghana",
     "old_names": ["Gold Coast", "Côte-de-l'Or", "Accra", "Kumasi"], "places": ["cape-coast-castle"]},
    {"id": "egypte", "name": "Égypte", "flag": "🇪🇬", "fr": "Histoire de l'Égypte", "en": "History of Egypt",
     "old_names": ["Egypt", "Cairo", "Le Caire", "Alexandria"], "places": ["giza-pyramides"]},
    {"id": "maroc", "name": "Maroc", "flag": "🇲🇦", "fr": "Histoire du Maroc", "en": "History of Morocco",
     "old_names": ["Morocco", "Marrakech", "Fès", "Tanger"], "places": ["marrakech-jemaa-el-fna"]},
    {"id": "afrique-du-sud", "name": "Afrique du Sud", "flag": "🇿🇦", "fr": "Histoire de l'Afrique du Sud",
     "en": "History of South Africa", "old_names": ["Cape Town", "Kaapstad", "Johannesburg", "Cape Colony"],
     "places": ["cape-town-adderley"]},
    {"id": "france", "name": "France", "flag": "🇫🇷", "fr": "Histoire de France", "en": "History of France",
     "old_names": ["Paris", "France"], "places": ["paris-parvis-notre-dame"]},
    {"id": "espagne", "name": "Espagne", "flag": "🇪🇸", "fr": "Histoire de l'Espagne", "en": "History of Spain",
     "old_names": ["Madrid", "España", "Sevilla"], "places": ["madrid-puerta-del-sol"]},
    {"id": "royaume-uni", "name": "Royaume-Uni", "flag": "🇬🇧", "fr": "Histoire du Royaume-Uni",
     "en": "History of the United Kingdom", "old_names": ["London", "Londres"], "places": ["london-tower-bridge"]},
    {"id": "italie", "name": "Italie", "flag": "🇮🇹", "fr": "Histoire de l'Italie", "en": "History of Italy",
     "old_names": ["Roma", "Rome", "Napoli", "Firenze"], "places": ["rome-colisee"]},
    {"id": "turquie", "name": "Turquie", "flag": "🇹🇷", "fr": "Histoire de la Turquie", "en": "History of Turkey",
     "old_names": ["Constantinople", "Istanbul", "Ottoman"], "places": ["istanbul-sainte-sophie"]},
    {"id": "inde", "name": "Inde", "flag": "🇮🇳", "fr": "Histoire de l'Inde", "en": "History of India",
     "old_names": ["India", "Delhi", "Calcutta", "Bombay"], "places": ["agra-taj-mahal"]},
    {"id": "etats-unis", "name": "États-Unis", "flag": "🇺🇸", "fr": "Histoire des États-Unis",
     "en": "History of the United States", "old_names": ["New York", "Washington", "Chicago"],
     "places": ["new-york-flatiron"]},
    {"id": "bresil", "name": "Brésil", "flag": "🇧🇷", "fr": "Histoire du Brésil", "en": "History of Brazil",
     "old_names": ["Brasil", "Rio de Janeiro", "Bahia", "Salvador"], "places": ["salvador-pelourinho"]},
]

BY_ID = {c["id"]: c for c in COUNTRIES}
