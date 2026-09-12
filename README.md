# NICE-POWER / KUAIQU SPPS-A3010D

Modern Linux GUI for the NICE-POWER / KUAIQU SPPS-A3010D programmable laboratory DC power supply.

## Version

**1.0 Stable**

**Author:** Marian Jędrych

## Features

- USB / serial communication
- Automatic serial port detection
- Voltage monitoring and control
- Current monitoring and control
- Output ON / OFF control
- Remote / Local mode
- Live voltage, current and power monitoring
- Live V / A / W chart
- Adjustable measurement interval
- CSV data logging
- Measurement history
- Auto-scale chart
- Dark modern graphical interface
- Polish and English versions

## Supported device

- NICE-POWER / KUAIQU SPPS-A3010D
- Maximum voltage: 30 V
- Maximum current: 10 A
- Serial communication: 9600 baud, 8N1

## Requirements

- Ubuntu / Debian-based Linux
- Python 3
- Python Tkinter
- pySerial
- Matplotlib
- USB serial interface

## USB permissions

The application requires access to the serial device.

Add your user to the `dialout` group:

```bash
sudo usermod -aG dialout $USER
```

After that, log out and log in again.

## Installation

### Polish version

Download:

`nice-power-spps-a3010d_1.0_Stable_PL.deb`

Install:

```bash
sudo apt install ./nice-power-spps-a3010d_1.0_Stable_PL.deb
```

### English version

Download:

`nice-power-spps-a3010d_1.0_Stable_EN.deb`

Install:

```bash
sudo apt install ./nice-power-spps-a3010d_1.0_Stable_EN.deb
```

## Running

Launch **NICE-POWER** from the application menu.

The application automatically detects available serial ports. Select the port connected to the power supply and press **Connect**.

## Data logging

Measurements can be saved to CSV files.

The recorded data includes:

- Time
- Voltage
- Current
- Power

---

# Polski

## NICE-POWER / KUAIQU SPPS-A3010D

Nowoczesny interfejs graficzny dla systemu Linux do obsługi programowalnego zasilacza laboratoryjnego NICE-POWER / KUAIQU SPPS-A3010D.

### Wersja

**1.0 Stable**

**Autor:** Marian Jędrych

### Funkcje

- komunikacja USB / szeregowa
- automatyczne wykrywanie portów szeregowych
- odczyt i ustawianie napięcia
- odczyt i ustawianie natężenia prądu
- włączanie i wyłączanie wyjścia
- tryb Remote / Local
- monitorowanie napięcia, prądu i mocy
- wspólny wykres V / A / W
- regulowana częstotliwość odczytu
- zapis danych do CSV
- historia pomiarów
- automatyczne skalowanie wykresu
- nowoczesny ciemny interfejs
- wersja polska i angielska

### Obsługiwane urządzenie

- NICE-POWER / KUAIQU SPPS-A3010D
- maksymalne napięcie: 30 V
- maksymalny prąd: 10 A
- komunikacja szeregowa: 9600 baud, 8N1

### Uprawnienia USB

Użytkownik musi mieć dostęp do urządzenia szeregowego.

```bash
sudo usermod -aG dialout $USER
```

Po wykonaniu polecenia należy wylogować się i zalogować ponownie.

### Instalacja

Polska wersja:

```bash
sudo apt install ./nice-power-spps-a3010d_1.0_Stable_PL.deb
```

Angielska wersja:

```bash
sudo apt install ./nice-power-spps-a3010d_1.0_Stable_EN.deb
```

### Uruchomienie

Po instalacji uruchom **NICE-POWER** z menu aplikacji.

Program automatycznie wykrywa dostępne porty szeregowe. Wybierz port, do którego podłączony jest zasilacz, a następnie kliknij **Connect**.

### Zapis danych

Program umożliwia zapis pomiarów do plików CSV.

Zapisywane dane obejmują:

- czas
- napięcie
- natężenie
- moc

---

**NICE-POWER — 1.0 Stable**

**Author / Autor: Marian Jędrych**
## ☕ Support the project

If you find NICE-POWER useful and would like to support its further development, you can buy me a coffee:

[☕ Buy me a coffee](https://buycoffee.to/mrj3)

Thank you for your support! ❤️

---

## ☕ Wesprzyj projekt

Jeśli projekt NICE-POWER jest dla Ciebie przydatny i chcesz wesprzeć jego dalszy rozwój, możesz postawić mi kawę:

[☕ Postaw mi kawę](https://buycoffee.to/mrj3)

Dziękuję za wsparcie! ❤️
