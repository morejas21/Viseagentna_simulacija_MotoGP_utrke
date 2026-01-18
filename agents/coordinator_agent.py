"""
CoordinatorAgent - Centralni koordinator utrke
FIXED: Centralizirani position tracking baziran na total_time
"""

import asyncio
import json
from datetime import datetime
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import pandas as pd
import numpy as np

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.race_config import RaceConfig


class CoordinatorAgent(Agent):
    """Koordinator utrke - upravlja pozicijama i rezultatima"""

    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.race_results = []
        self.race_started = False
        self.race_finished = False

        # NOVO: Position tracking
        self.rider_positions = {}  # {rider_id: {'total_time': float, 'position': int, 'lap': int}}
        self.finished_riders = set()

    class RaceCoordinator(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=1)

            if msg:
                ontology = msg.get_metadata("ontology")

                # Lap update - ažuriraj pozicije
                if ontology == "lap_update":
                    data = json.loads(msg.body)
                    rider_id = data['rider_id']

                    # Update tracking
                    self.agent.rider_positions[rider_id] = {
                        'total_time': data['total_time'],
                        'lap': data['lap'],
                        'tire_wear': data['tire_wear']
                    }

                    # Izračunaj pozicije baziran na total_time
                    self.agent.update_positions()

                    # Pošalji position update natrag rideru
                    position = self.agent.rider_positions[rider_id]['position']
                    response = Message(to=str(msg.sender))
                    response.set_metadata("performative", "inform")
                    response.set_metadata("ontology", "position_update")
                    response.body = json.dumps({'position': position})
                    await self.send(response)

                # Race results
                elif ontology == "results":
                    data = json.loads(msg.body)
                    rider_id = data['rider_id']

                    # Dodaj tačnu final poziciju iz trackinga
                    if rider_id in self.agent.rider_positions:
                        data['final_position'] = self.agent.rider_positions[rider_id]['position']

                    self.agent.race_results.append(data)
                    self.agent.finished_riders.add(rider_id)
                    self.agent.log(f"Primio rezultate od Rider {rider_id}")

                    # Provjera kraja
                    if len(self.agent.finished_riders) >= RaceConfig.NUM_RIDERS:
                        self.agent.race_finished = True
                        self.agent.log("✓ Svi vozači su završili!")
                        self.agent.log("🏁 Utrka završena!")

    def update_positions(self):
        """Ažuriraj pozicije baziran na total_time"""
        if not self.rider_positions:
            return

        # Sortiraj po total_time (brži = bolja pozicija)
        sorted_riders = sorted(
            self.rider_positions.items(),
            key=lambda x: x[1]['total_time']
        )

        # Dodijeli pozicije
        for position, (rider_id, data) in enumerate(sorted_riders, start=1):
            self.rider_positions[rider_id]['position'] = position

    async def setup(self):
        self.log("Pokretanje Race Coordinator...")

        behaviour = self.RaceCoordinator()
        self.add_behaviour(behaviour)

        self.race_started = True

    async def wait_for_completion(self):
        """Čekaj da svi vozači završe"""
        self.log("Čekam završetak utrke...")

        while not self.race_finished:
            await asyncio.sleep(1)

    def print_results_summary(self):
        """Ispis rezultata"""
        if not self.race_results:
            print("❌ Nema rezultata!")
            return

        # Sortiraj po total_time (ne po final_position jer može biti bug)
        sorted_results = sorted(self.race_results, key=lambda x: x['total_time'])

        print("\n" + "="*80)
        print("📊 REZULTATI UTRKE")
        print("="*80)

        print("\n🏆 TOP 5 FINISHING ORDER:")
        print("-"*80)
        for i, result in enumerate(sorted_results[:5], 1):
            print(f"{i}. Rider {result['rider_id']:2d} - "
                  f"Time: {result['total_time']:.2f}s - "
                  f"Tires: {result['tire_compound']:6s} - "
                  f"Overtakes: {result['overtakes']:2d} - "
                  f"Avg Lap: {result['avg_lap_time']:.2f}s")

        print("\n" + "="*80)
        print("📈 TIRE STRATEGY PERFORMANCE:")
        print("="*80)

        df = pd.DataFrame(self.race_results)

        for compound in ['soft', 'medium', 'hard']:
            compound_data = df[df['tire_compound'] == compound]
            if len(compound_data) > 0:
                print(f"\n{compound.upper()} Tires:")
                print(f"  • Riders: {len(compound_data)}")
                print(f"  • Avg finish time: {compound_data['total_time'].mean():.2f} ± {compound_data['total_time'].std():.2f}s")
                print(f"  • Avg overtakes: {compound_data['overtakes'].mean():.1f}")
                # Best position baziran na sortiranom indexu
                best_idx = sorted_results.index(min(compound_data.to_dict('records'), key=lambda x: x['total_time'])) + 1
                print(f"  • Best position: P{best_idx}")

        print("\n" + "="*80)
        print("🔬 KEY CORRELATIONS:")
        print("="*80)
        corr_aggr_overtakes = df['aggression'].corr(df['overtakes'])
        corr_skill_time = df['skill_level'].corr(df['total_time'])
        corr_cons_std = df['consistency'].corr(df['lap_time_std'])

        print(f"• Aggression ↔ Overtakes:  r = {corr_aggr_overtakes:7.3f}")
        print(f"• Skill ↔ Total Time:      r = {corr_skill_time:7.3f}")
        print(f"• Consistency ↔ Lap Std:   r = {corr_cons_std:7.3f}")
        print("\n" + "="*80)

    def save_results(self):
        """Spremi rezultate u CSV"""
        if not self.race_results:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Race results
        df_results = pd.DataFrame(self.race_results)
        df_results['type'] = 'race_results'

        # Sortiraj po total_time i dodaj STVARNU final_position
        df_results = df_results.sort_values('total_time').reset_index(drop=True)
        df_results['final_position'] = range(1, len(df_results) + 1)

        results_file = f"results/race_results_{timestamp}.csv"
        df_results.to_csv(results_file, index=False)
        self.log(f"💾 Rezultati spremljeni: {results_file}")

        # Lap data
        all_lap_data = []
        for result in self.race_results:
            rider_id = result['rider_id']
            for lap_info in result['lap_data']:
                all_lap_data.append({
                    'rider_id': rider_id,
                    'lap': lap_info['lap'],
                    'lap_time': lap_info['time'],
                    'tire_wear': lap_info['tire_wear'],
                    'position': lap_info['position'],
                    'overtake': lap_info['overtake']
                })

        df_laps = pd.DataFrame(all_lap_data)
        lap_data_file = f"results/lap_data_{timestamp}.csv"
        df_laps.to_csv(lap_data_file, index=False)
        self.log(f"💾 Lap data spremljen: {lap_data_file}")

        return timestamp

    def get_results_dataframe(self):
        """Vrati DataFrame rezultata"""
        if not self.race_results:
            return None

        df = pd.DataFrame(self.race_results)

        # Sortiraj po total_time i fiksaj final_position
        df = df.sort_values('total_time').reset_index(drop=True)
        df['final_position'] = range(1, len(df) + 1)

        return df

    def log(self, message):
        print(f"[Coordinator] {message}")