"""Entity types and the label templates used to replace them, per output language."""

from __future__ import annotations

# Entity types produced by the recognizers.
PERSON = "PERSON"
TAX_CODE = "TAX_CODE"          # personal tax/identification codes (codice fiscale, NINO, DNI, NIR, Steuer-ID)
ID_DOCUMENT = "ID_DOCUMENT"    # identity card, passport, driving licence numbers
HEALTH_ID = "HEALTH_ID"        # health service numbers (e.g. NHS number)
IBAN = "IBAN"
PAYMENT_CARD = "PAYMENT_CARD"
EMAIL = "EMAIL"
PHONE = "PHONE"
BIRTH = "BIRTH"                # place and/or date of birth
ADDRESS = "ADDRESS"            # home address of a person
PLATE = "PLATE"                # vehicle registration plate
VAT_NUMBER = "VAT_NUMBER"      # usually a company (public data), sometimes a sole trader

ALL_TYPES = [PERSON, TAX_CODE, ID_DOCUMENT, HEALTH_ID, IBAN, PAYMENT_CARD, EMAIL, PHONE, BIRTH,
             ADDRESS, PLATE, VAT_NUMBER]

LABELS: dict[str, dict[str, str]] = {
    "en": {PERSON: "Person {n}", TAX_CODE: "Tax code {n}", ID_DOCUMENT: "ID document {n}",
           HEALTH_ID: "Health number {n}", IBAN: "IBAN {n}", PAYMENT_CARD: "Card {n}",
           EMAIL: "Email {n}", PHONE: "Phone {n}", BIRTH: "Birth data {n}", ADDRESS: "Address {n}",
           PLATE: "Plate {n}", VAT_NUMBER: "VAT number {n}"},
    "it": {PERSON: "Persona {n}", TAX_CODE: "Codice fiscale {n}", ID_DOCUMENT: "Documento {n}",
           HEALTH_ID: "Tessera sanitaria {n}", IBAN: "IBAN {n}", PAYMENT_CARD: "Carta {n}",
           EMAIL: "Email {n}", PHONE: "Telefono {n}", BIRTH: "Dati di nascita {n}",
           ADDRESS: "Indirizzo {n}", PLATE: "Targa {n}", VAT_NUMBER: "Partita IVA {n}"},
    "es": {PERSON: "Persona {n}", TAX_CODE: "DNI/NIE {n}", ID_DOCUMENT: "Documento {n}",
           HEALTH_ID: "Tarjeta sanitaria {n}", IBAN: "IBAN {n}", PAYMENT_CARD: "Tarjeta {n}",
           EMAIL: "Email {n}", PHONE: "Teléfono {n}", BIRTH: "Datos de nacimiento {n}",
           ADDRESS: "Dirección {n}", PLATE: "Matrícula {n}", VAT_NUMBER: "NIF {n}"},
    "fr": {PERSON: "Personne {n}", TAX_CODE: "NIR {n}", ID_DOCUMENT: "Pièce d'identité {n}",
           HEALTH_ID: "Numéro de santé {n}", IBAN: "IBAN {n}", PAYMENT_CARD: "Carte {n}",
           EMAIL: "Courriel {n}", PHONE: "Téléphone {n}", BIRTH: "Naissance {n}",
           ADDRESS: "Adresse {n}", PLATE: "Immatriculation {n}", VAT_NUMBER: "TVA {n}"},
    "de": {PERSON: "Person {n}", TAX_CODE: "Steuer-ID {n}", ID_DOCUMENT: "Ausweis {n}",
           HEALTH_ID: "Versichertennummer {n}", IBAN: "IBAN {n}", PAYMENT_CARD: "Karte {n}",
           EMAIL: "E-Mail {n}", PHONE: "Telefon {n}", BIRTH: "Geburtsdaten {n}",
           ADDRESS: "Adresse {n}", PLATE: "Kennzeichen {n}", VAT_NUMBER: "USt-IdNr. {n}"},
}

# Fallback when the full label does not fit in the space of the redacted text.
SHORT_LABELS: dict[str, str] = {
    PERSON: "P{n}", TAX_CODE: "TC{n}", ID_DOCUMENT: "ID{n}", HEALTH_ID: "H{n}", IBAN: "IBAN{n}",
    PAYMENT_CARD: "C{n}", EMAIL: "E{n}", PHONE: "T{n}", BIRTH: "B{n}", ADDRESS: "A{n}",
    PLATE: "PL{n}", VAT_NUMBER: "V{n}",
}

STAMPS: dict[str, str] = {
    "en": "Document generated from the original by redacting personal data; names of officials acting in their public role remain visible",
    "it": "Documento generato dall'originale oscurando i dati personali; restano visibili i nomi di amministratori e funzionari nel loro ruolo pubblico",
    "es": "Documento generado a partir del original ocultando los datos personales; los nombres de cargos públicos en su función siguen visibles",
    "fr": "Document généré à partir de l'original en occultant les données personnelles ; les noms des responsables publics dans leur fonction restent visibles",
    "de": "Aus dem Original erzeugtes Dokument mit geschwärzten personenbezogenen Daten; Namen von Amtsträgern in ihrer Funktion bleiben sichtbar",
}

# When only the file properties (author, title...) contained personal data: the text is untouched.
STAMPS_METADATA: dict[str, str] = {
    "en": "Document generated from the original by removing personal data from the file properties; the text is unchanged",
    "it": "Documento generato dall'originale rimuovendo i dati personali dalle proprietà del file; il testo è invariato",
    "es": "Documento generado a partir del original eliminando los datos personales de las propiedades del archivo; el texto no cambia",
    "fr": "Document généré à partir de l'original en supprimant les données personnelles des propriétés du fichier ; le texte est inchangé",
    "de": "Aus dem Original erzeugtes Dokument; personenbezogene Daten aus den Dateieigenschaften entfernt, Text unverändert",
}
