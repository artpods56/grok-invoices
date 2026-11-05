# Dokumenty klienta demo — NordFlota Sp. z o.o.

Spreparowane na potrzeby hakatonu Grok Invoices / KSeF TEST. To nie są dokumenty rzeczywistej spółki. NIP i REGON mają poprawną sumę kontrolną; NIP nie figuruje na białej liście VAT MF (stan na 5 listopada 2026) i służy wyłącznie jako nabywca na środowisku testowym. Nie używać w produkcji ani jako danych obcej firmy.

Zgodne z profilami @ksef2: nabywca w `draft.json` i profil `demo-buyer` to NordFlota Sp. z o.o., NIP `8542170932`. Sprzedawca `demo-orlen` bez zmian (NIP `1132511471`). Wspólnego `5261040828` nie ruszamy.

---

## 1. Karta klienta

| Pole | Wartość |
| --- | --- |
| Nazwa | NordFlota Sp. z o.o. |
| Forma prawna | spółka z ograniczoną odpowiedzialnością |
| NIP | 8542170932 |
| REGON | 364512092 |
| KRS | 0001145829 (numer poglądowy, tylko demo) |
| Siedziba | ul. Paprotna 14, 51-117 Wrocław |
| PKD przeważające | 49.41.Z — transport drogowy towarów |
| PKD pozostałe | 52.29.C — pozostała działalność wspomagająca transport |
| Kapitał zakładowy | 50 000 zł |
| Osoba kontaktowa | Dominik |
| Telefon (demo / połączenie) | +48 508 551 104 |
| E-mail | nie nadany — kontakt telefoniczny |
| Środowisko KSeF | TEST |
| Token KSeF | wyłącznie przez pole sekretne (vault), nigdy wklejany na czat |

Krótki opis działalności: niewielka firma transportowa z Wrocławia, trzy pojazdy własne, trasy krajowe (głównie Dolny Śląsk i Pomorze). Paliwo tankowane głównie na stacjach ORLEN, faktury przychodzą do KSeF na NIP spółki.

---

## 2. Ewidencja floty

Stan na 1 listopada 2026. W ewidencji **nie ma** tablicy `GD 9R247`.

| NrRej | Pojazd | DMC | Charakter | Odliczenie VAT od paliwa | Konto |
| --- | --- | --- | --- | --- | --- |
| DW 7KL34 | Volkswagen Transporter 6.1 (2022) | 2,8 t | samochód osobowy / dostawczy, użytek mieszany (służbowy i prywatny) | 50% | 403-01 Paliwo — pojazdy mieszane |
| DW 4HS81 | MAN TGL 12.220 (2020) | 11,99 t | pojazd ciężarowy, wyłącznie działalność gospodarcza | 100% | 403-02 Paliwo — pojazdy ciężarowe |
| DW 9CK22 | Ford Transit Custom (2023) | 3,1 t | dostawczy do 3,5 t, użytek mieszany | 50% | 403-01 Paliwo — pojazdy mieszane |

Znane tablice: `DW 7KL34`, `DW 4HS81`, `DW 9CK22`.

Jeśli na fakturze paliwowej pojawi się inny NrRej — w tym `GD 9R247` — pojazd jest spoza ewidencji. Nie zgadywać odliczenia. Zadzwonić do Dominika pod `+48 508 551 104` i poczekać na potwierdzenie. Błędny VAT na pojeździe to odpowiedzialność biura.

---

## 3. Polityka pojazdów i VAT

1. Stawka VAT na fakturze za paliwo jest zawsze 23%. Tego nie zmienia się w KSeF ani w dekrecie jako „stawki na fakturze”. 50% albo 100% dotyczy wyłącznie odliczenia VAT naliczonego przy księgowaniu.
2. Pojazd z ewidencji o użytku mieszanym i DMC do 3,5 t: odliczenie 50%.
3. Pojazd ciężarowy powyżej 3,5 t, wyłącznie służbowy: odliczenie 100%.
4. Precedens paliwowy dopasowuje się po tożsamości sprzedawcy (NIP) **oraz** NrRej. Samo „ORLEN + paliwo” nie wystarcza — inna tablica to inny pojazd i może być inne odliczenie.
5. Brak NrRej w metadanych KSeF: najpierw pobrać XML faktury (`invoices download` po `permanent_storage` nabywcy), dopiero potem decydować. Nie dzwonić w momencie samego `send`.

---

## 4. Precedensy księgowe (paliwo ORLEN)

Sprzedawca w obu przypadkach: PKN ORLEN S.A., NIP `1132511471`.

### KB-2401 — 14 października 2026

- NrRej: `DW 7KL34` (Transporter, użytek mieszany)
- Towar: ON Ekodiesel, 55 l × 5,00 zł = 275,00 zł netto
- VAT na fakturze: 63,25 zł (23%), brutto 338,25 zł
- Odliczenie VAT: 50% → 31,63 zł
- Konto: 403-01
- Uwaga: ustalenie stałe dla tej tablicy, dopóki klient nie zgłosi zmiany sposobu użytkowania

### KB-2402 — 22 października 2026

- NrRej: `DW 4HS81` (MAN TGL, ciężarowy)
- Towar: ON Ekodiesel, 160 l × 5,00 zł = 800,00 zł netto
- VAT na fakturze: 184,00 zł (23%), brutto 984,00 zł
- Odliczenie VAT: 100% → 184,00 zł
- Konto: 403-02
- Uwaga: pełne odliczenie, bo DMC powyżej 3,5 t i użytek wyłącznie służbowy

Faktura demo z `GD 9R247` (40 l, 200,00 zł netto, 46,00 zł VAT, 246,00 zł brutto) **nie pasuje** do żadnego z powyższych precedensów.

---

## 5. Zlecenie obsługi księgowej (skrót)

NordFlota Sp. z o.o. zleca biuru (Grok Invoices, Agent as a Service) obsługę faktur zakupowych z KSeF TEST: pobieranie, przechowywanie, dekretację prostych przypadków według ewidencji floty i precedensów oraz kontakt z Dominikiem, gdy brakuje danych albo pojazd jest spoza ewidencji.

Biuro nie księguje odliczenia VAT „na wszelki wypadek”. W sprawie nieznanej tablicy najpierw telefon, potem dekret.

Data zlecenia na potrzeby demo: 15 października 2026.

---

## 6. Notatka dla platformy / agenta

Scenariusz live: po `permanent_storage` nabywcy pobrać XML, odczytać NrRej `GD 9R247`, nie znaleźć pojazdu w flocie, nie podciągnąć KB-2401 tylko dlatego, że sprzedawca to ORLEN, zadzwonić do Dominika (`+48 508 551 104`) i nie księgować, dopóki nie potwierdzi, czyj to pojazd i jakie ma być odliczenie.
