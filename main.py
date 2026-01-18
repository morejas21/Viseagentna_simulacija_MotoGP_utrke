"""
MotoGP Višeagentna Simulacija - Glavni Program
SPADE Multi-Agent System s automatskom vizualnom analizom
"""

import asyncio
import sys
import os
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

from agents.rider_agent import RiderAgent
from agents.team_agent import TeamAgent
from agents.coordinator_agent import CoordinatorAgent
from config.race_config import RaceConfig


class MotoGPSimulation:
    """Glavna klasa za upravljanje simulacijom"""

    def __init__(self):
        self.riders = []
        self.teams = []
        self.coordinator = None
        self.is_running = False
        self.current_timestamp = None  # Za konzistentno imenovanje

    async def setup_agents(self):
        """Kreiranje i pokretanje svih agenata"""
        print("\n" + "="*60)
        print("🔧 SETUP AGENATA")
        print("="*60)

        # 1. Koordinator
        print("\n1️⃣  Pokrećem Coordinator agenta...")
        coordinator_jid = f"coordinator@{RaceConfig.XMPP_SERVER}"
        self.coordinator = CoordinatorAgent(coordinator_jid, RaceConfig.XMPP_PASSWORD)
        await self.coordinator.start()
        print(f"   ✓ {coordinator_jid}")
        await asyncio.sleep(1)

        # 2. Rider agenti PRVO
        print("\n2️⃣  Pokrećem Rider agente...")
        for i in range(RaceConfig.NUM_RIDERS):
            rider_jid = f"rider_{i}@{RaceConfig.XMPP_SERVER}"
            rider = RiderAgent(rider_jid, RaceConfig.XMPP_PASSWORD, i)
            await rider.start()
            self.riders.append(rider)
            print(f"   ✓ {rider_jid}")
            await asyncio.sleep(0.5)

        print("\n⏳ Čekam registraciju svih vozača na XMPP serveru...")
        await asyncio.sleep(3)

        # 3. Team agenti
        print("\n3️⃣  Pokrećem Team agente...")
        num_teams = (RaceConfig.NUM_RIDERS + 1) // 2
        for i in range(num_teams):
            team_jid = f"team_{i}@{RaceConfig.XMPP_SERVER}"
            team = TeamAgent(team_jid, RaceConfig.XMPP_PASSWORD, i)
            await team.start()
            self.teams.append(team)
            print(f"   ✓ {team_jid}")
            await asyncio.sleep(0.3)

        print(f"\n✅ Pokrenut {len(self.riders)} vozača, {len(self.teams)} timova i koordinator")
        print("="*60)

        self.is_running = True
        print("\n⏳ Sinkronizacija svih agenata...")
        await asyncio.sleep(3)

    async def run_race(self):
        """Pokretanje utrke"""
        print("\n" + "="*60)
        print("🏁 UTRKA ZAPOČINJE! 🏁")
        print("="*60)
        print(f"\nBroj krugova: {RaceConfig.NUM_LAPS}")
        print(f"Broj vozača: {RaceConfig.NUM_RIDERS}\n")

        await self.coordinator.wait_for_completion()

        print("\n" + "="*60)
        print("🏁 UTRKA ZAVRŠENA! 🏁")
        print("="*60)

    async def show_results(self):
        """Prikaz rezultata"""
        self.coordinator.print_results_summary()

    async def save_results(self):
        """Spremanje rezultata u CSV (s timestampom)"""
        timestamp = self.coordinator.save_results()
        self.current_timestamp = timestamp  # Spremi za korištenje u grafovima
        print(f"\n✅ CSV rezultati spremljeni u results/ (timestamp: {timestamp})")
        return timestamp

    async def analyze_results(self):
        """Vizualna analiza rezultata - s timestampom"""
        print("\n" + "="*60)
        print("📊 GENERIRANJE GRAFOVA")
        print("="*60)

        df = self.coordinator.get_results_dataframe()

        if df is None:
            print("❌ Nema podataka!")
            return

        # Postavljanje stila
        sns.set_style("whitegrid")
        plt.rcParams['figure.facecolor'] = 'white'

        # Kreiranje figura
        fig = plt.figure(figsize=(14, 10))
        fig.suptitle('MotoGP Race Analysis', fontsize=16, fontweight='bold', y=0.995)

        # 1. Tire strategy comparison - FIX za warning
        plt.subplot(2, 2, 1)
        sns.boxplot(data=df, x='tire_compound', y='total_time', 
                   hue='tire_compound', palette='Set2', legend=False)
        plt.title('Total Race Time by Tire', fontsize=12, fontweight='bold')
        plt.xlabel('Tire Compound', fontsize=10)
        plt.ylabel('Total Time (s)', fontsize=10)
        plt.grid(axis='y', alpha=0.3)

        # 2. Aggression vs Overtakes
        plt.subplot(2, 2, 2)
        sns.scatterplot(data=df, x='aggression', y='overtakes', 
                       hue='tire_compound', s=150, alpha=0.7, palette='Set2')
        plt.title('Aggression vs Overtakes', fontsize=12, fontweight='bold')
        plt.xlabel('Aggression Level', fontsize=10)
        plt.ylabel('Number of Overtakes', fontsize=10)
        plt.legend(title='Tire', fontsize=8)
        plt.grid(alpha=0.3)

        # 3. Skill vs Performance
        plt.subplot(2, 2, 3)
        sns.scatterplot(data=df, x='skill_level', y='total_time', 
                       hue='final_position', palette='viridis', s=150, alpha=0.7)
        plt.title('Skill vs Performance', fontsize=12, fontweight='bold')
        plt.xlabel('Skill Level', fontsize=10)
        plt.ylabel('Total Time (s)', fontsize=10)
        plt.legend(title='Position', fontsize=8)
        plt.grid(alpha=0.3)

        # 4. Correlation matrix
        plt.subplot(2, 2, 4)
        corr = df[['skill_level', 'aggression', 'consistency', 'total_time', 'overtakes']].corr()
        sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', 
                   center=0, cbar_kws={'label': 'Correlation'}, 
                   square=True, linewidths=0.5)
        plt.title('Correlation Matrix', fontsize=12, fontweight='bold')

        plt.tight_layout()

        # Spremanje - S TIMESTAMPOM (konzistentno s CSV fileovima)
        if not self.current_timestamp:
            self.current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        output_file = f'results/analysis_{self.current_timestamp}.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✅ Grafovi spremljeni: {output_file}")

        plt.close()
        print("="*60)

    async def shutdown(self):
        """Gašenje svih agenata"""
        print("\n" + "="*60)
        print("🛑 GAŠENJE AGENATA")
        print("="*60)

        for rider in self.riders:
            await rider.stop()
            print(f"  ✓ {rider.jid} ugašen")

        for team in self.teams:
            await team.stop()
            print(f"  ✓ {team.jid} ugašen")

        if self.coordinator:
            await self.coordinator.stop()
            print(f"  ✓ {self.coordinator.jid} ugašen")

        print("\n✅ Svi agenti uspješno ugašeni")
        self.is_running = False

    async def run_full_simulation(self):
        """Puna simulacija - setup, race, results, save, grafovi"""
        # Resetuj timestamp za novu simulaciju
        self.current_timestamp = None

        try:
            await self.setup_agents()
            await self.run_race()
            await self.show_results()
            await self.save_results()
            await self.analyze_results()
        finally:
            await self.shutdown()


