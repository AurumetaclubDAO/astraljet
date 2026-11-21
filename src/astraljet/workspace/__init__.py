"""Trade Workspace Astry: planowanie, ochrona pozycji, triggery i przegląd historii.

Moduł działa wyłącznie z symulowanym adapterem brokera. Nie importuje MetaTrader5,
nie otwiera połączeń sieciowych z brokerem i nie jest częścią read-only Obserwatorium
(`astraljet.dashboard`). Docelowa obsługa DEMO/LIVE jest opisana w
`docs/workspace/README.md`; w tej wersji każdy adapter inny niż SIMULATED jest blokowany.
"""

__version__ = "0.1.0"
