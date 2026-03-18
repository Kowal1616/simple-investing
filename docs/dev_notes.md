Oto zwięzłe podsumowanie wszystkich naszych dotychczasowych ustaleń i wdrożeń technicznych w projekcie Simple Investing:

**1. Architektura i Baza Danych (Migracja do V2)**
*   **Znormalizowany Schemat (V2):** Przeszliśmy z szerokiej tabeli V1 (gdzie każdy ETF miał własną kolumnę) na znormalizowaną tabelę V2 (`HistoricalDataEtfs`), gdzie każdy wiersz to pojedynczy odczyt dla danego miesiąca z kluczem obcym `etf_id`. Pozwala to na nieograniczone dodawanie nowych aktywów bez zmiany schematu bazy.
*   **Integralność Danych:** Dodano zabezpieczenie `UniqueConstraint` (unikalna para `date` + `etf_id`), zapobiegające duplikowaniu wpisów podczas comiesięcznych aktualizacji.
*   **Śledzenie Źródeł:** Dodano nową kolumnę `source`, która jednoznacznie określa pochodzenie każdego rekordu wyceny (np. `yfinance`, `alphavantage`, `index_proxy`, `extrapolated`).

**2. Pozyskiwanie Danych Historycznych (30-40 lat wstecz)**
*   **Skrypt `populate_v2.py`:** Zbudowano od zera mechanizm w pełni automatycznie ściągający i łączący współczesne notowania ETF-ów z danymi historycznymi sprzed ich powstania (tzw. "proxy"). Okno pobierania ustawiono na 485 miesięcy (ponad 40 lat głąb), by poprawnie obsłużyć wymagane pętle 30-letnie.
*   **Zewnętrzne Źródła Proxy (Symulacja historii):**
    *   **Złoto (4GLD):** Cofnięte w czasie oparte o bezpośredni import spotowych cen `xauusd` (plik d_csv ze stooq.pl).
    *   **Akcje USA, World i ACWI (SXR8, EUNL, IUSQ):** Ponieważ historyczne indeksy MSCI World na otwartych API często wygasały, ekstrapolujemy krzyłą przeszłości (przed startem owych ETF-ów) opierając bazowy wykres ciągłości o indeks S&P 500 (`^GSPC` z yfinance - historia od ~1927 r.).
    *   **Sektor Technologiczny (XDWT):** Yahoo Finance udostępnia realną historię samego ETF-a aż od 1985 roku, co nie wymagało podpinania symulacji "proxy".
    *   **Wektor Obliczeń:** Metoda łączenia nie wkleja surowej ceny starych indeksów (np. 1800$), lecz procentowe, comiesięczne zmiany cen indeksów bazowych liczone **wstecz** od faktycznej ceny otwarcia wybranego ETF-a. Skutkiem czego wykres jest absolutnie ciągły.

**3. Korekty Logiki Finansowej (skrypt `helpers_v2.py`)**
*   **Błąd Portfela CAGR (Naprawiony):** Pierwotny kod niepoprawnie liczył roczną średnią wielozłożoną (CAGR) dla wielo-aktywowych koszyków (np. 80/20) jako zwykłą średnią ważoną z gotowych zwrotów. Zastąpiono to rzetelnym modelem instytucjonalnym: system najpierw buduje historyczny, syntetyczny wektor wirtualnych wycen całego portfela (mnożąc rzędy cenowe różnych ETFów przez ich dany %, miesiąc po miesiącu), by następnie wyliczyć rentowność CAGR na całej nowo-utworzonej serii.
*   **Max Drawdown (Naprawiony):** Ponieważ funkcja z użytego pakietu zwraca spadki kapitału jako wartości mniejsze lub równe zeru, poprawiono funkcję zapisującą z błędnego `max()` na `min()`, by przechwycić to faktycznie "najgorsze", czyli najbardziej ujemne obsunięcie dla danego okresu.

Dzięki tym fundamentalnym zmianom, architektura stała się bezobsługowa, rozszerzalna dla jakiejkolwiek ilości funduszy inwestycyjnych, a podawane współczynniki zwrotów przeszły walidację twardą matematyką finansową.
