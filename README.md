# AutoSalon Premium – Aplikacja do zarządzania salonem samochodowym

Desktopowa aplikacja napisana w Pythonie (Tkinter + SQLite) wspierająca codzienną pracę salonu samochodowego.

## Zespół

| Rola | Osoba |
|------|-------|
| Project Manager | Sebastian Rusin |
| Developer | Wojciech Armata |
| Database Developer | Konrad Mazur |
| Tester / QA | Tomasz Bieńko |

Zarządzanie zadaniami: [Jira – projekt SS](https://sebastianrusin2000.atlassian.net/jira/software/c/projects/SS/boards/69)

## Funkcjonalności

| Moduł | Opis |
|-------|------|
| **Pojazdy** | Lista pojazdów z filtrowaniem, operacje CRUD, zmiana statusów (Dostępny / Zarezerwowany / Sprzedany / W serwisie), import danych z CSV |
| **Klienci** | Zarządzanie bazą klientów, historia zakupów |
| **Pracownicy** | Ewidencja pracowników, operacje CRUD |
| **Sprzedaże** | Rejestracja transakcji, automatyczna zmiana statusu pojazdu, generowanie faktur PDF |
| **Przypomnienia** | Zdarzenia (przeglądy, ubezpieczenia) z oznaczaniem kolorystycznym i statusem wykonania |
| **Raporty** | Raporty sprzedażowe z filtrem dat, eksport do PDF, kalkulator marży |
| **Wykresy** | Wykresy analityczne (sprzedaż wg marki, paliwa, pracownika) |
| **Predykcja ceny** | Model regresji liniowej (scikit-learn) do szacowania wartości pojazdu |

## Wymagania

- Python 3.12+
- Biblioteki (instalacja poniżej):

```
pandas
matplotlib
seaborn
scikit-learn
reportlab
requests
```

## Instalacja i uruchomienie

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/sebastianrusin00/salon-samochodowy.git
cd salon-samochodowy

# 2. Zainstaluj zależności
pip install -r requirements.txt

# 3. Uruchom aplikację
python app.py
```

Baza danych (`salon.db`) tworzy się automatycznie przy pierwszym uruchomieniu.  
Opcjonalnie: umieść plik `Updated_Car_Sales_Data.csv` w tym samym folderze co `app.py`, aby załadować przykładowe dane pojazdów.

## Stos technologiczny

- **Język:** Python 3.12
- **GUI:** Tkinter / ttk
- **Baza danych:** SQLite 3
- **Analiza danych:** pandas, matplotlib, seaborn
- **Machine Learning:** scikit-learn (LinearRegression)
- **Generowanie PDF:** reportlab
- **Środowisko:** Visual Studio Code
- **Kontrola wersji:** Git / GitHub
- **Zarządzanie projektem:** Jira (Scrum, 4 sprinty)