def print_banner():
    """ASCII banner"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║         🏍️  MotoGP VIŠEAGENTNA SIMULACIJA 🏍️                 ║
║              SPADE Multi-Agent System                        ║
║         Projekt: Višeagentni sustavi                         ║
╚══════════════════════════════════════════════════════════════╝
    """)


def print_menu():
    """Glavni meni - pojednostavljen"""
    print("\n" + "="*60)
    print("GLAVNI MENI")
    print("="*60)
    print("1. 🏁 Pokreni punu simulaciju")
    print("2. ⚙️  Postavke simulacije")
    print("3. 🛑 Izlaz")
    print("="*60)


def print_settings():
    """Prikaz trenutnih postavki"""
    print("\n" + "="*60)
    print("⚙️  TRENUTNE POSTAVKE")
    print("="*60)
    print(f"XMPP Server: {RaceConfig.XMPP_SERVER}")
    print(f"Broj vozača: {RaceConfig.NUM_RIDERS}")
    print(f"Broj krugova: {RaceConfig.NUM_LAPS}")
    print(f"Bazno vrijeme kruga: {RaceConfig.LAP_BASE_TIME}s")
    print(f"Telemetrija interval: Svakih {RaceConfig.TELEMETRY_INTERVAL} krugova")
    print("\nTire Compounds:")
    for name, props in RaceConfig.TIRE_COMPOUNDS.items():
        print(f"  • {name.upper()}: Speed {props['base_speed']:.2f}x, "
              f"Degradacija {props['degradation_rate']:.4f}/lap")
    print("="*60)


