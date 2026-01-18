"""
Centralna konfiguracija za MotoGP višeagentnu simulaciju
"""

class RaceConfig:
    """Globalne postavke utrke"""

    # XMPP Server postavke
    XMPP_SERVER = "localhost"
    XMPP_PASSWORD = "password"

    # Postavke utrke
    NUM_LAPS = 20
    NUM_RIDERS = 8
    LAP_BASE_TIME = 90.0  # sekunde
    TRACK_LENGTH = 4500   # metri

    # Tire compounds i njihove karakteristike
    TIRE_COMPOUNDS = {
        'soft': {
            'base_speed': 1.05,
            'degradation_rate': 0.003,
            'optimal_laps': 8,
            'description': 'Brze ali brzo se troše'
        },
        'medium': {
            'base_speed': 1.00,
            'degradation_rate': 0.0015,
            'optimal_laps': 15,
            'description': 'Balansirane performanse'
        },
        'hard': {
            'base_speed': 0.97,
            'degradation_rate': 0.0008,
            'optimal_laps': 25,
            'description': 'Spore ali izdržljive'
        }
    }

    # Rider karakteristike rasponi
    SKILL_RANGE = (0.85, 1.0)
    AGGRESSION_RANGE = (0.3, 0.9)
    CONSISTENCY_RANGE = (0.7, 0.95)

    # Simulacijske postavke
    TELEMETRY_INTERVAL = 5  # Svakih koliko krugova vozači šalju telemetriju
    SIMULATION_DELAY = 0.1  # Delay između krugova (sekunde)

    # Output direktoriji
    RESULTS_DIR = "results"
    DATA_DIR = "data"

    @classmethod
    def update_config(cls, **kwargs):
        """Dinamičko ažuriranje konfiguracije"""
        for key, value in kwargs.items():
            if hasattr(cls, key):
                setattr(cls, key, value)

    @classmethod
    def get_tire_strategy(cls, team_id):
        """Dohvaća strategiju guma za određeni tim"""
        strategies = list(cls.TIRE_COMPOUNDS.keys())
        return strategies[team_id % len(strategies)]
