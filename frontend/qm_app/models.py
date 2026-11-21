"""Dataclasses matching SQL/generate_schema.sql; server-managed values stay optional until loaded."""
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any
from uuid import UUID

THEMA_STATUS = ('offen', 'in_bearbeitung', 'geprueft', 'abgeschlossen', 'abgebrochen', 'wiederaufgenommen')
SITZUNG_STATUS = ('geplant', 'durchgefuehrt', 'freigegeben', 'abgesagt')
BESPRECHUNG_STATUS = ('vorgemerkt', 'in_beratung', 'beschlossen', 'vertagt', 'abgesetzt')
MASSNAHME_STATUS = ('offen', 'in_bearbeitung', 'umgesetzt', 'wirksamkeit_zu_pruefen', 'wirksam', 'nicht_wirksam', 'abgebrochen', 'zurueckgestellt', 'abgelehnt')
WIRKSAMKEIT_ERGEBNIS = ('wirksam', 'teilweise_wirksam', 'nicht_wirksam', 'nicht_pruefbar')
DOKUMENT_STATUS = ('entwurf', 'in_pruefung', 'freigegeben', 'obsolet', 'archiviert')


@dataclass(kw_only=True)
class Thema:
    id: UUID | None = None
    titel: str
    beschreibung: str | None = None
    kategorie: str
    prioritaet: str | None = None
    status: str = 'offen'
    erfasst_am: datetime | None = None
    abgeschlossen_am: datetime | None = None
    verantwortlich: str | None = None
    epz_fall_id: str | None = None
    vorgaenger_thema_id: UUID | None = None
    wiederaufnahme_am: datetime | None = None
    wiederaufnahme_durch: str | None = None
    wiederaufnahme_grund: str | None = None
    erstellt_von: str
    erstellt_am: datetime | None = None
    geaendert_von: str | None = None
    geaendert_am: datetime | None = None
    version: int = 1


@dataclass(kw_only=True)
class Sitzung:
    id: UUID | None = None
    bezeichnung: str
    datum: date
    beginn: time | None = None
    ende: time | None = None
    sitzungsart: str | None = None
    ort: str | None = None
    leitung: str | None = None
    protokollfuehrung: str | None = None
    status: str = 'geplant'
    erstellt_von: str
    erstellt_am: datetime | None = None
    geaendert_von: str | None = None
    geaendert_am: datetime | None = None
    version: int = 1


@dataclass(kw_only=True)
class SitzungTeilnehmer:
    id: UUID | None = None
    sitzung_id: UUID
    person: str
    rolle: str | None = None
    anwesend: bool = True
    vertretung_durch: str | None = None
    bemerkung: str | None = None


@dataclass(kw_only=True)
class Besprechung:
    id: UUID | None = None
    sitzung_id: UUID
    thema_id: UUID
    top_nr: str | None = None
    reihenfolge: int | None = None
    status: str = 'vorgemerkt'
    ergebnis: str | None = None
    beschluss: str | None = None
    behandelt_am: datetime | None = None
    vertagung_nach_sitzung_id: UUID | None = None
    erstellt_von: str
    erstellt_am: datetime | None = None
    geaendert_von: str | None = None
    geaendert_am: datetime | None = None
    version: int = 1


@dataclass(kw_only=True)
class Massnahme:
    id: UUID | None = None
    thema_id: UUID
    besprechung_id: UUID | None = None
    vorgaenger_massnahme_id: UUID | None = None
    titel: str
    beschreibung: str | None = None
    ziel: str | None = None
    verantwortlich: str
    faellig_am: date | None = None
    status: str = 'offen'
    abgeschlossen_am: date | None = None
    wirksamkeitspruefung_ergebnis: str | None = None
    wirksamkeitspruefung_am: date | None = None
    wirksamkeitspruefung_durch: str | None = None
    begruendung: str | None = None
    erstellt_von: str
    erstellt_am: datetime | None = None
    geaendert_von: str | None = None
    geaendert_am: datetime | None = None
    version: int = 1


@dataclass(kw_only=True)
class Dokument:
    id: UUID | None = None
    dateiname: str
    mime_type: str
    dateigroesse: int = 0
    pruefsumme_sha256: bytes | None = None
    dokumenttyp: str | None = None
    status: str = 'entwurf'
    version: int = 1
    dokument_gruppe_id: UUID | None = None
    vorgaenger_dokument_id: UUID | None = None
    freigegeben_von: str | None = None
    freigegeben_am: datetime | None = None
    erstellt_von: str
    erstellt_am: datetime | None = None


@dataclass(kw_only=True)
class Verlauf:
    id: int | None = None
    zeitpunkt: datetime | None = None
    benutzer: str
    entitaet: str
    entitaet_id: str
    ereignis_art: str
    begruendung: str | None = None
    alte_werte: dict[str, Any] | None = None
    neue_werte: dict[str, Any] | None = None
    transaktion_id: int | None = None