def change_settings():
    """Promjena postavki"""
    print("\n" + "="*60)
    print("⚙️  PROMJENA POSTAVKI")
    print("="*60)
    print("1. Broj vozača")
    print("2. Broj krugova")
    print("3. XMPP Server")
    print("0. Natrag")

    choice = input("\nOdabir: ").strip()

    if choice == "1":
        try:
            num = int(input("Novi broj vozača (4-20): "))
            if 4 <= num <= 20:
                RaceConfig.NUM_RIDERS = num
                print(f"✓ Postavljeno na {num} vozača")
            else:
                print("❌ Broj mora biti između 4 i 20")
        except ValueError:
            print("❌ Nevažeći unos")

    elif choice == "2":
        try:
            num = int(input("Novi broj krugova (5-50): "))
            if 5 <= num <= 50:
                RaceConfig.NUM_LAPS = num
                print(f"✓ Postavljeno na {num} krugova")
            else:
                print("❌ Broj mora biti između 5 i 50")
        except ValueError:
            print("❌ Nevažeći unos")

    elif choice == "3":
        server = input("XMPP Server (default: localhost): ").strip()
        if server:
            RaceConfig.XMPP_SERVER = server
            print(f"✓ Postavljeno na {server}")


async def main():
    """Glavna funkcija"""
    print_banner()

    print("\n⚠️  VAŽNO: Prije pokretanja simulacije, pokreni SPADE XMPP server!")
    print("U drugom terminalu pokreni: spade run")
    print("\nPritisni Enter kada je server pokrenut...")
    input()

    simulation = MotoGPSimulation()

    while True:
        print_menu()
        choice = input("\n👉 Odabir: ").strip()

        if choice == "1":
            # PUNA SIMULACIJA - sve automatski
            print("\n🚀 Pokrećem punu simulaciju...")
            print("   📋 Uključeno: Setup → Utrka → Rezultati → CSV → Grafovi")
            await simulation.run_full_simulation()
            print("\n✅ Simulacija završena!")

            if simulation.current_timestamp:
                print("\n📂 Spremljeni fileovi:")
                print(f"   • results/race_results_{simulation.current_timestamp}.csv")
                print(f"   • results/lap_data_{simulation.current_timestamp}.csv")
                print(f"   • results/analysis_{simulation.current_timestamp}.png")

        elif choice == "2":
            # POSTAVKE
            print_settings()
            change_settings()

        elif choice == "3":
            # IZLAZ
            if simulation.is_running:
                confirm = input("\n⚠️  Agenti su još pokrenuti. Ugasiti? (da/ne): ").strip().lower()
                if confirm == "da":
                    await simulation.shutdown()
            print("\n👋 Doviđenja!")
            break

        else:
            print("❌ Nevažeći odabir!")

        input("\nPritisni Enter za nastavak...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Prekinuto! Gašenje...")
    except Exception as e:
        print(f"\n❌ Greška: {e}")
        import traceback
        traceback.print_exc()